import type { AwsConnectionStatus, DeploymentConfig, HealthState, OperationSummary } from "@infra/shared";

export interface StoredConfigResponse {
  config: DeploymentConfig;
  updatedAt: string;
  secretsVersion: number;
  configHash: string;
}

export interface ToolCheck {
  name: string;
  ok: boolean;
  version?: string;
  required: boolean;
  help: string;
}

export interface DoctorResponse {
  tools: ToolCheck[];
  passphraseSet: boolean;
  aws: AwsConnectionStatus;
}

export interface InstanceTypeInfo {
  type: string;
  vcpus: number;
  memoryGiB: number;
  architectures: string[];
  burstable: boolean;
}

export interface UbuntuImage {
  version: string;
  amiId: string;
  name: string;
  creationDate?: string;
  architecture: "x86_64" | "arm64";
}

export interface ProjectInfo {
  repoRoot: string;
  dockerfiles: { path: string; exposedPorts: number[]; envPort?: number; hasHealthcheck: boolean; buildArgs: string[]; baseImages: string[]; stages: number; user?: string }[];
  composeFiles: string[];
  envExampleKeys: string[];
  healthEndpoints: string[];
}

export interface InstancesResponse {
  provisioned: boolean;
  stackName: string;
  region?: string;
  instance?: {
    instanceId: string;
    state: string;
    instanceType?: string;
    publicIp?: string;
    privateIp?: string;
    launchTime?: string;
    availabilityZone?: string;
    name?: string;
    systemStatus?: string;
    instanceStatus?: string;
  } | null;
  ubuntu?: string;
  ssmOnline?: boolean;
  docker?: { active: boolean; version?: string; bootstrapDone: boolean };
  image?: string;
  containers?: { name: string; state: string; status: string }[];
  appUrl?: string;
  http?: { ok: boolean; status?: number; error?: string; ms?: number };
  health?: { state: HealthState; reason: string };
  outputs?: Record<string, unknown>;
}

export interface OperationStarted {
  operationId: string;
  summary: OperationSummary;
}
