/**
 * Ações sobre a instância pelo SDK (sem Pulumi): ligar/desligar/reiniciar, métricas, comandos FIXOS pelo SSM
 * (status, logs, publicar) e o registro da imagem no Parameter Store. Não há execução de comando livre.
 */
import { CloudWatchClient, GetMetricDataCommand } from "@aws-sdk/client-cloudwatch";
import {
  DescribeInstanceStatusCommand,
  DescribeInstancesCommand,
  EC2Client,
  RebootInstancesCommand,
  StartInstancesCommand,
  StopInstancesCommand,
} from "@aws-sdk/client-ec2";
import { ECRClient, GetAuthorizationTokenCommand } from "@aws-sdk/client-ecr";
import {
  DescribeInstanceInformationCommand,
  GetCommandInvocationCommand,
  PutParameterCommand,
  SendCommandCommand,
  SSMClient,
} from "@aws-sdk/client-ssm";
import { APP_DIR, BOOTSTRAP_LOG } from "@infra/pulumi";
import { redact, registerSecret } from "../services/redact";
import type { AwsSession } from "./credentials";

/** Os únicos comandos que o painel executa na instância. */
export const FIXED_COMMANDS = {
  status: [`${APP_DIR}/status.sh`],
  deploy: [`${APP_DIR}/deploy.sh`],
  appLogs: [`docker compose --project-directory ${APP_DIR} -f ${APP_DIR}/docker-compose.yml logs --no-color --tail 200 app`],
  bootstrapLog: [`tail -n 200 ${BOOTSTRAP_LOG}`],
} as const;
export type FixedCommand = keyof typeof FIXED_COMMANDS;

export interface InstanceInfo {
  instanceId: string;
  state: string;
  instanceType?: string;
  publicIp?: string;
  privateIp?: string;
  launchTime?: string;
  availabilityZone?: string;
  name?: string;
  systemStatus?: string;
  instanceStatus?: string;
}

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

export class AwsOperations {
  constructor(private readonly session: AwsSession, private readonly wait: (ms: number) => Promise<void> = sleep) {}

  private ec2(region: string) {
    return new EC2Client(this.session.clientConfig(region));
  }

  private ssm(region: string) {
    return new SSMClient(this.session.clientConfig(region));
  }

  async describe(region: string, instanceId: string): Promise<InstanceInfo | null> {
    const out = await this.ec2(region).send(new DescribeInstancesCommand({ InstanceIds: [instanceId] })).catch((e: { name?: string }) => {
      if (e.name === "InvalidInstanceID.NotFound") {
        return null;
      }
      throw e;
    });
    const inst = out?.Reservations?.[0]?.Instances?.[0];
    if (!inst) {
      return null;
    }
    const status = await this.ec2(region).send(new DescribeInstanceStatusCommand({ InstanceIds: [instanceId], IncludeAllInstances: true }));
    const st = status.InstanceStatuses?.[0];
    return {
      instanceId,
      state: inst.State?.Name ?? "unknown",
      instanceType: inst.InstanceType,
      publicIp: inst.PublicIpAddress,
      privateIp: inst.PrivateIpAddress,
      launchTime: inst.LaunchTime?.toISOString(),
      availabilityZone: inst.Placement?.AvailabilityZone,
      name: inst.Tags?.find((t) => t.Key === "Name")?.Value,
      systemStatus: st?.SystemStatus?.Status,
      instanceStatus: st?.InstanceStatus?.Status,
    };
  }

  async lifecycle(region: string, instanceId: string, action: "start" | "stop" | "reboot"): Promise<void> {
    const ec2 = this.ec2(region);
    if (action === "start") {
      await ec2.send(new StartInstancesCommand({ InstanceIds: [instanceId] }));
    } else if (action === "stop") {
      await ec2.send(new StopInstancesCommand({ InstanceIds: [instanceId] }));
    } else {
      await ec2.send(new RebootInstancesCommand({ InstanceIds: [instanceId] }));
    }
  }

  async cpuUtilization(region: string, instanceId: string, hours = 3): Promise<{ time: string; value: number }[]> {
    const cw = new CloudWatchClient(this.session.clientConfig(region));
    const end = new Date();
    const out = await cw.send(new GetMetricDataCommand({
      StartTime: new Date(end.getTime() - hours * 3600_000),
      EndTime: end,
      MetricDataQueries: [{
        Id: "cpu",
        MetricStat: {
          Metric: { Namespace: "AWS/EC2", MetricName: "CPUUtilization", Dimensions: [{ Name: "InstanceId", Value: instanceId }] },
          Period: 300,
          Stat: "Average",
        },
      }],
    }));
    const r = out.MetricDataResults?.[0];
    return (r?.Timestamps ?? [])
      .map((t, i) => ({ time: t.toISOString(), value: Math.round((r?.Values?.[i] ?? 0) * 10) / 10 }))
      .sort((a, b) => a.time.localeCompare(b.time));
  }

  /** A instância aparece no Systems Manager (agente rodando e papel IAM certo)? */
  async ssmOnline(region: string, instanceId: string): Promise<boolean> {
    const out = await this.ssm(region).send(new DescribeInstanceInformationCommand({ Filters: [{ Key: "InstanceIds", Values: [instanceId] }] }));
    return out.InstanceInformationList?.[0]?.PingStatus === "Online";
  }

  async waitSsmOnline(region: string, instanceId: string, timeoutMs: number, onWait?: (msg: string) => void): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await this.ssmOnline(region, instanceId).catch(() => false)) {
        return;
      }
      onWait?.("Aguardando o agente do Systems Manager na instância…");
      await this.wait(10_000);
    }
    throw new Error("A instância não ficou disponível no Systems Manager a tempo (agente SSM, papel IAM ou saída para a internet).");
  }

  /** Roda um dos comandos fixos e espera o resultado (saída mascarada). */
  async runFixed(region: string, instanceId: string, command: FixedCommand, timeoutSeconds = 600): Promise<{ status: string; output: string }> {
    const ssm = this.ssm(region);
    const sent = await ssm.send(new SendCommandCommand({
      InstanceIds: [instanceId],
      DocumentName: "AWS-RunShellScript",
      Comment: `painel: ${command}`,
      TimeoutSeconds: timeoutSeconds,
      Parameters: { commands: [...FIXED_COMMANDS[command]], executionTimeout: [String(timeoutSeconds)] },
    }));
    const commandId = sent.Command?.CommandId;
    if (!commandId) {
      throw new Error("O Systems Manager não aceitou o comando.");
    }
    const deadline = Date.now() + (timeoutSeconds + 60) * 1000;
    await this.wait(2000);
    while (Date.now() < deadline) {
      const inv = await ssm.send(new GetCommandInvocationCommand({ CommandId: commandId, InstanceId: instanceId })).catch((e: { name?: string }) => {
        if (e.name === "InvocationDoesNotExist") {
          return null;
        }
        throw e;
      });
      if (inv && !["Pending", "InProgress", "Delayed"].includes(inv.Status ?? "")) {
        const output = [inv.StandardOutputContent, inv.StandardErrorContent].filter(Boolean).join("\n");
        return { status: inv.Status ?? "Unknown", output: redact(output) };
      }
      await this.wait(3000);
    }
    throw new Error(`O comando ${command} não terminou a tempo.`);
  }

  async putImage(region: string, parameterName: string, imageUri: string): Promise<void> {
    if (!/^\/[A-Za-z0-9_./-]+\/image$/.test(parameterName)) {
      throw new Error("Parâmetro da imagem inválido.");
    }
    await this.ssm(region).send(new PutParameterCommand({ Name: parameterName, Value: imageUri, Type: "String", Overwrite: true }));
  }

  /** Senha temporária do ECR (12 h) para o docker login local, entregue pelo stdin e mascarada nos logs. */
  async ecrLogin(region: string): Promise<{ registry: string; username: string; password: string }> {
    const out = await new ECRClient(this.session.clientConfig(region)).send(new GetAuthorizationTokenCommand({}));
    const data = out.authorizationData?.[0];
    if (!data?.authorizationToken || !data.proxyEndpoint) {
      throw new Error("O ECR não devolveu o token de acesso.");
    }
    const [username, password] = Buffer.from(data.authorizationToken, "base64").toString("utf8").split(":");
    registerSecret(password);
    registerSecret(data.authorizationToken);
    return { registry: data.proxyEndpoint.replace(/^https:\/\//, ""), username: username ?? "AWS", password: password ?? "" };
  }
}

/** Interpreta a saída do status.sh. */
export function parseStatusOutput(output: string) {
  const values: Record<string, string> = {};
  const containers: { name: string; state: string; status: string }[] = [];
  for (const line of output.split(/\r?\n/)) {
    const m = /^([a-z_]+)=(.*)$/.exec(line.trim());
    if (!m) {
      continue;
    }
    if (m[1] === "container") {
      const [name = "", state = "", status = ""] = (m[2] ?? "").split("|");
      containers.push({ name, state, status });
    } else {
      values[m[1]!] = m[2] ?? "";
    }
  }
  return {
    bootstrapDone: values.bootstrap === "done",
    dockerActive: values.docker === "active",
    dockerVersion: values.docker_version || undefined,
    ubuntu: values.ubuntu || undefined,
    image: values.image || undefined,
    containers,
  };
}
