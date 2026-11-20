import { KeyRound, Plus, Trash2 } from "lucide-react";
import type { EnvVar } from "@infra/shared";
import type { PageProps } from "../App";
import { SaveBar } from "../components/SaveBar";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Select, Switch } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { get } from "../services/api";
import type { ProjectInfo } from "../services/types";

export function DockerAppPage(_props: PageProps) {
  const { draft, update, issues } = useConfig();
  const project = useAsync(() => get<ProjectInfo>("/api/project"), []);
  if (!draft) return null;
  const app = draft.application;
  const setApp = (patch: Partial<typeof app>) => update((c) => ({ ...c, application: { ...c.application, ...patch } }));
  const setEnv = (i: number, patch: Partial<EnvVar>) => setApp({ env: app.env.map((e, j) => (j === i ? { ...e, ...patch } : e)) });
  const df = project.data?.dockerfiles.find((d) => d.path === app.dockerfile);

  return (
    <>
      <PageHeader title="Docker e aplicação" description="Como a imagem é gerada aqui e executada na EC2 (docker compose, reinício automático e volumes persistentes)." />
      <div className="space-y-4">
        <Card title="Projeto detectado" description={project.data ? <code className="text-xs">{project.data.repoRoot}</code> : undefined}>
          {project.error && <Alert tone="error">{project.error}</Alert>}
          {project.data && (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                {project.data.dockerfiles.map((d) => (
                  <Badge key={d.path} tone={d.path === app.dockerfile ? "blue" : "gray"}>
                    {d.path} · {d.baseImages.join(" → ")} · porta {d.envPort ?? d.exposedPorts.join("/")}
                  </Badge>
                ))}
                {project.data.dockerfiles.length === 0 && <Badge tone="red">Nenhum Dockerfile encontrado</Badge>}
              </div>
              <p>
                Docker Compose: {project.data.composeFiles.length ? project.data.composeFiles.join(", ") : "nenhum (o painel gera o compose da EC2)"} · Endpoints de saúde:{" "}
                {project.data.healthEndpoints.length ? project.data.healthEndpoints.join(", ") : "nenhum dedicado (usa a página inicial)"}
              </p>
              {df && !df.hasHealthcheck && <Alert tone="info">O Dockerfile não tem HEALTHCHECK: o painel define um no docker compose da EC2 usando o caminho de saúde abaixo.</Alert>}
              {df && df.exposedPorts.length > 0 && !df.exposedPorts.includes(app.containerPort) && (
                <Alert tone="warning">O Dockerfile expõe {df.exposedPorts.join(", ")}, mas a porta do contêiner configurada é {app.containerPort}.</Alert>
              )}
            </div>
          )}
        </Card>

        <Card title="Imagem e execução">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Nome da aplicação" htmlFor="appname" error={issues["application.name"]} help="Nomeia o projeto compose, o repositório ECR e os parâmetros.">
              <Input id="appname" value={app.name} onChange={(e) => setApp({ name: e.target.value.toLowerCase() })} />
            </Field>
            <Field label="Dockerfile" htmlFor="dockerfile" error={issues["application.dockerfile"]} help="Relativo à raiz do repositório.">
              <Select id="dockerfile" value={app.dockerfile} onChange={(e) => setApp({ dockerfile: e.target.value })}>
                {[...new Set([app.dockerfile, ...(project.data?.dockerfiles.map((d) => d.path) ?? [])])].map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Contexto do build" htmlFor="ctx" error={issues["application.buildContext"]} help="Pasta enviada ao docker build (relativa à raiz).">
              <Input id="ctx" value={app.buildContext} onChange={(e) => setApp({ buildContext: e.target.value })} />
            </Field>
            <Field label="Porta do contêiner" htmlFor="cport" error={issues["application.containerPort"]}>
              <Input id="cport" type="number" value={app.containerPort} onChange={(e) => setApp({ containerPort: Number(e.target.value) })} />
            </Field>
            <Field label="Porta na EC2 (host)" htmlFor="hport" error={issues["application.hostPort"]} help="80 = acesso por http://IP sem porta.">
              <Input id="hport" type="number" value={app.hostPort} onChange={(e) => setApp({ hostPort: Number(e.target.value) })} />
            </Field>
            <Field label="Caminho de saúde (HTTP)" htmlFor="hpath" error={issues["application.healthPath"]} help="Usado no HEALTHCHECK e na verificação do painel.">
              <Input id="hpath" value={app.healthPath} onChange={(e) => setApp({ healthPath: e.target.value })} />
            </Field>
            <Field label="Política de reinício" htmlFor="restart">
              <Select id="restart" value={app.restartPolicy} onChange={(e) => setApp({ restartPolicy: e.target.value as typeof app.restartPolicy })}>
                <option value="unless-stopped">unless-stopped (recomendado)</option>
                <option value="always">always</option>
                <option value="on-failure">on-failure</option>
              </Select>
            </Field>
            <Field label="Argumentos do build (CHAVE=valor, um por linha)" htmlFor="bargs" error={issues["application.buildArgs"]}>
              <textarea
                id="bargs"
                className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm dark:border-slate-700 dark:bg-slate-950"
                rows={2}
                defaultValue={Object.entries(app.buildArgs).map(([k, v]) => `${k}=${v}`).join("\n")}
                onBlur={(e) => setApp({ buildArgs: Object.fromEntries(e.target.value.split("\n").map((l) => l.trim()).filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)])) })}
              />
            </Field>
          </div>
        </Card>

        <Card
          title="Variáveis de ambiente"
          description="SECRET_KEY e DATABASE_URL são geradas pelo painel. Valores secretos vão cifrados para o estado do Pulumi e para o SSM (SecureString) e nunca voltam para a tela."
          actions={
            <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setApp({ env: [...app.env, { key: "", value: "", secret: false }] })}>
              Adicionar variável
            </Button>
          }
        >
          {issues["application.env"] && <p className="mb-2 text-sm text-red-700">{issues["application.env"]}</p>}
          <div className="space-y-2">
            {app.env.map((e, i) => (
              <div key={i} className="grid items-start gap-2 sm:grid-cols-[1fr_1.5fr_auto_auto]">
                <Input aria-label="Nome da variável" value={e.key} invalid={Boolean(issues[`application.env.${i}.key`])} onChange={(ev) => setEnv(i, { key: ev.target.value.toUpperCase() })} placeholder="MAIL_SERVER" />
                <Input
                  aria-label={`Valor de ${e.key || "variável"}`}
                  type={e.secret ? "password" : "text"}
                  value={e.value}
                  invalid={Boolean(issues[`application.env.${i}.value`])}
                  onChange={(ev) => setEnv(i, { value: ev.target.value })}
                  placeholder={e.secret && e.hasValue ? "•••• guardado (digite para trocar)" : ""}
                  autoComplete="off"
                />
                <label className="flex items-center gap-1.5 pt-2 text-sm">
                  <input type="checkbox" checked={e.secret} onChange={(ev) => setEnv(i, { secret: ev.target.checked, value: "" })} />
                  <KeyRound className="h-3.5 w-3.5" aria-hidden /> segredo
                </label>
                <Button variant="ghost" aria-label={`Remover ${e.key}`} onClick={() => setApp({ env: app.env.filter((_, j) => j !== i) })}>
                  <Trash2 className="h-4 w-4" />
                </Button>
                {(issues[`application.env.${i}.key`] || issues[`application.env.${i}.value`]) && (
                  <p className="text-xs text-red-700 sm:col-span-4">{issues[`application.env.${i}.key`] ?? issues[`application.env.${i}.value`]}</p>
                )}
              </div>
            ))}
          </div>
          {project.data && project.data.envExampleKeys.length > 0 && (
            <p className="mt-3 text-xs text-slate-500">Variáveis conhecidas do projeto: {project.data.envExampleKeys.join(", ")}.</p>
          )}
        </Card>

        <Card title="Volumes da aplicação e banco de dados" description="Pastas do contêiner guardadas nos volumes de dados (sobrevivem a novas publicações e à troca da instância).">
          <div className="space-y-2">
            {app.volumes.map((v, i) => (
              <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <Input aria-label="Pasta na EC2" value={v.hostPath} invalid={Boolean(issues[`application.volumes.${i}.hostPath`])} onChange={(e) => setApp({ volumes: app.volumes.map((x, j) => (j === i ? { ...x, hostPath: e.target.value } : x)) })} />
                <Input aria-label="Pasta no contêiner" value={v.containerPath} onChange={(e) => setApp({ volumes: app.volumes.map((x, j) => (j === i ? { ...x, containerPath: e.target.value } : x)) })} />
                <Button variant="ghost" aria-label="Remover volume" onClick={() => setApp({ volumes: app.volumes.filter((_, j) => j !== i) })}>
                  <Trash2 className="h-4 w-4" />
                </Button>
                {issues[`application.volumes.${i}.hostPath`] && <p className="text-xs text-red-700 sm:col-span-3">{issues[`application.volumes.${i}.hostPath`]}</p>}
              </div>
            ))}
            <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setApp({ volumes: [...app.volumes, { hostPath: `${draft.dataVolumes[0]?.mountPath ?? "/data"}/nova`, containerPath: "/app/nova" }] })}>
              Adicionar pasta
            </Button>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Switch
              checked={app.database.enabled}
              onChange={(v) => setApp({ database: { ...app.database, enabled: v } })}
              label="MySQL em contêiner na mesma EC2"
              description={`Dados em ${draft.dataVolumes[0]?.mountPath ?? "(sem volume)"}/mysql; senhas geradas e guardadas cifradas. A DATABASE_URL é montada sozinha.`}
            />
            {app.database.enabled && (
              <Field label="Imagem do MySQL" htmlFor="mysqlimg" error={issues["application.database.image"]}>
                <Input id="mysqlimg" value={app.database.image} onChange={(e) => setApp({ database: { ...app.database, image: e.target.value } })} />
              </Field>
            )}
          </div>
        </Card>
      </div>
      <SaveBar />
    </>
  );
}
