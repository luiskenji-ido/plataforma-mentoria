import { CheckCircle2, Circle, Loader2, MinusCircle, XCircle } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import type { OperationEvent, OperationSummary, StepStatus } from "@infra/shared";
import { Alert, Badge, Card, cn } from "./ui";

const icons: Record<StepStatus, ReactNode> = {
  pending: <Circle className="h-4 w-4 text-slate-400" aria-hidden />,
  running: <Loader2 className="h-4 w-4 animate-spin text-indigo-500" aria-hidden />,
  done: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />,
  failed: <XCircle className="h-4 w-4 text-red-600" aria-hidden />,
  skipped: <MinusCircle className="h-4 w-4 text-slate-400" aria-hidden />,
};
const statusText: Record<StepStatus, string> = { pending: "aguardando", running: "em andamento", done: "concluído", failed: "falhou", skipped: "não executado" };

export function StepList({ summary }: { summary: OperationSummary }) {
  return (
    <ol className="space-y-2" aria-label="Etapas">
      {summary.steps.map((s) => (
        <li key={s.key} className="flex items-start gap-3 text-sm">
          <span className="mt-0.5">{icons[s.status]}</span>
          <div className="min-w-0">
            <p className={cn("font-medium", s.status === "pending" && "text-slate-500")}>
              {s.label} <span className="sr-only">({statusText[s.status]})</span>
            </p>
            {s.detail && <p className={cn("break-words text-xs", s.status === "failed" ? "text-red-700 dark:text-red-400" : "text-slate-600 dark:text-slate-400")}>{s.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function LogViewer({ events, height = "h-96" }: { events: OperationEvent[]; height?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [events]);
  return (
    <div
      ref={ref}
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
      }}
      className={cn("overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200", height)}
      role="log"
      aria-live="polite"
    >
      {events.length === 0 && <p className="text-slate-500">Sem eventos ainda.</p>}
      {events.map((e) => (
        <div key={e.seq} className={cn("whitespace-pre-wrap break-words", e.level === "error" && "text-red-400", e.level === "warn" && "text-amber-300", e.type === "step" && "text-sky-300", e.type === "result" && "font-bold")}>
          <span className="text-slate-500">{e.time.slice(11, 19)} </span>
          {e.message}
        </div>
      ))}
    </div>
  );
}

const kindLabel: Record<string, string> = { preview: "Prévia", provision: "Provisionamento", deploy: "Publicação", refresh: "Atualização do estado", destroy: "Destruição" };

export function OperationPanel({ summary, events }: { summary?: OperationSummary; events: OperationEvent[] }) {
  if (!summary) return null;
  const tone = summary.status === "succeeded" ? "green" : summary.status === "failed" ? "red" : "blue";
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          {kindLabel[summary.kind] ?? summary.kind} · {summary.stackName}
          <Badge tone={tone}>{summary.status === "running" ? "em andamento" : summary.status === "succeeded" ? "concluído" : "falhou"}</Badge>
        </span>
      }
      description={`Início ${new Date(summary.startedAt).toLocaleString()}${summary.finishedAt ? ` · fim ${new Date(summary.finishedAt).toLocaleString()}` : ""}`}
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(260px,1fr)_2fr]">
        <StepList summary={summary} />
        <LogViewer events={events} />
      </div>
      {summary.status === "failed" && (
        <div className="mt-4">
          <Alert tone="error" title="A operação falhou">
            <p>{summary.error}</p>
            <p className="mt-1">
              Os recursos já criados continuam na conta (o Pulumi registrou tudo no estado). Corrija o problema e rode de novo: o Pulumi só cria o que
              falta. Para remover tudo, use Destruir infraestrutura em Instâncias.
            </p>
          </Alert>
        </div>
      )}
    </Card>
  );
}
