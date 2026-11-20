import type { FastifyInstance } from "fastify";
import { z } from "zod";
import type { OperationEvent } from "@infra/shared";
import type { AppContext } from "../context";
import { parse } from "./util";

export function operationRoutes(app: FastifyInstance, ctx: AppContext): void {
  const started = (op: { id: string; summary: unknown }) => ({ operationId: op.id, summary: op.summary });

  app.post("/api/operations/preview", async () => started(await ctx.workflows.preview(await ctx.store.load())));

  app.get("/api/preview", async () => ({ preview: ctx.workflows.getLastPreview() ?? null }));

  app.post("/api/operations/provision", async (request) => {
    const body = parse(z.object({ configHash: z.string().regex(/^[0-9a-f]{16}$/), confirmStackName: z.string().max(60), acceptCosts: z.literal(true) }), request.body);
    return started(await ctx.workflows.provision(await ctx.store.load(), body));
  });

  app.post("/api/operations/deploy", async () => started(await ctx.workflows.deploy(await ctx.store.load())));

  app.post("/api/operations/refresh", async () => started(await ctx.workflows.refresh(await ctx.store.load())));

  app.post("/api/operations/destroy", async (request) => {
    const body = parse(z.object({ confirmStackName: z.string().max(60), confirmPhrase: z.string().max(80) }), request.body);
    return started(await ctx.workflows.destroy(await ctx.store.load(), body));
  });

  app.get("/api/operations", async () => ({ operations: ctx.operations.list(), savedLogs: await ctx.operations.savedLogs() }));

  app.get("/api/operations/:id", async (request, reply) => {
    const { id } = parse(z.object({ id: z.uuid() }), request.params);
    const op = ctx.operations.get(id);
    if (!op) {
      return reply.code(404).send({ error: "Operação não encontrada." });
    }
    return { summary: op.summary, events: op.events };
  });

  app.get("/api/logs/:name", async (request) => {
    const { name } = parse(z.object({ name: z.string().regex(/^[\w.-]+\.jsonl$/) }), request.params);
    return { events: await ctx.operations.readSavedLog(name) };
  });

  /** Eventos ao vivo (Server-Sent Events). Reenvia os eventos anteriores a ?after=<seq>. */
  app.get("/api/operations/:id/events", async (request, reply) => {
    const { id } = parse(z.object({ id: z.uuid() }), request.params);
    const { after } = parse(z.object({ after: z.coerce.number().int().min(0).default(0) }), request.query);
    const op = ctx.operations.get(id);
    if (!op) {
      return reply.code(404).send({ error: "Operação não encontrada." });
    }
    reply.hijack();
    const res = reply.raw;
    res.writeHead(200, { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store", Connection: "keep-alive", "X-Content-Type-Options": "nosniff" });
    const send = (event: OperationEvent) => res.write(`id: ${event.seq}\ndata: ${JSON.stringify(event)}\n\n`);
    const sendSummary = () => res.write(`event: summary\ndata: ${JSON.stringify(op.summary)}\n\n`);
    op.events.filter((e) => e.seq > after).forEach(send);
    sendSummary();
    if (op.summary.status !== "running") {
      res.write("event: end\ndata: {}\n\n");
      res.end();
      return reply;
    }
    const onEvent = (e: OperationEvent) => {
      send(e);
      if (e.type === "step") {
        sendSummary();
      }
    };
    const onEnd = () => {
      sendSummary();
      res.write("event: end\ndata: {}\n\n");
      cleanup();
      res.end();
    };
    const ping = setInterval(() => res.write(": ping\n\n"), 15_000);
    const cleanup = () => {
      clearInterval(ping);
      op.emitter.off("event", onEvent);
      op.emitter.off("end", onEnd);
    };
    op.emitter.on("event", onEvent);
    op.emitter.on("end", onEnd);
    request.raw.on("close", cleanup);
    return reply;
  });
}
