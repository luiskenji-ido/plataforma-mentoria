import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import type { PageProps } from "../App";
import { Alert, Badge, Button, Card, KeyValue, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { get } from "../services/api";
import type { DoctorResponse, InstancesResponse } from "../services/types";

export function OverviewPage({ go, aws }: PageProps) {
  const { draft } = useConfig();
  const doctor = useAsync(() => get<DoctorResponse>("/api/doctor"), []);
  const inst = useAsync(() => get<InstancesResponse>("/api/instances"), [aws?.connected], Boolean(aws?.connected));
  const missing = doctor.data?.tools.filter((t) => t.required && !t.ok) ?? [];

  const steps = [
    { done: Boolean(doctor.data && missing.length === 0), label: "Pré-requisitos instalados (Node, Pulumi, Docker)", page: "settings" as const },
    { done: Boolean(doctor.data?.passphraseSet), label: "Senha do estado do Pulumi definida", page: "settings" as const },
    { done: Boolean(aws?.connected), label: "Conectado à AWS", page: "credentials" as const },
    { done: Boolean(draft?.instance.amiId), label: "EC2 configurada (região, tipo, Ubuntu e disco)", page: "ec2" as const },
    { done: Boolean(draft), label: "Rede, armazenamento e aplicação revisados", page: "storage" as const },
    { done: Boolean(inst.data?.provisioned), label: "Prévia aprovada e infraestrutura provisionada", page: "preview" as const },
  ];

  return (
    <>
      <PageHeader
        title="Visão geral"
        description="Provisione uma EC2 com Ubuntu, instale o Docker e publique a aplicação a partir deste computador. Nada é criado na AWS sem prévia e confirmação explícita."
      />
      {missing.length > 0 && (
        <div className="mb-4">
          <Alert tone="warning" title="Faltam pré-requisitos">
            {missing.map((t) => t.name).join(", ")} — veja Configurações.
          </Alert>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Passo a passo">
          <ol className="space-y-3">
            {steps.map((s, i) => (
              <li key={i} className="flex items-center justify-between gap-3 text-sm">
                <span className="flex items-center gap-2">
                  {s.done ? <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden /> : <Circle className="h-4 w-4 text-slate-400" aria-hidden />}
                  {s.label}
                  <span className="sr-only">{s.done ? "(feito)" : "(pendente)"}</span>
                </span>
                <Button variant="ghost" className="px-2 py-1" onClick={() => go(s.page)} aria-label={`Ir para: ${s.label}`}>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ol>
        </Card>
        <Card title="Configuração atual" actions={<Button variant="secondary" onClick={() => go("ec2")}>Editar</Button>}>
          {draft && (
            <KeyValue
              items={[
                ["Stack", <code key="s">{draft.stackName}</code>],
                ["Região", draft.instance.region],
                ["Instância", `${draft.instance.instanceType} (${draft.instance.architecture})`],
                ["Ubuntu", `${draft.instance.ubuntuVersion} LTS ${draft.instance.amiId ? `· ${draft.instance.amiId}` : "· AMI não resolvida"}`],
                ["Disco", `${draft.rootDisk.sizeGb} GiB ${draft.rootDisk.type} + ${draft.dataVolumes.length} volume(s) de dados`],
                ["Aplicação", `${draft.application.name} · porta ${draft.application.hostPort} → ${draft.application.containerPort}`],
              ]}
            />
          )}
        </Card>
        <Card title="Infraestrutura" actions={<Button variant="secondary" onClick={() => go("instances")}>Instâncias</Button>}>
          {!aws?.connected ? (
            <p className="text-sm text-slate-600 dark:text-slate-400">Conecte-se à AWS para ver o estado.</p>
          ) : inst.loading ? (
            <p className="text-sm">Consultando…</p>
          ) : inst.data?.provisioned ? (
            <KeyValue
              items={[
                ["Estado", <Badge key="h" tone={inst.data.health?.state === "Running" ? "green" : inst.data.health?.state === "Stopped" ? "gray" : "amber"}>{inst.data.health?.state}</Badge>],
                ["Instância", inst.data.instance?.instanceId],
                ["Endereço", inst.data.appUrl ? <a key="u" className="text-indigo-600 underline" href={inst.data.appUrl} target="_blank" rel="noreferrer">{inst.data.appUrl}</a> : "—"],
              ]}
            />
          ) : (
            <p className="text-sm text-slate-600 dark:text-slate-400">Nenhuma infraestrutura provisionada para este stack.</p>
          )}
        </Card>
        <Card title="Segurança">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">
            <li>Painel e API só em localhost, com proteção contra CSRF e DNS rebinding.</li>
            <li>Credenciais da AWS só na memória da API; nunca no navegador nem em disco.</li>
            <li>Segredos da aplicação cifrados no estado do Pulumi e no SSM (SecureString).</li>
            <li>SSH fechado por padrão: acesso administrativo pelo Session Manager.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
