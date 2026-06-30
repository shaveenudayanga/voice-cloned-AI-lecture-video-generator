// SPDX-License-Identifier: Apache-2.0
import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests run against a live stack (`make up` must be running).
 * Tests tagged @slow are excluded from the default run; use --grep @slow to include.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 1,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    extraHTTPHeaders: {
      "X-API-Key": process.env.API_KEY ?? "test-api-key",
    },
    trace: "on-first-retry",
    video: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
