import { defineConfig } from "vitest/config";

export default defineConfig({
  // Match Next.js's automatic JSX runtime so .tsx modules don't need `import React`.
  esbuild: { jsx: "automatic" },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
