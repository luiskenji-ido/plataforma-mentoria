import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { ARCHITECTURES, AWS_REGIONS, awsConnectionSchema, regionSchema } from "@infra/shared";
import { listProfiles } from "../aws/credentials";
import type { AppContext } from "../context";
import { parse } from "./util";

const regionQuery = z.object({ region: regionSchema });

export function awsRoutes(app: FastifyInstance, ctx: AppContext): void {
  app.get("/api/aws/status", async () => ctx.session.getStatus());

  app.get("/api/aws/profiles", async () => ({ profiles: await listProfiles().catch(() => []) }));

  app.post("/api/aws/connect", async (request) => {
    const input = parse(awsConnectionSchema, request.body);
    return ctx.session.connect(input);
  });

  app.post("/api/aws/disconnect", async () => {
    ctx.session.disconnect();
    return { connected: false };
  });

  /** Abre o login do IAM Identity Center no navegador (fluxo oficial da AWS CLI; o painel nunca vê senha). */
  app.post("/api/aws/sso-login", async (request) => {
    const { profile } = parse(z.object({ profile: z.string().regex(/^[\w.+@-]{1,64}$/) }), request.body);
    const r = await ctx.runner("aws", ["sso", "login", "--profile", profile], { timeoutMs: 5 * 60_000 });
    if (r.code !== 0) {
      return { ok: false, error: `O login SSO não foi concluído: ${(r.stderr || r.stdout).split("\n").slice(-3).join(" ").trim()}` };
    }
    return { ok: true };
  });

  app.get("/api/aws/regions", async () => ({ regions: AWS_REGIONS }));

  app.get("/api/aws/instance-types", async (request) => {
    const { region } = parse(regionQuery, request.query);
    return { instanceTypes: await ctx.catalog.instanceTypes(region) };
  });

  app.get("/api/aws/ubuntu", async (request) => {
    const q = parse(regionQuery.extend({ architecture: z.enum(ARCHITECTURES) }), request.query);
    return { images: await ctx.catalog.ubuntuVersions(q.region, q.architecture) };
  });

  app.get("/api/aws/zones", async (request) => {
    const { region } = parse(regionQuery, request.query);
    return { zones: await ctx.catalog.availabilityZones(region) };
  });

  app.get("/api/aws/vpcs", async (request) => {
    const { region } = parse(regionQuery, request.query);
    return { vpcs: await ctx.catalog.vpcs(region) };
  });

  app.get("/api/aws/subnets", async (request) => {
    const q = parse(regionQuery.extend({ vpcId: z.string().regex(/^vpc-[0-9a-f]{8,17}$/) }), request.query);
    return { subnets: await ctx.catalog.subnets(q.region, q.vpcId) };
  });
}
