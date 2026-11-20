/** Lê o repositório da aplicação para preencher a tela Docker e Aplicação (Dockerfile, porta, health check, variáveis). */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

export interface DetectedDockerfile {
  path: string;
  exposedPorts: number[];
  envPort?: number;
  hasHealthcheck: boolean;
  buildArgs: string[];
  baseImages: string[];
  stages: number;
  user?: string;
}

export interface ProjectInfo {
  repoRoot: string;
  dockerfiles: DetectedDockerfile[];
  composeFiles: string[];
  envExampleKeys: string[];
  healthEndpoints: string[];
}

const SKIP = new Set([".git", "node_modules", ".venv", ".venv-1", ".venv-2", "infrastructure", "Agent Reports", "uploads", "instance", "__pycache__", "Backup_repository"]);

/** Resolve um caminho relativo dentro do repositório; recusa qualquer coisa que saia dele. */
export function insideRepo(repoRoot: string, relative: string): string {
  const full = path.resolve(repoRoot, relative);
  const rel = path.relative(repoRoot, full);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new Error("Caminho fora do repositório da aplicação.");
  }
  return full;
}

function walk(dir: string, depth: number, found: string[]): void {
  if (depth < 0) {
    return;
  }
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) {
      continue;
    }
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, depth - 1, found);
    } else if (/^(Dockerfile(\..+)?|.+\.Dockerfile|(docker-)?compose(\.[a-z]+)?\.ya?ml)$/i.test(entry.name)) {
      found.push(full);
    }
  }
}

export function parseDockerfile(text: string, relPath: string): DetectedDockerfile {
  const lines = text.replace(/\\\r?\n/g, " ").split(/\r?\n/).map((l) => l.trim());
  const exposed = new Set<number>();
  let envPort: number | undefined;
  const args: string[] = [];
  const bases: string[] = [];
  let user: string | undefined;
  for (const line of lines) {
    const [instr = "", ...rest] = line.split(/\s+/);
    const body = rest.join(" ");
    switch (instr.toUpperCase()) {
      case "EXPOSE":
        for (const p of body.split(/\s+/)) {
          const n = Number(p.split("/")[0]);
          if (Number.isInteger(n) && n > 0) {
            exposed.add(n);
          }
        }
        break;
      case "ENV": {
        const m = /\bPORT[= ](\d{2,5})\b/.exec(body);
        if (m) {
          envPort = Number(m[1]);
        }
        break;
      }
      case "ARG":
        args.push(body.split("=")[0]!.trim());
        break;
      case "FROM":
        bases.push(rest[0] ?? "");
        break;
      case "USER":
        user = body;
        break;
    }
  }
  return {
    path: relPath,
    exposedPorts: [...exposed],
    envPort,
    hasHealthcheck: lines.some((l) => /^HEALTHCHECK\s+(?!NONE)/i.test(l)),
    buildArgs: args,
    baseImages: bases,
    stages: bases.length,
    user,
  };
}

export function detectProject(repoRoot: string): ProjectInfo {
  const files: string[] = [];
  walk(repoRoot, 4, files);
  const rel = (f: string) => path.relative(repoRoot, f).split(path.sep).join("/");
  const dockerfiles = files
    .filter((f) => /dockerfile/i.test(path.basename(f)))
    .map((f) => parseDockerfile(readFileSync(f, "utf8"), rel(f)));
  const composeFiles = files.filter((f) => /compose/i.test(path.basename(f))).map(rel);
  const envKeys = new Set<string>();
  for (const candidate of [".env.example", "deploy/ubuntu/env.exemplo", "env.example"]) {
    const full = path.join(repoRoot, candidate);
    if (existsSync(full) && statSync(full).isFile()) {
      for (const line of readFileSync(full, "utf8").split(/\r?\n/)) {
        const m = /^\s*([A-Z_][A-Z0-9_]*)\s*=/.exec(line);
        if (m) {
          envKeys.add(m[1]!);
        }
      }
    }
  }
  const health: string[] = [];
  for (const candidate of ["app.py", "saude.py"]) {
    const full = path.join(repoRoot, candidate);
    if (existsSync(full)) {
      const text = readFileSync(full, "utf8");
      for (const m of text.matchAll(/route\(\s*['"](\/(?:healthz|readyz|health|saude)[^'"]*)['"]/g)) {
        health.push(m[1]!);
      }
    }
  }
  return { repoRoot, dockerfiles, composeFiles, envExampleKeys: [...envKeys].sort(), healthEndpoints: [...new Set(health)] };
}
