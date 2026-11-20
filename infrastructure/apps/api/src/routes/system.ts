import type { FastifyInstance } from "fastify";
import { z } from "zod";
import type { AppContext } from "../context";
import { MIN_PASSPHRASE } from "../pulumi/stacks";
import { parse } from "./util";

export interface ToolCheck {
  name: string;
  ok: boolean;
  version?: string;
  required: boolean;
  help: string;
}

const MIN_NODE_MAJOR = 20;

export async function checkTools(ctx: Pick<AppContext, "runner">): Promise<ToolCheck[]> {
  const version = async (cmd: string, args: string[], pick: (out: string) => string | undefined) => {
    const r = await ctx.runner(cmd, args, { timeoutMs: 20_000 }).catch(() => null);
    return r && r.code === 0 ? pick(r.stdout.trim()) : undefined;
  };
  const node = process.versions.node;
  const [pulumi, docker, dockerServer, aws, git] = await Promise.all([
    version("pulumi", ["version"], (o) => o.replace(/^v/, "")),
    version("docker", ["--version"], (o) => /(\d+\.\d+\.\d+)/.exec(o)?.[1]),
    version("docker", ["version", "--format", "{{.Server.Version}}"], (o) => o || undefined),
    version("aws", ["--version"], (o) => /aws-cli\/(\S+)/.exec(o)?.[1]),
    version("git", ["--version"], (o) => /(\d+\.\d+\.\d+)/.exec(o)?.[1]),
  ]);
  return [
    { name: "Node.js", ok: Number(node.split(".")[0]) >= MIN_NODE_MAJOR, version: node, required: true, help: `Instale o Node.js ${MIN_NODE_MAJOR}+ LTS: winget install OpenJS.NodeJS.LTS` },
    { name: "Pulumi CLI", ok: Boolean(pulumi), version: pulumi, required: true, help: "winget install Pulumi.Pulumi (ou https://www.pulumi.com/docs/install/)" },
    { name: "Docker (cliente)", ok: Boolean(docker), version: docker, required: true, help: "Instale o Docker Desktop (com WSL 2): https://www.docker.com/products/docker-desktop/" },
    { name: "Docker Engine rodando", ok: Boolean(dockerServer), version: dockerServer, required: true, help: "Abra o Docker Desktop e espere \"Engine running\"." },
    { name: "AWS CLI v2", ok: Boolean(aws), version: aws, required: false, help: "Necessária só para o login SSO: winget install Amazon.AWSCLI" },
    { name: "Git", ok: Boolean(git), version: git, required: false, help: "Usado para marcar a imagem com o commit." },
  ];
}

export function systemRoutes(app: FastifyInstance, ctx: AppContext): void {
  app.get("/api/doctor", async () => ({
    tools: await checkTools(ctx),
    passphraseSet: ctx.stacks.hasPassphrase(),
    aws: ctx.session.getStatus(),
  }));

  app.get("/api/settings", async () => ({
    passphraseSet: ctx.stacks.hasPassphrase(),
    stateDir: ctx.settings.stateDir,
    backendUrl: ctx.stacks.backendUrl(),
    repoRoot: ctx.settings.repoRoot,
    host: ctx.settings.host,
    port: ctx.settings.port,
  }));

  /** A senha fica só na memória desta execução da API (não é gravada em disco). */
  app.post("/api/settings/passphrase", async (request) => {
    const { passphrase } = parse(z.object({ passphrase: z.string().min(MIN_PASSPHRASE, `Use pelo menos ${MIN_PASSPHRASE} caracteres.`).max(256) }), request.body);
    ctx.stacks.setPassphrase(passphrase);
    return { passphraseSet: true };
  });
}
