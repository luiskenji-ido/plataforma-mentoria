/** Build da imagem local e envio ao ECR com tag imutável (data + commit), sempre sem shell. */
import type { DeploymentConfig } from "@infra/shared";
import { insideRepo } from "../services/project";
import type { Runner } from "../services/process";

export function platformFor(arch: DeploymentConfig["instance"]["architecture"]): string {
  return arch === "arm64" ? "linux/arm64" : "linux/amd64";
}

/** Tag única por publicação: 20261120-153012-a1b2c3d (+ "-dirty" quando há mudanças não commitadas). */
export async function immutableTag(runner: Runner, repoRoot: string, now = new Date()): Promise<string> {
  const stamp = now.toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
  const sha = await runner("git", ["rev-parse", "--short=7", "HEAD"], { cwd: repoRoot, timeoutMs: 15_000 }).then(
    (r) => (r.code === 0 ? r.stdout.trim() : ""),
    () => "",
  );
  if (!/^[0-9a-f]{7}$/.test(sha)) {
    return `${stamp}-local`;
  }
  const dirty = await runner("git", ["status", "--porcelain", "--untracked-files=no"], { cwd: repoRoot, timeoutMs: 15_000 }).then(
    (r) => r.code === 0 && r.stdout.trim().length > 0,
    () => false,
  );
  return `${stamp}-${sha}${dirty ? "-dirty" : ""}`;
}

export class DockerImages {
  constructor(private readonly runner: Runner) {}

  /** Versão do Docker Engine (falha se o Docker Desktop não estiver rodando). */
  async serverVersion(): Promise<string> {
    const r = await this.runner("docker", ["version", "--format", "{{.Server.Version}}"], { timeoutMs: 20_000 });
    if (r.code !== 0 || !r.stdout.trim()) {
      throw new Error("O Docker não está rodando: abra o Docker Desktop e espere \"Engine running\".");
    }
    return r.stdout.trim();
  }

  buildArgs(config: DeploymentConfig, repoRoot: string, imageRef: string): string[] {
    const app = config.application;
    const dockerfile = insideRepo(repoRoot, app.dockerfile);
    const context = insideRepo(repoRoot, app.buildContext);
    const args = ["build", "--platform", platformFor(config.instance.architecture), "-f", dockerfile, "-t", imageRef, "--pull"];
    for (const [k, v] of Object.entries(app.buildArgs)) {
      args.push("--build-arg", `${k}=${v}`);
    }
    args.push("--label", `org.opencontainers.image.title=${app.name}`, context);
    return args;
  }

  async build(config: DeploymentConfig, repoRoot: string, imageRef: string, onLine: (l: string) => void): Promise<void> {
    const r = await this.runner("docker", this.buildArgs(config, repoRoot, imageRef), { cwd: repoRoot, onLine, timeoutMs: 45 * 60_000 });
    if (r.code !== 0) {
      throw new Error(`O build da imagem falhou (docker build, código ${r.code}). Veja as últimas linhas do log.`);
    }
  }

  /** docker login (senha pelo stdin) → push → logout. Devolve o digest publicado. */
  async push(imageRef: string, auth: { registry: string; username: string; password: string }, onLine: (l: string) => void): Promise<string | undefined> {
    const login = await this.runner("docker", ["login", "--username", auth.username, "--password-stdin", auth.registry], { stdin: auth.password, timeoutMs: 60_000 });
    if (login.code !== 0) {
      throw new Error("O docker login no ECR falhou.");
    }
    try {
      const r = await this.runner("docker", ["push", imageRef], { onLine, timeoutMs: 45 * 60_000 });
      if (r.code !== 0) {
        throw new Error(`O envio da imagem ao ECR falhou (docker push, código ${r.code}).`);
      }
      return /digest: (sha256:[0-9a-f]{64})/.exec(r.stdout)?.[1];
    } finally {
      await this.runner("docker", ["logout", auth.registry], { timeoutMs: 30_000 }).catch(() => undefined);
    }
  }
}
