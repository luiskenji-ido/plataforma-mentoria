/**
 * Programa Pulumi (inline) da infraestrutura da aplicação. Chamado pela API pelo Automation API:
 *   VPC/sub-rede (ou existentes) → Security Group → ECR → SSM Parameter Store → IAM → EBS + EC2.
 * Os segredos (SECRET_KEY, senhas do MySQL e variáveis secretas) vêm da configuração do stack, cifrada pelo
 * provedor de segredos do Pulumi (senha), e viram SecureString no SSM.
 */
import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import type { DeploymentConfig } from "@infra/shared";
import { AppParameters, ssmPrefixFor, type AppSecrets } from "./components/appConfig";
import { InstanceIdentity } from "./components/iam";
import { AppNetwork, AppSecurityGroup } from "./components/network";
import { AppRegistry } from "./components/registry";
import { AppServer } from "./components/server";

export const PROJECT_NAME = "mentoria-infra";

/** Chaves da configuração (cifrada) do stack. */
export const CONFIG_KEYS = {
  secretKey: "appSecretKey",
  dbPassword: "dbPassword",
  dbRootPassword: "dbRootPassword",
  secretEnv: "secretEnv",
} as const;

export function resourceTags(config: DeploymentConfig): Record<string, string> {
  return { Project: config.application.name, Stack: config.stackName, ManagedBy: "pulumi-mentoria-infra" };
}

export function repositoryNameFor(config: DeploymentConfig): string {
  return `${config.application.name}/${config.stackName}`;
}

export function createProgram(config: DeploymentConfig) {
  return async () => {
    const settings = new pulumi.Config();
    const secrets: AppSecrets = {
      secretKey: settings.requireSecret(CONFIG_KEYS.secretKey),
      dbPassword: settings.requireSecret(CONFIG_KEYS.dbPassword),
      dbRootPassword: settings.requireSecret(CONFIG_KEYS.dbRootPassword),
      secretEnv: settings.getSecretObject<Record<string, string>>(CONFIG_KEYS.secretEnv) ?? pulumi.secret<Record<string, string>>({}),
    };
    const tags = resourceTags(config);
    const provider = new aws.Provider("aws", { region: config.instance.region as aws.Region, defaultTags: { tags } });
    const opts = { provider };
    const name = config.stackName;
    const prefix = ssmPrefixFor(config.application.name, config.stackName);
    const identity = await aws.getCallerIdentity({}, { provider });
    const partition = await aws.getPartition({}, { provider });

    const network = new AppNetwork(name, config.network, tags, opts);
    const securityGroup = new AppSecurityGroup(name, config, network.vpcId, tags, opts);
    const registry = new AppRegistry(name, repositoryNameFor(config), tags, opts);
    const parameters = new AppParameters(name, config, prefix, secrets, tags, opts);
    const iam = new InstanceIdentity(name, {
      repositoryArn: registry.repositoryArn,
      parameterArnPrefix: `arn:${partition.partition}:ssm:${config.instance.region}:${identity.accountId}:parameter${prefix}`,
      tags,
    }, opts);
    const server = new AppServer(name, {
      config,
      subnetId: network.subnetId,
      securityGroupId: securityGroup.id,
      instanceProfileName: iam.profileName,
      ssmPrefix: prefix,
      tags,
    }, { ...opts, dependsOn: [parameters] });

    const port = config.application.hostPort;
    return {
      region: config.instance.region,
      accountId: identity.accountId,
      instanceId: server.instanceId,
      publicIp: server.publicIp,
      privateIp: server.privateIp,
      publicDns: server.publicDns,
      appUrl: config.network.exposeApp && config.network.assignPublicIp
        ? pulumi.interpolate`http://${server.publicIp}${port === 80 ? "" : `:${port}`}`
        : "",
      ecrRepositoryUrl: registry.repositoryUrl,
      ecrRepositoryName: registry.repositoryName,
      imageParameterName: parameters.imageParameterName,
      ssmPrefix: prefix,
      vpcId: network.vpcId,
      subnetId: network.subnetId,
      securityGroupId: securityGroup.id,
      dataVolumeIds: pulumi.all(server.volumeIds),
      ubuntuVersion: config.instance.ubuntuVersion,
      amiId: config.instance.amiId ?? "",
    };
  };
}
