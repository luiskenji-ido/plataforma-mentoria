/** Proteções do painel local: Host, Origin, CSRF, JSON, cabeçalhos e validação de entrada. */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { CSRF, HEADERS, fakeSession, makeApp } from "./helpers";
import type { AppContext } from "../src/context";
import { loadSettings } from "../src/settings";

let app: FastifyInstance;
beforeAll(async () => {
  ({ app } = await makeApp({ session: fakeSession(false) as unknown as AppContext["session"] }));
});
afterAll(() => app.close());

describe("acesso local", () => {
  it("recusa Host que não seja localhost (DNS rebinding)", async () => {
    const r = await app.inject({ method: "GET", url: "/api/aws/status", headers: { host: "atacante.example:3000" } });
    expect(r.statusCode).toBe(403);
  });

  it("entrega o token CSRF só para o próprio painel", async () => {
    const r = await app.inject({ method: "GET", url: "/api/session", headers: { host: "localhost:3000" } });
    expect(r.json()).toEqual({ csrfToken: CSRF });
    expect(r.headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("pedido que muda algo exige Origin do painel", async () => {
    const r = await app.inject({ method: "POST", url: "/api/aws/disconnect", headers: { ...HEADERS, origin: "https://site-malicioso.example" }, payload: "{}" });
    expect(r.statusCode).toBe(403);
    const sem = await app.inject({ method: "POST", url: "/api/aws/disconnect", headers: { host: "localhost:3000", "content-type": "application/json", "x-csrf-token": CSRF }, payload: "{}" });
    expect(sem.statusCode).toBe(403);
  });

  it("pedido que muda algo exige o token CSRF", async () => {
    const r = await app.inject({ method: "POST", url: "/api/aws/disconnect", headers: { ...HEADERS, "x-csrf-token": "errado" }, payload: "{}" });
    expect(r.statusCode).toBe(403);
    expect(r.json().error).toMatch(/Token/);
  });

  it("exige JSON (bloqueia formulários de outros sites)", async () => {
    const r = await app.inject({ method: "POST", url: "/api/aws/disconnect", headers: { ...HEADERS, "content-type": "text/plain" }, payload: "x" });
    expect(r.statusCode).toBe(415);
  });

  it("com tudo certo, aceita", async () => {
    const r = await app.inject({ method: "POST", url: "/api/aws/disconnect", headers: HEADERS, payload: "{}" });
    expect(r.statusCode).toBe(200);
  });

  it("envia cabeçalhos de segurança e no-store na API", async () => {
    const r = await app.inject({ method: "GET", url: "/api/health", headers: { host: "127.0.0.1:3000" } });
    expect(r.headers["x-frame-options"]).toBe("DENY");
    expect(r.headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(r.headers["cache-control"]).toBe("no-store");
  });
});

describe("validação de entrada", () => {
  it("credenciais com formato inválido: 400 com os campos, sem ecoar valores", async () => {
    const r = await app.inject({
      method: "POST",
      url: "/api/aws/connect",
      headers: HEADERS,
      payload: { mode: "temporary", accessKeyId: "nao-e-chave", secretAccessKey: "curto-demais-SEGREDO", region: "sa-east-1" },
    });
    expect(r.statusCode).toBe(400);
    expect(r.body).not.toContain("SEGREDO");
    expect(r.json().issues.map((i: { path: string }) => i.path)).toEqual(expect.arrayContaining(["accessKeyId", "secretAccessKey"]));
  });

  it("parâmetros de consulta validados (região)", async () => {
    const r = await app.inject({ method: "GET", url: "/api/aws/instance-types?region=../../etc", headers: { host: "localhost:3000" } });
    expect(r.statusCode).toBe(400);
  });

  it("nome de log não permite sair da pasta", async () => {
    const r = await app.inject({ method: "GET", url: "/api/logs/..%2F..%2Fconfig.json", headers: { host: "localhost:3000" } });
    expect(r.statusCode).toBe(400);
  });

  it("ações na instância exigem o ID confirmado", async () => {
    const r = await app.inject({ method: "POST", url: "/api/instances/action", headers: HEADERS, payload: { action: "terminate", confirmInstanceId: "i-123" } });
    expect(r.statusCode).toBe(400);
  });

  it("não existe rota de comando livre na instância", async () => {
    const r = await app.inject({ method: "GET", url: "/api/instances/logs?kind=rm%20-rf", headers: { host: "localhost:3000" } });
    expect(r.statusCode).toBe(400);
  });
});

describe("configuração do servidor", () => {
  it("por padrão escuta só em 127.0.0.1 e recusa expor na rede sem opt-in", () => {
    expect(loadSettings({}).host).toBe("127.0.0.1");
    expect(() => loadSettings({ INFRA_HOST: "0.0.0.0" })).toThrow(/exporia o painel/);
    expect(loadSettings({ INFRA_HOST: "0.0.0.0", INFRA_ALLOW_NETWORK: "1" }).host).toBe("0.0.0.0");
  });
});
