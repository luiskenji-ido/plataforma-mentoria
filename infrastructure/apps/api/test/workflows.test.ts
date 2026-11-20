/** Fluxo de provisionamento/publicação com AWS, Pulumi e Docker simulados: ordem dos passos, aprovação e falhas. */
import { describe, expect, it, vi } from "vitest";
import type { OperationSummary } from "@infra/shared";
import { OperationManager, type Operation } from "../src/deployment/operations";
import { ApprovalError, Workflows, type WorkflowDeps } from "../src/deployment/workflows";
import { configHash, type StoredConfig } from "../src/services/configStore";
import { fakeSession, readyConfig, testSettings } from "./helpers";

function stored(): StoredConfig {
  return { config: readyConfig(), updatedAt: new Date().toISOString(), secretsVersion: 0 };
}

const OUTPUTS = {
  instanceId: "i-0123456789abcdef0",
  ecrRepositoryUrl: "123456789012.dkr.ecr.sa-east-1.amazonaws.com/mentoria/mentoria-test",
  imageParameterName: "/mentoria-infra/mentoria-test/image",
  appUrl: "http://203.0.113.7",
  region: "sa-east-1",
};

function deps(overrides: Partial<WorkflowDeps> = {}) {
  const calls: string[] = [];
  const d: WorkflowDeps = {
    session: fakeSession() as unknown as WorkflowDeps["session"],
    stacks: {
      ensureSecrets: vi.fn(async () => void calls.push("secrets")),
      preview: vi.fn(async () => {
        calls.push("preview");
        return { changeSummary: { create: 14 }, resources: [{ op: "create", type: "aws:ec2/instance:Instance", name: "mentoria-test-ec2" }] };
      }),
      up: vi.fn(async () => {
        calls.push("up");
        return Object.fromEntries(Object.entries(OUTPUTS).map(([k, v]) => [k, { value: v, secret: false }]));
      }),
      refresh: vi.fn(async () => void calls.push("refresh")),
      destroy: vi.fn(async () => void calls.push("destroy")),
      outputs: vi.fn(async () => ({ ...OUTPUTS })),
    } as unknown as WorkflowDeps["stacks"],
    aws: {
      waitSsmOnline: vi.fn(async () => void calls.push("ssm")),
      runFixed: vi.fn(async (_r: string, _i: string, cmd: string) => {
        calls.push(`run:${cmd}`);
        return cmd === "status"
          ? { status: "Success", output: "bootstrap=done\ndocker=active\ndocker_version=29.1.0\nubuntu=24.04\n" }
          : { status: "Success", output: "Imagem em execução: x" };
      }),
      putImage: vi.fn(async (_r: string, _n: string, uri: string) => void calls.push(`image:${uri}`)),
      ecrLogin: vi.fn(async () => ({ registry: "123456789012.dkr.ecr.sa-east-1.amazonaws.com", username: "AWS", password: "token-ecr" })),
    } as unknown as WorkflowDeps["aws"],
    docker: {
      serverVersion: vi.fn(async () => "29.1.0"),
      build: vi.fn(async () => void calls.push("build")),
      push: vi.fn(async () => {
        calls.push("push");
        return "sha256:" + "a".repeat(64);
      }),
    },
    runner: vi.fn(async (cmd: string, args: string[]) => {
      if (cmd === "git" && args[0] === "rev-parse") return { code: 0, stdout: "abc1234\n", stderr: "" };
      if (cmd === "git") return { code: 0, stdout: "", stderr: "" };
      return { code: 0, stdout: "", stderr: "" };
    }),
    http: vi.fn(async () => ({ ok: true, status: 200, ms: 40 })),
    prices: { ec2Hourly: async () => 0.0208, ebsGbMonth: async () => 0.0952 },
    repoRoot: testSettings().repoRoot,
    operations: new OperationManager(testSettings().stateDir),
    wait: async () => undefined,
    ...overrides,
  };
  return { d, calls };
}

function finished(op: Operation): Promise<OperationSummary> {
  return new Promise((resolve) => {
    if (op.summary.status !== "running") resolve(op.summary);
    else op.emitter.once("end", () => resolve(op.summary));
  });
}

describe("prévia e aprovação", () => {
  it("a prévia não cria nada e guarda o hash da configuração", async () => {
    const { d, calls } = deps();
    const wf = new Workflows(d);
    const s = stored();
    const summary = await finished(await wf.preview(s));
    expect(summary.status).toBe("succeeded");
    expect(calls).toEqual(["secrets", "preview"]);
    const p = wf.getLastPreview()!;
    expect(p.configHash).toBe(configHash(s.config, 0));
    expect(p.summary.openPorts).toEqual(["TCP 80 ← 0.0.0.0/0 (Aplicação)"]);
    expect(p.cost.monthlyTotalUsd).toBeGreaterThan(0);
  });

  it("provisionar sem prévia, com outra configuração, sem nome ou sem aceitar custos é recusado", async () => {
    const { d } = deps();
    const wf = new Workflows(d);
    const s = stored();
    const ok = { configHash: configHash(s.config, 0), confirmStackName: "mentoria-test", acceptCosts: true };
    await expect(wf.provision(s, ok)).rejects.toThrow(/prévia/);
    await finished(await wf.preview(s));
    const changed = stored();
    changed.config.instance.instanceType = "t3.large";
    await expect(wf.provision(changed, ok)).rejects.toThrow(/mudou depois da prévia/);
    await expect(wf.provision(s, { ...ok, confirmStackName: "outro" })).rejects.toThrow(/nome do stack/);
    await expect(wf.provision(s, { ...ok, acceptCosts: false })).rejects.toBeInstanceOf(ApprovalError);
    expect(d.stacks.up).not.toHaveBeenCalled();
  });

  it("a prévia expira", async () => {
    const { d } = deps();
    const wf = new Workflows(d);
    const s = stored();
    await finished(await wf.preview(s));
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(Date.now() + 31 * 60_000);
    try {
      await expect(wf.provision(s, { configHash: configHash(s.config, 0), confirmStackName: "mentoria-test", acceptCosts: true })).rejects.toThrow(/expirou/);
    } finally {
      vi.useRealTimers();
    }
  });

  it("sem AWS conectada nada começa", async () => {
    const { d } = deps({ session: fakeSession(false) as unknown as WorkflowDeps["session"] });
    await expect(new Workflows(d).preview(stored())).rejects.toThrow(/Conecte-se/);
  });
});

describe("provisionamento", () => {
  it("executa os passos na ordem: build antes da infraestrutura, depois ECR, SSM, bootstrap, deploy e saúde", async () => {
    const { d, calls } = deps();
    const wf = new Workflows(d);
    const s = stored();
    await finished(await wf.preview(s));
    calls.length = 0;
    const op = await wf.provision(s, { configHash: configHash(s.config, 0), confirmStackName: "mentoria-test", acceptCosts: true });
    const summary = await finished(op);
    expect(summary.status).toBe("succeeded");
    expect(calls[0]).toBe("secrets");
    expect(calls.indexOf("build")).toBeLessThan(calls.indexOf("up"));
    expect(calls.slice(calls.indexOf("up"))).toEqual([
      "up",
      "push",
      expect.stringMatching(/^image:123456789012\.dkr\.ecr\.sa-east-1\.amazonaws\.com\/mentoria\/mentoria-test:\d{8}-\d{6}-abc1234$/),
      "ssm",
      "run:status",
      "run:deploy",
    ]);
    expect(d.http).toHaveBeenCalledWith("http://203.0.113.7/");
    expect(summary.steps.every((st) => st.status === "done")).toBe(true);
    // A aprovação vale para uma execução só
    await expect(wf.provision(s, { configHash: configHash(s.config, 0), confirmStackName: "mentoria-test", acceptCosts: true })).rejects.toThrow(/prévia/);
  });

  it("falha no build: para antes de criar qualquer recurso", async () => {
    const { d, calls } = deps();
    (d.docker.build as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("O build da imagem falhou"));
    const wf = new Workflows(d);
    const s = stored();
    await finished(await wf.preview(s));
    const summary = await finished(await wf.provision(s, { configHash: configHash(s.config, 0), confirmStackName: "mentoria-test", acceptCosts: true }));
    expect(summary.status).toBe("failed");
    expect(summary.steps.find((x) => x.key === "build")?.status).toBe("failed");
    expect(summary.steps.find((x) => x.key === "infra")?.status).toBe("skipped");
    expect(calls).not.toContain("up");
  });

  it("deploy na instância falhou: operação falha com mensagem útil", async () => {
    const { d } = deps();
    (d.aws.runFixed as ReturnType<typeof vi.fn>).mockImplementation(async (_r: string, _i: string, cmd: string) =>
      cmd === "deploy" ? { status: "Failed", output: "Error response from daemon: pull access denied" } : { status: "Success", output: "bootstrap=done\ndocker=active\n" },
    );
    const op = await new Workflows(d).deploy(stored());
    const summary = await finished(op);
    expect(summary.status).toBe("failed");
    expect(summary.error).toMatch(/terminou como Failed/);
    expect(op.events.some((e) => e.message.includes("pull access denied"))).toBe(true);
  });

  it("app que não responde: falha na verificação de saúde (sem fingir sucesso)", async () => {
    const { d } = deps({ http: vi.fn(async () => ({ ok: false, error: "tempo esgotado" })) });
    vi.useFakeTimers({ toFake: ["Date"] });
    const start = Date.now();
    let t = start;
    d.wait = async (ms) => {
      t += ms;
      vi.setSystemTime(t);
    };
    try {
      const summary = await finished(await new Workflows(d).deploy(stored()));
      expect(summary.status).toBe("failed");
      expect(summary.steps.find((x) => x.key === "health")?.status).toBe("failed");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("operações", () => {
  it("não deixa duas operações no mesmo stack ao mesmo tempo", async () => {
    const manager = new OperationManager(testSettings().stateDir);
    let release!: () => void;
    const op = await manager.start("deploy", "s1", [{ key: "a", label: "A" }], () => new Promise<void>((r) => (release = r)));
    await expect(manager.start("destroy", "s1", [], async () => undefined)).rejects.toThrow(/Já há uma operação/);
    const outro = await manager.start("preview", "s2", [], async () => undefined);
    release();
    await finished(op);
    await finished(outro);
    expect(manager.isBusy("s1")).toBe(false);
  });

  it("eventos e logs gravados passam pelo mascarador", async () => {
    const manager = new OperationManager(testSettings().stateDir);
    const op = await manager.start("preview", "s3", [], async (o) => o.log("conexão mysql+pymysql://app:senhaSecreta@mysql:3306/x"));
    await finished(op);
    expect(op.events.map((e) => e.message).join("\n")).not.toContain("senhaSecreta");
    const [file] = await manager.savedLogs();
    const saved = await manager.readSavedLog(file!);
    expect(JSON.stringify(saved)).not.toContain("senhaSecreta");
  });

  it("destroy exige o nome do stack e a frase exata", async () => {
    const { d } = deps();
    const wf = new Workflows(d);
    await expect(wf.destroy(stored(), { confirmStackName: "mentoria-test", confirmPhrase: "sim" })).rejects.toThrow(/destruir mentoria-test/);
    const op = await wf.destroy(stored(), { confirmStackName: "mentoria-test", confirmPhrase: "destruir mentoria-test" });
    await finished(op);
    expect(d.stacks.destroy).toHaveBeenCalledTimes(1);
    expect(op.events.some((e) => /preservados/.test(e.message))).toBe(true);
  });
});
