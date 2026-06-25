// SPDX-License-Identifier: Apache-2.0
// Zod schemas mirroring backend Pydantic models. Extended phase by phase.
import { z } from "zod";

export const HealthSchema = z.object({
  status: z.string(),
  version: z.string(),
});

export const ProjectSchema = z.object({
  id: z.string().uuid(),
  wizard_step: z.enum(["upload", "voice", "scripts", "audio", "render", "done"]),
});

export const JobSchema = z.object({
  id: z.string().uuid(),
  status: z.enum(["pending", "running", "success", "failed", "retrying"]),
  progress_pct: z.number().int().min(0).max(100),
});

export type Health = z.infer<typeof HealthSchema>;
export type Project = z.infer<typeof ProjectSchema>;
export type Job = z.infer<typeof JobSchema>;
