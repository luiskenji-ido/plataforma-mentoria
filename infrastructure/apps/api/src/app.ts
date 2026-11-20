import { existsSync } from "node:fs";
import fastifyStatic from "@fastify/static";
import Fastify, { type FastifyInstance } from "fastify";
import type { AppContext } from "./context";
import { awsRoutes } from "./routes/aws";
import { configRoutes } from "./routes/config";
import { instanceRoutes } from "./routes/instances";
import { operationRoutes } from "./routes/operations";
import { systemRoutes } from "./routes/system";
import { ValidationError } from "./routes/util";
import { registerSecurity } from "./security";
import { redact, safeErrorMessage } from "./services/redact";
import { allowedHosts, allowedOrigins } from "./settings";

export interface BuildOptions {
  logger?: boolean;
  csrfToken?: string;
  serveWeb?: boolean;
}

export async function buildApp(ctx: AppContext, options: BuildOptions = {}): Promise<FastifyInstance> {
  const app = Fastify({
    bodyLimit: 256 * 1024,
    requestTimeout: 6 * 60_000,
    logger: options.logger
      ? {
          level: "info",
          // Sem corpo, cabeçalhos ou query nos logs (podem ter credenciais)
          serializers: {
            req: (req: { method: string; url: string }) => ({ method: req.method, url: req.url.split("?")[0] }),
            res: (res: { statusCode: number }) => ({ statusCode: res.statusCode }),
          },
          hooks: {
            logMethod(args, method) {
              method.apply(this, args.map((a) => (typeof a === "string" ? redact(a) : a)) as Parameters<typeof method>);
            },
          },
        }
      : false,
  });

  registerSecurity(app, { allowedHosts: allowedHosts(ctx.settings), allowedOrigins: allowedOrigins(ctx.settings), csrfToken: options.csrfToken });

  app.setErrorHandler((error: Error & { statusCode?: number; validation?: unknown }, request, reply) => {
    const status = error instanceof ValidationError ? 400 : error.statusCode && error.statusCode >= 400 && error.statusCode < 600 ? error.statusCode : 500;
    if (status >= 500) {
      request.log.error({ err: safeErrorMessage(error) }, "erro na API");
    }
    const body: Record<string, unknown> = { error: status >= 500 && !(error.name?.includes("Error") && error.message) ? "Erro interno." : safeErrorMessage(error) };
    if (error instanceof ValidationError) {
      body.issues = error.issues;
    }
    void reply.code(status).send(body);
  });

  awsRoutes(app, ctx);
  configRoutes(app, ctx);
  operationRoutes(app, ctx);
  instanceRoutes(app, ctx);
  systemRoutes(app, ctx);
  app.get("/api/health", async () => ({ ok: true }));

  if (options.serveWeb && existsSync(ctx.settings.webDist)) {
    await app.register(fastifyStatic, { root: ctx.settings.webDist, prefix: "/", wildcard: false });
    app.setNotFoundHandler((request, reply) => {
      if (request.url.startsWith("/api/")) {
        return reply.code(404).send({ error: "Rota não encontrada." });
      }
      return reply.sendFile("index.html");
    });
  }
  return app;
}
