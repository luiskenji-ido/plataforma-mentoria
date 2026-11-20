/** Dados da AWS para os formulários: tipos de instância, AMIs oficiais do Ubuntu, zonas, VPCs e sub-redes. */
import {
  DescribeAvailabilityZonesCommand,
  DescribeImagesCommand,
  DescribeInstanceTypesCommand,
  DescribeSubnetsCommand,
  DescribeVpcsCommand,
  EC2Client,
  type _InstanceType as InstanceType,
} from "@aws-sdk/client-ec2";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { UBUNTU_VERSIONS, type DeploymentConfig } from "@infra/shared";
import type { AwsSession } from "./credentials";

/** Conta oficial da Canonical que publica as AMIs do Ubuntu. */
export const CANONICAL_OWNER_ID = "099720109477";

/** Tipos oferecidos no painel (baratos e adequados a um app web com banco). A disponibilidade vem da API da região. */
export const CURATED_INSTANCE_TYPES = [
  "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge",
  "t3a.micro", "t3a.small", "t3a.medium", "t3a.large",
  "t4g.micro", "t4g.small", "t4g.medium", "t4g.large", "t4g.xlarge",
  "m6i.large", "m6i.xlarge", "m7g.large", "m7g.xlarge", "c6i.large", "c7g.large",
];

export interface InstanceTypeInfo {
  type: string;
  vcpus: number;
  memoryGiB: number;
  architectures: string[];
  burstable: boolean;
}

export interface UbuntuImage {
  version: string;
  amiId: string;
  name: string;
  creationDate?: string;
  architecture: DeploymentConfig["instance"]["architecture"];
  parameter: string;
}

export function ubuntuParameterNames(version: string, arch: DeploymentConfig["instance"]["architecture"]): string[] {
  const a = arch === "arm64" ? "arm64" : "amd64";
  // A Canonical publica a AMI atual de cada versão em parâmetros públicos do SSM (gp3 nas versões novas, gp2 nas antigas)
  return ["ebs-gp3", "ebs-gp2"].map((disk) => `/aws/service/canonical/ubuntu/server/${version}/stable/current/${a}/hvm/${disk}/ami-id`);
}

export class AwsCatalog {
  constructor(private readonly session: AwsSession) {}

  private ec2(region: string) {
    return new EC2Client(this.session.clientConfig(region));
  }

  async instanceTypes(region: string): Promise<InstanceTypeInfo[]> {
    const out = await this.ec2(region).send(new DescribeInstanceTypesCommand({ InstanceTypes: CURATED_INSTANCE_TYPES as InstanceType[] })).catch(async (error) => {
      // Algum tipo não existe na região: consulta um a um e ignora os ausentes
      if ((error as { name?: string }).name !== "InvalidInstanceType") {
        throw error;
      }
      const found = await Promise.all(
        CURATED_INSTANCE_TYPES.map((t) =>
          this.ec2(region).send(new DescribeInstanceTypesCommand({ InstanceTypes: [t as InstanceType] })).then((r) => r.InstanceTypes ?? [], () => []),
        ),
      );
      return { InstanceTypes: found.flat() };
    });
    return (out.InstanceTypes ?? [])
      .map((t) => ({
        type: t.InstanceType ?? "",
        vcpus: t.VCpuInfo?.DefaultVCpus ?? 0,
        memoryGiB: Math.round(((t.MemoryInfo?.SizeInMiB ?? 0) / 1024) * 10) / 10,
        architectures: (t.ProcessorInfo?.SupportedArchitectures ?? []).filter((a) => a === "x86_64" || a === "arm64"),
        burstable: Boolean(t.BurstablePerformanceSupported),
      }))
      .sort((a, b) => CURATED_INSTANCE_TYPES.indexOf(a.type) - CURATED_INSTANCE_TYPES.indexOf(b.type));
  }

  /** AMI oficial atual do Ubuntu para a região e a arquitetura, conferindo que a dona é a Canonical. */
  async resolveUbuntu(region: string, version: string, arch: DeploymentConfig["instance"]["architecture"]): Promise<UbuntuImage | null> {
    const ssm = new SSMClient(this.session.clientConfig(region));
    for (const parameter of ubuntuParameterNames(version, arch)) {
      const amiId = await ssm.send(new GetParameterCommand({ Name: parameter })).then(
        (r) => r.Parameter?.Value,
        (error: { name?: string }) => {
          if (error.name === "ParameterNotFound") {
            return undefined;
          }
          throw error;
        },
      );
      if (!amiId) {
        continue;
      }
      const images = await this.ec2(region).send(new DescribeImagesCommand({ ImageIds: [amiId], Owners: [CANONICAL_OWNER_ID] }));
      const image = images.Images?.[0];
      if (!image || image.OwnerId !== CANONICAL_OWNER_ID || image.State !== "available") {
        throw new Error(`A AMI ${amiId} não é uma imagem oficial disponível da Canonical.`);
      }
      return { version, amiId, name: image.Name ?? amiId, creationDate: image.CreationDate, architecture: arch, parameter };
    }
    return null;
  }

  async ubuntuVersions(region: string, arch: DeploymentConfig["instance"]["architecture"]): Promise<UbuntuImage[]> {
    const found = await Promise.all(UBUNTU_VERSIONS.map((v) => this.resolveUbuntu(region, v, arch)));
    return found.filter((x): x is UbuntuImage => x !== null);
  }

  async availabilityZones(region: string): Promise<string[]> {
    const out = await this.ec2(region).send(new DescribeAvailabilityZonesCommand({
      Filters: [{ Name: "state", Values: ["available"] }, { Name: "zone-type", Values: ["availability-zone"] }],
    }));
    return (out.AvailabilityZones ?? []).map((z) => z.ZoneName ?? "").filter(Boolean).sort();
  }

  async vpcs(region: string) {
    const out = await this.ec2(region).send(new DescribeVpcsCommand({}));
    return (out.Vpcs ?? []).map((v) => ({
      id: v.VpcId ?? "",
      cidr: v.CidrBlock ?? "",
      isDefault: Boolean(v.IsDefault),
      name: v.Tags?.find((t) => t.Key === "Name")?.Value ?? "",
    }));
  }

  async subnets(region: string, vpcId: string) {
    const out = await this.ec2(region).send(new DescribeSubnetsCommand({ Filters: [{ Name: "vpc-id", Values: [vpcId] }] }));
    return (out.Subnets ?? []).map((s) => ({
      id: s.SubnetId ?? "",
      cidr: s.CidrBlock ?? "",
      availabilityZone: s.AvailabilityZone ?? "",
      publicByDefault: Boolean(s.MapPublicIpOnLaunch),
      name: s.Tags?.find((t) => t.Key === "Name")?.Value ?? "",
    }));
  }
}
