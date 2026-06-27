// SPDX-License-Identifier: Apache-2.0
// ONE place in the codebase that branches on DEPLOYMENT_MODE (§1.1 / ADR-0007).
// Nothing else in the wizard checks DEPLOYMENT_MODE.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { isWebMode } from "@/lib/deployment";
import { api } from "@/lib/api-client";
import type { ProjectResponse, VideoArtifactResponse } from "@/lib/schemas";

export interface DoneStepProps {
  projectId: string;
  project: ProjectResponse;
  videoArtifact: VideoArtifactResponse | null;
}

export function DoneStep({ project, videoArtifact }: DoneStepProps) {
  const [videoObjectUrl, setVideoObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!videoArtifact) return;
    let active = true;
    const urls: string[] = [];
    api.blobs
      .get(videoArtifact.video_blob_key)
      .then((b) => {
        if (!active) return;
        const u = URL.createObjectURL(b);
        urls.push(u);
        setVideoObjectUrl(u);
      })
      .catch(() => null);
    return () => {
      active = false;
      for (const u of urls) URL.revokeObjectURL(u);
    };
  }, [videoArtifact]);

  const handleDownload = () => {
    if (!videoObjectUrl) return;
    const a = document.createElement("a");
    a.href = videoObjectUrl;
    a.download = `${project.title.replace(/[^a-z0-9]/gi, "_")}.mp4`;
    a.click();
  };

  const handleSaveToFolder = () => {
    // DEPLOYMENT_MODE=desktop: Tauri filesystem access
    // Falls back to browser download when Tauri is not present
    if (
      typeof window !== "undefined" &&
      "__TAURI__" in window
    ) {
      // Tauri save dialog — handled by the Tauri shell (Phase 11)
      // @ts-expect-error — Tauri is injected at runtime in desktop mode
      void window.__TAURI__.dialog
        .save({ defaultPath: `${project.title}.mp4` })
        .then((path: string | null) => {
          if (!path || !videoObjectUrl) return;
          // Write file via Tauri FS API (injected at runtime)
          fetch(videoObjectUrl)
            .then((r) => r.arrayBuffer())
            .then((buf) => {
              // @ts-expect-error — Tauri fs at runtime
              void window.__TAURI__.fs.writeBinaryFile(path, new Uint8Array(buf));
            })
            .catch(console.error);
        });
    } else {
      // Tauri not available — fall back to browser download
      handleDownload();
    }
  };

  if (!videoArtifact) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Almost done…</h2>
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Video is not yet assembled. Please complete the Render step first.
        </p>
      </div>
    );
  }

  const fmtDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Your lecture video is ready!</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          {project.title} · {videoArtifact.slide_count} slides ·{" "}
          {fmtDuration(videoArtifact.total_duration_seconds)}
        </p>
      </div>

      {/* Video player */}
      {videoObjectUrl ? (
        <div className="rounded-[var(--radius-lg)] overflow-hidden border border-[var(--color-border)] bg-black">
          <video
            controls
            src={videoObjectUrl}
            className="w-full max-h-96"
          />
        </div>
      ) : (
        <div className="h-48 w-full rounded-[var(--radius-lg)] bg-[var(--color-muted)] flex items-center justify-center text-sm text-[var(--color-muted-foreground)] animate-pulse">
          Loading video…
        </div>
      )}

      {/* Action buttons — THE ONLY DEPLOYMENT_MODE BRANCH IN THE FRONTEND */}
      <div className="flex flex-wrap gap-3">
        {isWebMode ? (
          <button
            type="button"
            onClick={handleDownload}
            disabled={!videoObjectUrl}
            className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            Download video
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSaveToFolder}
            disabled={!videoObjectUrl}
            className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            Save to folder
          </button>
        )}

        <Link
          href="/"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-5 py-2.5 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
        >
          Back to dashboard
        </Link>
      </div>

      {/* Metadata */}
      <p className="text-xs text-[var(--color-muted-foreground)]">
        Assembled with ffmpeg {videoArtifact.ffmpeg_version}
      </p>
    </div>
  );
}
