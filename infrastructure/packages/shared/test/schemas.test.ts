import { describe, expect, it } from "vitest";
import { awsConnectionSchema, cidrContains, defaultDeploymentConfig, deploymentConfigSchema, type DeploymentConfig } from "../src";

function issues(config: DeploymentConfig) {
  const r = deploymentConfigSchema.safeParse(config);
  return r.success ? [] : r.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`);
}

function withChange(fn: (c: DeploymentConfig) => void): DeploymentConfig {
  const c = structuredClone(defaultDeploymentConfig());
  fn(c);
  return c;
}

describe("configuração da implantação", () => {
  it("a configuração padrão é válida", () => {
    expect(issues(defaultDeploymentConfig())).toEqual([]);
  });

  it("recusa SSH aberto para a internet inteira", () => {
    const c = withChange((x) => {
      x.network.ssh = { enabled: true, allowedCidrs: ["0.0.0.0/0"] };
    });
    expect(issues(c).join()).toMatch(/SSH aberto/);
  });

  it("aceita SSH de um IP específico", () => {
    const c = withChange((x) => {
      x.network.ssh = { enabled: true, allowedCidrs: ["203.0.113.10/32"] };
    });
    expect(issues(c)).toEqual([]);
  });

  it("exige a sub-rede dentro da VPC e a zona da região", () => {
    const c = withChange((x) => {
      x.network.subnetCidr = "192.168.1.0/24";
      x.network.availabilityZone = "us-east-1a";
    });
    const list = issues(c).join("\n");
    expect(list).toMatch(/network.subnetCidr: A sub-rede precisa estar dentro/);
    expect(list).toMatch(/network.availabilityZone: A zona precisa ser da região/);
  });

  it("respeita os limites de tamanho de cada tipo de EBS", () => {
    const c = withChange((x) => {
      x.dataVolumes[0] = { ...x.dataVolumes[0]!, type: "st1", sizeGb: 100 };
    });
    expect(issues(c).join()).toMatch(/st1 aceita de 125/);
  });

  it("recusa ponto de montagem do sistema e caminho com ..", () => {
    expect(issues(withChange((x) => (x.dataVolumes[0]!.mountPath = "/etc/dados"))).join()).toMatch(/caminho é do sistema/);
    expect(issues(withChange((x) => (x.dataVolumes[0]!.mountPath = "/data/../etc"))).length).toBeGreaterThan(0);
  });

  it("pastas do app precisam ficar num volume de dados", () => {
    const c = withChange((x) => x.application.volumes.push({ hostPath: "/srv/fora", containerPath: "/app/x" }));
    expect(issues(c).join()).toMatch(/dentro de um volume de dados/);
  });

  it("MySQL exige volume de dados", () => {
    const c = withChange((x) => {
      x.dataVolumes = [];
      x.application.volumes = [];
    });
    expect(issues(c).join()).toMatch(/MySQL precisa de um volume/);
  });

  it("recusa variáveis reservadas, repetidas ou com quebra de linha/aspas", () => {
    expect(issues(withChange((x) => x.application.env.push({ key: "SECRET_KEY", value: "x", secret: true }))).join()).toMatch(/gerada pelo painel/);
    expect(issues(withChange((x) => x.application.env.push({ key: "HOSPEDAGEM", value: "y", secret: false }))).join()).toMatch(/repetidas/);
    expect(issues(withChange((x) => x.application.env.push({ key: "A", value: "l1\nl2", secret: false }))).join()).toMatch(/quebra de linha/);
    expect(issues(withChange((x) => x.application.env.push({ key: "B", value: "it's", secret: false }))).join()).toMatch(/aspas simples/);
    expect(issues(withChange((x) => x.application.env.push({ key: "minuscula", value: "v", secret: false }))).length).toBeGreaterThan(0);
  });

  it("caminhos do Dockerfile não podem sair do repositório", () => {
    expect(issues(withChange((x) => (x.application.dockerfile = "../outro/Dockerfile"))).join()).toMatch(/fora do projeto/);
    expect(issues(withChange((x) => (x.application.buildContext = "a/../../b"))).join()).toMatch(/fora do projeto/);
  });

  it("app exposto precisa de IP público e de faixas autorizadas", () => {
    expect(issues(withChange((x) => (x.network.assignPublicIp = false))).join()).toMatch(/IP público/);
    expect(issues(withChange((x) => (x.network.appAllowedCidrs = []))).join()).toMatch(/quem pode acessar/);
  });

  it("VPC existente exige VPC e sub-rede", () => {
    expect(issues(withChange((x) => (x.network.mode = "existing"))).join()).toMatch(/VPC e a sub-rede/);
  });

  it("nomes de stack e de instância seguros", () => {
    expect(issues(withChange((x) => (x.stackName = "Stack com espaço"))).length).toBeGreaterThan(0);
    expect(issues(withChange((x) => (x.instance.name = "nome; rm -rf /"))).length).toBeGreaterThan(0);
    expect(issues(withChange((x) => (x.instance.amiId = "ami-xyz"))).length).toBeGreaterThan(0);
  });
});

describe("CIDR", () => {
  it("contém", () => {
    expect(cidrContains("10.0.0.0/16", "10.0.5.0/24")).toBe(true);
    expect(cidrContains("10.0.0.0/16", "10.1.0.0/24")).toBe(false);
    expect(cidrContains("10.0.0.0/24", "10.0.0.0/16")).toBe(false);
  });
});

describe("conexão com a AWS", () => {
  it("valida o formato das credenciais temporárias", () => {
    const ok = awsConnectionSchema.safeParse({ mode: "temporary", accessKeyId: "ASIAABCDEFGHIJKLMNOP", secretAccessKey: "x".repeat(40), sessionToken: "", region: "sa-east-1" });
    expect(ok.success).toBe(true);
    expect(ok.success && ok.data.mode === "temporary" && ok.data.sessionToken).toBeUndefined();
    expect(awsConnectionSchema.safeParse({ mode: "temporary", accessKeyId: "XYZ", secretAccessKey: "x".repeat(40), region: "sa-east-1" }).success).toBe(false);
  });

  it("recusa perfil com caracteres estranhos e região desconhecida", () => {
    expect(awsConnectionSchema.safeParse({ mode: "profile", profile: "a b;c", region: "sa-east-1" }).success).toBe(false);
    expect(awsConnectionSchema.safeParse({ mode: "profile", profile: "dev", region: "mars-1" }).success).toBe(false);
  });
});
