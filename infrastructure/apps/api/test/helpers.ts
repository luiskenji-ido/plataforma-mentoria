import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defaultDeploymentConfig, type AwsConnectionStatus, type DeploymentConfig } from "@infra/shared";
import { buildApp } from "../src/app";
import { createContext, type AppContext } from "../src/context";
import type { Settings } from "../src/settings";

export const CSRF = "token-de-teste-1234567890";
export const HEADERS = { host: "localhost:3000", origin: "http://localhost:3000", "x-csrf-token": CSRF, "content-type": "application/json" };

export function testSettings(): Settings {
  const dir = mkdtempSync(path.join(tmpdir(), "infra-test-"));
  return { host: "127.0.0.1", port: 3001, publicPort: 3000, stateDir: dir, repoRoot: path.resolve(import.meta.dirname, "..", "..", "..", ".."), webDist: path.join(dir, "web"), allowNetwork: false };
}

export function readyConfig(): DeploymentConfig {
  const c = defaultDeploymentConfig();
  c.stackName = "mentoria-test";
  c.instance.amiId = "ami-0123456789abcdef0";
  return c;
}

/** Sessão AWS falsa (conectada) que nunca vai à rede. */
export function fakeSession(connected = true) {
  const status: AwsConnectionStatus = connected
    ? { connected: true, mode: "profile", profile: "dev", region: "sa-east-1", accountId: "123456789012", arn: "arn:aws:iam::123456789012:user/dev" }
    : { connected: false };
  return {
    getStatus: () => status,
    envForSubprocess: async () => ({ AWS_ACCESS_KEY_ID: "AKIAFAKEFAKEFAKEFAKE", AWS_SECRET_ACCESS_KEY: "fake", AWS_REGION: "sa-east-1" }),
    connect: async () => status,
    disconnect: () => undefined,
    clientConfig: () => {
      throw new Error("sem rede nos testes");
    },
  };
}

export async function makeApp(overrides: Partial<AppContext> = {}) {
  const ctx = createContext(testSettings(), overrides);
  const app = await buildApp(ctx, { csrfToken: CSRF });
  return { app, ctx };
}
