/**
 * Conexão com a AWS mantida só na memória da API.
 * - Perfil da AWS CLI ou SSO (IAM Identity Center): o SDK lê ~/.aws e o cache do `aws sso login` (nada é copiado);
 * - credenciais temporárias: ficam só neste processo, nunca em disco, logs, respostas ou no navegador.
 * Credenciais root são recusadas.
 */
import { GetCallerIdentityCommand, STSClient } from "@aws-sdk/client-sts";
import { fromIni, fromSSO } from "@aws-sdk/credential-providers";
import { loadSharedConfigFiles } from "@smithy/shared-ini-file-loader";
import type { AwsCredentialIdentity, AwsCredentialIdentityProvider } from "@smithy/types";
import type { AwsConnectionInput, AwsConnectionStatus } from "@infra/shared";
import { forgetSecret, registerSecret } from "../services/redact";

export interface AwsProfileInfo {
  name: string;
  kind: "sso" | "keys" | "role" | "other";
  region?: string;
}

/** Perfis configurados em ~/.aws/config e ~/.aws/credentials (só os nomes e o tipo; nenhuma chave é lida para fora). */
export async function listProfiles(): Promise<AwsProfileInfo[]> {
  const files = await loadSharedConfigFiles({ ignoreCache: true });
  const names = new Set([...Object.keys(files.configFile ?? {}), ...Object.keys(files.credentialsFile ?? {})]);
  return [...names]
    .filter((n) => /^[\w.+@-]{1,64}$/.test(n))
    .sort()
    .map((name) => {
      const conf = files.configFile?.[name] ?? {};
      const cred = files.credentialsFile?.[name] ?? {};
      const kind: AwsProfileInfo["kind"] = conf.sso_session || conf.sso_start_url
        ? "sso"
        : conf.role_arn
          ? "role"
          : cred.aws_access_key_id || conf.aws_access_key_id
            ? "keys"
            : "other";
      return { name, kind, region: conf.region };
    });
}

export type StsFactory = (region: string, credentials: AwsCredentialIdentityProvider) => Pick<STSClient, "send">;
const defaultSts: StsFactory = (region, credentials) => new STSClient({ region, credentials, maxAttempts: 3 });

export class AwsSession {
  private input?: AwsConnectionInput;
  private provider?: AwsCredentialIdentityProvider;
  private status: AwsConnectionStatus = { connected: false };

  constructor(private readonly stsFactory: StsFactory = defaultSts) {}

  /** Valida as credenciais (STS GetCallerIdentity) e guarda a conexão só se der certo. */
  async connect(input: AwsConnectionInput): Promise<AwsConnectionStatus> {
    const provider = this.buildProvider(input);
    let identity;
    try {
      const sts = this.stsFactory(input.region, provider);
      identity = await sts.send(new GetCallerIdentityCommand({}));
    } catch (error) {
      if (input.mode === "temporary") {
        forgetSecret(input.secretAccessKey);
        forgetSecret(input.sessionToken);
      }
      return { connected: false, mode: input.mode, region: input.region, error: explainAuthError(error, input) };
    }
    const isRoot = Boolean(identity.Arn?.endsWith(":root"));
    if (isRoot) {
      return { connected: false, mode: input.mode, region: input.region, isRoot, error: "Credenciais da conta root não são aceitas: use um usuário IAM, um papel ou o SSO." };
    }
    this.disconnect();
    this.input = input;
    this.provider = provider;
    this.status = {
      connected: true,
      mode: input.mode,
      profile: input.mode === "temporary" ? undefined : input.profile,
      region: input.region,
      accountId: identity.Account,
      arn: identity.Arn,
      userId: identity.UserId,
      isRoot: false,
    };
    return this.status;
  }

  disconnect(): void {
    if (this.input?.mode === "temporary") {
      forgetSecret(this.input.secretAccessKey);
      forgetSecret(this.input.sessionToken);
    }
    this.input = undefined;
    this.provider = undefined;
    this.status = { connected: false };
  }

  getStatus(): AwsConnectionStatus {
    return { ...this.status };
  }

  /** Para os clientes do SDK: região + provedor de credenciais (com renovação automática no caso de SSO). */
  clientConfig(region?: string): { region: string; credentials: AwsCredentialIdentityProvider; maxAttempts: number } {
    if (!this.provider || !this.input) {
      throw new NotConnectedError();
    }
    return { region: region ?? this.input.region, credentials: this.provider, maxAttempts: 4 };
  }

  /**
   * Variáveis de ambiente para o processo do Pulumi (só no ambiente do processo filho, nunca em disco).
   * Resolve as credenciais na hora (renovando SSO/papéis quando preciso) e registra os valores no mascarador.
   */
  async envForSubprocess(region: string): Promise<Record<string, string>> {
    if (!this.provider) {
      throw new NotConnectedError();
    }
    const creds: AwsCredentialIdentity = await this.provider();
    registerSecret(creds.secretAccessKey);
    registerSecret(creds.sessionToken);
    const env: Record<string, string> = {
      AWS_ACCESS_KEY_ID: creds.accessKeyId,
      AWS_SECRET_ACCESS_KEY: creds.secretAccessKey,
      AWS_REGION: region,
      AWS_DEFAULT_REGION: region,
    };
    if (creds.sessionToken) {
      env.AWS_SESSION_TOKEN = creds.sessionToken;
    }
    return env;
  }

  private buildProvider(input: AwsConnectionInput): AwsCredentialIdentityProvider {
    switch (input.mode) {
      case "profile":
        return fromIni({ profile: input.profile, ignoreCache: true });
      case "sso":
        return fromSSO({ profile: input.profile });
      case "temporary": {
        registerSecret(input.secretAccessKey);
        registerSecret(input.sessionToken);
        const creds: AwsCredentialIdentity = {
          accessKeyId: input.accessKeyId,
          secretAccessKey: input.secretAccessKey,
          sessionToken: input.sessionToken,
        };
        return async () => creds;
      }
    }
  }
}

export class NotConnectedError extends Error {
  readonly statusCode = 409;
  constructor() {
    super("Conecte-se à AWS primeiro (menu Credenciais AWS).");
  }
}

export function explainAuthError(error: unknown, input: AwsConnectionInput): string {
  const name = (error as { name?: string })?.name ?? "";
  const message = (error as { message?: string })?.message ?? String(error);
  if (/SSO|token.*expired|refresh/i.test(message) && input.mode === "sso") {
    return `A sessão SSO do perfil ${input.profile} não está ativa ou expirou. Clique em "Entrar com SSO" (ou rode: aws sso login --profile ${input.profile}).`;
  }
  if (name === "CredentialsProviderError" || /could not load credentials|profile .* not found/i.test(message)) {
    return input.mode === "temporary" ? "Credenciais incompletas." : `Não foi possível ler o perfil "${input.profile}" em ~/.aws.`;
  }
  if (name === "InvalidClientTokenId" || name === "SignatureDoesNotMatch" || /security token.*invalid/i.test(message)) {
    return "A AWS recusou as credenciais (chave inválida ou revogada).";
  }
  if (name === "ExpiredToken" || /expired/i.test(message)) {
    return "As credenciais expiraram: gere novas credenciais temporárias.";
  }
  if (/ENOTFOUND|ECONNREFUSED|ETIMEDOUT|EAI_AGAIN/.test(message)) {
    return "Sem conexão com a AWS (verifique a internet ou o proxy).";
  }
  return `Falha ao validar as credenciais: ${name || "erro"}.`;
}
