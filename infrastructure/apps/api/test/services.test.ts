/** Preços, saúde, Docker, catálogo de AMIs, detecção do projeto e rotas de configuração (segredos). */
import { DescribeImagesCommand, EC2Client } from "@aws-sdk/client-ec2";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defaultDeploymentConfig } from "@infra/shared";
import { AwsCatalog, CANONICAL_OWNER_ID, ubuntuParameterNames } from "../src/aws/catalog";
import { parseStatusOutput } from "../src/aws/operations";
import { estimateCost, HOURS_PER_MONTH } from "../src/aws/pricing";
import { DockerImages, immutableTag, platformFor } from "../src/deployment/docker";
import { classifyHealth, waitHealthy } from "../src/deployment/health";
import { splitSecrets } from "../src/services/configStore";
import { insideRepo, parseDockerfile } from "../src/services/project";
import type { AppContext } from "../src/context";
import { HEADERS, fakeSession, makeApp, readyConfig } from "./helpers";

const ec2 = mockClient(EC2Client);
const ssm = mockClient(SSMClient);
afterEach(() => {
  ec2.reset();
  ssm.reset();
});
const session = { clientConfig: () => ({ region: "sa-east-1", credentials: async () => ({ accessKeyId: "a", secretAccessKey: "b" }), maxAttempts: 1 }) } as unknown as AppContext["session"];

describe("AMI oficial do Ubuntu", () => {
  it("resolve pelo parâmetro público da Canonical e confere a dona", async () => {
    ssm.on(GetParameterCommand, { Name: ubuntuParameterNames("24.04", "x86_64")[0] }).resolves({ Parameter: { Value: "ami-0aaaaaaaaaaaaaaaa" } });
    ec2.on(DescribeImagesCommand).resolves({ Images: [{ ImageId: "ami-0aaaaaaaaaaaaaaaa", OwnerId: CANONICAL_OWNER_ID, State: "available", Name: "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20261101" }] });
    const img = await new AwsCatalog(session).resolveUbuntu("sa-east-1", "24.04", "x86_64");
    expect(img).toMatchObject({ amiId: "ami-0aaaaaaaaaaaaaaaa", version: "24.04" });
  });

  it("recusa imagem que não é da Canonical", async () => {
    ssm.on(GetParameterCommand).resolves({ Parameter: { Value: "ami-0bbbbbbbbbbbbbbbb" } });
    ec2.on(DescribeImagesCommand).resolves({ Images: [{ ImageId: "ami-0bbbbbbbbbbbbbbbb", OwnerId: "999999999999", State: "available" }] });
    await expect(new AwsCatalog(session).resolveUbuntu("sa-east-1", "24.04", "x86_64")).rejects.toThrow(/não é uma imagem oficial/);
  });

  it("versão sem imagem na região: null (tenta gp3 e gp2)", async () => {
    ssm.on(GetParameterCommand).rejects(Object.assign(new Error("not found"), { name: "ParameterNotFound" }));
    expect(await new AwsCatalog(session).resolveUbuntu("sa-east-1", "26.04", "arm64")).toBeNull();
    expect(ssm.commandCalls(GetParameterCommand)).toHaveLength(2);
    expect(ubuntuParameterNames("22.04", "arm64")[1]).toBe("/aws/service/canonical/ubuntu/server/22.04/stable/current/arm64/hvm/ebs-gp2/ami-id");
  });
});

describe("custos", () => {
  it("soma EC2, EBS, IPv4 e ECR e marca o que cobra com a EC2 parada", async () => {
    const cost = await estimateCost(readyConfig(), { ec2Hourly: async () => 0.0208, ebsGbMonth: async () => 0.1 });
    const ec2Line = cost.lines.find((l) => l.item.startsWith("EC2"))!;
    expect(ec2Line.monthlyUsd).toBe(Math.round(0.0208 * HOURS_PER_MONTH * 100) / 100);
    expect(cost.lines.find((l) => l.item.startsWith("EBS raiz"))).toMatchObject({ monthlyUsd: 2, chargedWhenStopped: true });
    expect(cost.lines.find((l) => l.item === "IPv4 público")?.monthlyUsd).toBe(3.65);
    expect(cost.incomplete).toBe(false);
    expect(cost.disclaimer).toMatch(/Estimativa/);
  });

  it("preço indisponível não vira zero: marca como incompleto", async () => {
    const cost = await estimateCost(readyConfig(), { ec2Hourly: async () => null, ebsGbMonth: async () => 0.1 });
    expect(cost.incomplete).toBe(true);
    expect(cost.lines[0]!.monthlyUsd).toBeNull();
  });
});

describe("saúde", () => {
  it("classifica pelo que foi verificado", () => {
    expect(classifyHealth({ ec2State: "stopped" }).state).toBe("Stopped");
    expect(classifyHealth({ ec2State: "running", container: { state: "running", status: "Up 2 minutes (healthy)" }, http: { ok: true, status: 200, ms: 30 } }).state).toBe("Running");
    expect(classifyHealth({ ec2State: "running", container: { state: "running", status: "Up 1 minute (unhealthy)" }, http: { ok: true, status: 200 } }).state).toBe("Degraded");
    expect(classifyHealth({ ec2State: "running", container: { state: "exited", status: "Exited (1)" } }).state).toBe("Degraded");
    expect(classifyHealth({ ec2State: "running", ssmOnline: false }).state).toBe("Unknown");
    expect(classifyHealth({}).state).toBe("Unknown");
  });

  it("tenta de novo com espera crescente até responder", async () => {
    const results = [{ ok: false, error: "x" }, { ok: false, error: "x" }, { ok: true, status: 200 }];
    const waits: number[] = [];
    const r = await waitHealthy("http://x/", async () => results.shift()!, 60 * 60_000, () => undefined, async (ms) => void waits.push(ms));
    expect(r.ok).toBe(true);
    expect(waits).toEqual([10_000, 15_000]);
  });

  it("lê a saída do status.sh", () => {
    const s = parseStatusOutput("bootstrap=done\ndocker=active\ndocker_version=29.1.0\nubuntu=24.04\nimage=repo:tag\ncontainer=mentoria-app-1|running|Up 5 minutes (healthy)\n");
    expect(s).toMatchObject({ bootstrapDone: true, dockerActive: true, ubuntu: "24.04", image: "repo:tag" });
    expect(s.containers[0]).toEqual({ name: "mentoria-app-1", state: "running", status: "Up 5 minutes (healthy)" });
  });
});

describe("Docker", () => {
  const repo = readyConfig;
  it("monta o build sem shell, com plataforma da arquitetura e caminhos dentro do repositório", () => {
    const d = new DockerImages(vi.fn());
    const args = d.buildArgs(repo(), "C:/repo", "mentoria:tag");
    expect(args.slice(0, 3)).toEqual(["build", "--platform", "linux/amd64"]);
    expect(args).toContain("BANCO=mysql");
    expect(platformFor("arm64")).toBe("linux/arm64");
    const fora = repo();
    fora.application.dockerfile = "../../Windows/x";
    expect(() => d.buildArgs(fora, "C:/repo", "x")).toThrow(/fora do repositório/);
  });

  it("login no ECR pela entrada padrão (a senha nunca vai nos argumentos)", async () => {
    const runner = vi.fn(async (_cmd: string, _args: string[], _opts?: { stdin?: string }) => ({ code: 0, stdout: "latest: digest: sha256:" + "b".repeat(64) + " size: 1", stderr: "" }));
    const digest = await new DockerImages(runner).push("repo:tag", { registry: "r.example", username: "AWS", password: "SENHA-ECR" }, () => undefined);
    expect(digest).toBe("sha256:" + "b".repeat(64));
    const login = runner.mock.calls[0] as unknown as [string, string[], { stdin: string }];
    expect(login[1]).not.toContain("SENHA-ECR");
    expect(login[2].stdin).toBe("SENHA-ECR");
    expect(runner.mock.calls.at(-1)?.[1]).toEqual(["logout", "r.example"]);
  });

  it("tag imutável com data e commit (e -dirty com mudanças locais)", async () => {
    const runner = vi.fn(async (_c: string, args: string[]) => (args[0] === "rev-parse" ? { code: 0, stdout: "a1b2c3d\n", stderr: "" } : { code: 0, stdout: " M app.py\n", stderr: "" }));
    expect(await immutableTag(runner, "/r", new Date("2026-11-20T15:30:12Z"))).toBe("20261120-153012-a1b2c3d-dirty");
    const semGit = vi.fn(async () => ({ code: 128, stdout: "", stderr: "" }));
    expect(await immutableTag(semGit, "/r", new Date("2026-11-20T15:30:12Z"))).toBe("20261120-153012-local");
  });
});

describe("projeto", () => {
  it("lê porta, health check e argumentos do Dockerfile", () => {
    const d = parseDockerfile("FROM python:3.12-slim AS base\nARG BANCO=mysql\nENV PYTHONUNBUFFERED=1 PORT=8080\nEXPOSE 8080\nUSER app\nHEALTHCHECK CMD curl -f http://localhost:8080/ || exit 1\n", "Dockerfile");
    expect(d).toMatchObject({ exposedPorts: [8080], envPort: 8080, hasHealthcheck: true, buildArgs: ["BANCO"], stages: 1, user: "app" });
  });
  it("caminhos não saem do repositório", () => {
    expect(() => insideRepo("/repo", "../etc/passwd")).toThrow();
    expect(insideRepo("/repo", "deploy/Dockerfile")).toMatch(/deploy/);
  });
});

describe("rotas de configuração", () => {
  it("valores secretos vão para o Pulumi e nunca voltam na resposta nem no arquivo", async () => {
    const ensureSecrets = vi.fn(async () => undefined);
    const { app, ctx } = await makeApp({ session: fakeSession() as unknown as AppContext["session"], stacks: { ensureSecrets } as unknown as AppContext["stacks"] });
    const config = defaultDeploymentConfig();
    config.application.env.push({ key: "MAIL_PASSWORD", value: "valor-super-secreto", secret: true });
    const r = await app.inject({ method: "PUT", url: "/api/config", headers: HEADERS, payload: config });
    expect(r.statusCode).toBe(200);
    expect(r.body).not.toContain("valor-super-secreto");
    expect(r.json().config.application.env.at(-1)).toMatchObject({ key: "MAIL_PASSWORD", value: "", secret: true, hasValue: true });
    expect(ensureSecrets).toHaveBeenCalledWith(expect.anything(), { MAIL_PASSWORD: "valor-super-secreto" });
    const fs = await import("node:fs/promises");
    expect(await fs.readFile(`${ctx.settings.stateDir}/config.json`, "utf8")).not.toContain("valor-super-secreto");
    await app.close();
  });

  it("configuração inválida: 400 com os caminhos dos campos", async () => {
    const { app } = await makeApp();
    const config = defaultDeploymentConfig();
    config.network.ssh = { enabled: true, allowedCidrs: ["0.0.0.0/0"] };
    const r = await app.inject({ method: "PUT", url: "/api/config", headers: HEADERS, payload: config });
    expect(r.statusCode).toBe(400);
    expect(r.json().issues[0].path).toBe("network.ssh.allowedCidrs");
    await app.close();
  });

  it("splitSecrets mantém o 'hasValue' quando o segredo não foi redigitado", () => {
    const c = defaultDeploymentConfig();
    c.application.env.push({ key: "X", value: "", secret: true, hasValue: true });
    expect(splitSecrets(c).publicConfig.application.env.at(-1)).toMatchObject({ hasValue: true, value: "" });
    expect(splitSecrets(c).secretValues).toEqual({});
  });
});
