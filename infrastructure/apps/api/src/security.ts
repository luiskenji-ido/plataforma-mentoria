import { randomBytes, timingSafeEqual } from "node:crypto";
import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export interface SecurityOptions {
  allowedHosts: Set<string>;
  allowedOrigins: Set<string>;
  /** Token anti-CSRF desta execução da API (o painel busca em GET /api/session, que só o próprio site consegue ler). */
  csrfToken?: string;
}

export function newCsrfToken(): string {
  return randomBytes(32).toString("base64url");
}

function sameToken(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

/**
 * Proteções do painel local:
 * - Host: só localhost/127.0.0.1 nas portas do painel (bloqueia DNS rebinding);
 * - pedidos que mudam algo: Origin do próprio painel + cabeçalho X-CSRF-Token + JSON (bloqueia CSRF de outros sites);
 * - cabeçalhos de segurança e nada de CORS.
 */
export function registerSecurity(app: FastifyInstance, options: SecurityOptions): string {
  const token = options.csrfToken ?? newCsrfToken();

  app.addHook("onRequest", async (request: FastifyRequest, reply: FastifyReply) => {
    const host = (request.headers.host ?? "").toLowerCase();
    if (!options.allowedHosts.has(host)) {
      return reply.code(403).send({ error: "Acesso permitido só pelo endereço local do painel (localhost)." });
    }
    if (SAFE_METHODS.has(request.method)) {
      return undefined;
    }
    const origin = request.headers.origin;
    if (!origin || !options.allowedOrigins.has(origin)) {
      return reply.code(403).send({ error: "Origem não autorizada." });
    }
    const sent = request.headers["x-csrf-token"];
    if (typeof sent !== "string" || !sameToken(sent, token)) {
      return reply.code(403).send({ error: "Token de segurança ausente ou expirado: recarregue o painel." });
    }
    const type = request.headers["content-type"] ?? "";
    if (request.method !== "DELETE" && !type.startsWith("application/json")) {
      return reply.code(415).send({ error: "Envie JSON." });
    }
    return undefined;
  });

  app.addHook("onSend", async (request, reply, payload) => {
    reply.header("X-Content-Type-Options", "nosniff");
    reply.header("X-Frame-Options", "DENY");
    reply.header("Referrer-Policy", "no-referrer");
    reply.header("Cross-Origin-Opener-Policy", "same-origin");
    reply.header("Cross-Origin-Resource-Policy", "same-origin");
    reply.header(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    );
    if (request.url.startsWith("/api/")) {
      reply.header("Cache-Control", "no-store");
    }
    return payload;
  });

  app.get("/api/session", async () => ({ csrfToken: token }));
  return token;
}
