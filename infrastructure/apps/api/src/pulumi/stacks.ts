/**
 * Pulumi pelo Automation API, com o programa inline de @infra/pulumi.
 * - Estado: backend local em arquivo (.state/pulumi), sem conta no Pulumi Cloud.
 * - Segredos: provedor "passphrase" (a senha fica só na memória da API ou na variável PULUMI_CONFIG_PASSPHRASE).
 *   Sem senha, nada roda: não há queda silenciosa para segredos sem cifra.
 * - Credenciais da AWS: só no ambiente do processo do Pulumi, resolvidas na hora.
 */
import { randomBytes } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  LocalWorkspace,
  type EngineEvent,
  type LocalWorkspaceOptions,
  type OutputMap,
  type Stack,
} from "@pulumi/pulumi/automation";
import type { DeploymentConfig } from "@infra/shared";
import { CONFIG_KEYS, PROJECT_NAME, createProgram } from "@infra/pulumi";
import type { AwsSession } from "../aws/credentials";
import { registerSecret } from "../services/redact";

const require = createRequire(import.meta.url);
export const AWS_PLUGIN_VERSION = `v${(require("@pulumi/aws/package.json") as { version: string }).version}`;
export const MIN_PASSPHRASE = 12;

export class PassphraseMissingError extends Error {
  readonly statusCode = 412;
  constructor() {
    super("Defina a senha do estado do Pulumi (Configurações) antes: ela cifra os segredos do stack. Sem ela nada é criado.");
  }
}

export interface PlannedResource {
  op: string;
  type: string;
  name: string;
}

export interface StackRunHooks {
  onOutput?: (line: string) => void;
  onEvent?: (event: EngineEvent) => void;
}

export class StackService {
  private passphrase?: string;
  private pluginInstalled = false;

  constructor(private readonly stateDir: string, private readonly session: AwsSession, env: NodeJS.ProcessEnv = process.env) {
    if (env.PULUMI_CONFIG_PASSPHRASE) {
      this.setPassphrase(env.PULUMI_CONFIG_PASSPHRASE);
    }
  }

  setPassphrase(value: string): void {
    if (value.length < MIN_PASSPHRASE) {
      throw new Error(`A senha precisa de pelo menos ${MIN_PASSPHRASE} caracteres.`);
    }
    registerSecret(value);
    this.passphrase = value;
  }

  hasPassphrase(): boolean {
    return Boolean(this.passphrase);
  }

  backendUrl(): string {
    return pathToFileURL(path.join(this.stateDir, "pulumi")).href;
  }

  private async workspaceOptions(region: string | undefined): Promise<LocalWorkspaceOptions> {
    if (!this.passphrase) {
      throw new PassphraseMissingError();
    }
    await mkdir(path.join(this.stateDir, "pulumi"), { recursive: true });
    await mkdir(path.join(this.stateDir, "pulumi-work"), { recursive: true });
    const awsEnv = region ? await this.session.envForSubprocess(region) : {};
    return {
      workDir: path.join(this.stateDir, "pulumi-work"),
      projectSettings: { name: PROJECT_NAME, runtime: "nodejs", backend: { url: this.backendUrl() } },
      secretsProvider: "passphrase",
      envVars: {
        PULUMI_CONFIG_PASSPHRASE: this.passphrase,
        PULUMI_SKIP_UPDATE_CHECK: "true",
        PULUMI_AUTOMATION_API_SKIP_VERSION_CHECK: "true",
        ...awsEnv,
      },
    };
  }

  /** Abre (ou cria) o stack; com AWS = false não exige conexão (para gravar segredos da configuração). */
  async open(config: DeploymentConfig, withAws = true): Promise<Stack> {
    const options = await this.workspaceOptions(withAws ? config.instance.region : undefined);
    const stack = await LocalWorkspace.createOrSelectStack(
      { stackName: config.stackName, projectName: PROJECT_NAME, program: createProgram(config) },
      options,
    );
    if (withAws && !this.pluginInstalled) {
      await stack.workspace.installPlugin("aws", AWS_PLUGIN_VERSION);
      this.pluginInstalled = true;
    }
    if (withAws) {
      await stack.setConfig("aws:region", { value: config.instance.region });
    }
    return stack;
  }

  /** Gera (uma vez) os segredos da aplicação e grava os valores das variáveis secretas, tudo cifrado no stack. */
  async ensureSecrets(config: DeploymentConfig, secretEnv: Record<string, string> = {}): Promise<void> {
    const stack = await this.open(config, false);
    const all = await stack.getAllConfig();
    const has = (key: string) => Boolean(all[`${PROJECT_NAME}:${key}`]);
    const generate = (bytes: number) => randomBytes(bytes).toString("hex");
    if (!has(CONFIG_KEYS.secretKey)) {
      await stack.setConfig(CONFIG_KEYS.secretKey, { value: generate(32), secret: true });
    }
    if (!has(CONFIG_KEYS.dbPassword)) {
      await stack.setConfig(CONFIG_KEYS.dbPassword, { value: generate(24), secret: true });
    }
    if (!has(CONFIG_KEYS.dbRootPassword)) {
      await stack.setConfig(CONFIG_KEYS.dbRootPassword, { value: generate(24), secret: true });
    }
    const current = has(CONFIG_KEYS.secretEnv) ? (JSON.parse((await stack.getConfig(CONFIG_KEYS.secretEnv)).value) as Record<string, string>) : {};
    const wanted = new Set(config.application.env.filter((e) => e.secret).map((e) => e.key));
    const merged: Record<string, string> = {};
    for (const key of wanted) {
      const value = secretEnv[key] ?? current[key];
      if (value !== undefined) {
        merged[key] = value;
        registerSecret(value);
      }
    }
    if (JSON.stringify(merged) !== JSON.stringify(current)) {
      await stack.setConfig(CONFIG_KEYS.secretEnv, { value: JSON.stringify(merged), secret: true });
    }
  }

  async preview(config: DeploymentConfig, hooks: StackRunHooks = {}) {
    const stack = await this.open(config);
    const resources: PlannedResource[] = [];
    const result = await stack.preview({
      onOutput: hooks.onOutput,
      onEvent: (event) => {
        const pre = event.resourcePreEvent?.metadata;
        if (pre && pre.type !== "pulumi:pulumi:Stack" && !pre.type.startsWith("pulumi:providers:")) {
          resources.push({ op: pre.op, type: pre.type, name: pre.urn.split("::").pop() ?? pre.urn });
        }
        hooks.onEvent?.(event);
      },
      diff: false,
    });
    return { changeSummary: result.changeSummary as Record<string, number>, resources };
  }

  async up(config: DeploymentConfig, hooks: StackRunHooks = {}): Promise<OutputMap> {
    const stack = await this.open(config);
    const result = await stack.up({ onOutput: hooks.onOutput, onEvent: hooks.onEvent });
    return result.outputs;
  }

  async refresh(config: DeploymentConfig, hooks: StackRunHooks = {}): Promise<void> {
    const stack = await this.open(config);
    await stack.refresh({ onOutput: hooks.onOutput, onEvent: hooks.onEvent });
  }

  async destroy(config: DeploymentConfig, hooks: StackRunHooks = {}): Promise<void> {
    const stack = await this.open(config);
    await stack.destroy({ onOutput: hooks.onOutput, onEvent: hooks.onEvent });
  }

  /** Saídas do stack (sem os valores secretos). Não precisa da AWS. */
  async outputs(config: DeploymentConfig): Promise<Record<string, unknown>> {
    const stack = await this.open(config, false);
    const out = await stack.outputs();
    return Object.fromEntries(Object.entries(out).filter(([, v]) => !v.secret).map(([k, v]) => [k, v.value]));
  }

  async listStacks(): Promise<{ name: string; lastUpdate?: string; resourceCount?: number }[]> {
    if (!this.passphrase) {
      return [];
    }
    const ws = await LocalWorkspace.create(await this.workspaceOptions(undefined));
    const stacks = await ws.listStacks();
    return stacks.map((s) => ({ name: s.name, lastUpdate: s.lastUpdate, resourceCount: s.resourceCount }));
  }
}
