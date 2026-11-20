/**
 * Contrato único entre o painel (React), a API (Fastify) e o programa Pulumi.
 * Toda entrada externa passa por estes schemas antes de chegar à AWS ou ao Pulumi.
 */
import { z } from "zod";

// ---------------------------------------------------------------- regiões
export const AWS_REGIONS = [
  { code: "us-east-1", name: "EUA Leste (N. Virgínia)" },
  { code: "us-east-2", name: "EUA Leste (Ohio)" },
  { code: "us-west-2", name: "EUA Oeste (Oregon)" },
  { code: "sa-east-1", name: "América do Sul (São Paulo)" },
  { code: "ca-central-1", name: "Canadá (Central)" },
  { code: "eu-west-1", name: "Europa (Irlanda)" },
  { code: "eu-central-1", name: "Europa (Frankfurt)" },
  { code: "eu-west-2", name: "Europa (Londres)" },
  { code: "eu-south-2", name: "Europa (Espanha)" },
  { code: "ap-southeast-1", name: "Ásia-Pacífico (Singapura)" },
  { code: "ap-northeast-1", name: "Ásia-Pacífico (Tóquio)" },
  { code: "ap-south-1", name: "Ásia-Pacífico (Mumbai)" },
] as const;
export const regionSchema = z.enum(AWS_REGIONS.map((r) => r.code) as [string, ...string[]], {
  error: "Região não suportada pelo painel.",
});

// ---------------------------------------------------------------- utilitários
const CIDR = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}\/(\d|[12]\d|3[0-2])$/;
export const cidrSchema = z.string().trim().regex(CIDR, "Use o formato CIDR, ex.: 10.0.0.0/16 ou 203.0.113.10/32.");

export function cidrToRange(cidr: string): { start: number; end: number; prefix: number } {
  const [ip, bits] = cidr.split("/");
  const prefix = Number(bits);
  const parts = (ip ?? "").split(".").map(Number);
  const value = ((parts[0]! << 24) | (parts[1]! << 16) | (parts[2]! << 8) | parts[3]!) >>> 0;
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  const start = (value & mask) >>> 0;
  return { start, end: (start + 2 ** (32 - prefix) - 1) >>> 0, prefix };
}

export function cidrContains(outer: string, inner: string): boolean {
  const a = cidrToRange(outer);
  const b = cidrToRange(inner);
  return b.prefix >= a.prefix && b.start >= a.start && b.end <= a.end;
}

const SAFE_NAME = /^[a-zA-Z0-9][a-zA-Z0-9 ._-]{0,62}$/;
const RESERVED_MOUNTS = ["/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/root", "/run", "/sbin", "/sys", "/usr", "/var", "/tmp", "/snap"];

// ---------------------------------------------------------------- conexão AWS
const profileName = z.string().trim().regex(/^[\w.+@-]{1,64}$/, "Nome de perfil inválido.");
export const awsConnectionSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("profile"), profile: profileName, region: regionSchema }),
  z.object({ mode: z.literal("sso"), profile: profileName, region: regionSchema }),
  z.object({
    mode: z.literal("temporary"),
    accessKeyId: z.string().trim().regex(/^(AKIA|ASIA)[A-Z0-9]{16}$/, "Access Key ID inválida (começa com AKIA ou ASIA)."),
    secretAccessKey: z.string().trim().min(30, "Secret Access Key incompleta.").max(128),
    sessionToken: z
      .string()
      .trim()
      .max(4096)
      .optional()
      .transform((v) => v || undefined),
    region: regionSchema,
  }),
]);
export type AwsConnectionInput = z.infer<typeof awsConnectionSchema>;

/** O que a API devolve sobre a conexão: nunca contém chaves, tokens ou segredos. */
export interface AwsConnectionStatus {
  connected: boolean;
  mode?: AwsConnectionInput["mode"];
  profile?: string;
  region?: string;
  accountId?: string;
  arn?: string;
  userId?: string;
  isRoot?: boolean;
  expiresAt?: string;
  error?: string;
}

// ---------------------------------------------------------------- configuração da implantação
export const UBUNTU_VERSIONS = ["22.04", "24.04", "26.04"] as const;
export const ARCHITECTURES = ["x86_64", "arm64"] as const;
export const ROOT_VOLUME_TYPES = ["gp3", "gp2"] as const;
export const DATA_VOLUME_TYPES = ["gp3", "gp2", "st1", "sc1"] as const;

/** Limites de tamanho por tipo de volume EBS (GiB), da documentação da AWS. */
export const EBS_SIZE_LIMITS: Record<(typeof DATA_VOLUME_TYPES)[number], { min: number; max: number }> = {
  gp3: { min: 1, max: 16384 },
  gp2: { min: 1, max: 16384 },
  st1: { min: 125, max: 16384 },
  sc1: { min: 125, max: 16384 },
};
/** O Ubuntu Server precisa de pelo menos 8 GiB; com Docker e imagens, 20 GiB é um mínimo confortável. */
export const ROOT_DISK_MIN_GB = 8;
export const ROOT_DISK_RECOMMENDED_GB = 20;

const envKey = z.string().trim().regex(/^[A-Z_][A-Z0-9_]{0,127}$/, "Use letras maiúsculas, números e _ (ex.: MAIL_SERVER).");
export const envVarSchema = z.object({
  key: envKey,
  /** Valor em texto. Para segredos, a API guarda o valor cifrado no Pulumi e devolve vazio. */
  value: z
    .string()
    .max(4096)
    .refine((v) => !/[\r\n]/.test(v), "O valor não pode ter quebra de linha.")
    .refine((v) => !v.includes("'"), "O valor não pode ter aspas simples (')."),
  secret: z.boolean().default(false),
  /** Só na resposta da API: o segredo já tem valor guardado (o valor em si nunca volta). */
  hasValue: z.boolean().optional(),
});
export type EnvVar = z.infer<typeof envVarSchema>;

export const dataVolumeSchema = z
  .object({
    name: z.string().trim().regex(/^[a-z0-9][a-z0-9-]{0,30}$/, "Use letras minúsculas, números e -."),
    sizeGb: z.number().int(),
    type: z.enum(DATA_VOLUME_TYPES),
    mountPath: z
      .string()
      .trim()
      .regex(/^\/[a-z0-9][a-z0-9/_-]{0,62}$/, "Caminho absoluto com letras minúsculas, números, /, _ e -.")
      .refine((p) => !p.includes("..") && !p.endsWith("/"), "Caminho inválido."),
    /** false (padrão): o volume continua na conta quando a infraestrutura é destruída (dados preservados). */
    deleteOnDestroy: z.boolean().default(false),
  })
  .superRefine((v, ctx) => {
    const lim = EBS_SIZE_LIMITS[v.type];
    if (v.sizeGb < lim.min || v.sizeGb > lim.max) {
      ctx.addIssue({ code: "custom", path: ["sizeGb"], message: `${v.type} aceita de ${lim.min} a ${lim.max} GiB.` });
    }
    if (RESERVED_MOUNTS.some((r) => v.mountPath === r || (r !== "/" && v.mountPath.startsWith(`${r}/`)))) {
      ctx.addIssue({ code: "custom", path: ["mountPath"], message: "Esse caminho é do sistema: use algo como /data." });
    }
  });
export type DataVolume = z.infer<typeof dataVolumeSchema>;

export const appVolumeSchema = z.object({
  /** Pasta dentro de um volume de dados (ex.: /data/uploads). */
  hostPath: z.string().trim().regex(/^\/[a-z0-9][a-z0-9/_-]{0,120}$/).refine((p) => !p.includes(".."), "Caminho inválido."),
  containerPath: z.string().trim().regex(/^\/[A-Za-z0-9][A-Za-z0-9/_.-]{0,120}$/).refine((p) => !p.includes(".."), "Caminho inválido."),
});

export const deploymentConfigSchema = z
  .object({
    stackName: z.string().trim().regex(/^[a-z0-9][a-z0-9-]{2,39}$/, "3 a 40 caracteres: letras minúsculas, números e -."),
    instance: z.object({
      name: z.string().trim().regex(SAFE_NAME, "Use letras, números, espaço, ., _ e -."),
      region: regionSchema,
      instanceType: z.string().trim().regex(/^[a-z][a-z0-9-]*\.[a-z0-9]+$/, "Tipo de instância inválido (ex.: t3.small)."),
      architecture: z.enum(ARCHITECTURES),
      ubuntuVersion: z.enum(UBUNTU_VERSIONS),
      /** AMI oficial da Canonical resolvida pela API para a região e a arquitetura (nunca digitada à mão). */
      amiId: z.string().regex(/^ami-[0-9a-f]{8,17}$/).optional(),
      amiName: z.string().max(200).optional(),
    }),
    rootDisk: z.object({
      type: z.enum(ROOT_VOLUME_TYPES),
      sizeGb: z.number().int().min(ROOT_DISK_MIN_GB, `Mínimo de ${ROOT_DISK_MIN_GB} GiB.`).max(16384),
      encrypted: z.boolean().default(true),
    }),
    dataVolumes: z.array(dataVolumeSchema).max(4, "No máximo 4 volumes extras."),
    network: z.object({
      mode: z.enum(["new", "existing"]),
      vpcCidr: cidrSchema,
      subnetCidr: cidrSchema,
      availabilityZone: z.string().trim().regex(/^[a-z]{2}-[a-z]+-\d[a-z]$/, "Zona inválida (ex.: sa-east-1a)."),
      existingVpcId: z.string().regex(/^vpc-[0-9a-f]{8,17}$/).optional(),
      existingSubnetId: z.string().regex(/^subnet-[0-9a-f]{8,17}$/).optional(),
      assignPublicIp: z.boolean(),
      exposeApp: z.boolean(),
      appAllowedCidrs: z.array(cidrSchema).max(20),
      ssh: z.object({ enabled: z.boolean(), allowedCidrs: z.array(cidrSchema).max(10) }),
    }),
    application: z.object({
      name: z.string().trim().regex(/^[a-z0-9][a-z0-9-]{1,39}$/, "Letras minúsculas, números e -."),
      dockerfile: z.string().trim().regex(/^[A-Za-z0-9_./-]{1,200}$/).refine((p) => !p.split("/").includes(".."), "Caminho fora do projeto."),
      buildContext: z.string().trim().regex(/^[A-Za-z0-9_./-]{1,200}$/).refine((p) => !p.split("/").includes(".."), "Caminho fora do projeto."),
      buildArgs: z.record(z.string().regex(/^[A-Za-z_][A-Za-z0-9_]{0,63}$/), z.string().max(200).regex(/^[^\r\n]*$/)),
      containerPort: z.number().int().min(1).max(65535),
      hostPort: z.number().int().min(1).max(65535),
      healthPath: z.string().trim().regex(/^\/[A-Za-z0-9/_.-]{0,100}$/, "Caminho HTTP que começa com /."),
      restartPolicy: z.enum(["unless-stopped", "always", "on-failure"]),
      env: z.array(envVarSchema).max(100),
      volumes: z.array(appVolumeSchema).max(10),
      database: z.object({ enabled: z.boolean(), image: z.string().regex(/^mysql:8\.[0-9]+(\.[0-9]+)?$/, "Use uma imagem oficial mysql:8.x.") }),
    }),
  })
  .superRefine((c, ctx) => {
    const n = c.network;
    if (n.mode === "new") {
      if (cidrToRange(n.vpcCidr).prefix < 16 || cidrToRange(n.vpcCidr).prefix > 28) {
        ctx.addIssue({ code: "custom", path: ["network", "vpcCidr"], message: "A VPC precisa ter de /16 a /28." });
      }
      if (!cidrContains(n.vpcCidr, n.subnetCidr)) {
        ctx.addIssue({ code: "custom", path: ["network", "subnetCidr"], message: "A sub-rede precisa estar dentro da faixa da VPC." });
      }
    } else if (!n.existingVpcId || !n.existingSubnetId) {
      ctx.addIssue({ code: "custom", path: ["network", "existingSubnetId"], message: "Escolha a VPC e a sub-rede existentes." });
    }
    if (!n.availabilityZone.startsWith(c.instance.region)) {
      ctx.addIssue({ code: "custom", path: ["network", "availabilityZone"], message: "A zona precisa ser da região escolhida." });
    }
    if (n.exposeApp && n.appAllowedCidrs.length === 0) {
      ctx.addIssue({ code: "custom", path: ["network", "appAllowedCidrs"], message: "Informe quem pode acessar o app (ex.: 0.0.0.0/0 para todos)." });
    }
    if (n.exposeApp && !n.assignPublicIp) {
      ctx.addIssue({ code: "custom", path: ["network", "assignPublicIp"], message: "Para expor o app na internet a instância precisa de IP público." });
    }
    if (n.ssh.enabled && n.ssh.allowedCidrs.some((cidr) => cidrToRange(cidr).prefix === 0)) {
      ctx.addIssue({ code: "custom", path: ["network", "ssh", "allowedCidrs"], message: "SSH aberto para a internet inteira não é permitido: use o seu IP/32 ou o Session Manager." });
    }
    if (n.ssh.enabled && n.ssh.allowedCidrs.length === 0) {
      ctx.addIssue({ code: "custom", path: ["network", "ssh", "allowedCidrs"], message: "Informe de qual IP o SSH será aceito." });
    }
    if (c.application.hostPort === 22) {
      ctx.addIssue({ code: "custom", path: ["application", "hostPort"], message: "A porta 22 é do SSH." });
    }
    const mounts = c.dataVolumes.map((v) => v.mountPath);
    if (new Set(mounts).size !== mounts.length) {
      ctx.addIssue({ code: "custom", path: ["dataVolumes"], message: "Dois volumes não podem usar o mesmo caminho." });
    }
    const names = c.dataVolumes.map((v) => v.name);
    if (new Set(names).size !== names.length) {
      ctx.addIssue({ code: "custom", path: ["dataVolumes"], message: "Os nomes dos volumes precisam ser diferentes." });
    }
    c.application.volumes.forEach((v, i) => {
      if (!mounts.some((m) => v.hostPath === m || v.hostPath.startsWith(`${m}/`))) {
        ctx.addIssue({ code: "custom", path: ["application", "volumes", i, "hostPath"], message: "A pasta precisa ficar dentro de um volume de dados (para sobreviver à troca da instância)." });
      }
    });
    if (c.application.database.enabled && mounts.length === 0) {
      ctx.addIssue({ code: "custom", path: ["dataVolumes"], message: "O MySQL precisa de um volume de dados para guardar o banco." });
    }
    const keys = c.application.env.map((e) => e.key);
    if (new Set(keys).size !== keys.length) {
      ctx.addIssue({ code: "custom", path: ["application", "env"], message: "Há variáveis de ambiente repetidas." });
    }
    for (const reservada of ["DATABASE_URL", "SECRET_KEY", "PORT"]) {
      if (keys.includes(reservada) && (reservada !== "DATABASE_URL" || c.application.database.enabled)) {
        ctx.addIssue({ code: "custom", path: ["application", "env"], message: `${reservada} é gerada pelo painel: remova da lista.` });
      }
    }
  });
export type DeploymentConfig = z.infer<typeof deploymentConfigSchema>;

/** Configuração inicial pensada para a plataforma Mentoria (contêiner Flask na porta 8080 + MySQL). */
export function defaultDeploymentConfig(region = "sa-east-1"): DeploymentConfig {
  return {
    stackName: "mentoria-dev",
    instance: { name: "mentoria-app", region, instanceType: "t3.small", architecture: "x86_64", ubuntuVersion: "24.04" },
    rootDisk: { type: "gp3", sizeGb: ROOT_DISK_RECOMMENDED_GB, encrypted: true },
    dataVolumes: [{ name: "dados", sizeGb: 20, type: "gp3", mountPath: "/data", deleteOnDestroy: false }],
    network: {
      mode: "new",
      vpcCidr: "10.42.0.0/16",
      subnetCidr: "10.42.1.0/24",
      availabilityZone: `${region}a`,
      assignPublicIp: true,
      exposeApp: true,
      appAllowedCidrs: ["0.0.0.0/0"],
      ssh: { enabled: false, allowedCidrs: [] },
    },
    application: {
      name: "mentoria",
      dockerfile: "deploy/conteiner/Dockerfile",
      buildContext: ".",
      buildArgs: { BANCO: "mysql" },
      containerPort: 8080,
      hostPort: 80,
      healthPath: "/",
      restartPolicy: "unless-stopped",
      env: [
        { key: "MENTORIA_PRODUCAO", value: "1", secret: false },
        { key: "HOSPEDAGEM", value: "aws_vm", secret: false },
        { key: "DISCO_PERSISTENTE", value: "1", secret: false },
      ],
      volumes: [
        { hostPath: "/data/uploads", containerPath: "/app/uploads" },
        { hostPath: "/data/instance", containerPath: "/app/instance" },
      ],
      database: { enabled: true, image: "mysql:8.4" },
    },
  };
}

// ---------------------------------------------------------------- operações e eventos
export const OPERATION_KINDS = ["preview", "provision", "deploy", "refresh", "destroy"] as const;
export type OperationKind = (typeof OPERATION_KINDS)[number];
export type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface OperationEvent {
  seq: number;
  time: string;
  type: "step" | "log" | "result";
  step?: string;
  status?: StepStatus;
  message: string;
  level?: "info" | "warn" | "error";
}

export interface OperationSummary {
  id: string;
  kind: OperationKind;
  stackName: string;
  status: "running" | "succeeded" | "failed";
  startedAt: string;
  finishedAt?: string;
  error?: string;
  steps: { key: string; label: string; status: StepStatus; detail?: string }[];
}

export interface PreviewResult {
  stackName: string;
  configHash: string;
  createdAt: string;
  expiresAt: string;
  changeSummary: Record<string, number>;
  resources: { op: string; type: string; name: string }[];
  summary: {
    region: string;
    instanceType: string;
    ubuntu: string;
    amiId?: string;
    rootDisk: string;
    dataVolumes: string[];
    network: string;
    openPorts: string[];
    image: string;
  };
  cost: CostEstimate;
}

export interface CostLine {
  item: string;
  monthlyUsd: number | null;
  hourlyUsd?: number | null;
  source: string;
  note?: string;
  chargedWhenStopped: boolean;
}

export interface CostEstimate {
  lines: CostLine[];
  monthlyTotalUsd: number;
  incomplete: boolean;
  pricingDate: string;
  disclaimer: string;
}

export type HealthState = "Running" | "Degraded" | "Stopped" | "Unknown";
