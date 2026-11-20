import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
/** Pasta infrastructure/ (funciona tanto em src/ com tsx quanto em dist/ depois do build). */
export const INFRA_ROOT = path.resolve(here, "..", "..", "..");

export interface Settings {
  host: string;
  port: number;
  /** Porta em que o navegador abre o painel (3000). Em desenvolvimento a API fica em 3001 atrás do Vite. */
  publicPort: number;
  stateDir: string;
  repoRoot: string;
  webDist: string;
  allowNetwork: boolean;
}

const LOOPBACK = new Set(["127.0.0.1", "::1", "localhost"]);

export function loadSettings(env: NodeJS.ProcessEnv = process.env): Settings {
  const dev = env.NODE_ENV !== "production" && env.INFRA_MODE !== "production";
  const port = Number(env.INFRA_API_PORT ?? (dev ? 3001 : 3000));
  const publicPort = Number(env.INFRA_PUBLIC_PORT ?? 3000);
  const host = env.INFRA_HOST ?? "127.0.0.1";
  const allowNetwork = env.INFRA_ALLOW_NETWORK === "1";
  if (!LOOPBACK.has(host) && !allowNetwork) {
    throw new Error(`INFRA_HOST=${host} exporia o painel na rede. Use 127.0.0.1 (padrão) ou, sabendo do risco, INFRA_ALLOW_NETWORK=1.`);
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("INFRA_API_PORT inválida.");
  }
  const repoRoot = path.resolve(env.APP_REPO_ROOT ?? path.join(INFRA_ROOT, ".."));
  if (!existsSync(repoRoot)) {
    throw new Error(`APP_REPO_ROOT não existe: ${repoRoot}`);
  }
  return {
    host,
    port,
    publicPort,
    stateDir: path.resolve(env.INFRA_STATE_DIR ?? path.join(INFRA_ROOT, ".state")),
    repoRoot,
    webDist: path.join(INFRA_ROOT, "apps", "web", "dist"),
    allowNetwork,
  };
}

export function allowedHosts(s: Pick<Settings, "port" | "publicPort">): Set<string> {
  const hosts = new Set<string>();
  for (const p of new Set([s.port, s.publicPort])) {
    for (const h of ["localhost", "127.0.0.1", "[::1]"]) {
      hosts.add(`${h}:${p}`);
    }
  }
  return hosts;
}

export function allowedOrigins(s: Pick<Settings, "port" | "publicPort">): Set<string> {
  return new Set([...allowedHosts(s)].map((h) => `http://${h}`));
}
