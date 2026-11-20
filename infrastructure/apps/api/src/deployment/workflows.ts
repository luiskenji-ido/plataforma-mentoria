/**
 * Fluxos do painel. Nada é criado sem uma prévia aprovada: o provisionamento exige o hash da configuração exata
 * mostrada na prévia (válida por 30 minutos), o nome do stack digitado e o aceite dos custos.
 */
import type { EngineEvent } from "@pulumi/pulumi/automation";
import { deploymentConfigSchema, type DeploymentConfig, type PreviewResult } from "@infra/shared";
import { ingressRules } from "@infra/pulumi";
import type { AwsSession } from "../aws/credentials";
import { parseStatusOutput, type AwsOperations } from "../aws/operations";
import { estimateCost, type PriceSource } from "../aws/pricing";
import type { StackService } from "../pulumi/stacks";
import { configHash, type StoredConfig } from "../services/configStore";
import type { DockerImages } from "./docker";
import { immutableTag } from "./docker";
import { waitHealthy, type HttpCheck } from "./health";
import type { Operation, OperationManager } from "./operations";
import type { Runner } from "../services/process";

export const PREVIEW_TTL_MS = 30 * 60_000;
export const BOOTSTRAP_TIMEOUT_MS = 20 * 60_000;
export const HEALTH_TIMEOUT_MS = 6 * 60_000;

export interface WorkflowDeps {
  session: Pick<AwsSession, "getStatus" | "envForSubprocess">;
  stacks: Pick<StackService, "ensureSecrets" | "preview" | "up" | "refresh" | "destroy" | "outputs">;
  aws: Pick<AwsOperations, "waitSsmOnline" | "runFixed" | "putImage" | "ecrLogin">;
  docker: Pick<DockerImages, "serverVersion" | "build" | "push">;
  runner: Runner;
  http: HttpCheck;
  prices: PriceSource;
  repoRoot: string;
  operations: OperationManager;
  wait?: (ms: number) => Promise<void>;
}

export class ApprovalError extends Error {
  readonly statusCode = 412;
}

const STEP_LABELS = {
  credentials: "Validando as credenciais da AWS",
  config: "Validando a configuração",
  secrets: "Preparando os segredos (cifrados no stack)",
  preview: "Calculando as mudanças (pulumi preview)",
  cost: "Estimando os custos",
  infra: "Criando a infraestrutura (VPC, sub-rede, Security Group, IAM, ECR, EBS e EC2)",
  build: "Gerando a imagem Docker",
  push: "Enviando a imagem ao ECR",
  register: "Registrando a nova versão",
  ready: "Aguardando a instância ficar pronta",
  bootstrap: "Instalando o Docker no Ubuntu (cloud-init)",
  deploy: "Baixando a imagem e iniciando o contêiner",
  health: "Verificando a saúde da aplicação",
  outputs: "Lendo os dados do stack",
  refresh: "Atualizando o estado (pulumi refresh)",
  destroy: "Destruindo a infraestrutura (pulumi destroy)",
} as const;
type StepKey = keyof typeof STEP_LABELS;
const steps = (...keys: StepKey[]) => keys.map((key) => ({ key, label: STEP_LABELS[key] }));

function pulumiLogger(op: Operation) {
  return {
    onOutput: (line: string) => op.log(line.trimEnd()),
    onEvent: (event: EngineEvent) => {
      const out = event.resOutputsEvent?.metadata;
      if (out && !out.type.startsWith("pulumi:")) {
        const verb = { create: "criado", update: "atualizado", delete: "removido", replace: "substituído", same: "sem mudança" }[out.op as string] ?? out.op;
        op.log(`✔ ${out.type} ${out.urn.split("::").pop()} — ${verb}`);
      }
      const fail = event.resOpFailedEvent?.metadata;
      if (fail) {
        op.log(`✖ ${fail.type} ${fail.urn.split("::").pop()} falhou`, "error");
      }
      if (event.diagnosticEvent?.severity === "error") {
        op.log(event.diagnosticEvent.message, "error");
      }
    },
  };
}

export function previewSummary(config: DeploymentConfig): PreviewResult["summary"] {
  const n = config.network;
  return {
    region: config.instance.region,
    instanceType: `${config.instance.instanceType} (${config.instance.architecture})`,
    ubuntu: `Ubuntu Server ${config.instance.ubuntuVersion} LTS${config.instance.amiName ? ` — ${config.instance.amiName}` : ""}`,
    amiId: config.instance.amiId,
    rootDisk: `${config.rootDisk.sizeGb} GiB ${config.rootDisk.type}${config.rootDisk.encrypted ? " cifrado" : ""}`,
    dataVolumes: config.dataVolumes.map((v) => `${v.name}: ${v.sizeGb} GiB ${v.type} em ${v.mountPath} (cifrado; ${v.deleteOnDestroy ? "apagado no destroy" : "preservado no destroy"})`),
    network: n.mode === "new"
      ? `VPC nova ${n.vpcCidr}, sub-rede pública ${n.subnetCidr} em ${n.availabilityZone}${n.assignPublicIp ? ", com IPv4 público" : ", sem IP público"}`
      : `VPC existente ${n.existingVpcId}, sub-rede ${n.existingSubnetId}`,
    openPorts: ingressRules(config).map((r) => `TCP ${r.fromPort} ← ${(r.cidrBlocks as string[]).join(", ")} (${r.description})`),
    image: `ECR ${config.application.name}/${config.stackName} (tag imutável por publicação), Dockerfile ${config.application.dockerfile}`,
  };
}

export class Workflows {
  private lastPreview?: PreviewResult;

  constructor(private readonly deps: WorkflowDeps) {}

  getLastPreview(): PreviewResult | undefined {
    return this.lastPreview;
  }

  private ensureConnected(): void {
    if (!this.deps.session.getStatus().connected) {
      throw new ApprovalError("Conecte-se à AWS primeiro (menu Credenciais AWS).");
    }
  }

  private validate(stored: StoredConfig): DeploymentConfig {
    const parsed = deploymentConfigSchema.safeParse(stored.config);
    if (!parsed.success) {
      throw new ApprovalError(`Configuração inválida: ${parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ")}`);
    }
    if (!parsed.data.instance.amiId) {
      throw new ApprovalError("Escolha a versão do Ubuntu na tela Configuração da EC2 (a AMI oficial é resolvida na hora).");
    }
    const missing = parsed.data.application.env.filter((e) => e.secret && !e.hasValue).map((e) => e.key);
    if (missing.length) {
      throw new ApprovalError(`Preencha o valor das variáveis secretas: ${missing.join(", ")}.`);
    }
    return parsed.data;
  }

  async preview(stored: StoredConfig): Promise<Operation> {
    this.ensureConnected();
    const config = this.validate(stored);
    return this.deps.operations.start("preview", config.stackName, steps("credentials", "config", "secrets", "preview", "cost"), async (op) => {
      await op.run("credentials", () => this.deps.session.envForSubprocess(config.instance.region).then(() => undefined), () => this.deps.session.getStatus().arn);
      await op.run("config", async () => undefined, () => "ok");
      await op.run("secrets", () => this.deps.stacks.ensureSecrets(config));
      const plan = await op.run("preview", () => this.deps.stacks.preview(config, pulumiLogger(op)), (p) => Object.entries(p.changeSummary).map(([k, v]) => `${k}: ${v}`).join(", "));
      const cost = await op.run("cost", () => estimateCost(config, this.deps.prices), (c) => `~US$ ${c.monthlyTotalUsd.toFixed(2)}/mês${c.incomplete ? " (incompleto)" : ""}`);
      const now = Date.now();
      this.lastPreview = {
        stackName: config.stackName,
        configHash: configHash(stored.config, stored.secretsVersion),
        createdAt: new Date(now).toISOString(),
        expiresAt: new Date(now + PREVIEW_TTL_MS).toISOString(),
        changeSummary: plan.changeSummary,
        resources: plan.resources,
        summary: previewSummary(config),
        cost,
      };
    });
  }

  /** Confere que o pedido de provisionamento aprova exatamente a última prévia. */
  checkApproval(stored: StoredConfig, approval: { configHash: string; confirmStackName: string; acceptCosts: boolean }): DeploymentConfig {
    const config = this.validate(stored);
    const p = this.lastPreview;
    if (!p || p.stackName !== config.stackName) {
      throw new ApprovalError("Gere a prévia da infraestrutura antes de provisionar.");
    }
    if (Date.parse(p.expiresAt) < Date.now()) {
      throw new ApprovalError("A prévia expirou (30 minutos): gere de novo.");
    }
    const current = configHash(stored.config, stored.secretsVersion);
    if (approval.configHash !== p.configHash || current !== p.configHash) {
      throw new ApprovalError("A configuração mudou depois da prévia: gere a prévia de novo e confira.");
    }
    if (approval.confirmStackName !== config.stackName) {
      throw new ApprovalError("Digite o nome do stack para confirmar.");
    }
    if (!approval.acceptCosts) {
      throw new ApprovalError("Confirme que entende que os recursos são cobrados pela AWS.");
    }
    return config;
  }

  async provision(stored: StoredConfig, approval: { configHash: string; confirmStackName: string; acceptCosts: boolean }): Promise<Operation> {
    this.ensureConnected();
    const config = this.checkApproval(stored, approval);
    this.lastPreview = undefined; // uma aprovação vale para uma execução
    return this.deps.operations.start(
      "provision",
      config.stackName,
      steps("credentials", "config", "secrets", "build", "infra", "push", "register", "ready", "bootstrap", "deploy", "health"),
      async (op) => {
        await op.run("credentials", () => this.deps.session.envForSubprocess(config.instance.region).then(() => undefined), () => this.deps.session.getStatus().arn);
        await op.run("config", () => this.deps.docker.serverVersion(), (v) => `Docker ${v}; configuração aprovada na prévia`);
        await op.run("secrets", () => this.deps.stacks.ensureSecrets(config));
        // A imagem é gerada antes da infraestrutura: um erro no build não deixa recursos cobrados parados
        const tag = await immutableTag(this.deps.runner, this.deps.repoRoot);
        const localRef = `${config.application.name}:${tag}`;
        await op.run("build", () => this.deps.docker.build(config, this.deps.repoRoot, localRef, (l) => op.log(l)), () => localRef);
        const outputs = await op.run("infra", () => this.deps.stacks.up(config, pulumiLogger(op)), (o) => `instância ${String(o.instanceId?.value ?? "")}`);
        const out = Object.fromEntries(Object.entries(outputs).map(([k, v]) => [k, v.value])) as Record<string, unknown>;
        await this.publish(op, config, out, tag, localRef, true);
      },
    );
  }

  async deploy(stored: StoredConfig): Promise<Operation> {
    this.ensureConnected();
    const config = this.validate(stored);
    return this.deps.operations.start("deploy", config.stackName, steps("credentials", "outputs", "build", "push", "register", "ready", "deploy", "health"), async (op) => {
      await op.run("credentials", () => this.deps.session.envForSubprocess(config.instance.region).then(() => undefined));
      const out = await op.run("outputs", () => this.deps.stacks.outputs(config), (o) => String(o.instanceId ?? ""));
      if (!out.instanceId || !out.ecrRepositoryUrl) {
        throw new Error("O stack ainda não foi provisionado: use Provisionar infraestrutura.");
      }
      await this.deps.docker.serverVersion();
      const tag = await immutableTag(this.deps.runner, this.deps.repoRoot);
      const localRef = `${config.application.name}:${tag}`;
      await op.run("build", () => this.deps.docker.build(config, this.deps.repoRoot, localRef, (l) => op.log(l)), () => localRef);
      await this.publish(op, config, out, tag, localRef, false);
    });
  }

  /** push → registra a imagem → espera a instância → (bootstrap) → deploy fixo pelo SSM → saúde. */
  private async publish(op: Operation, config: DeploymentConfig, out: Record<string, unknown>, tag: string, localRef: string, firstTime: boolean) {
    const region = config.instance.region;
    const instanceId = String(out.instanceId);
    const repo = String(out.ecrRepositoryUrl);
    const remoteRef = `${repo}:${tag}`;
    await op.run("push", async () => {
      const auth = await this.deps.aws.ecrLogin(region);
      // retag local → remoto (sem shell) e envia
      const r = await this.deps.runner("docker", ["tag", localRef, remoteRef], { timeoutMs: 60_000 });
      if (r.code !== 0) {
        throw new Error("Não foi possível marcar a imagem para o ECR (docker tag).");
      }
      return this.deps.docker.push(remoteRef, auth, (l) => op.log(l));
    }, (digest) => `${remoteRef}${digest ? ` (${digest.slice(0, 19)}…)` : ""}`);
    await op.run("register", () => this.deps.aws.putImage(region, String(out.imageParameterName), remoteRef), () => String(out.imageParameterName));
    await op.run("ready", () => this.deps.aws.waitSsmOnline(region, instanceId, 10 * 60_000, (m) => op.log(m)), () => `${instanceId} online no Systems Manager`);
    if (firstTime) {
      await op.run("bootstrap", () => this.waitBootstrap(op, region, instanceId), (s) => `Docker ${s.dockerVersion ?? "?"} no Ubuntu ${s.ubuntu ?? "?"}`);
    }
    const deploy = await op.run("deploy", () => this.deps.aws.runFixed(region, instanceId, "deploy", 900), (r) => r.status);
    op.log(deploy.output);
    if (deploy.status !== "Success") {
      throw new Error(`A publicação na instância terminou como ${deploy.status}. Veja o log acima (Logs e diagnóstico › log do bootstrap).`);
    }
    const appUrl = String(out.appUrl ?? "");
    if (!appUrl) {
      op.step("health", "skipped", "O app não está exposto na internet: verifique pelo Session Manager.");
      return;
    }
    const url = `${appUrl}${config.application.healthPath === "/" ? "/" : config.application.healthPath}`;
    await op.run("health", async () => {
      const result = await waitHealthy(url, this.deps.http, HEALTH_TIMEOUT_MS, (r, n) => op.log(`Tentativa ${n}: ${r.ok ? `HTTP ${r.status}` : `falhou (${r.error ?? r.status})`}`), this.deps.wait);
      if (!result.ok) {
        throw new Error(`A aplicação não respondeu em ${url}. Contêiner pode estar reiniciando: veja Instâncias › logs do app.`);
      }
      return result;
    }, (r) => `${url} respondeu HTTP ${r.status}`);
  }

  private async waitBootstrap(op: Operation, region: string, instanceId: string) {
    const wait = this.deps.wait ?? ((ms: number) => new Promise((r) => setTimeout(r, ms)));
    const deadline = Date.now() + BOOTSTRAP_TIMEOUT_MS;
    while (Date.now() < deadline) {
      const r = await this.deps.aws.runFixed(region, instanceId, "status", 60).catch(() => null);
      if (r) {
        const s = parseStatusOutput(r.output);
        if (s.bootstrapDone && s.dockerActive) {
          return s;
        }
        op.log(`cloud-init em andamento (docker: ${s.dockerActive ? "ativo" : "instalando"})…`);
      }
      await wait(20_000);
    }
    throw new Error("O bootstrap não terminou em 20 minutos. Veja Logs e diagnóstico › log do bootstrap.");
  }

  async refresh(stored: StoredConfig): Promise<Operation> {
    this.ensureConnected();
    const config = this.validate(stored);
    return this.deps.operations.start("refresh", config.stackName, steps("credentials", "refresh"), async (op) => {
      await op.run("credentials", () => this.deps.session.envForSubprocess(config.instance.region).then(() => undefined));
      await op.run("refresh", () => this.deps.stacks.refresh(config, pulumiLogger(op)));
    });
  }

  async destroy(stored: StoredConfig, confirm: { confirmStackName: string; confirmPhrase: string }): Promise<Operation> {
    this.ensureConnected();
    const config = stored.config;
    if (confirm.confirmStackName !== config.stackName || confirm.confirmPhrase !== `destruir ${config.stackName}`) {
      throw new ApprovalError(`Para destruir, digite o nome do stack e a frase "destruir ${config.stackName}".`);
    }
    return this.deps.operations.start("destroy", config.stackName, steps("credentials", "destroy"), async (op) => {
      await op.run("credentials", () => this.deps.session.envForSubprocess(config.instance.region).then(() => undefined));
      const kept = config.dataVolumes.filter((v) => !v.deleteOnDestroy).map((v) => v.name);
      if (kept.length) {
        op.log(`Volumes de dados preservados (continuam cobrando até você apagá-los no console da AWS): ${kept.join(", ")}.`, "warn");
      }
      await op.run("destroy", () => this.deps.stacks.destroy(config, pulumiLogger(op)));
    });
  }
}
