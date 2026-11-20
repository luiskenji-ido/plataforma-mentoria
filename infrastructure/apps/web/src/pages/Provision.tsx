import { Rocket, UploadCloud } from "lucide-react";
import { useState } from "react";
import type { PreviewResult } from "@infra/shared";
import type { PageProps } from "../App";
import { OperationPanel } from "../components/OperationView";
import { Alert, Button, Card, ConfirmDialog, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { useOperation } from "../hooks/useOperation";
import { ApiError, get, post } from "../services/api";
import type { InstancesResponse, OperationStarted } from "../services/types";
import { PreviewSummary } from "./Preview";

export function ProvisionPage({ go, aws }: PageProps) {
  const { saved, dirty } = useConfig();
  const preview = useAsync(() => get<{ preview: PreviewResult | null }>("/api/preview"), []);
  const inst = useAsync(() => get<InstancesResponse>("/api/instances"), [aws?.connected], Boolean(aws?.connected));
  const [confirming, setConfirming] = useState<"provision" | "deploy" | null>(null);
  const [accept, setAccept] = useState(false);
  const [opId, setOpId] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const op = useOperation(opId);
  const p = preview.data?.preview;
  const expired = p ? Date.parse(p.expiresAt) < Date.now() : true;
  const stale = Boolean(p && saved && p.configHash !== saved.configHash);
  const running = op.summary?.status === "running";

  async function provision(typed: string) {
    if (!p) return;
    setBusy(true);
    setError(undefined);
    try {
      const r = await post<OperationStarted>("/api/operations/provision", { configHash: p.configHash, confirmStackName: typed.trim(), acceptCosts: true });
      setOpId(r.operationId);
      setConfirming(null);
      setAccept(false);
      void preview.reload();
    } catch (e) {
      setError((e as ApiError).message);
      setConfirming(null);
    } finally {
      setBusy(false);
    }
  }

  async function deploy() {
    setBusy(true);
    setError(undefined);
    try {
      const r = await post<OperationStarted>("/api/operations/deploy");
      setOpId(r.operationId);
      setConfirming(null);
    } catch (e) {
      setError((e as ApiError).message);
      setConfirming(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Provisionamento e deploy"
        description="Cria a infraestrutura aprovada na prévia, gera a imagem, envia ao ECR, instala o Docker no Ubuntu e inicia a aplicação. Os passos e logs aparecem ao vivo."
      />
      <div className="space-y-4">
        {error && <Alert tone="error" title="Não foi possível começar">{error}</Alert>}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Provisionar infraestrutura" description="Cria recursos cobrados na sua conta da AWS.">
            {!p ? (
              <div className="space-y-3">
                <Alert tone="info">Gere a prévia primeiro: só a configuração exata da prévia pode ser provisionada.</Alert>
                <Button variant="secondary" onClick={() => go("preview")}>Ir para a prévia</Button>
              </div>
            ) : expired || stale || dirty ? (
              <div className="space-y-3">
                <Alert tone="warning">{dirty ? "Há mudanças não salvas." : stale ? "A configuração mudou depois da prévia." : "A prévia expirou (30 min)."} Gere a prévia de novo.</Alert>
                <Button variant="secondary" onClick={() => go("preview")}>Ir para a prévia</Button>
              </div>
            ) : (
              <div className="space-y-3 text-sm">
                <p>
                  Prévia de <b>{p.stackName}</b>: {p.resources.filter((r) => r.op !== "same").length} recurso(s) a criar/alterar, ~US$ {p.cost.monthlyTotalUsd.toFixed(2)}/mês.
                </p>
                <Button variant="warning" icon={<Rocket className="h-4 w-4" />} onClick={() => setConfirming("provision")} disabled={running || !aws?.connected} className="px-5 py-2.5 text-base">
                  Provisionar infraestrutura
                </Button>
              </div>
            )}
          </Card>
          <Card title="Publicar nova versão da aplicação" description="Gera uma imagem nova (tag imutável), envia ao ECR e reinicia o contêiner na EC2 já provisionada.">
            <Button icon={<UploadCloud className="h-4 w-4" />} onClick={() => setConfirming("deploy")} disabled={running || !inst.data?.provisioned || !aws?.connected}>
              Publicar nova versão
            </Button>
            {!inst.data?.provisioned && <p className="mt-2 text-xs text-slate-500">Disponível depois do primeiro provisionamento.</p>}
          </Card>
        </div>
        {p && !expired && !stale && (
          <details className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <summary className="cursor-pointer text-sm font-semibold">Ver a prévia aprovada</summary>
            <div className="mt-4">
              <PreviewSummary preview={p} />
            </div>
          </details>
        )}
        <OperationPanel summary={op.summary} events={op.events} />
        {op.summary?.status === "succeeded" && op.summary.kind !== "preview" && (
          <Alert tone="success" title="Pronto">
            A aplicação respondeu na verificação de saúde. Acompanhe em <button className="underline" onClick={() => go("instances")}>Instâncias e monitoramento</button>.
          </Alert>
        )}
      </div>
      <ConfirmDialog
        open={confirming === "provision"}
        title="Criar recursos cobrados na AWS?"
        confirmLabel="Provisionar agora"
        tone="warning"
        requireText={p?.stackName}
        loading={busy}
        onClose={() => setConfirming(null)}
        onConfirm={(typed) => void provision(typed)}
        extraCheck={{ label: `Entendo que estes recursos são cobrados pela AWS (estimativa ~US$ ${p?.cost.monthlyTotalUsd.toFixed(2)}/mês) até serem destruídos.`, checked: accept, onChange: setAccept }}
      >
        <p>Serão criados na região <b>{p?.summary.region}</b>: {p?.resources.filter((r) => r.op === "create").length} recurso(s), incluindo a EC2 {p?.summary.instanceType} e os volumes EBS.</p>
        <p>Depois a imagem é gerada neste computador e enviada ao ECR.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirming === "deploy"}
        title="Publicar uma nova versão?"
        confirmLabel="Publicar"
        tone="primary"
        loading={busy}
        onClose={() => setConfirming(null)}
        onConfirm={() => void deploy()}
      >
        <p>O contêiner da aplicação será recriado com a nova imagem (alguns segundos fora do ar). Os dados nos volumes são mantidos.</p>
      </ConfirmDialog>
    </>
  );
}
