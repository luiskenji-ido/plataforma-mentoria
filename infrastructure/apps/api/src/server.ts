import { buildApp } from "./app";
import { createContext } from "./context";
import { loadSettings } from "./settings";

async function main(): Promise<void> {
  const settings = loadSettings();
  const ctx = createContext(settings);
  const production = process.env.NODE_ENV === "production" || process.env.INFRA_MODE === "production";
  const app = await buildApp(ctx, { logger: true, serveWeb: production });

  await app.listen({ host: settings.host, port: settings.port });
  const url = `http://localhost:${production ? settings.port : settings.publicPort}`;
  app.log.info(`Painel de infraestrutura: ${url} (API em ${settings.host}:${settings.port}, só acesso local)`);
  if (!ctx.stacks.hasPassphrase()) {
    app.log.warn("PULUMI_CONFIG_PASSPHRASE não definida: informe a senha do estado em Configurações antes de provisionar.");
  }

  for (const signal of ["SIGINT", "SIGTERM"] as const) {
    process.on(signal, () => {
      void app.close().then(() => process.exit(0));
    });
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
