// SPDX-License-Identifier: Apache-2.0
// Pure TypeScript — ZERO React imports, ZERO API calls.
// All functions are deterministic: given the same inputs they return the same
// output. This keeps them trivially testable with any Node-compatible runner.

export type WizardStep =
  | "upload"
  | "voice"
  | "scripts"
  | "audio"
  | "render"
  | "done";

/** Snapshot of project state needed for step-navigation decisions. */
export interface WizardProjectState {
  /** The furthest step the user has ever reached (persisted on Project). */
  wizard_step: WizardStep;
  /** UUID string or null if no voice profile has been selected. */
  voice_profile_id: string | null;
  /** How many slides exist for this project (0 until ingestion completes). */
  slide_count: number;
  /** How many slides have an associated Script row. */
  script_count: number;
  /** How many slides have an associated AudioClip row. */
  audio_clip_count: number;
  /** True once a VideoArtifact row exists for this project. */
  has_video_artifact: boolean;
}

/** Canonical step order — index drives prev/next arithmetic. */
export const STEP_ORDER: readonly WizardStep[] = [
  "upload",
  "voice",
  "scripts",
  "audio",
  "render",
  "done",
] as const;

/**
 * Return the step that follows `current`, or null if already at the last step.
 * noUncheckedIndexedAccess-safe: result typed as WizardStep | undefined.
 */
export function getNextStep(current: WizardStep): WizardStep | null {
  const idx = STEP_ORDER.indexOf(current);
  if (idx === -1 || idx === STEP_ORDER.length - 1) return null;
  return STEP_ORDER[idx + 1] ?? null;
}

/**
 * Return the step that precedes `current`, or null if already at the first step.
 */
export function getPrevStep(current: WizardStep): WizardStep | null {
  const idx = STEP_ORDER.indexOf(current);
  if (idx <= 0) return null;
  return STEP_ORDER[idx - 1] ?? null;
}

/**
 * Prerequisite check for each step.
 *
 *  upload  → always accessible
 *  voice   → ≥1 slide exists
 *  scripts → voice_profile_id is set
 *  audio   → every slide has a script
 *  render  → every slide has an audio clip
 *  done    → video artifact exists
 */
export function canAdvanceTo(
  step: WizardStep,
  project: WizardProjectState
): boolean {
  switch (step) {
    case "upload":
      return true;
    case "voice":
      return project.slide_count > 0;
    case "scripts":
      return project.voice_profile_id !== null;
    case "audio":
      return (
        project.slide_count > 0 &&
        project.script_count >= project.slide_count
      );
    case "render":
      return (
        project.slide_count > 0 &&
        project.audio_clip_count >= project.slide_count
      );
    case "done":
      return project.has_video_artifact;
  }
}

/**
 * True when the work associated with `step` is fully done.
 * Used to show ✓ indicators in the stepper header.
 */
export function isStepComplete(
  step: WizardStep,
  project: WizardProjectState
): boolean {
  switch (step) {
    case "upload":
      return project.slide_count > 0;
    case "voice":
      return project.voice_profile_id !== null;
    case "scripts":
      return (
        project.slide_count > 0 &&
        project.script_count >= project.slide_count
      );
    case "audio":
      return (
        project.slide_count > 0 &&
        project.audio_clip_count >= project.slide_count
      );
    case "render":
      return project.has_video_artifact;
    case "done":
      return project.has_video_artifact;
  }
}

/** Human-readable label for the stepper UI. */
export const STEP_LABELS: Record<WizardStep, string> = {
  upload: "Upload slides",
  voice: "Voice",
  scripts: "Scripts",
  audio: "Audio",
  render: "Render",
  done: "Done",
};

/** Type guard: is an arbitrary string a valid WizardStep? */
export function isValidStep(s: string | null): s is WizardStep {
  return s !== null && (STEP_ORDER as readonly string[]).includes(s);
}
