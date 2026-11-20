import type { FastifyInstance } from "fastify";
import { z } from "zod";
import type { AppContext } from "../context";
import { parseStatusOutput } from "../aws/operations";
import { classifyHealth } from "../deployment/health";
import { parse } from "./util";

export function instanceRoutes(app: FastifyInstance, ctx: AppContext): void {
  /** Saídas do stack (não precisa da AWS; precisa da senha do estado). */
  async function outputs() {
    const stored = await ctx.store.load();
    const out = await ctx.stacks.outputs(stored.config).catch(() => ({}) as Record<string, unknown>);
    return { config: stored.config, out };
  }

  app.get("/api/stack", async () => {
    const { config, out } = await outputs();
    return { stackName: config.stackName, outputs: out, stacks: await ctx.stacks.listStacks().catch(() => []) };
  });

  /** Situação real: EC2 (SDK), contêineres e Docker (status.sh pelo SSM) e HTTP público. */
  app.get("/api/instances", async () => {
    const { config, out } = await outputs();
    const instanceId = typeof out.instanceId === "string" ? out.instanceId : undefined;
    if (!instanceId) {
      return { provisioned: false, stackName: config.stackName };
    }
    const region = String(out.region ?? config.instance.region);
    const ec2 = await ctx.aws.describe(region, instanceId);
    let ssmOnline: boolean | undefined;
    let status: ReturnType<typeof parseStatusOutput> | undefined;
    if (ec2?.state === "running") {
      ssmOnline = await ctx.aws.ssmOnline(region, instanceId).catch(() => false);
      if (ssmOnline) {
        const r = await ctx.aws.runFixed(region, instanceId, "status", 60).catch(() => null);
        status = r ? parseStatusOutput(r.output) : undefined;
      }
    }
    const appUrl = ec2?.publicIp && config.network.exposeApp
      ? `http://${ec2.publicIp}${config.application.hostPort === 80 ? "" : `:${config.application.hostPort}`}`
      : "";
    const http = appUrl && ec2?.state === "running" ? await ctx.http(`${appUrl}${config.application.healthPath}`) : undefined;
    const container = status?.containers.find((c) => /-app-\d+$|^app$/.test(c.name));
    return {
      provisioned: true,
      stackName: config.stackName,
      region,
      instance: ec2,
      ubuntu: status?.ubuntu ?? String(out.ubuntuVersion ?? ""),
      ssmOnline,
      docker: status ? { active: status.dockerActive, version: status.dockerVersion, bootstrapDone: status.bootstrapDone } : undefined,
      image: status?.image,
      containers: status?.containers ?? [],
      appUrl,
      http,
      health: classifyHealth({ ec2State: ec2?.state, ssmOnline, container, http }),
      outputs: out,
    };
  });

  app.post("/api/instances/action", async (request) => {
    const body = parse(z.object({ action: z.enum(["start", "stop", "reboot"]), confirmInstanceId: z.string().regex(/^i-[0-9a-f]{8,17}$/) }), request.body);
    const { config, out } = await outputs();
    if (out.instanceId !== body.confirmInstanceId) {
      throw Object.assign(new Error("A instância confirmada não é a deste stack."), { statusCode: 400 });
    }
    await ctx.aws.lifecycle(String(out.region ?? config.instance.region), body.confirmInstanceId, body.action);
    return { ok: true };
  });

  app.get("/api/instances/metrics", async () => {
    const { config, out } = await outputs();
    if (typeof out.instanceId !== "string") {
      return { cpu: [] };
    }
    return { cpu: await ctx.aws.cpuUtilization(String(out.region ?? config.instance.region), out.instanceId) };
  });

  /** Logs por comandos fixos do SSM (nenhum comando digitado chega à instância). */
  app.get("/api/instances/logs", async (request) => {
    const { kind } = parse(z.object({ kind: z.enum(["appLogs", "bootstrapLog"]) }), request.query);
    const { config, out } = await outputs();
    if (typeof out.instanceId !== "string") {
      throw Object.assign(new Error("Nenhuma instância provisionada."), { statusCode: 404 });
    }
    return ctx.aws.runFixed(String(out.region ?? config.instance.region), out.instanceId, kind, 120);
  });
}
