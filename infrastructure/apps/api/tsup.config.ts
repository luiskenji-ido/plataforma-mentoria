import { defineConfig } from "tsup";

// CommonJS: os pacotes do Pulumi são CommonJS (com carregamento preguiçoso dos módulos da AWS) e funcionam
// melhor com require. O shim de import.meta.url mantém o mesmo código de desenvolvimento (tsx/ESM).
export default defineConfig({
  entry: ["src/server.ts"],
  format: ["cjs"],
  platform: "node",
  target: "node20",
  outDir: "dist",
  clean: true,
  sourcemap: true,
  shims: true,
  // Os pacotes do monorepo (TypeScript puro) entram no bundle; os do npm continuam em node_modules
  noExternal: [/^@infra\//],
  // O Pulumi carrega plugins e metadados do próprio pacote: fica sempre em node_modules
  external: [/^@pulumi\//],
});
