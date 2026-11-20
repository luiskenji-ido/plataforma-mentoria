/**
 * Configuração da implantação guardada em .state/config.json — SEM valores secretos.
 * Os valores das variáveis marcadas como segredo vão para a configuração cifrada do stack do Pulumi; aqui fica só
 * a indicação de que existe valor (hasValue).
 */
import { createHash, randomBytes } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { deploymentConfigSchema, defaultDeploymentConfig, type DeploymentConfig } from "@infra/shared";

export interface StoredConfig {
  config: DeploymentConfig;
  updatedAt: string;
  /** Muda sempre que um segredo é alterado (entra no hash da prévia). */
  secretsVersion: number;
}

export function withUniqueStackName(config: DeploymentConfig): DeploymentConfig {
  const suffix = randomBytes(3).toString("hex").slice(0, 4);
  return { ...config, stackName: `${config.application.name}-${suffix}` };
}

/** Separa os valores secretos (que vão para o Pulumi) da configuração que pode ser gravada em disco. */
export function splitSecrets(config: DeploymentConfig): { publicConfig: DeploymentConfig; secretValues: Record<string, string> } {
  const secretValues: Record<string, string> = {};
  const env = config.application.env.map((e) => {
    if (!e.secret) {
      return { key: e.key, value: e.value, secret: false };
    }
    if (e.value) {
      secretValues[e.key] = e.value;
    }
    return { key: e.key, value: "", secret: true, hasValue: Boolean(e.value) || Boolean(e.hasValue) };
  });
  return { publicConfig: { ...config, application: { ...config.application, env } }, secretValues };
}

export function configHash(config: DeploymentConfig, secretsVersion: number): string {
  return createHash("sha256").update(JSON.stringify({ config, secretsVersion })).digest("hex").slice(0, 16);
}

export class ConfigStore {
  private readonly file: string;

  constructor(stateDir: string) {
    this.file = path.join(stateDir, "config.json");
  }

  async load(): Promise<StoredConfig> {
    try {
      const raw = JSON.parse(await readFile(this.file, "utf8")) as StoredConfig;
      const parsed = deploymentConfigSchema.safeParse(raw.config);
      if (parsed.success) {
        return { config: parsed.data, updatedAt: raw.updatedAt, secretsVersion: raw.secretsVersion ?? 0 };
      }
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
        throw error;
      }
    }
    // Primeira execução: grava a configuração padrão com um nome de stack único (fica fixo daí em diante)
    return this.write({ config: withUniqueStackName(defaultDeploymentConfig()), updatedAt: new Date().toISOString(), secretsVersion: 0 });
  }

  private async write(stored: StoredConfig): Promise<StoredConfig> {
    await mkdir(path.dirname(this.file), { recursive: true });
    const tmp = `${this.file}.tmp`;
    await writeFile(tmp, JSON.stringify(stored, null, 2), { encoding: "utf8", mode: 0o600 });
    await rename(tmp, this.file);
    return stored;
  }

  async save(config: DeploymentConfig, secretsChanged: boolean): Promise<StoredConfig> {
    const current = await this.load();
    const { publicConfig } = splitSecrets(config);
    return this.write({
      config: publicConfig,
      updatedAt: new Date().toISOString(),
      secretsVersion: current.secretsVersion + (secretsChanged ? 1 : 0),
    });
  }
}
