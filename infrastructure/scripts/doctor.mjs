#!/usr/bin/env node
/**
 * Confere os pré-requisitos do painel. Não instala nada: só mostra o que falta e como instalar.
 *   node scripts/doctor.mjs          → sai com erro se faltar algo obrigatório
 *   node scripts/doctor.mjs --warn   → só avisa (usado pelo npm run dev)
 */
import { spawnSync } from "node:child_process";

const warnOnly = process.argv.includes("--warn");
const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: false, windowsHide: true, timeout: 20000 });
  return r.status === 0 ? (r.stdout || r.stderr).trim() : null;
};

const nodeMajor = Number(process.versions.node.split(".")[0]);
const checks = [
  { name: "Node.js 20+", ok: nodeMajor >= 20, info: process.versions.node, required: true, help: "winget install OpenJS.NodeJS.LTS" },
  { name: "Pulumi CLI", ok: Boolean(run("pulumi", ["version"])), info: run("pulumi", ["version"]), required: true, help: "winget install Pulumi.Pulumi" },
  { name: "Docker", ok: Boolean(run("docker", ["--version"])), info: run("docker", ["--version"]), required: true, help: "Instale o Docker Desktop (WSL 2) e abra-o" },
  { name: "Docker Engine rodando", ok: Boolean(run("docker", ["version", "--format", "{{.Server.Version}}"])), required: true, help: "Abra o Docker Desktop" },
  { name: "AWS CLI v2 (para SSO)", ok: Boolean(run("aws", ["--version"])), info: run("aws", ["--version"]), required: false, help: "winget install Amazon.AWSCLI" },
  { name: "PULUMI_CONFIG_PASSPHRASE", ok: Boolean(process.env.PULUMI_CONFIG_PASSPHRASE), required: false, help: "Opcional: também pode ser informada na tela Configurações" },
];

let missing = 0;
for (const c of checks) {
  const mark = c.ok ? "OK " : c.required ? "FALTA" : "aviso";
  if (!c.ok && c.required) missing += 1;
  console.log(`[${mark.padEnd(5)}] ${c.name}${c.ok && c.info ? ` — ${c.info.split("\n")[0]}` : ""}${c.ok ? "" : `  →  ${c.help}`}`);
}
if (missing) {
  console.log(`\n${missing} pré-requisito(s) obrigatório(s) faltando. O painel abre, mas provisionar/publicar vai falhar até instalar.`);
  if (!warnOnly) process.exit(1);
}
