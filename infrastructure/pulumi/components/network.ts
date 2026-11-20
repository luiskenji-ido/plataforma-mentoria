import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import type { DeploymentConfig } from "@infra/shared";

export interface NetworkOutputs {
  vpcId: pulumi.Output<string>;
  subnetId: pulumi.Output<string>;
}

/**
 * Rede mínima e barata: Internet Gateway → sub-rede pública → EC2. Sem NAT Gateway nem Load Balancer.
 * Com mode = "existing", só usa a VPC e a sub-rede informadas (nada é criado).
 */
export class AppNetwork extends pulumi.ComponentResource implements NetworkOutputs {
  public readonly vpcId: pulumi.Output<string>;
  public readonly subnetId: pulumi.Output<string>;

  constructor(name: string, net: DeploymentConfig["network"], tags: Record<string, string>, opts?: pulumi.ComponentResourceOptions) {
    super("mentoria:infra:Network", name, {}, opts);
    const child = { parent: this };
    if (net.mode === "existing") {
      this.vpcId = pulumi.output(net.existingVpcId!);
      this.subnetId = pulumi.output(net.existingSubnetId!);
    } else {
      const vpc = new aws.ec2.Vpc(`${name}-vpc`, {
        cidrBlock: net.vpcCidr,
        enableDnsHostnames: true,
        enableDnsSupport: true,
        tags: { ...tags, Name: `${name}-vpc` },
      }, child);
      const igw = new aws.ec2.InternetGateway(`${name}-igw`, { vpcId: vpc.id, tags: { ...tags, Name: `${name}-igw` } }, child);
      const subnet = new aws.ec2.Subnet(`${name}-public`, {
        vpcId: vpc.id,
        cidrBlock: net.subnetCidr,
        availabilityZone: net.availabilityZone,
        mapPublicIpOnLaunch: false, // o IP público é decidido na instância (assignPublicIp)
        tags: { ...tags, Name: `${name}-public` },
      }, child);
      const routes = new aws.ec2.RouteTable(`${name}-rt`, {
        vpcId: vpc.id,
        routes: [{ cidrBlock: "0.0.0.0/0", gatewayId: igw.id }],
        tags: { ...tags, Name: `${name}-rt` },
      }, child);
      new aws.ec2.RouteTableAssociation(`${name}-rta`, { subnetId: subnet.id, routeTableId: routes.id }, child);
      this.vpcId = vpc.id;
      this.subnetId = subnet.id;
    }
    this.registerOutputs({ vpcId: this.vpcId, subnetId: this.subnetId });
  }
}

/** Regras de entrada: só a porta do app (para as faixas autorizadas) e, se pedido, o SSH de IPs específicos. */
export function ingressRules(config: DeploymentConfig): aws.types.input.ec2.SecurityGroupIngress[] {
  const rules: aws.types.input.ec2.SecurityGroupIngress[] = [];
  if (config.network.exposeApp) {
    rules.push({
      description: "Aplicação",
      protocol: "tcp",
      fromPort: config.application.hostPort,
      toPort: config.application.hostPort,
      cidrBlocks: config.network.appAllowedCidrs,
    });
  }
  if (config.network.ssh.enabled) {
    rules.push({ description: "SSH (IPs autorizados)", protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: config.network.ssh.allowedCidrs });
  }
  return rules;
}

export class AppSecurityGroup extends pulumi.ComponentResource {
  public readonly id: pulumi.Output<string>;

  constructor(name: string, config: DeploymentConfig, vpcId: pulumi.Input<string>, tags: Record<string, string>, opts?: pulumi.ComponentResourceOptions) {
    super("mentoria:infra:SecurityGroup", name, {}, opts);
    const sg = new aws.ec2.SecurityGroup(`${name}-sg`, {
      vpcId,
      description: `Acesso da aplicação ${config.application.name} (gerenciado pelo painel)`,
      ingress: ingressRules(config),
      // Saída liberada: apt, Docker Hub/ECR, SSM e as APIs que a aplicação usa
      egress: [{ description: "Saída", protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"], ipv6CidrBlocks: ["::/0"] }],
      tags: { ...tags, Name: `${name}-sg` },
    }, { parent: this });
    this.id = sg.id;
    this.registerOutputs({ id: this.id });
  }
}
