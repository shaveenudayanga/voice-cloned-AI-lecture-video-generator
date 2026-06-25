// SPDX-License-Identifier: Apache-2.0
// Typed API client — will be regenerated from OpenAPI spec in Phase 2+.
// For Phase 1 this is a minimal fetch wrapper used by unit tests and placeholder pages.

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = process.env.NEXT_PUBLIC_API_KEY ?? "";
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: {
    live: () => apiFetch<{ status: string; version: string }>("/health/live"),
  },
  projects: {
    list: () => apiFetch<{ projects: unknown[] }>("/projects"),
    create: () => apiFetch<{ id: string; wizard_step: string }>("/projects", { method: "POST" }),
  },
};
