// SPDX-License-Identifier: Apache-2.0
// Zod schemas mirroring backend Pydantic models (backend/app/schemas/__init__.py).
// Keep in sync — if the backend schema changes, update here and regenerate from OpenAPI.
import { z } from "zod";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export const HealthSchema = z.object({
  status: z.string(),
  version: z.string(),
});
export type Health = z.infer<typeof HealthSchema>;

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

export const JobStatusSchema = z.enum(["queued", "running", "complete", "failed"]);
export type JobStatus = z.infer<typeof JobStatusSchema>;

export const JobResponseSchema = z.object({
  job_id: z.string().uuid(),
  status: JobStatusSchema,
  progress_pct: z.number().int().min(0).max(100),
  error_message: z.string().nullable(),
  result: z.record(z.unknown()).nullable(),
});
export type JobResponse = z.infer<typeof JobResponseSchema>;

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export const WizardStepSchema = z.enum([
  "upload",
  "voice",
  "scripts",
  "audio",
  "render",
  "done",
]);
export type WizardStep = z.infer<typeof WizardStepSchema>;

export const ProjectResponseSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  title: z.string(),
  voice_profile_id: z.string().uuid().nullable(),
  wizard_step: WizardStepSchema,
  created_at: z.string(),
  updated_at: z.string(),
});
export type ProjectResponse = z.infer<typeof ProjectResponseSchema>;

export const ProjectCreateRequestSchema = z.object({
  title: z.string().min(1),
});
export type ProjectCreateRequest = z.infer<typeof ProjectCreateRequestSchema>;

export const ProjectPatchRequestSchema = z.object({
  voice_profile_id: z.string().uuid().nullish(),
  wizard_step: WizardStepSchema.optional(),
});
export type ProjectPatchRequest = z.infer<typeof ProjectPatchRequestSchema>;

// ---------------------------------------------------------------------------
// Slides
// ---------------------------------------------------------------------------

export const SlideItemSchema = z.object({
  id: z.string().uuid(),
  order_index: z.number().int(),
  extracted_text: z.string(),
});
export type SlideItem = z.infer<typeof SlideItemSchema>;

export const SlideListResponseSchema = z.object({
  slides: z.array(SlideItemSchema),
});
export type SlideListResponse = z.infer<typeof SlideListResponseSchema>;

export const SlideUploadResponseSchema = z.object({
  job_id: z.string().uuid(),
  project_id: z.string().uuid(),
  status: z.literal("queued"),
});
export type SlideUploadResponse = z.infer<typeof SlideUploadResponseSchema>;

// ---------------------------------------------------------------------------
// Voice profiles
// ---------------------------------------------------------------------------

export const VoiceUploadResponseSchema = z.object({
  profile_id: z.string().uuid(),
  job_id: z.string().uuid(),
  status: z.literal("queued"),
});
export type VoiceUploadResponse = z.infer<typeof VoiceUploadResponseSchema>;

export const VoiceProfileSummarySchema = z.object({
  id: z.string().uuid(),
  display_name: z.string(),
  is_default: z.boolean(),
  transcript_preview: z.string(),
  has_transcript: z.boolean(),
  created_at: z.string(),
});
export type VoiceProfileSummary = z.infer<typeof VoiceProfileSummarySchema>;

export const VoiceProfileDetailSchema = z.object({
  id: z.string().uuid(),
  display_name: z.string(),
  is_default: z.boolean(),
  style_reference_transcript: z.string(),
  transcript_preview: z.string(),
  has_transcript: z.boolean(),
  extra_style_sample: z.string().nullable(),
  tts_engine: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type VoiceProfileDetail = z.infer<typeof VoiceProfileDetailSchema>;

export const VoicePreviewResponseSchema = z.object({
  job_id: z.string().uuid(),
  voice_profile_id: z.string().uuid(),
  status: z.literal("queued"),
});
export type VoicePreviewResponse = z.infer<typeof VoicePreviewResponseSchema>;

// ---------------------------------------------------------------------------
// Scripts
// ---------------------------------------------------------------------------

export const ScriptListItemSchema = z.object({
  id: z.string().uuid(),
  slide_id: z.string().uuid(),
  order_index: z.number().int(),
  text: z.string(),
  estimated_reading_seconds: z.number().int(),
  pronunciation_hints: z.string().nullable(),
  version: z.number().int(),
  script_hash: z.string(),
});
export type ScriptListItem = z.infer<typeof ScriptListItemSchema>;

export const ScriptResponseSchema = z.object({
  id: z.string().uuid(),
  slide_id: z.string().uuid(),
  project_id: z.string().uuid(),
  text: z.string(),
  estimated_reading_seconds: z.number().int(),
  pronunciation_hints: z.string().nullable(),
  version: z.number().int(),
  script_hash: z.string(),
  updated_at: z.string(),
});
export type ScriptResponse = z.infer<typeof ScriptResponseSchema>;

export const ScriptGenerateResponseSchema = z.object({
  job_ids: z.array(z.string().uuid()),
  slide_count: z.number().int(),
  status: z.string(),
});
export type ScriptGenerateResponse = z.infer<typeof ScriptGenerateResponseSchema>;

// ---------------------------------------------------------------------------
// Audio
// ---------------------------------------------------------------------------

export const AudioSynthesizeResponseSchema = z.object({
  job_ids: z.array(z.string().uuid()),
  slide_count: z.number().int(),
  status: z.literal("queued"),
});
export type AudioSynthesizeResponse = z.infer<typeof AudioSynthesizeResponseSchema>;

export const AudioClipItemSchema = z.object({
  id: z.string().uuid(),
  slide_id: z.string().uuid(),
  order_index: z.number().int(),
  audio_blob_key: z.string(),
  duration_seconds: z.number(),
  engine_used: z.string(),
  synthesis_fingerprint: z.string(),
});
export type AudioClipItem = z.infer<typeof AudioClipItemSchema>;

// ---------------------------------------------------------------------------
// Video
// ---------------------------------------------------------------------------

export const VideoAssembleResponseSchema = z.object({
  job_id: z.string().uuid(),
  project_id: z.string().uuid(),
  status: z.literal("queued"),
});
export type VideoAssembleResponse = z.infer<typeof VideoAssembleResponseSchema>;

export const VideoArtifactResponseSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  video_blob_key: z.string(),
  srt_blob_key: z.string().nullable(),
  total_duration_seconds: z.number(),
  slide_count: z.number().int(),
  ffmpeg_version: z.string(),
  created_at: z.string(),
});
export type VideoArtifactResponse = z.infer<typeof VideoArtifactResponseSchema>;

// Keep the old exported types for backward compatibility
export const ProjectSchema = ProjectResponseSchema;
export const JobSchema = JobResponseSchema;
export type Project = ProjectResponse;
export type Job = JobResponse;
