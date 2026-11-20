import type { FastifyInstance } from "fastify";
import { deploymentConfigSchema } from "@infra/shared";
import type { AppContext } from "../context";
import { estimateCost } from "../aws/pricing";
import { configHash, splitSecrets } from "../services/configStore";
import { detectProject } from "../services/project";
import { parse } from "./util";

export function configRoutes(app: FastifyInstance, ctx: AppContext): void {
  app.get("/api/project", async () => detectProject(ctx.settings.repoRoot));

  app.get("/api/config", async () => {
    const stored = await ctx.store.load();
    return { ...stored, configHash: configHash(stored.config, stored.secretsVersion) };
  });

  /**
   * Grava a configuração. Valores de variáveis secretas vão direto para a configuração cifrada do stack (Pulumi);
   * em disco e nas respostas fica só "hasValue". A AMI escolhida é conferida na AWS (dona = Canonical).
   */
  app.put("/api/config", async (request) => {
    const config = parse(deploymentConfigSchema, request.body);
    const current = await ctx.store.load();
    if (current.config.stackName !== config.stackName && ctx.operations.isBusy(current.config.stackName)) {
      throw Object.assign(new Error("Há uma operação em andamento: espere terminar para trocar o stack."), { statusCode: 409 });
    }
    const { secretValues } = splitSecrets(config);
    if (Object.keys(secretValues).length) {
      await ctx.stacks.ensureSecrets(config, secretValues);
    }
    const stored = await ctx.store.save(config, Object.keys(secretValues).length > 0);
    return { ...stored, configHash: configHash(stored.config, stored.secretsVersion) };
  });

  /** Resolve a AMI oficial do Ubuntu da configuração atual (região + versão + arquitetura). */
  app.post("/api/config/resolve-ami", async () => {
    const stored = await ctx.store.load();
    const { region, ubuntuVersion, architecture } = stored.config.instance;
    const image = await ctx.catalog.resolveUbuntu(region, ubuntuVersion, architecture);
    if (!image) {
      throw Object.assign(new Error(`O Ubuntu ${ubuntuVersion} (${architecture}) não está disponível em ${region}.`), { statusCode: 404 });
    }
    const config = { ...stored.config, instance: { ...stored.config.instance, amiId: image.amiId, amiName: image.name } };
    const saved = await ctx.store.save(config, false);
    return { image, ...saved, configHash: configHash(saved.config, saved.secretsVersion) };
  });

  app.get("/api/costs", async () => {
    const stored = await ctx.store.load();
    if (!ctx.session.getStatus().connected) {
      throw Object.assign(new Error("Conecte-se à AWS para consultar os preços."), { statusCode: 409 });
    }
    return estimateCost(stored.config, ctx.prices);
  });
}
