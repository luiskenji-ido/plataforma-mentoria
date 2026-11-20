/** Programa Pulumi com mocks do runtime: valida os recursos e as propriedades de segurança sem chamar a AWS. */
import * as pulumi from "@pulumi/pulumi";
import { beforeAll, describe, expect, it } from "vitest";
import { defaultDeploymentConfig, type DeploymentConfig } from "@infra/shared";

interface Created {
  type: string;
  name: string;
  inputs: Record<string, unknown>;
}

let created: Created[] = [];

beforeAll(() => {
  pulumi.runtime.setMocks(
    {
      newResource: (args) => {
        created.push({ type: args.type, name: args.name, inputs: args.inputs });
        const state: Record<string, unknown> = { ...args.inputs, arn: `arn:aws:mock:::${args.name}` };
        if (args.type === "aws:ecr/repository:Repository") state.repositoryUrl = `123456789012.dkr.ecr.sa-east-1.amazonaws.com/${args.inputs.name}`;
        if (args.type === "aws:ec2/instance:Instance") Object.assign(state, { publicIp: "203.0.113.7", privateIp: "10.42.1.10", publicDns: "ec2.example" });
        const n = created.length.toString(16).padStart(8, "0");
        const prefix = { "aws:ebs/volume:Volume": "vol-", "aws:ec2/instance:Instance": "i-", "aws:ec2/vpc:Vpc": "vpc-", "aws:ec2/subnet:Subnet": "subnet-" }[args.type];
        return { id: prefix ? `${prefix}0a${n}` : `${args.name}-id`, state };
      },
      call: (args) => {
        if (args.token === "aws:index/getCallerIdentity:getCallerIdentity") return { accountId: "123456789012", arn: "arn:aws:iam::123456789012:user/x", userId: "x" };
        if (args.token === "aws:index/getPartition:getPartition") return { partition: "aws", dnsSuffix: "amazonaws.com" };
        return args.inputs;
      },
    },
    "mentoria-infra",
    "teste",
    false,
  );
  pulumi.runtime.setConfig("mentoria-infra:appSecretKey", "chave-de-teste");
  pulumi.runtime.setConfig("mentoria-infra:dbPassword", "senha-db");
  pulumi.runtime.setConfig("mentoria-infra:dbRootPassword", "senha-root");
  pulumi.runtime.setConfig("mentoria-infra:secretEnv", JSON.stringify({ MAIL_PASSWORD: "segredo-mail" }));
});

async function run(config: DeploymentConfig) {
  created = [];
  const { createProgram } = await import("../program");
  const outputs = await createProgram(config)();
  await new Promise((r) => setTimeout(r, 50));
  const resolve = <T,>(o: pulumi.Output<T> | T) => new Promise<T>((r) => (pulumi.Output.isInstance(o) ? (o as pulumi.Output<T>).apply((v) => r(v)) : r(o as T)));
  return { outputs, resolve };
}

function base(): DeploymentConfig {
  const c = defaultDeploymentConfig();
  c.instance.amiId = "ami-0123456789abcdef0";
  c.application.env.push({ key: "MAIL_PASSWORD", value: "", secret: true, hasValue: true });
  return c;
}

const byType = (t: string) => created.filter((c) => c.type === t);

describe("programa Pulumi", () => {
  it("cria rede mínima, EC2 com IMDSv2, discos cifrados e ECR imutável", async () => {
    const { outputs, resolve } = await run(base());
    expect(byType("aws:ec2/vpc:Vpc")).toHaveLength(1);
    expect(byType("aws:ec2/internetGateway:InternetGateway")).toHaveLength(1);
    expect(byType("aws:ec2/natGateway:NatGateway")).toHaveLength(0);
    expect(created.some((c) => c.type.startsWith("aws:lb/"))).toBe(false);

    const instance = byType("aws:ec2/instance:Instance")[0]!;
    expect(instance.inputs.metadataOptions).toMatchObject({ httpTokens: "required" });
    expect(instance.inputs.rootBlockDevice).toMatchObject({ encrypted: true, volumeType: "gp3", volumeSize: 20 });
    expect(instance.inputs.ami).toBe("ami-0123456789abcdef0");

    expect(byType("aws:ebs/volume:Volume")[0]!.inputs.encrypted).toBe(true);
    expect(byType("aws:ec2/volumeAttachment:VolumeAttachment")[0]!.inputs.deviceName).toBe("/dev/sdf");
    expect(byType("aws:ecr/repository:Repository")[0]!.inputs).toMatchObject({ imageTagMutability: "IMMUTABLE", imageScanningConfiguration: { scanOnPush: true } });

    expect(await resolve(outputs.appUrl)).toBe("http://203.0.113.7");
  });

  it("Security Group sem SSH por padrão", async () => {
    await run(base());
    const sg = byType("aws:ec2/securityGroup:SecurityGroup")[0]!;
    const ingress = sg.inputs.ingress as { fromPort: number }[];
    expect(ingress.map((r) => r.fromPort)).toEqual([80]);
  });

  it("segredos viram SecureString; variáveis comuns viram String", async () => {
    await run(base());
    const params = byType("aws:ssm/parameter:Parameter").map((p) => ({ name: p.inputs.name as string, type: p.inputs.type as string }));
    const find = (suffix: string) => params.find((p) => p.name.endsWith(suffix));
    expect(find("/env/SECRET_KEY")?.type).toBe("SecureString");
    expect(find("/env/DATABASE_URL")?.type).toBe("SecureString");
    expect(find("/env/MAIL_PASSWORD")?.type).toBe("SecureString");
    expect(find("/db/MYSQL_ROOT_PASSWORD")?.type).toBe("SecureString");
    expect(find("/env/HOSPEDAGEM")?.type).toBe("String");
    expect(find("/image")?.type).toBe("String");
  });

  it("o user data não carrega segredos", async () => {
    await run(base());
    const instance = byType("aws:ec2/instance:Instance")[0]!;
    const userData = String(instance.inputs.userData);
    for (const secret of ["chave-de-teste", "senha-db", "senha-root", "segredo-mail"]) {
      expect(userData).not.toContain(secret);
    }
  });

  it("papel IAM com Session Manager e política mínima", async () => {
    await run(base());
    expect(byType("aws:iam/rolePolicyAttachment:RolePolicyAttachment")[0]!.inputs.policyArn).toBe("arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore");
    const assume = JSON.parse(String(byType("aws:iam/role:Role")[0]!.inputs.assumeRolePolicy));
    expect(assume.Statement[0].Principal.Service).toBe("ec2.amazonaws.com");
  });

  it("VPC existente: não cria rede", async () => {
    const c = base();
    c.network = { ...c.network, mode: "existing", existingVpcId: "vpc-0123456789abcdef0", existingSubnetId: "subnet-0123456789abcdef0" };
    await run(c);
    expect(byType("aws:ec2/vpc:Vpc")).toHaveLength(0);
    expect(byType("aws:ec2/subnet:Subnet")).toHaveLength(0);
    expect(byType("aws:ec2/instance:Instance")[0]!.inputs.subnetId).toBe("subnet-0123456789abcdef0");
  });

  it("sem AMI resolvida, o programa não cria nada", async () => {
    const c = base();
    delete c.instance.amiId;
    await expect(run(c)).rejects.toThrow(/AMI do Ubuntu não foi resolvida/);
  });
});
