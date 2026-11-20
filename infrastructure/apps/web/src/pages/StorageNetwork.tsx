import { Plus, Trash2 } from "lucide-react";
import { DATA_VOLUME_TYPES, EBS_SIZE_LIMITS, type DataVolume } from "@infra/shared";
import type { PageProps } from "../App";
import { SaveBar } from "../components/SaveBar";
import { Alert, Button, Card, Field, Input, PageHeader, Select, Switch } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { get } from "../services/api";

/** Editor simples de lista de CIDRs (uma faixa por linha). */
function CidrList({ id, value, onChange, error }: { id: string; value: string[]; onChange: (v: string[]) => void; error?: string }) {
  return (
    <textarea
      id={id}
      className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm dark:border-slate-700 dark:bg-slate-950"
      rows={Math.max(2, value.length + 1)}
      value={value.join("\n")}
      aria-invalid={error ? true : undefined}
      onChange={(e) => onChange(e.target.value.split(/\s*\n\s*/).map((s) => s.trim()).filter(Boolean))}
      spellCheck={false}
    />
  );
}

export function StorageNetworkPage({ aws }: PageProps) {
  const { draft, update, issues } = useConfig();
  const connected = Boolean(aws?.connected);
  const region = draft?.instance.region ?? "";
  const vpcs = useAsync(() => get<{ vpcs: { id: string; cidr: string; isDefault: boolean; name: string }[] }>(`/api/aws/vpcs?region=${region}`), [region, connected], connected && draft?.network.mode === "existing");
  const vpcId = draft?.network.existingVpcId;
  const subnets = useAsync(
    () => get<{ subnets: { id: string; cidr: string; availabilityZone: string; publicByDefault: boolean; name: string }[] }>(`/api/aws/subnets?region=${region}&vpcId=${vpcId}`),
    [region, vpcId, connected],
    connected && Boolean(vpcId),
  );
  if (!draft) return null;
  const n = draft.network;
  const setNet = (patch: Partial<typeof n>) => update((c) => ({ ...c, network: { ...c.network, ...patch } }));
  const setVol = (i: number, patch: Partial<DataVolume>) =>
    update((c) => ({ ...c, dataVolumes: c.dataVolumes.map((v, j) => (j === i ? { ...v, ...patch } : v)) }));

  return (
    <>
      <PageHeader title="Armazenamento e rede" description="Volumes de dados persistentes e a rede mínima: Internet Gateway → sub-rede pública → EC2. Sem NAT Gateway nem Load Balancer." />
      <div className="space-y-4">
        <Card
          title="Volumes de dados (EBS)"
          description="Ficam separados da instância: trocar ou recriar a EC2 não apaga os dados. Montados pelo UUID, voltam sozinhos depois de reiniciar."
          actions={
            <Button
              variant="secondary"
              icon={<Plus className="h-4 w-4" />}
              disabled={draft.dataVolumes.length >= 4}
              onClick={() => update((c) => ({ ...c, dataVolumes: [...c.dataVolumes, { name: `vol${c.dataVolumes.length + 1}`, sizeGb: 10, type: "gp3", mountPath: `/data${c.dataVolumes.length + 1}`, deleteOnDestroy: false }] }))}
            >
              Adicionar volume
            </Button>
          }
        >
          {issues.dataVolumes && <p className="mb-3 text-sm text-red-700">{issues.dataVolumes}</p>}
          {draft.dataVolumes.length === 0 && <p className="text-sm text-slate-600">Nenhum volume de dados: tudo fica no disco raiz (perdido se a instância for recriada).</p>}
          <div className="space-y-4">
            {draft.dataVolumes.map((v, i) => (
              <div key={i} className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-[1fr_1fr_1fr_1.4fr_auto] dark:border-slate-800">
                <Field label="Nome" htmlFor={`vn${i}`} error={issues[`dataVolumes.${i}.name`]}>
                  <Input id={`vn${i}`} value={v.name} onChange={(e) => setVol(i, { name: e.target.value })} />
                </Field>
                <Field label="Tipo" htmlFor={`vt${i}`} help={`${EBS_SIZE_LIMITS[v.type].min}–${EBS_SIZE_LIMITS[v.type].max} GiB`}>
                  <Select id={`vt${i}`} value={v.type} onChange={(e) => setVol(i, { type: e.target.value as DataVolume["type"] })}>
                    {DATA_VOLUME_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Tamanho (GiB)" htmlFor={`vs${i}`} error={issues[`dataVolumes.${i}.sizeGb`]}>
                  <Input id={`vs${i}`} type="number" value={v.sizeGb} onChange={(e) => setVol(i, { sizeGb: Number(e.target.value) })} />
                </Field>
                <Field label="Ponto de montagem" htmlFor={`vm${i}`} error={issues[`dataVolumes.${i}.mountPath`]}>
                  <Input id={`vm${i}`} value={v.mountPath} onChange={(e) => setVol(i, { mountPath: e.target.value })} />
                </Field>
                <div className="flex items-end">
                  <Button variant="ghost" aria-label={`Remover o volume ${v.name}`} onClick={() => update((c) => ({ ...c, dataVolumes: c.dataVolumes.filter((_, j) => j !== i) }))}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="sm:col-span-5">
                  <Switch
                    checked={v.deleteOnDestroy}
                    onChange={(val) => setVol(i, { deleteOnDestroy: val })}
                    label="Apagar este volume ao destruir a infraestrutura"
                    description={v.deleteOnDestroy ? "Os dados serão perdidos no destroy." : "Padrão: o volume é preservado no destroy (continua cobrando até ser apagado no console)."}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Rede (VPC)">
          <div className="mb-4 flex flex-wrap gap-4">
            {(["new", "existing"] as const).map((m) => (
              <label key={m} className="flex items-center gap-2 text-sm">
                <input type="radio" name="vpcmode" checked={n.mode === m} onChange={() => setNet({ mode: m })} />
                {m === "new" ? "Criar uma VPC nova (recomendado)" : "Usar uma VPC existente"}
              </label>
            ))}
          </div>
          {n.mode === "new" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Faixa da VPC (CIDR)" htmlFor="vpccidr" error={issues["network.vpcCidr"]} help="Ex.: 10.42.0.0/16">
                <Input id="vpccidr" value={n.vpcCidr} onChange={(e) => setNet({ vpcCidr: e.target.value })} />
              </Field>
              <Field label="Sub-rede pública (CIDR)" htmlFor="subcidr" error={issues["network.subnetCidr"]} help={`Dentro da VPC, na zona ${n.availabilityZone}.`}>
                <Input id="subcidr" value={n.subnetCidr} onChange={(e) => setNet({ subnetCidr: e.target.value })} />
              </Field>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="VPC" htmlFor="vpcsel" error={issues["network.existingVpcId"]}>
                <Select id="vpcsel" value={n.existingVpcId ?? ""} onChange={(e) => setNet({ existingVpcId: e.target.value || undefined, existingSubnetId: undefined })}>
                  <option value="">{connected ? "Escolha…" : "Conecte-se à AWS"}</option>
                  {vpcs.data?.vpcs.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.id} {v.name && `· ${v.name}`} · {v.cidr} {v.isDefault ? "(padrão)" : ""}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Sub-rede" htmlFor="subsel" error={issues["network.existingSubnetId"]} help="Precisa ter rota para um Internet Gateway (sub-rede pública).">
                <Select
                  id="subsel"
                  value={n.existingSubnetId ?? ""}
                  onChange={(e) => {
                    const s = subnets.data?.subnets.find((x) => x.id === e.target.value);
                    setNet({ existingSubnetId: e.target.value || undefined, ...(s ? { availabilityZone: s.availabilityZone, subnetCidr: s.cidr } : {}) });
                  }}
                >
                  <option value="">Escolha…</option>
                  {subnets.data?.subnets.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.id} · {s.cidr} · {s.availabilityZone} {s.publicByDefault ? "(pública)" : ""}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          )}
          <div className="mt-4 space-y-3">
            <Switch checked={n.assignPublicIp} onChange={(v) => setNet({ assignPublicIp: v })} label="IPv4 público na instância" description="Necessário para acessar o app pela internet (cobrança por hora do IPv4)." />
            {issues["network.assignPublicIp"] && <p className="text-sm text-red-700">{issues["network.assignPublicIp"]}</p>}
          </div>
        </Card>

        <Card title="Security Group (portas abertas)" description="Só as portas listadas aceitam conexões de fora. A saída para a internet fica liberada (atualizações, ECR, SSM).">
          <div className="space-y-5">
            <div className="space-y-3">
              <Switch checked={n.exposeApp} onChange={(v) => setNet({ exposeApp: v })} label={`Expor a aplicação (porta TCP ${draft.application.hostPort})`} description="Desligado: o app só é acessível pelo Session Manager (túnel de porta)." />
              {n.exposeApp && (
                <Field label="Quem pode acessar o app (um CIDR por linha)" htmlFor="appcidrs" error={issues["network.appAllowedCidrs"]} help="0.0.0.0/0 = qualquer pessoa na internet. Para testes, prefira o seu IP com /32.">
                  <CidrList id="appcidrs" value={n.appAllowedCidrs} onChange={(v) => setNet({ appAllowedCidrs: v })} error={issues["network.appAllowedCidrs"]} />
                </Field>
              )}
            </div>
            <div className="space-y-3">
              <Switch
                checked={n.ssh.enabled}
                onChange={(v) => setNet({ ssh: { ...n.ssh, enabled: v } })}
                label="Abrir SSH (porta 22)"
                description="Desligado por padrão. A administração é feita pelo AWS Systems Manager (Session Manager), sem porta aberta e sem chave SSH."
              />
              {n.ssh.enabled && (
                <Field label="IPs autorizados para SSH (um por linha)" htmlFor="sshcidrs" error={issues["network.ssh.allowedCidrs"]} help="Use o IP público do seu computador com /32. 0.0.0.0/0 não é aceito.">
                  <CidrList id="sshcidrs" value={n.ssh.allowedCidrs} onChange={(v) => setNet({ ssh: { ...n.ssh, allowedCidrs: v } })} />
                </Field>
              )}
            </div>
            <Alert tone={n.exposeApp && n.appAllowedCidrs.includes("0.0.0.0/0") ? "warning" : "info"} title="Ficarão acessíveis">
              {!n.exposeApp && !n.ssh.enabled ? (
                "Nenhuma porta de entrada: a instância não recebe conexões da internet."
              ) : (
                <ul className="list-disc pl-5">
                  {n.exposeApp && <li>TCP {draft.application.hostPort} (aplicação) ← {n.appAllowedCidrs.join(", ") || "—"}</li>}
                  {n.ssh.enabled && <li>TCP 22 (SSH) ← {n.ssh.allowedCidrs.join(", ") || "—"}</li>}
                </ul>
              )}
            </Alert>
          </div>
        </Card>
      </div>
      <SaveBar />
    </>
  );
}
