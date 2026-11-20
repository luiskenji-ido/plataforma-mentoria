import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

/**
 * Política mínima da instância:
 * - baixar só as imagens do repositório da aplicação (o GetAuthorizationToken não aceita recurso específico);
 * - ler só os parâmetros do SSM do próprio stack (variáveis e segredos da aplicação).
 * O acesso administrativo (Session Manager e Run Command) vem da política gerenciada AmazonSSMManagedInstanceCore.
 */
export function instancePolicyDocument(repositoryArn: string, parameterArnPrefix: string): string {
  return JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      { Sid: "EcrLogin", Effect: "Allow", Action: ["ecr:GetAuthorizationToken"], Resource: "*" },
      {
        Sid: "EcrPullAppImages",
        Effect: "Allow",
        Action: ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
        Resource: repositoryArn,
      },
      {
        Sid: "ReadAppParameters",
        Effect: "Allow",
        Action: ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
        Resource: [parameterArnPrefix, `${parameterArnPrefix}/*`],
      },
    ],
  });
}

export const SSM_CORE_POLICY_ARN = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore";

export class InstanceIdentity extends pulumi.ComponentResource {
  public readonly profileName: pulumi.Output<string>;
  public readonly roleName: pulumi.Output<string>;

  constructor(
    name: string,
    args: { repositoryArn: pulumi.Input<string>; parameterArnPrefix: pulumi.Input<string>; tags: Record<string, string> },
    opts?: pulumi.ComponentResourceOptions,
  ) {
    super("mentoria:infra:InstanceIdentity", name, {}, opts);
    const child = { parent: this };
    const role = new aws.iam.Role(`${name}-role`, {
      description: "Papel da EC2 da aplicação (gerenciado pelo painel de infraestrutura)",
      assumeRolePolicy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [{ Effect: "Allow", Principal: { Service: "ec2.amazonaws.com" }, Action: "sts:AssumeRole" }],
      }),
      tags: args.tags,
    }, child);
    new aws.iam.RolePolicyAttachment(`${name}-ssm-core`, { role: role.name, policyArn: SSM_CORE_POLICY_ARN }, child);
    new aws.iam.RolePolicy(`${name}-app`, {
      role: role.id,
      policy: pulumi.all([args.repositoryArn, args.parameterArnPrefix]).apply(([repo, prefix]) => instancePolicyDocument(repo, prefix)),
    }, child);
    const profile = new aws.iam.InstanceProfile(`${name}-profile`, { role: role.name, tags: args.tags }, child);
    this.profileName = profile.name;
    this.roleName = role.name;
    this.registerOutputs({ profileName: this.profileName });
  }
}
