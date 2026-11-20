import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// O painel abre em http://localhost:3000; em desenvolvimento a API fica em 127.0.0.1:3001 atrás deste proxy.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:3001", changeOrigin: false },
    },
  },
  preview: { host: "127.0.0.1", port: 3000, strictPort: true },
  build: { outDir: "dist", sourcemap: false },
});
