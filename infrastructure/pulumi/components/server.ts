import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import type { DeploymentConfig } from "@infra/shared";
import { deviceNameFor, renderUserData } from "../bootstrap/render";

/**
 * EC2 Ubuntu + volumes EBS de dados. Os volumes de dados ficam fora da instância: trocar a instância (outro tipo
 * ou outra AMI) não apaga os dados. Por padrão eles também sobrevivem ao destroy (retainOnDelete).
 */
export class AppServer extends pulumi.ComponentResource {
  public readonly instanceId: pulumi.Output<string>;
  public readonly publicIp: pulumi.Output<string>;
  public readonly privateIp: pulumi.Output<string>;
  public readonly publicDns: pulumi.Output<string>;
  public readonly volumeIds: pulumi.Output<string>[];

  constructor(
    name: string,
    args: {
      config: DeploymentConfig;
      subnetId: pulumi.Input<string>;
      securityGroupId: pulumi.Input<string>;
      instanceProfileName: pulumi.Input<string>;
      ssmPrefix: string;
      tags: Record<string, string>;
    },
    opts?: pulumi.ComponentResourceOptions,
  ) {
    super("mentoria:infra:Server", name, {}, opts);
    const { config, tags } = args;
    const child = { parent: this };
    if (!config.instance.amiId) {
      throw new Error("A AMI do Ubuntu não foi resolvida: atualize a configuração da EC2 no painel.");
    }

    const volumes = config.dataVolumes.map(
      (v) =>
        new aws.ebs.Volume(`${name}-vol-${v.name}`, {
          availabilityZone: config.network.availabilityZone,
          size: v.sizeGb,
          type: v.type,
          encrypted: true,
          tags: { ...tags, Name: `${config.instance.name}-${v.name}`, MountPath: v.mountPath },
        }, { ...child, retainOnDelete: !v.deleteOnDestroy }),
    );

    const userData = pulumi
      .all(volumes.map((v) => v.id))
      .apply((ids) =>
        renderUserData({
          config,
          region: config.instance.region,
          ssmPrefix: args.ssmPrefix,
          volumes: ids.map((volumeId, i) => ({ volumeId, mountPath: config.dataVolumes[i]!.mountPath, deviceName: deviceNameFor(i) })),
        }),
      );

    const instance = new aws.ec2.Instance(`${name}-ec2`, {
      ami: config.instance.amiId,
      instanceType: config.instance.instanceType,
      subnetId: args.subnetId,
      availabilityZone: config.network.availabilityZone,
      vpcSecurityGroupIds: [args.securityGroupId],
      iamInstanceProfile: args.instanceProfileName,
      associatePublicIpAddress: config.network.assignPublicIp,
      rootBlockDevice: {
        volumeType: config.rootDisk.type,
        volumeSize: config.rootDisk.sizeGb,
        encrypted: config.rootDisk.encrypted,
        deleteOnTermination: true,
        tags: { ...tags, Name: `${config.instance.name}-root` },
      },
      metadataOptions: { httpEndpoint: "enabled", httpTokens: "required", httpPutResponseHopLimit: 2 }, // IMDSv2
      userData,
      userDataReplaceOnChange: false,
      monitoring: false,
      tags: { ...tags, Name: config.instance.name, Ubuntu: config.instance.ubuntuVersion },
    }, child);

    volumes.forEach((volume, i) => {
      new aws.ec2.VolumeAttachment(`${name}-att-${config.dataVolumes[i]!.name}`, {
        deviceName: deviceNameFor(i),
        volumeId: volume.id,
        instanceId: instance.id,
        // Para a instância antes de desanexar (evita perder escrita em andamento)
        stopInstanceBeforeDetaching: true,
      }, child);
    });

    this.instanceId = instance.id;
    this.publicIp = instance.publicIp;
    this.privateIp = instance.privateIp;
    this.publicDns = instance.publicDns;
    this.volumeIds = volumes.map((v) => v.id);
    this.registerOutputs({ instanceId: this.instanceId });
  }
}
