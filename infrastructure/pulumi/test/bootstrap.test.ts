import { describe, expect, it } from "vitest";
import { defaultDeploymentConfig } from "@infra/shared";
import { ingressRules, instancePolicyDocument, lifecyclePolicy, renderCompose, renderDeployScript, renderUserData, ssmPrefixFor } from "../index";

const config = { ...defaultDeploymentConfig(), instance: { ...defaultDeploymentConfig().instance, amiId: "ami-0123456789abcdef0" } };
const input = { config, region: "sa-east-1", ssmPrefix: ssmPrefixFor("mentoria", config.stackName), volumes: [{ volumeId: "vol-0abc123", mountPath: "/data", deviceName: "/dev/sdf" }] };

describe("bootstrap (user data)", () => {
  const script = renderUserData(input);

  it("instala o Docker pelo repositório oficial e o plugin compose", () => {
    expect(script).toContain("https://download.docker.com/linux/ubuntu/gpg");
    expect(script).toContain("docker-compose-plugin");
    expect(script).toContain("systemctl enable --now docker");
  });

  it("monta o volume pelo UUID com nofail e só formata volume vazio", () => {
    expect(script).toContain("mount_volume vol-0abc123 /data /dev/sdf");
    expect(script).toMatch(/UUID=\$uuid \$dir ext4 defaults,nofail/);
    expect(script).toMatch(/if ! blkid "\$dev"/);
  });

  it("habilita a unidade systemd (a aplicação volta depois de reiniciar)", () => {
    expect(script).toContain("systemctl enable app.service");
    expect(script).toContain("RequiresMountsFor=/data");
  });

  it("não contém segredos: só o caminho dos parâmetros do SSM", () => {
    expect(script).not.toMatch(/SECRET_KEY=|MYSQL_PASSWORD=|password=/i);
    expect(script).toContain(`${input.ssmPrefix}/env/`);
  });

  it("recusa valores inseguros (defesa em profundidade)", () => {
    expect(() => renderUserData({ ...input, volumes: [{ volumeId: "vol-1; rm -rf /", mountPath: "/data", deviceName: "/dev/sdf" }] })).toThrow(/inseguro/);
    expect(() => renderUserData({ ...input, ssmPrefix: "/x $(id)" })).toThrow(/inseguro/);
  });
});

describe("docker compose da EC2", () => {
  const compose = renderCompose(config);
  it("publica a porta, monta os volumes e tem health check", () => {
    expect(compose).toContain('- "80:8080"');
    expect(compose).toContain("- /data/uploads:/app/uploads");
    expect(compose).toContain("healthcheck:");
    expect(compose).toContain("http://127.0.0.1:8080/");
    expect(compose).toContain("restart: unless-stopped");
  });
  it("sobe o MySQL com dados no volume e o app depende dele saudável", () => {
    expect(compose).toContain("image: mysql:8.4");
    expect(compose).toContain("- /data/mysql:/var/lib/mysql");
    expect(compose).toContain("condition: service_healthy");
  });
  it("sem banco não declara o MySQL", () => {
    const sem = renderCompose({ ...config, application: { ...config.application, database: { ...config.application.database, enabled: false } } });
    expect(sem).not.toContain("mysql");
  });
});

describe("script de publicação", () => {
  it("autentica no ECR pelo papel IAM e lê segredos do SSM com decryption", () => {
    const s = renderDeployScript("sa-east-1", "/mentoria-infra/x", true);
    expect(s).toContain("aws ecr get-login-password --region sa-east-1 | docker login --username AWS --password-stdin");
    expect(s).toContain("--with-decryption");
    expect(s).toContain("umask 077");
    expect(s).toContain('if [ "$IMAGE" = "none" ]');
  });
});

describe("rede e IAM", () => {
  it("por padrão só a porta do app fica aberta (SSH fechado)", () => {
    const rules = ingressRules(config);
    expect(rules).toHaveLength(1);
    expect(rules[0]).toMatchObject({ fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] });
  });
  it("sem expor o app, nenhuma porta de entrada", () => {
    expect(ingressRules({ ...config, network: { ...config.network, exposeApp: false } })).toEqual([]);
  });
  it("a política da instância é mínima (repositório e prefixo do stack)", () => {
    const doc = JSON.parse(instancePolicyDocument("arn:aws:ecr:sa-east-1:1:repository/m/x", "arn:aws:ssm:sa-east-1:1:parameter/m-infra/x"));
    const pull = doc.Statement.find((s: { Sid: string }) => s.Sid === "EcrPullAppImages");
    expect(pull.Resource).toBe("arn:aws:ecr:sa-east-1:1:repository/m/x");
    expect(pull.Action).not.toContain("ecr:PutImage");
    const params = doc.Statement.find((s: { Sid: string }) => s.Sid === "ReadAppParameters");
    expect(params.Resource).toEqual(["arn:aws:ssm:sa-east-1:1:parameter/m-infra/x", "arn:aws:ssm:sa-east-1:1:parameter/m-infra/x/*"]);
    expect(JSON.stringify(doc)).not.toMatch(/"Action":"\*"|ssm:PutParameter|iam:/);
  });
  it("o ECR guarda só as imagens recentes", () => {
    expect(JSON.parse(lifecyclePolicy(5)).rules[0].selection.countNumber).toBe(5);
  });
});
