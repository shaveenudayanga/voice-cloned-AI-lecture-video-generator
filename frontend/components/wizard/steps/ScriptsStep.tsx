// SPDX-License-Identifier: Apache-2.0
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { ScriptListItem, SlideItem } from "@/lib/schemas";
import { JobProgress } from "@/components/wizard/job-progress/JobProgress";

export interface ScriptsStepProps {
  projectId: string;
  slides: SlideItem[];
  scripts: ScriptListItem[];
  onComplete: () => void;
}

export function ScriptsStep({
  projectId,
  slides,
  scripts,
  onComplete,
}: ScriptsStepProps) {
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFiredAutoRef = useRef(false);

  const hasScripts = scripts.length >= slides.length && slides.length > 0;

  const generate = useCallback(async () => {
    setError(null);
    setIsGenerating(true);
    try {
      const resp = await api.scripts.generate(projectId);
      setJobIds(resp.job_ids);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setIsGenerating(false);
    }
  }, [projectId]);

  // Auto-trigger on enter if no scripts exist yet.
  // Ref instead of state — avoids synchronous setState in effect body.
  useEffect(() => {
    if (!hasFiredAutoRef.current && slides.length > 0 && scripts.length === 0) {
      hasFiredAutoRef.current = true;
      void generate();
    }
  }, [slides.length, scripts.length, generate]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Generate scripts</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            The AI will write a narration script for each slide in your voice style.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void generate()}
          disabled={isGenerating}
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors disabled:opacity-40"
        >
          ↺ Regenerate all
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {isGenerating && (
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Enqueueing…
        </p>
      )}

      {jobIds.length > 0 && (
        <JobProgress
          job_ids={jobIds}
          label={`Generating scripts for ${jobIds.length} slide${jobIds.length !== 1 ? "s" : ""}…`}
          onAllComplete={onComplete}
          onAnyFailed={(_, err) => setError(`A slide failed: ${err}`)}
        />
      )}

      {/* Script previews */}
      {scripts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-green-700">
              ✓ {scripts.length} / {slides.length} scripts ready
            </p>
            <p className="text-xs text-[var(--color-muted-foreground)]">
              Full per-slide editing available in Phase 8
            </p>
          </div>
          <div className="space-y-2">
            {scripts.map((s) => (
              <div
                key={s.id}
                className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-3"
              >
                <p className="text-xs font-medium text-[var(--color-muted-foreground)] mb-1">
                  Slide {s.order_index + 1}
                </p>
                <p className="text-sm text-[var(--color-foreground)] line-clamp-2">
                  {s.text.slice(0, 120)}
                  {s.text.length > 120 ? "…" : ""}
                </p>
                <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                  ~{s.estimated_reading_seconds}s
                </p>
              </div>
            ))}
          </div>
          {hasScripts && (
            <p className="text-xs text-[var(--color-muted-foreground)] italic">
              Script editor — full per-slide editing coming in Phase 8
            </p>
          )}
        </div>
      )}
    </div>
  );
}
