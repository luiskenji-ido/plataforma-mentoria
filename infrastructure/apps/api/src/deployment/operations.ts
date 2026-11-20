/**
 * Operações longas (prévia, provisionamento, publicação, refresh, destroy): uma por vez em cada stack,
 * com passos e eventos transmitidos ao vivo (SSE) e gravados em .state/logs/<id>.jsonl (sempre mascarados).
 */
import { randomUUID } from "node:crypto";
import { EventEmitter } from "node:events";
import { appendFile, mkdir, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { OperationEvent, OperationKind, OperationSummary, StepStatus } from "@infra/shared";
import { redact, safeErrorMessage } from "../services/redact";

export class BusyError extends Error {
  readonly statusCode = 409;
  constructor(stack: string, kind: string) {
    super(`Já há uma operação (${kind}) em andamento no stack ${stack}. Espere terminar.`);
  }
}

export class Operation {
  readonly id = randomUUID();
  readonly events: OperationEvent[] = [];
  readonly emitter = new EventEmitter();
  readonly summary: OperationSummary;
  private seq = 0;

  constructor(kind: OperationKind, stackName: string, steps: { key: string; label: string }[], private readonly logFile: string) {
    this.summary = {
      id: this.id,
      kind,
      stackName,
      status: "running",
      startedAt: new Date().toISOString(),
      steps: steps.map((s) => ({ ...s, status: "pending" as StepStatus })),
    };
    this.emitter.setMaxListeners(50);
  }

  private push(event: Omit<OperationEvent, "seq" | "time">): void {
    const full: OperationEvent = { ...event, message: redact(event.message), seq: ++this.seq, time: new Date().toISOString() };
    this.events.push(full);
    if (this.events.length > 5000) {
      this.events.splice(0, this.events.length - 5000);
    }
    this.emitter.emit("event", full);
    appendFile(this.logFile, `${JSON.stringify(full)}\n`, { encoding: "utf8", mode: 0o600 }).catch(() => undefined);
  }

  log(message: string, level: OperationEvent["level"] = "info"): void {
    for (const line of message.split(/\r?\n/)) {
      if (line.trim()) {
        this.push({ type: "log", message: line, level });
      }
    }
  }

  step(key: string, status: StepStatus, detail?: string): void {
    const step = this.summary.steps.find((s) => s.key === key);
    if (step) {
      step.status = status;
      step.detail = detail ? redact(detail) : step.detail;
    }
    this.push({ type: "step", step: key, status, message: `${step?.label ?? key}${detail ? `: ${detail}` : ""}`, level: status === "failed" ? "error" : "info" });
  }

  /** Executa um passo: marca running → done (ou failed, relançando o erro). */
  async run<T>(key: string, fn: () => Promise<T>, doneDetail?: (r: T) => string | undefined): Promise<T> {
    this.step(key, "running");
    try {
      const result = await fn();
      this.step(key, "done", doneDetail?.(result));
      return result;
    } catch (error) {
      this.step(key, "failed", safeErrorMessage(error));
      throw error;
    }
  }

  finish(error?: unknown): void {
    this.summary.finishedAt = new Date().toISOString();
    this.summary.status = error ? "failed" : "succeeded";
    if (error) {
      this.summary.error = safeErrorMessage(error);
      for (const s of this.summary.steps) {
        if (s.status === "pending") {
          s.status = "skipped";
        }
      }
    }
    this.push({ type: "result", message: error ? `Falhou: ${this.summary.error}` : "Concluído com sucesso.", level: error ? "error" : "info" });
    this.emitter.emit("end");
  }
}

export class OperationManager {
  private readonly operations = new Map<string, Operation>();
  private readonly running = new Map<string, Operation>();
  private readonly logDir: string;

  constructor(stateDir: string) {
    this.logDir = path.join(stateDir, "logs");
  }

  /** Começa uma operação em segundo plano; recusa se o stack já tiver outra em andamento. */
  async start(
    kind: OperationKind,
    stackName: string,
    steps: { key: string; label: string }[],
    work: (op: Operation) => Promise<void>,
  ): Promise<Operation> {
    const busy = this.running.get(stackName);
    if (busy) {
      throw new BusyError(stackName, busy.summary.kind);
    }
    await mkdir(this.logDir, { recursive: true });
    const op = new Operation(kind, stackName, steps, path.join(this.logDir, `${new Date().toISOString().replace(/[:.]/g, "-")}_${kind}.jsonl`));
    this.operations.set(op.id, op);
    this.running.set(stackName, op);
    void (async () => {
      try {
        await work(op);
        op.finish();
      } catch (error) {
        op.log(safeErrorMessage(error), "error");
        op.finish(error);
      } finally {
        this.running.delete(stackName);
      }
    })();
    return op;
  }

  get(id: string): Operation | undefined {
    return this.operations.get(id);
  }

  isBusy(stackName: string): boolean {
    return this.running.has(stackName);
  }

  list(): OperationSummary[] {
    return [...this.operations.values()].map((o) => o.summary).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  }

  /** Logs gravados de operações anteriores (inclusive de outras execuções do painel). */
  async savedLogs(): Promise<string[]> {
    try {
      return (await readdir(this.logDir)).filter((f) => f.endsWith(".jsonl")).sort().reverse().slice(0, 50);
    } catch {
      return [];
    }
  }

  async readSavedLog(name: string): Promise<OperationEvent[]> {
    if (!/^[\w.-]+\.jsonl$/.test(name)) {
      throw new Error("Nome de log inválido.");
    }
    const text = await readFile(path.join(this.logDir, name), "utf8");
    return text.split("\n").filter(Boolean).map((l) => JSON.parse(l) as OperationEvent);
  }
}
