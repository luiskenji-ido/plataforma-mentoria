/**
 * Execução de programas externos (docker, git, pulumi, aws) SEM shell: o programa e cada argumento vão separados,
 * então nada digitado no painel vira comando. Segredos só entram pelo stdin; a saída passa pelo mascarador.
 */
import { spawn } from "node:child_process";
import { redact } from "./redact";

export interface RunOptions {
  cwd?: string;
  stdin?: string;
  env?: Record<string, string>;
  timeoutMs?: number;
  onLine?: (line: string) => void;
}

export interface RunResult {
  code: number;
  stdout: string;
  stderr: string;
}

export type Runner = (command: string, args: string[], options?: RunOptions) => Promise<RunResult>;

const ARG_OK = /^[^\0\r\n]*$/;

export const runProcess: Runner = (command, args, options = {}) =>
  new Promise((resolve, reject) => {
    if (!/^[a-z0-9._-]+$/i.test(command) || !args.every((a) => ARG_OK.test(a))) {
      reject(new Error("Comando ou argumento inválido."));
      return;
    }
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...options.env },
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let pending = "";
    const timer = options.timeoutMs
      ? setTimeout(() => {
          child.kill("SIGTERM");
        }, options.timeoutMs)
      : undefined;
    const feed = (chunk: Buffer, target: "out" | "err") => {
      const text = chunk.toString("utf8");
      if (target === "out") {
        stdout += text;
      } else {
        stderr += text;
      }
      if (options.onLine) {
        pending += text;
        const lines = pending.split(/\r?\n|\r/);
        pending = lines.pop() ?? "";
        for (const line of lines) {
          if (line.trim()) {
            options.onLine(redact(line));
          }
        }
      }
    };
    child.stdout.on("data", (c: Buffer) => feed(c, "out"));
    child.stderr.on("data", (c: Buffer) => feed(c, "err"));
    child.on("error", (error: NodeJS.ErrnoException) => {
      clearTimeout(timer);
      reject(error.code === "ENOENT" ? new Error(`Programa não encontrado: ${command}. Veja o menu Configurações › Pré-requisitos.`) : error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (options.onLine && pending.trim()) {
        options.onLine(redact(pending));
      }
      resolve({ code: code ?? -1, stdout: redact(stdout), stderr: redact(stderr) });
    });
    if (options.stdin !== undefined) {
      child.stdin.end(options.stdin);
    } else {
      child.stdin.end();
    }
  });
