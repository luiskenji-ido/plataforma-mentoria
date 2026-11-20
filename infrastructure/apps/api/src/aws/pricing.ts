/**
 * Estimativa de custo mensal. Preços da EC2 e do EBS vêm da AWS Price List API (consultada na hora, com cache);
 * os itens sem consulta automática usam valores públicos documentados abaixo, com a data em que foram conferidos.
 */
import { GetProductsCommand, PricingClient } from "@aws-sdk/client-pricing";
import type { CostEstimate, CostLine, DeploymentConfig } from "@infra/shared";
import type { AwsSession } from "./credentials";

export const HOURS_PER_MONTH = 730;
/** Valores públicos da AWS usados quando não há consulta automática (conferir em aws.amazon.com/pricing). */
export const DOCUMENTED_PRICES = {
  checkedOn: "2026-11-20",
  publicIpv4PerHour: 0.005, // IPv4 público, cobrado desde 01/02/2024 (em uso ou não)
  ecrStoragePerGbMonth: 0.1, // armazenamento de imagens no ECR (us-east-1)
  ecrImageGb: 0.6, // tamanho típico comprimido da imagem da plataforma (python slim + dependências)
  freeDataTransferOutGb: 100, // saída para a internet: os primeiros 100 GB/mês da conta são gratuitos
};

export interface PriceSource {
  ec2Hourly(region: string, instanceType: string): Promise<number | null>;
  ebsGbMonth(region: string, volumeType: string): Promise<number | null>;
}

const cache = new Map<string, Promise<number | null>>();

function firstUsdPrice(priceList: string[] | undefined): number | null {
  for (const item of priceList ?? []) {
    const product = JSON.parse(item) as { terms?: { OnDemand?: Record<string, { priceDimensions: Record<string, { pricePerUnit: { USD?: string } }> }> } };
    for (const term of Object.values(product.terms?.OnDemand ?? {})) {
      for (const dim of Object.values(term.priceDimensions)) {
        const usd = Number(dim.pricePerUnit.USD);
        if (Number.isFinite(usd) && usd > 0) {
          return usd;
        }
      }
    }
  }
  return null;
}

export class AwsPriceList implements PriceSource {
  constructor(private readonly session: AwsSession) {}

  private client() {
    // A Price List API só existe em algumas regiões; us-east-1 atende todas as regiões
    return new PricingClient(this.session.clientConfig("us-east-1"));
  }

  ec2Hourly(region: string, instanceType: string): Promise<number | null> {
    const key = `ec2:${region}:${instanceType}`;
    if (!cache.has(key)) {
      cache.set(key, this.client().send(new GetProductsCommand({
        ServiceCode: "AmazonEC2",
        MaxResults: 10,
        Filters: [
          { Type: "TERM_MATCH", Field: "regionCode", Value: region },
          { Type: "TERM_MATCH", Field: "instanceType", Value: instanceType },
          { Type: "TERM_MATCH", Field: "operatingSystem", Value: "Linux" },
          { Type: "TERM_MATCH", Field: "tenancy", Value: "Shared" },
          { Type: "TERM_MATCH", Field: "preInstalledSw", Value: "NA" },
          { Type: "TERM_MATCH", Field: "capacitystatus", Value: "Used" },
          { Type: "TERM_MATCH", Field: "licenseModel", Value: "No License required" },
        ],
      })).then((r) => firstUsdPrice(r.PriceList), () => null));
    }
    return cache.get(key)!;
  }

  ebsGbMonth(region: string, volumeType: string): Promise<number | null> {
    const key = `ebs:${region}:${volumeType}`;
    if (!cache.has(key)) {
      cache.set(key, this.client().send(new GetProductsCommand({
        ServiceCode: "AmazonEC2",
        MaxResults: 10,
        Filters: [
          { Type: "TERM_MATCH", Field: "regionCode", Value: region },
          { Type: "TERM_MATCH", Field: "productFamily", Value: "Storage" },
          { Type: "TERM_MATCH", Field: "volumeApiName", Value: volumeType },
        ],
      })).then((r) => firstUsdPrice(r.PriceList), () => null));
    }
    return cache.get(key)!;
  }
}

const round = (n: number) => Math.round(n * 100) / 100;

export async function estimateCost(config: DeploymentConfig, prices: PriceSource): Promise<CostEstimate> {
  const region = config.instance.region;
  const lines: CostLine[] = [];
  const hourly = await prices.ec2Hourly(region, config.instance.instanceType);
  lines.push({
    item: `EC2 ${config.instance.instanceType} (Linux, sob demanda)`,
    hourlyUsd: hourly,
    monthlyUsd: hourly === null ? null : round(hourly * HOURS_PER_MONTH),
    source: hourly === null ? "Preço indisponível na Price List API" : "AWS Price List API",
    note: config.instance.instanceType.startsWith("t") ? "Instâncias t* podem ter cobrança extra de CPU se passarem do crédito (modo unlimited)." : undefined,
    chargedWhenStopped: false,
  });
  const disks = [
    { label: `EBS raiz ${config.rootDisk.type} ${config.rootDisk.sizeGb} GiB`, type: config.rootDisk.type, size: config.rootDisk.sizeGb },
    ...config.dataVolumes.map((v) => ({ label: `EBS dados "${v.name}" ${v.type} ${v.sizeGb} GiB`, type: v.type, size: v.sizeGb })),
  ];
  for (const d of disks) {
    const perGb = await prices.ebsGbMonth(region, d.type);
    lines.push({
      item: d.label,
      monthlyUsd: perGb === null ? null : round(perGb * d.size),
      source: perGb === null ? "Preço indisponível na Price List API" : "AWS Price List API",
      note: d.type === "gp3" ? "Inclui os 3.000 IOPS e 125 MB/s de base do gp3." : undefined,
      chargedWhenStopped: true,
    });
  }
  if (config.network.assignPublicIp) {
    lines.push({
      item: "IPv4 público",
      hourlyUsd: DOCUMENTED_PRICES.publicIpv4PerHour,
      monthlyUsd: round(DOCUMENTED_PRICES.publicIpv4PerHour * HOURS_PER_MONTH),
      source: `Preço público documentado (conferido em ${DOCUMENTED_PRICES.checkedOn})`,
      note: "Com a instância parada o IP automático é liberado (e muda ao ligar de novo).",
      chargedWhenStopped: false,
    });
  }
  lines.push({
    item: "ECR (imagens guardadas)",
    monthlyUsd: round(DOCUMENTED_PRICES.ecrStoragePerGbMonth * DOCUMENTED_PRICES.ecrImageGb * 3),
    source: `Preço público documentado (conferido em ${DOCUMENTED_PRICES.checkedOn}); supõe ~3 imagens de ${DOCUMENTED_PRICES.ecrImageGb} GB`,
    chargedWhenStopped: true,
  });
  lines.push({
    item: "Transferência de dados",
    monthlyUsd: 0,
    source: `Supõe menos de ${DOCUMENTED_PRICES.freeDataTransferOutGb} GB/mês de saída para a internet (faixa gratuita da conta)`,
    chargedWhenStopped: false,
  });
  const known = lines.filter((l) => l.monthlyUsd !== null);
  return {
    lines,
    monthlyTotalUsd: round(known.reduce((sum, l) => sum + (l.monthlyUsd ?? 0), 0)),
    incomplete: known.length !== lines.length,
    pricingDate: new Date().toISOString().slice(0, 10),
    disclaimer:
      "Estimativa: a cobrança real da AWS pode ser diferente (impostos, uso de CPU acima do crédito, snapshots, tráfego e alterações de preço). Volumes EBS e o ECR continuam cobrando com a EC2 parada.",
  };
}
