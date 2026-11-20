import { Bomb, FileText, Play, RefreshCw, RotateCcw, Square, UploadCloud } from "lucide-react";
import { useState } from "react";
import type { HealthState } from "@infra/shared";
import type { PageProps } from "../App";
import { OperationPanel } from "../components/OperationView";
import { Alert, Badge, Button, Card, ConfirmDialog, KeyValue, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { useOperation } from "../hooks/useOperation";
import { ApiError, get, post } from "../services/api";
import type { InstancesResponse, OperationStarted } from "../services/types";

const healthTone: Record<HealthState, "green" | "amber" | "gray" | "blue"> = { Running: "green", Degraded: "amber", Stopped: "gray", Unknown: "blue" };
const healthText: Record<HealthState, string> = { Running: "Rodando", Degraded: "Degradado", Stopped: "Parado", Unknown: "Desconhecido" };

function Sparkline({ points }: { points: { time: string; value: number }[] }) {
  if (points.length < 2) return <p className="text-sm text-slate-500">Sem dados de CPU ainda (o CloudWatch publica a cada 5 minutos).</p>;
  const w = 480;
  const h = 80;
  const max = Math.max(10, ...points.map((p) => p.value));
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${((i / (points.length - 1)) * w).toFixed(1)},${(h - (p.value / max) * h).toFixed(1)}`).join(" ");
  const lastPoint = points[points.length - 1];
  return (
    <figure>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-20 w-full text-indigo-500" role="img" aria-label={`CPU nas últimas horas; agora ${lastPoint?.value}%`}>
        <path d={d} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <figcaption className="text-xs text-slate-500">CPU média (5 min) · máx. {Math.max(...points.map((p) => p.value))}% · agora {lastPoint?.value}%</figcaption>
    </figure>
  );
}

export function InstancesPage({ aws }: PageProps) {
  const { saved } = useConfig();
  const connected = Boolean(aws?.connected);
  const inst = useAsync(() => get<InstancesResponse>("/api/instances"), [connected], connected);
  const metrics = useAsync(() => get<{ cpu: { time: string; value: number }[] }>("/api/instances/metrics"), [connected, inst.data?.instance?.instanceId], connected && Boolean(inst.data?.provisioned));
  const [logs, setLogs] = useState<{ title: string; text: string }>();
  const [logsBusy, setLogsBusy] = useState(false);
  const [confirm, setConfirm] = useState<"start" | "stop" | "reboot" | "destroy" | "deploy" | "refresh" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [opId, setOpId] = useState<string>();
  const op = useOperation(opId);
  const i = inst.data;
  const stack = saved?.config.stackName ?? "";

  async function action(kind: "start" | "stop" | "reboot", typed: string) {
    setBusy(true);
    setError(undefined);
    try {
      await post("/api/instances/action", { action: kind, confirmInstanceId: typed.trim() });
      setConfirm(null);
      setTimeout(() => void inst.reload(), 4000);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function operation(path: string, body?: unknown) {
    setBusy(true);
    setError(undefined);
    try {
      const r = await post<OperationStarted>(path, body);
      setOpId(r.operationId);
      setConfirm(null);
    } catch (e) {
      setError((e as ApiError).message);
      setConfirm(null);
    } finally {
      setBusy(false);
    }
  }

  async function showLogs(kind: "appLogs" | "bootstrapLog") {
    setLogsBusy(true);
    try {
      const r = await get<{ status: string; output: string }>(`/api/instances/logs?kind=${kind}`);
      setLogs({ title: kind === "appLogs" ? "Logs da aplicação (últimas 200 linhas)" : "Log do bootstrap (cloud-init)", text: r.output || "(vazio)" });
    } catch (e) {
      setLogs({ title: "Erro", text: (e as Error).message });
    } finally {
      setLogsBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Instâncias e monitoramento"
        description="Situação real (EC2, Systems Manager, contêineres e HTTP). Parar a EC2 não apaga nada; destruir remove a infraestrutura."
        actions={
          <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} onClick={() => { void inst.reload(); void metrics.reload(); }} loading={inst.loading} disabled={!connected}>
            Atualizar status
          </Button>
        }
      />
      <div className="space-y-4">
        {!connected && <Alert tone="warning">Conecte-se à AWS para consultar as instâncias.</Alert>}
        {inst.error && <Alert tone="error">{inst.error}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        {i && !i.provisioned && <Alert tone="info">Nenhuma instância provisionada no stack {i.stackName}.</Alert>}
        {i?.provisioned && (
          <>
            <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
              <Card
                title={<span className="flex items-center gap-2">{i.instance?.name ?? "Instância"} {i.health && <Badge tone={healthTone[i.health.state]}>{healthText[i.health.state]}</Badge>}</span>}
                description={i.health?.reason}
              >
                <KeyValue
                  items={[
                    ["Stack", <code key="s">{i.stackName}</code>],
                    ["Região", i.region],
                    ["ID da instância", <code key="id">{i.instance?.instanceId}</code>],
                    ["Tipo", i.instance?.instanceType],
                    ["Estado da EC2", i.instance?.state],
                    ["Verificações da AWS", i.instance?.systemStatus ? `sistema ${i.instance.systemStatus} · instância ${i.instance.instanceStatus}` : "—"],
                    ["IP público", i.instance?.publicIp ?? "nenhum (muda ao ligar de novo)"],
                    ["IP privado", i.instance?.privateIp],
                    ["Ubuntu", i.ubuntu ? `${i.ubuntu} LTS` : "—"],
                    ["Systems Manager", i.ssmOnline === undefined ? "—" : i.ssmOnline ? "online" : "offline"],
                    ["Docker", i.docker ? `${i.docker.active ? "ativo" : "inativo"} ${i.docker.version ?? ""} ${i.docker.bootstrapDone ? "" : "(bootstrap em andamento)"}` : "—"],
                    ["Imagem em execução", i.image ? <code key="img" className="text-xs">{i.image}</code> : "—"],
                    ["Contêineres", i.containers?.length ? i.containers.map((c) => `${c.name}: ${c.status}`).join(" · ") : "—"],
                    ["Aplicação", i.appUrl ? <a key="url" className="text-indigo-600 underline" href={i.appUrl} target="_blank" rel="noreferrer">{i.appUrl}</a> : "não exposta"],
                    ["Verificação HTTP", i.http ? (i.http.ok ? `HTTP ${i.http.status} em ${i.http.ms} ms` : `falhou (${i.http.error ?? i.http.status})`) : "—"],
                  ]}
                />
              </Card>
              <div className="space-y-4">
                <Card title="Ações da instância">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" icon={<Play className="h-4 w-4" />} onClick={() => setConfirm("start")} disabled={i.instance?.state !== "stopped"}>Ligar</Button>
                    <Button variant="secondary" icon={<Square className="h-4 w-4" />} onClick={() => setConfirm("stop")} disabled={i.instance?.state !== "running"}>Parar</Button>
                    <Button variant="secondary" icon={<RotateCcw className="h-4 w-4" />} onClick={() => setConfirm("reboot")} disabled={i.instance?.state !== "running"}>Reiniciar</Button>
                    <Button variant="secondary" icon={<UploadCloud className="h-4 w-4" />} onClick={() => setConfirm("deploy")} disabled={i.instance?.state !== "running"}>Publicar de novo</Button>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">Parar a EC2 interrompe a cobrança da instância, mas os volumes EBS, o ECR e eventuais IPs fixos continuam cobrando.</p>
                </Card>
                <Card title="CPU (CloudWatch)">{metrics.data && <Sparkline points={metrics.data.cpu} />}</Card>
                <Card title="Logs">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" icon={<FileText className="h-4 w-4" />} loading={logsBusy} onClick={() => void showLogs("appLogs")} disabled={!i.ssmOnline}>Logs do app</Button>
                    <Button variant="secondary" icon={<FileText className="h-4 w-4" />} loading={logsBusy} onClick={() => void showLogs("bootstrapLog")} disabled={!i.ssmOnline}>Log do bootstrap</Button>
                  </div>
                </Card>
              </div>
            </div>
            {logs && (
              <Card title={logs.title} actions={<Button variant="ghost" onClick={() => setLogs(undefined)}>Fechar</Button>}>
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-200">{logs.text}</pre>
              </Card>
            )}
            <Card title="Stack do Pulumi" description="Saídas do stack e operações de infraestrutura.">
              <div className="mb-4 grid gap-1 font-mono text-xs">
                {Object.entries(i.outputs ?? {}).map(([k, v]) => (
                  <div key={k} className="break-all">
                    <span className="text-slate-500">{k}:</span> {typeof v === "string" ? v : JSON.stringify(v)}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} onClick={() => setConfirm("refresh")}>Sincronizar estado (refresh)</Button>
                <Button variant="danger" icon={<Bomb className="h-4 w-4" />} onClick={() => setConfirm("destroy")}>Destruir infraestrutura</Button>
              </div>
            </Card>
          </>
        )}
        <OperationPanel summary={op.summary} events={op.events} />
      </div>

      {(["start", "stop", "reboot"] as const).map((k) => (
        <ConfirmDialog
          key={k}
          open={confirm === k}
          title={{ start: "Ligar a instância?", stop: "Parar a instância?", reboot: "Reiniciar a instância?" }[k]}
          confirmLabel={{ start: "Ligar", stop: "Parar", reboot: "Reiniciar" }[k]}
          tone={k === "start" ? "primary" : "warning"}
          requireText={i?.instance?.instanceId}
          loading={busy}
          onClose={() => setConfirm(null)}
          onConfirm={(typed) => void action(k, typed)}
        >
          {k === "stop" && <p>A aplicação fica fora do ar. Nada é apagado; o IP público automático muda ao ligar de novo.</p>}
          {k === "reboot" && <p>A aplicação fica alguns minutos fora do ar e volta sozinha (docker compose com reinício automático).</p>}
          {k === "start" && <p>A instância volta a ser cobrada por hora.</p>}
        </ConfirmDialog>
      ))}
      <ConfirmDialog open={confirm === "deploy"} title="Publicar uma nova versão?" confirmLabel="Publicar" tone="primary" loading={busy} onClose={() => setConfirm(null)} onConfirm={() => void operation("/api/operations/deploy")}>
        <p>Gera uma imagem nova com o código atual deste computador e reinicia o contêiner.</p>
      </ConfirmDialog>
      <ConfirmDialog open={confirm === "refresh"} title="Sincronizar o estado com a AWS?" confirmLabel="Sincronizar" tone="primary" loading={busy} onClose={() => setConfirm(null)} onConfirm={() => void operation("/api/operations/refresh")}>
        <p>O Pulumi lê o estado real dos recursos na AWS e atualiza o estado local. Nada é criado nem apagado.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirm === "destroy"}
        title={`Destruir a infraestrutura do stack ${stack}?`}
        confirmLabel="Destruir permanentemente"
        tone="danger"
        requireText={`destruir ${stack}`}
        loading={busy}
        onClose={() => setConfirm(null)}
        onConfirm={(typed) => void operation("/api/operations/destroy", { confirmStackName: stack, confirmPhrase: typed.trim() })}
      >
        <Alert tone="error" title="Não dá para desfazer">
          Remove a EC2 {i?.instance?.instanceId}, o disco raiz, a rede criada, o Security Group, o papel IAM, os parâmetros do SSM e o repositório ECR (com as imagens).
        </Alert>
        <p>
          Volumes de dados:{" "}
          {saved?.config.dataVolumes.map((v) => `${v.name} (${v.deleteOnDestroy ? "APAGADO" : "preservado"})`).join(", ") || "nenhum"}. Volumes preservados continuam na conta (e cobrando) até você apagá-los.
        </p>
      </ConfirmDialog>
    </>
  );
}

