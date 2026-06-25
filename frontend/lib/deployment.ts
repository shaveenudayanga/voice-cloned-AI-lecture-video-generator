// SPDX-License-Identifier: Apache-2.0
// Single source for the web vs. desktop output-step branch (§1.1 / ADR-0007).
// The ONLY place in the codebase that reads DEPLOYMENT_MODE.
// All other code imports this module — never reads the env var directly.

export type DeploymentMode = "web" | "desktop";

export const deploymentMode: DeploymentMode =
  (process.env.NEXT_PUBLIC_DEPLOYMENT_MODE as DeploymentMode | undefined) ?? "web";

export const isWebMode = deploymentMode === "web";
export const isDesktopMode = deploymentMode === "desktop";
