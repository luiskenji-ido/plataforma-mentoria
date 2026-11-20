import { RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { AWS_REGIONS, ROOT_DISK_MIN_GB, ROOT_DISK_RECOMMENDED_GB, type CostEstimate } from "@infra/shared";
import type { PageProps } from "../App";
import { SaveBar } from "../components/SaveBar";
import { Alert, Button, Card, Field, Input, PageHeader, Select, Switch } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useConfig } from "../hooks/useConfig";
import { get } from "../services/api";
import type { InstanceTypeInfo, UbuntuImage } from "../services/types";

export function CostCard({ connected, refreshKey }: { connected: boolean; refreshKey: unknown }) {
  const cost = useAsync(() => get<CostEstimate>("/api/costs"), [refreshKey], connected);
  return (
    <Card title="Custo estimado (configuração salva)" description="Preços da AWS Price List API e valores públicos documentados.">
      {!connected ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">Conecte-se à AWS para consultar os preços.</p>
      ) : cost.error ? (
        <Alert tone="warning">{cost.error}</Alert>
      ) : cost.data ? (
        <CostTable cost={cost.data} />
      ) : (
        <p className="text-sm">Consultando preços…</p>
      )}
    </Card>
  );
}

export function CostTable({ cost }: { cost: CostEstimate }) {
  return (
    <div className="space-y-3">
      <table className="w-full text-sm">
        <caption className="sr-only">Custos estimados por mês</caption>
        <thead>
          <tr className="text-left text-xs text-slate-500">
            <th className="py-1 font-medium">Item</th>
            <th className="py-1 text-right font-medium">US$/mês</th>
          </tr>
        </thead>
        <tbody>
          {cost.lines.map((l) => (
            <tr key={l.item} className="border-t border-slate-100 align-top dark:border-slate-800">
              <td className="py-1.5 pr-2">
                {l.item}
                {l.chargedWhenStopped && <span className="ml-1 text-xs text-amber-700 dark:text-amber-400">(cobra com a EC2 parada)</span>}
                <span className="block text-xs text-slate-500">{l.source}{l.note ? ` · ${l.note}` : ""}</span>
              </td>
              <td className="py-1.5 text-right font-mono">{l.monthlyUsd === null ? "?" : l.monthlyUsd.toFixed(2)}</td>
            </tr>
          ))}
          <tr className="border-t-2 border-slate-300 font-semibold dark:border-slate-700">
            <td className="py-1.5">Total estimado{cost.incomplete ? " (sem os itens com ?)" : ""}</td>
            <td className="py-1.5 text-right font-mono">{cost.monthlyTotalUsd.toFixed(2)}</td>
          </tr>
        </tbody>
      </table>
      <p className="text-xs text-slate-500">
        Consulta de {cost.pricingDate}. {cost.disclaimer}
      </p>
    </div>
  );
}

export function Ec2ConfigPage({ aws }: PageProps) {
  const { draft, update, issues, saved } = useConfig();
  const region = draft?.instance.region ?? "sa-east-1";
  const arch = draft?.instance.architecture ?? "x86_64";
  const connected = Boolean(aws?.connected);
  const types = useAsync(() => get<{ instanceTypes: InstanceTypeInfo[] }>(`/api/aws/instance-types?region=${region}`), [region, connected], connected);
  const images = useAsync(() => get<{ images: UbuntuImage[] }>(`/api/aws/ubuntu?region=${region}&architecture=${arch}`), [region, arch, connected], connected);
  const zones = useAsync(() => get<{ zones: string[] }>(`/api/aws/zones?region=${region}`), [region, connected], connected);

  // Ao trocar região/arquitetura/versão, a AMI vem da lista oficial resolvida para essa combinação
  useEffect(() => {
    if (!draft || !images.data) return;
    const img = images.data.images.find((i) => i.version === draft.instance.ubuntuVersion);
    if (img && img.amiId !== draft.instance.amiId) {
      update((c) => ({ ...c, instance: { ...c.instance, amiId: img.amiId, amiName: img.name } }));
    }
    if (!img && draft.instance.amiId) {
      update((c) => ({ ...c, instance: { ...c.instance, amiId: undefined, amiName: undefined } }));
    }
  }, [images.data, draft?.instance.ubuntuVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!draft) return null;
  const selectedType = types.data?.instanceTypes.find((t) => t.type === draft.instance.instanceType);
  const archMismatch = selectedType && !selectedType.architectures.includes(arch);

  return (
    <>
      <PageHeader title="Configuração da EC2" description="Região, tipo de instância, Ubuntu e disco principal. Nada é criado ao salvar." />
      {!connected && (
        <div className="mb-4">
          <Alert tone="warning">Conecte-se à AWS para listar os tipos de instância, as versões do Ubuntu e as zonas da região.</Alert>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-4">
          <Card title="Instância">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nome da instância" htmlFor="nome" error={issues["instance.name"]} help="Aparece no console da AWS (tag Name).">
                <Input id="nome" value={draft.instance.name} onChange={(e) => update((c) => ({ ...c, instance: { ...c.instance, name: e.target.value } }))} />
              </Field>
              <Field label="Nome do stack (Pulumi)" htmlFor="stack" error={issues.stackName} help="Único por ambiente; também nomeia o repositório ECR e os parâmetros do SSM.">
                <Input id="stack" value={draft.stackName} onChange={(e) => update((c) => ({ ...c, stackName: e.target.value.toLowerCase() }))} />
              </Field>
              <Field label="Região da AWS" htmlFor="reg" error={issues["instance.region"]}>
                <Select
                  id="reg"
                  value={region}
                  onChange={(e) => {
                    const r = e.target.value;
                    update((c) => ({ ...c, instance: { ...c.instance, region: r, amiId: undefined, amiName: undefined }, network: { ...c.network, availabilityZone: `${r}a`, existingVpcId: undefined, existingSubnetId: undefined } }));
                  }}
                >
                  {AWS_REGIONS.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.name} — {r.code}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Arquitetura" htmlFor="arch" help="A imagem Docker precisa ser da mesma arquitetura (o painel gera para a escolhida).">
                <Select id="arch" value={arch} onChange={(e) => update((c) => ({ ...c, instance: { ...c.instance, architecture: e.target.value as "x86_64" | "arm64", amiId: undefined } }))}>
                  <option value="x86_64">x86_64 (Intel/AMD) — recomendado</option>
                  <option value="arm64">arm64 (Graviton) — mais barato, build mais lento</option>
                </Select>
              </Field>
              <Field label="Tipo de instância" htmlFor="tipo" error={issues["instance.instanceType"]} help={selectedType ? `${selectedType.vcpus} vCPU · ${selectedType.memoryGiB} GiB · ${selectedType.architectures.join("/")}${selectedType.burstable ? " · créditos de CPU (t*)" : ""}` : "Lista da API EC2 da região."}>
                <Select id="tipo" value={draft.instance.instanceType} onChange={(e) => update((c) => ({ ...c, instance: { ...c.instance, instanceType: e.target.value } }))}>
                  {!types.data && <option value={draft.instance.instanceType}>{draft.instance.instanceType}</option>}
                  {types.data?.instanceTypes.map((t) => (
                    <option key={t.type} value={t.type} disabled={!t.architectures.includes(arch)}>
                      {t.type} — {t.vcpus} vCPU, {t.memoryGiB} GiB ({t.architectures.join("/")})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Zona de disponibilidade" htmlFor="az" error={issues["network.availabilityZone"]}>
                <Select id="az" value={draft.network.availabilityZone} onChange={(e) => update((c) => ({ ...c, network: { ...c.network, availabilityZone: e.target.value } }))}>
                  {!zones.data?.zones.includes(draft.network.availabilityZone) && <option value={draft.network.availabilityZone}>{draft.network.availabilityZone}</option>}
                  {zones.data?.zones.map((z) => (
                    <option key={z} value={z}>
                      {z}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            {archMismatch && (
              <div className="mt-4">
                <Alert tone="error">O tipo {selectedType.type} não é {arch}. Troque o tipo ou a arquitetura.</Alert>
              </div>
            )}
            {arch === "arm64" && (
              <div className="mt-4">
                <Alert tone="warning" title="arm64 (Graviton)">
                  A imagem será gerada para linux/arm64 com emulação no Docker Desktop (mais lenta) e todas as dependências da aplicação precisam ter versão para arm64.
                </Alert>
              </div>
            )}
          </Card>
          <Card title="Sistema operacional" description="Só imagens oficiais da Canonical, resolvidas na hora para a região e a arquitetura (nenhum ID fixo).">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Ubuntu Server LTS" htmlFor="ubuntu" error={issues["instance.ubuntuVersion"]}>
                <Select id="ubuntu" value={draft.instance.ubuntuVersion} onChange={(e) => update((c) => ({ ...c, instance: { ...c.instance, ubuntuVersion: e.target.value as typeof c.instance.ubuntuVersion } }))}>
                  {(images.data?.images.length ? images.data.images.map((i) => i.version) : [draft.instance.ubuntuVersion]).map((v) => (
                    <option key={v} value={v}>
                      Ubuntu Server {v} LTS
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="AMI resolvida" help={draft.instance.amiName ?? "Escolha a versão com a AWS conectada."}>
                <div className="flex items-center gap-2">
                  <code className="rounded bg-slate-100 px-2 py-1.5 text-sm dark:bg-slate-800">{draft.instance.amiId ?? "—"}</code>
                  <Button variant="ghost" onClick={() => void images.reload()} aria-label="Atualizar a lista de imagens" disabled={!connected}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </Field>
            </div>
            {images.error && <p className="mt-2 text-sm text-red-700">{images.error}</p>}
          </Card>
          <Card title="Disco principal (raiz)">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Tipo de volume" htmlFor="rtipo" help="gp3 é mais barato e rápido que gp2.">
                <Select id="rtipo" value={draft.rootDisk.type} onChange={(e) => update((c) => ({ ...c, rootDisk: { ...c.rootDisk, type: e.target.value as "gp3" | "gp2" } }))}>
                  <option value="gp3">gp3 (recomendado)</option>
                  <option value="gp2">gp2</option>
                </Select>
              </Field>
              <Field label="Tamanho (GiB)" htmlFor="rsize" error={issues["rootDisk.sizeGb"]} help={`Mínimo ${ROOT_DISK_MIN_GB}; com Docker, ${ROOT_DISK_RECOMMENDED_GB}+ recomendado.`}>
                <Input id="rsize" type="number" min={ROOT_DISK_MIN_GB} max={16384} value={draft.rootDisk.sizeGb} onChange={(e) => update((c) => ({ ...c, rootDisk: { ...c.rootDisk, sizeGb: Number(e.target.value) } }))} />
              </Field>
              <div className="pt-6">
                <Switch checked={draft.rootDisk.encrypted} onChange={(v) => update((c) => ({ ...c, rootDisk: { ...c.rootDisk, encrypted: v } }))} label="Disco cifrado" description="Padrão: ligado (chave gerenciada da AWS)." />
              </div>
            </div>
          </Card>
        </div>
        <div className="space-y-4">
          <CostCard connected={connected} refreshKey={saved?.updatedAt} />
        </div>
      </div>
      <SaveBar />
    </>
  );
}
