// SPDX-License-Identifier: Apache-2.0
// Typed API client for the LectureVoice backend.
// All calls go through apiFetch — no raw fetch in components.

import type {
  AudioClipItem,
  AudioSynthesizeResponse,
  JobResponse,
  ProjectCreateRequest,
  ProjectPatchRequest,
  ProjectResponse,
  ScriptGenerateResponse,
  ScriptListItem,
  ScriptResponse,
  SlideAudioSynthesizeResponse,
  SlideItem,
  SlideScriptRegenerateResponse,
  SlideUploadResponse,
  VideoArtifactResponse,
  VideoAssembleResponse,
  VoicePreviewResponse,
  VoiceProfileDetail,
  VoiceProfileSummary,
  VoiceUploadResponse,
} from "@/lib/schemas";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const getApiKey = () => process.env.NEXT_PUBLIC_API_KEY ?? "";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Never force application/json for FormData bodies — the browser must set the
  // multipart/form-data Content-Type (with boundary) itself, otherwise the
  // server cannot parse the upload and rejects it with 422.
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      "X-API-Key": getApiKey(),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

/** Fetch a blob (for authenticated media elements). */
async function fetchBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "X-API-Key": getApiKey() },
  });
  if (!response.ok) {
    throw new Error(`Blob fetch ${response.status}`);
  }
  return response.blob();
}

export const api = {
  // -------------------------------------------------------------------------
  // Health
  // -------------------------------------------------------------------------
  health: {
    live: () => apiFetch<{ status: string; version: string }>("/health/live"),
  },

  // -------------------------------------------------------------------------
  // Projects
  // -------------------------------------------------------------------------
  projects: {
    list: () => apiFetch<ProjectResponse[]>("/projects"),
    create: (body: ProjectCreateRequest) =>
      apiFetch<ProjectResponse>("/projects", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: string) => apiFetch<ProjectResponse>(`/projects/${id}`),
    patch: (id: string, body: ProjectPatchRequest) =>
      apiFetch<ProjectResponse>(`/projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
  },

  // -------------------------------------------------------------------------
  // Slides
  // -------------------------------------------------------------------------
  slides: {
    list: (projectId: string) =>
      apiFetch<{ slides: SlideItem[] }>(`/projects/${projectId}/slides`),
    upload: (projectId: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return apiFetch<SlideUploadResponse>(
        `/projects/${projectId}/slides/upload`,
        {
          method: "POST",
          headers: { "X-API-Key": getApiKey() },
          body: form,
        }
      );
    },
  },

  // -------------------------------------------------------------------------
  // Voice profiles
  // -------------------------------------------------------------------------
  voices: {
    list: () => apiFetch<VoiceProfileSummary[]>("/voices"),
    get: (id: string) => apiFetch<VoiceProfileDetail>(`/voices/${id}`),
    create: (file: Blob, displayName: string) => {
      const form = new FormData();
      form.append("file", file, "recording.webm");
      form.append("display_name", displayName);
      return apiFetch<VoiceUploadResponse>("/voices", {
        method: "POST",
        headers: { "X-API-Key": getApiKey() },
        body: form,
      });
    },
    patch: (
      id: string,
      body: { display_name?: string; extra_style_sample?: string; is_default?: boolean }
    ) =>
      apiFetch<VoiceProfileDetail>(`/voices/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      apiFetch<void>(`/voices/${id}`, { method: "DELETE" }),
    preview: (id: string) =>
      apiFetch<VoicePreviewResponse>(`/voices/${id}/preview`, {
        method: "POST",
      }),
  },

  // -------------------------------------------------------------------------
  // Scripts
  // -------------------------------------------------------------------------
  scripts: {
    generate: (projectId: string) =>
      apiFetch<ScriptGenerateResponse>(
        `/projects/${projectId}/scripts/generate`,
        { method: "POST" }
      ),
    list: (projectId: string) =>
      apiFetch<ScriptListItem[]>(`/projects/${projectId}/scripts/`),
    patch: (
      projectId: string,
      scriptId: string,
      body: { text?: string; pronunciation_hints?: string }
    ) =>
      apiFetch<ScriptResponse>(`/projects/${projectId}/scripts/${scriptId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    getById: (projectId: string, scriptId: string) =>
      apiFetch<ScriptResponse>(`/projects/${projectId}/scripts/${scriptId}`),
    regenerateSlide: (projectId: string, slideId: string) =>
      apiFetch<SlideScriptRegenerateResponse>(
        `/projects/${projectId}/scripts/${slideId}/regenerate`,
        { method: "POST" }
      ),
  },

  // -------------------------------------------------------------------------
  // Audio
  // -------------------------------------------------------------------------
  audio: {
    synthesize: (projectId: string) =>
      apiFetch<AudioSynthesizeResponse>(
        `/projects/${projectId}/audio/synthesize`,
        { method: "POST" }
      ),
    synthesizeSlide: (projectId: string, slideId: string) =>
      apiFetch<SlideAudioSynthesizeResponse>(
        `/projects/${projectId}/audio/${slideId}/synthesize`,
        { method: "POST" }
      ),
    list: (projectId: string) =>
      apiFetch<AudioClipItem[]>(`/projects/${projectId}/audio/`),
  },

  // -------------------------------------------------------------------------
  // Video
  // -------------------------------------------------------------------------
  video: {
    assemble: (projectId: string) =>
      apiFetch<VideoAssembleResponse>(
        `/projects/${projectId}/video/assemble`,
        { method: "POST" }
      ),
    get: (projectId: string) =>
      apiFetch<VideoArtifactResponse>(`/projects/${projectId}/video/`),
  },

  // -------------------------------------------------------------------------
  // Jobs
  // -------------------------------------------------------------------------
  jobs: {
    get: (jobId: string) => apiFetch<JobResponse>(`/jobs/${jobId}`),
  },

  // -------------------------------------------------------------------------
  // Blobs
  // -------------------------------------------------------------------------
  blobs: {
    /**
     * Returns the proxied URL for a blob key.
     * Use in contexts where you need the URL synchronously (e.g., useBlobUrl).
     * Slashes in the key are NOT encoded — the FastAPI :path converter preserves them.
     */
    getUrl: (blobKey: string): string => `${API_BASE}/blobs/${blobKey}`,

    /** Fetch blob bytes with auth header — use with useBlobUrl hook. */
    get: (blobKey: string) => fetchBlob(`/blobs/${blobKey}`),
  },
};
