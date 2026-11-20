import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

/** Mantém as últimas imagens publicadas; as mais antigas são apagadas pelo próprio ECR. */
export const KEEP_IMAGES = 15;

export function lifecyclePolicy(keep = KEEP_IMAGES): string {
  return JSON.stringify({
    rules: [
      {
        rulePriority: 1,
        description: `Mantém as ${keep} imagens mais recentes`,
        selection: { tagStatus: "any", countType: "imageCountMoreThan", countNumber: keep },
        action: { type: "expire" },
      },
    ],
  });
}

/** Repositório ECR com tags imutáveis (cada publicação usa uma tag nova) e varredura de vulnerabilidades. */
export class AppRegistry extends pulumi.ComponentResource {
  public readonly repositoryUrl: pulumi.Output<string>;
  public readonly repositoryArn: pulumi.Output<string>;
  public readonly repositoryName: pulumi.Output<string>;

  constructor(name: string, repoName: string, tags: Record<string, string>, opts?: pulumi.ComponentResourceOptions) {
    super("mentoria:infra:Registry", name, {}, opts);
    const repo = new aws.ecr.Repository(`${name}-repo`, {
      name: repoName,
      imageTagMutability: "IMMUTABLE",
      imageScanningConfiguration: { scanOnPush: true },
      encryptionConfigurations: [{ encryptionType: "AES256" }],
      // As imagens são reconstruídas a partir do código: o destroy apaga o repositório mesmo com imagens
      forceDelete: true,
      tags,
    }, { parent: this });
    new aws.ecr.LifecyclePolicy(`${name}-lifecycle`, { repository: repo.name, policy: lifecyclePolicy() }, { parent: this });
    this.repositoryUrl = repo.repositoryUrl;
    this.repositoryArn = repo.arn;
    this.repositoryName = repo.name;
    this.registerOutputs({ repositoryUrl: this.repositoryUrl });
  }
}
