/** Credenciais: STS GetCallerIdentity, recusa de root, mensagens claras e nada de segredo em respostas ou logs. */
import { GetCallerIdentityCommand, STSClient } from "@aws-sdk/client-sts";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, describe, expect, it } from "vitest";
import { AwsSession, explainAuthError } from "../src/aws/credentials";
import { redact } from "../src/services/redact";

const sts = mockClient(STSClient);
afterEach(() => sts.reset());

const TEMP = { mode: "temporary" as const, accessKeyId: "ASIAABCDEFGHIJKLMNOP", secretAccessKey: "SuperSegredo/abcdefghijklmnopqrstuvwxyz0123", sessionToken: "TokenDaSessao1234567890", region: "sa-east-1" };

describe("AwsSession", () => {
  it("conecta com credenciais temporárias e devolve só a identidade", async () => {
    sts.on(GetCallerIdentityCommand).resolves({ Account: "123456789012", Arn: "arn:aws:sts::123456789012:assumed-role/Dev/eu", UserId: "AROA:eu" });
    const s = new AwsSession();
    const status = await s.connect(TEMP);
    expect(status).toMatchObject({ connected: true, accountId: "123456789012", region: "sa-east-1", mode: "temporary" });
    const text = JSON.stringify(status);
    expect(text).not.toContain(TEMP.secretAccessKey);
    expect(text).not.toContain(TEMP.sessionToken);
    expect(text).not.toContain(TEMP.accessKeyId);
  });

  it("recusa credenciais da conta root", async () => {
    sts.on(GetCallerIdentityCommand).resolves({ Account: "123456789012", Arn: "arn:aws:iam::123456789012:root", UserId: "123456789012" });
    const s = new AwsSession();
    const status = await s.connect(TEMP);
    expect(status.connected).toBe(false);
    expect(status.error).toMatch(/root/);
    expect(s.getStatus().connected).toBe(false);
  });

  it("credencial recusada pela AWS: mensagem clara e não fica conectado", async () => {
    sts.on(GetCallerIdentityCommand).rejects(Object.assign(new Error("The security token included in the request is invalid."), { name: "InvalidClientTokenId" }));
    const s = new AwsSession();
    const status = await s.connect(TEMP);
    expect(status).toMatchObject({ connected: false, error: "A AWS recusou as credenciais (chave inválida ou revogada)." });
  });

  it("segredos temporários são mascarados nos logs e esquecidos ao desconectar", async () => {
    sts.on(GetCallerIdentityCommand).resolves({ Account: "1", Arn: "arn:aws:iam::1:user/x" });
    const s = new AwsSession();
    await s.connect(TEMP);
    expect(redact(`erro com ${TEMP.secretAccessKey} e ${TEMP.sessionToken}`)).toBe("erro com **** e ****");
    const env = await s.envForSubprocess("sa-east-1");
    expect(env).toMatchObject({ AWS_ACCESS_KEY_ID: TEMP.accessKeyId, AWS_REGION: "sa-east-1", AWS_SESSION_TOKEN: TEMP.sessionToken });
    s.disconnect();
    expect(redact(TEMP.secretAccessKey)).not.toBe("****");
    await expect(s.envForSubprocess("sa-east-1")).rejects.toThrow(/Conecte-se/);
  });

  it("sem conexão, não entrega configuração de cliente", () => {
    expect(() => new AwsSession().clientConfig()).toThrow(/Conecte-se/);
  });
});

describe("mensagens de erro", () => {
  it("SSO expirado orienta o login", () => {
    expect(explainAuthError(new Error("The SSO session associated with this profile has expired"), { mode: "sso", profile: "dev", region: "sa-east-1" })).toMatch(/aws sso login --profile dev/);
  });
  it("sem rede", () => {
    expect(explainAuthError(new Error("getaddrinfo ENOTFOUND sts.amazonaws.com"), { mode: "profile", profile: "dev", region: "sa-east-1" })).toMatch(/Sem conexão/);
  });
});

describe("redact", () => {
  it("mascara padrões conhecidos sem estragar texto comum", () => {
    expect(redact("AKIAABCDEFGHIJKLMNOP")).toBe("AKIA****************");
    expect(redact("mysql+pymysql://app:s3nh4@mysql:3306/db")).toBe("mysql+pymysql://app:****@mysql:3306/db");
    expect(redact('aws_secret_access_key = "abcdefghijklmnopqrstuvwxyz"')).toContain("****");
    expect(redact("PULUMI_CONFIG_PASSPHRASE=minhasenha")).toBe("PULUMI_CONFIG_PASSPHRASE=****");
    expect(redact("PULUMI_CONFIG_PASSPHRASE não definida")).toBe("PULUMI_CONFIG_PASSPHRASE não definida");
    expect(redact("password: hunter2")).toBe("password: ****");
  });
});
