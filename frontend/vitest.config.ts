// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    // Node is the default; component tests override with @vitest-environment jsdom
    environment: "node",
    globals: true,
    include: ["lib/**/*.test.ts", "components/**/*.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
