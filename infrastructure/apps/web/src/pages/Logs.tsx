import { useState } from "react";
import type { OperationEvent, OperationSummary } from "@infra/shared";
import type { PageProps } from "../App";
import { LogViewer, OperationPanel } from "../components/OperationView";
import { Alert, Badge, Button, Card, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useOperation } from "../hooks/useOperation";
import { get } from "../services/api";

const TIPS: [string, string][] = [
  ["Credenciais expiradas", "Credenciais temporárias e sessões SSO expiram: reconecte em Credenciais AWS e rode a operação de novo."],
  ["O Docker não está rodando", "Abra o Docker Desktop e espere \"Engine running\" antes de provisionar ou publicar."],
  ["A instância não aparece no Systems Manager", "Leva alguns minutos após criar. Confira se a sub-rede tem saída para a internet (rota para o Internet Gateway) e se a instância tem IP público."],
  ["O bootstrap não termina", "Abra Instâncias › Log do bootstrap: mostra o apt, a instalação do Docker e a montagem dos volumes."],
  ["A aplicação não responde", "Veja Instâncias › Logs do app. Confira a porta do contêiner, o caminho de saúde e as variáveis de ambiente obrigatórias."],
  ["Falha no meio do provisionamento", "Os recursos criados ficam registrados no estado do Pulumi: corrigir e provisionar de novo só cria o que falta. Use \"Sincronizar estado\" se algo foi mudado à mão no console."],
];

export function LogsPage(_props: PageProps) {
  const list = useAsync(() => get<{ operations: OperationSummary[]; savedLogs: string[] }>("/api/operations"), []);
  const [opId, setOpId] = useState<string>();
  const [saved, setSaved] = useState<{ name: string; events: OperationEvent[] }>();
  const op = useOperation(opId);

  return (
    <>
      <PageHeader title="Logs e diagnóstico" description="Histórico das operações (gravado em .state/logs, sempre com segredos mascarados) e soluções para os problemas comuns." actions={<Button variant="secondary" onClick={() => void list.reload()}>Atualizar</Button>} />
      <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        <div className="space-y-4">
          <Card title="Nesta execução do painel">
            {list.data?.operations.length ? (
              <ul className="space-y-1 text-sm">
                {list.data.operations.map((o) => (
                  <li key={o.id}>
                    <button className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => { setSaved(undefined); setOpId(o.id); }}>
                      <span>{o.kind} · {new Date(o.startedAt).toLocaleTimeString()}</span>
                      <Badge tone={o.status === "succeeded" ? "green" : o.status === "failed" ? "red" : "blue"}>{o.status}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">Nenhuma operação ainda.</p>
            )}
          </Card>
          <Card title="Logs gravados">
            {list.data?.savedLogs.length ? (
              <ul className="max-h-72 space-y-1 overflow-auto text-sm">
                {list.data.savedLogs.map((name) => (
                  <li key={name}>
                    <button className="w-full truncate rounded px-2 py-1 text-left font-mono text-xs hover:bg-slate-100 dark:hover:bg-slate-800" onClick={() => void get<{ events: OperationEvent[] }>(`/api/logs/${name}`).then((r) => { setOpId(undefined); setSaved({ name, events: r.events }); })}>
                      {name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">Sem logs gravados.</p>
            )}
          </Card>
        </div>
        <div className="space-y-4">
          <OperationPanel summary={op.summary} events={op.events} />
          {saved && (
            <Card title={saved.name}>
              <LogViewer events={saved.events} height="h-[32rem]" />
            </Card>
          )}
          <Card title="Problemas comuns">
            <div className="space-y-2">
              {TIPS.map(([t, d]) => (
                <Alert key={t} tone="info" title={t}>
                  {d}
                </Alert>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
