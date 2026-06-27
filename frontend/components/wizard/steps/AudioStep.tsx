// SPDX-License-Identifier: Apache-2.0
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { AudioClipItem, SlideItem } from "@/lib/schemas";
import { JobProgress } from "@/components/wizard/job-progress/JobProgress";
import type { WizardStep } from "@/lib/wizard-state";

export interface AudioStepProps {
  projectId: string;
  slides: SlideItem[];
  audioClips: AudioClipItem[];
  onNavigate: (step: WizardStep) => void;
  onComplete: () => void;
}

function AudioPlayer({ blobKey }: { blobKey: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    api.blobs
      .get(blobKey)
      .then((b) => {
        if (!active) return;
        const u = URL.createObjectURL(b);
        urls.push(u);
        setObjectUrl(u);
      })
      .catch(() => null);
    return () => {
      active = false;
      for (const u of urls) URL.revokeObjectURL(u);
    };
  }, [blobKey]);

  if (!objectUrl) {
    return (
      <div className="h-8 w-full rounded bg-[var(--color-muted)] animate-pulse" />
    );
  }
  return <audio controls src={objectUrl} className="w-full h-8" />;
}

export function AudioStep({
  projectId,
  slides,
  audioClips,
  onNavigate,
  onComplete,
}: AudioStepProps) {
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const hasFiredAutoRef = useRef(false);

  const hasAllAudio =
    slides.length > 0 && audioClips.length >= slides.length;

  const synthesize = useCallback(async () => {
    setError(null);
    setIsSynthesizing(true);
    try {
      const resp = await api.audio.synthesize(projectId);
      setJobIds(resp.job_ids);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Synthesis failed");
    } finally {
      setIsSynthesizing(false);
    }
  }, [projectId]);

  // Auto-trigger if no audio clips exist
  useEffect(() => {
    if (!hasFiredAutoRef.current && slides.length > 0 && audioClips.length === 0) {
      hasFiredAutoRef.current = true;
      void synthesize();
    }
  }, [slides.length, audioClips.length, synthesize]);

  // Build a map of slide_id → clip for the UI
  const clipBySlide = new Map(audioClips.map((c) => [c.slide_id, c]));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Synthesise audio</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          Each slide&apos;s script is synthesised in your cloned voice.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {isSynthesizing && (
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Enqueueing…
        </p>
      )}

      {jobIds.length > 0 && !hasAllAudio && (
        <JobProgress
          job_ids={jobIds}
          label={`Synthesising audio for ${jobIds.length} slide${jobIds.length !== 1 ? "s" : ""}…`}
          onAllComplete={onComplete}
          onAnyFailed={(_, err) => setError(`A slide failed: ${err}`)}
        />
      )}

      {/* Per-slide clips */}
      {slides.length > 0 && (
        <div className="space-y-3">
          {hasAllAudio && (
            <p className="text-sm font-medium text-green-700">
              ✓ All {slides.length} audio clips ready
            </p>
          )}
          {slides.map((slide, idx) => {
            const clip = clipBySlide.get(slide.id);
            return (
              <div
                key={slide.id}
                className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-[var(--color-foreground)]">
                    Slide {idx + 1}
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => onNavigate("voice")}
                      className="text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] border border-[var(--color-border)] rounded px-2 py-1"
                    >
                      Change voice
                    </button>
                    <button
                      type="button"
                      onClick={() => onNavigate("scripts")}
                      className="text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] border border-[var(--color-border)] rounded px-2 py-1"
                    >
                      Change script
                    </button>
                  </div>
                </div>

                {clip ? (
                  <div className="space-y-2">
                    <AudioPlayer blobKey={clip.audio_blob_key} />
                    <p className="text-xs text-[var(--color-muted-foreground)]">
                      {clip.duration_seconds.toFixed(1)}s · {clip.engine_used}
                    </p>
                  </div>
                ) : (
                  <div className="h-8 w-full rounded bg-[var(--color-muted)] animate-pulse" />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
