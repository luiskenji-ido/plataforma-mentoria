import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: "node",
          environment: "node",
          include: ["packages/*/test/**/*.test.ts", "pulumi/test/**/*.test.ts", "apps/api/test/**/*.test.ts"],
          testTimeout: 20_000,
        },
      },
      {
        plugins: [react()],
        test: {
          name: "web",
          environment: "jsdom",
          include: ["apps/web/test/**/*.test.tsx"],
          setupFiles: ["apps/web/test/setup.ts"],
        },
      },
    ],
  },
});
