import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import type { DeploymentConfig } from "@infra/shared";

/** Valor inicial do parâmetro da imagem: o bootstrap não publica nada até o painel registrar a primeira imagem. */
export const NO_IMAGE = "none";

export interface AppSecrets {
  secretKey: pulumi.Output<string>;
  dbPassword: pulumi.Output<string>;
  dbRootPassword: pulumi.Output<string>;
  /** Valores das variáveis marcadas como segredo (chave → valor), guardados cifrados na configuração do stack. */
  secretEnv: pulumi.Output<Record<string, string>>;
}

export function ssmPrefixFor(appName: string, stackName: string): string {
  return `/${appName}-infra/${stackName}`;
}

/**
 * Configuração da aplicação no SSM Parameter Store, lida pela instância no deploy:
 *   <prefixo>/image        imagem atual (o painel atualiza a cada publicação; o Pulumi não sobrescreve)
 *   <prefixo>/env/<CHAVE>  variáveis do app (SecureString para segredos)
 *   <prefixo>/db/<CHAVE>   variáveis do contêiner MySQL
 */
export class AppParameters extends pulumi.ComponentResource {
  public readonly imageParameterName: pulumi.Output<string>;

  constructor(name: string, config: DeploymentConfig, prefix: string, secrets: AppSecrets, tags: Record<string, string>, opts?: pulumi.ComponentResourceOptions) {
    super("mentoria:infra:AppParameters", name, {}, opts);
    const child = { parent: this };
    const param = (key: string, path: string, value: pulumi.Input<string>, secure: boolean) =>
      new aws.ssm.Parameter(`${name}-${key}`, { name: `${prefix}/${path}`, type: secure ? "SecureString" : "String", value, tags }, child);

    const image = new aws.ssm.Parameter(`${name}-image`, {
      name: `${prefix}/image`,
      type: "String",
      value: NO_IMAGE,
      description: "Imagem da aplicação em execução (atualizada pelo painel a cada publicação)",
      tags,
    }, { ...child, ignoreChanges: ["value"] });
    this.imageParameterName = image.name;

    param("env-secret-key", "env/SECRET_KEY", secrets.secretKey, true);
    for (const e of config.application.env) {
      const key = `env-${e.key.toLowerCase().replace(/_/g, "-")}`;
      const value = e.secret ? secrets.secretEnv.apply((s) => s[e.key] ?? "") : e.value;
      param(key, `env/${e.key}`, value, e.secret);
    }
    if (config.application.database.enabled) {
      const dbName = config.application.name.replace(/-/g, "_");
      param("env-database-url", "env/DATABASE_URL",
        pulumi.interpolate`mysql+pymysql://app:${secrets.dbPassword}@mysql:3306/${dbName}?charset=utf8mb4`, true);
      param("db-name", "db/MYSQL_DATABASE", dbName, false);
      param("db-user", "db/MYSQL_USER", "app", false);
      param("db-password", "db/MYSQL_PASSWORD", secrets.dbPassword, true);
      param("db-root-password", "db/MYSQL_ROOT_PASSWORD", secrets.dbRootPassword, true);
    }
    this.registerOutputs({ imageParameterName: this.imageParameterName });
  }
}
