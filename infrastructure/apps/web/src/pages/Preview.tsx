import { ScanEye } from "lucide-react";
import { useEffect, useState } from "react";
import type { PreviewResult } from "@infra/shared";
import type { PageProps } from "../App";
import { OperationPanel } from "../components/OperationView";
import { Alert, Badge, Button, Card, KeyValue, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { useOperation } from "../hooks/useOperation";
import { ApiError, get, post } from "../services/api";
import type { OperationStarted } from "../services/types";
import { CostTable } from "./Ec2Config";

const opLabel: Record<string, { text: string; tone: "green" | "amber" | "red" | "blue" | "gray" }> = {
  create: { text: "criar", tone: "green" },
  update: { text: "alterar", tone: "amber" },
  replace: { text: "substituir", tone: "red" },
  "create-replacement": { text: "substituir", tone: "red" },
  delete: { text: "apagar", tone: "red" },
  same: { text: "sem mudança", tone: "gray" },
};

export function PreviewSummary({ preview }: { preview: PreviewResult }) {
  const s = preview.summary;
  const changes = preview.resources.filter((r) => r.op !== "same");
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Resumo" description={`Prévia gerada às ${new Date(preview.createdAt).toLocaleTimeString()} · vale até ${new Date(preview.expiresAt).toLocaleTimeString()}`}>
        <KeyValue
          items={[
            ["Região", s.region],
            ["Instância", s.instanceType],
            ["Ubuntu", <span key="u">{s.ubuntu}{s.amiId && <code className="ml-1 text-xs">{s.amiId}</code>}</span>],
            ["Disco raiz", s.rootDisk],
            ["Volumes de dados", s.dataVolumes.length ? <ul key="v" className="list-disc pl-4">{s.dataVolumes.map((v) => <li key={v}>{v}</li>)}</ul> : "nenhum"],
            ["Rede", s.network],
            ["Portas abertas", s.openPorts.length ? <ul key="p" className="list-disc pl-4">{s.openPorts.map((p) => <li key={p}>{p}</li>)}</ul> : "nenhuma"],
            ["Imagem Docker", s.image],
          ]}
        />
      </Card>
      <Card title="Custos estimados">
        <CostTable cost={preview.cost} />
      </Card>
      <Card title={`Recursos (${changes.length} mudança(s))`} className="lg:col-span-2" description={Object.entries(preview.changeSummary).map(([k, v]) => `${opLabel[k]?.text ?? k}: ${v}`).join(" · ")}>
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-1">Ação</th>
                <th className="py-1">Tipo</th>
                <th className="py-1">Nome</th>
              </tr>
            </thead>
            <tbody>
              {preview.resources.map((r, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1">
                    <Badge tone={opLabel[r.op]?.tone ?? "gray"}>{opLabel[r.op]?.text ?? r.op}</Badge>
                  </td>
                  <td className="py-1 font-mono text-xs">{r.type}</td>
                  <td className="py-1">{r.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export function PreviewPage({ go, aws }: PageProps) {
  const { dirty } = useConfig();
  const last = useAsync(() => get<{ preview: PreviewResult | null }>("/api/preview"), []);
  const [opId, setOpId] = useState<string>();
  const [error, setError] = useState<string>();
  const [starting, setStarting] = useState(false);
  const op = useOperation(opId);
  const running = op.summary?.status === "running";

  // Quando a prévia termina, busca o resultado novo
  const finished = op.summary?.status === "succeeded" ? op.summary.finishedAt : undefined;
  useEffect(() => {
    if (finished) void last.reload();
  }, [finished]); // eslint-disable-line react-hooks/exhaustive-deps

  async function start() {
    setStarting(true);
    setError(undefined);
    try {
      const r = await post<OperationStarted>("/api/operations/preview");
      setOpId(r.operationId);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Prévia da infraestrutura"
        description="Mostra exatamente o que o Pulumi criaria, alteraria ou apagaria e quanto deve custar. A prévia não cria nada."
        actions={
          <Button icon={<ScanEye className="h-4 w-4" />} onClick={() => void start()} loading={starting || running} disabled={!aws?.connected || dirty} className="px-5 py-2.5 text-base">
            Prévia da infraestrutura
          </Button>
        }
      />
      <div className="space-y-4">
        {!aws?.connected && <Alert tone="warning">Conecte-se à AWS (menu Credenciais AWS) para gerar a prévia.</Alert>}
        {dirty && <Alert tone="warning">Há mudanças não salvas na configuração: salve antes de gerar a prévia.</Alert>}
        {error && <Alert tone="error" title="Não foi possível gerar a prévia">{error}</Alert>}
        <OperationPanel summary={op.summary} events={op.events} />
        {last.data?.preview && (
          <>
            <PreviewSummary preview={last.data.preview} />
            <div className="flex justify-end">
              <Button onClick={() => go("provision")}>Revisar e provisionar →</Button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
