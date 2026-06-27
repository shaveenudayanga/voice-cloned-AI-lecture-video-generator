// SPDX-License-Identifier: Apache-2.0
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { ScriptListItem, SlideItem } from "@/lib/schemas";
import { JobProgress } from "@/components/wizard/job-progress/JobProgress";
import { SlideEditor } from "@/components/slide-editor/SlideEditor";

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
  const [skippedCount, setSkippedCount] = useState<number | null>(null);
  const hasFiredAutoRef = useRef(false);

  const hasScripts = scripts.length >= slides.length && slides.length > 0;

  // -------------------------------------------------------------------------
  // Full-project generation (fan-out via per-slide endpoint for edited-slide skip)
  // -------------------------------------------------------------------------

  const generate = useCallback(async () => {
    setError(null);
    setSkippedCount(null);
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

  // "Regenerate all" — skips slides whose version > 1 (manually edited)
  const handleRegenerateAll = useCallback(async () => {
    setError(null);
    setSkippedCount(null);
    setIsGenerating(true);

    const slideScriptMap = new Map(scripts.map((s) => [s.slide_id, s]));

    // Slides with no script OR with version === 1 (never manually edited)
    const toRegen = slides.filter((slide) => {
      const script = slideScriptMap.get(slide.id);
      return !script || script.version === 1;
    });
    const skipped = slides.length - toRegen.length;
    if (skipped > 0) setSkippedCount(skipped);

    if (toRegen.length === 0) {
      setIsGenerating(false);
      setError(
        "All slides have manual edits — nothing to regenerate. Edit individual slides using the editor below."
      );
      return;
    }

    try {
      const results = await Promise.allSettled(
        toRegen.map((slide) =>
          api.scripts.regenerateSlide(projectId, slide.id)
        )
      );

      const newJobIds: string[] = [];
      const failures: string[] = [];
      for (const result of results) {
        if (result.status === "fulfilled") {
          newJobIds.push(result.value.job_id);
        } else {
          failures.push(
            result.reason instanceof Error
              ? result.reason.message
              : "Unknown error"
          );
        }
      }

      if (failures.length > 0) {
        setError(`${failures.length} slide(s) failed to enqueue: ${failures[0]}`);
      }
      if (newJobIds.length > 0) {
        setJobIds(newJobIds);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Regeneration failed");
    } finally {
      setIsGenerating(false);
    }
  }, [projectId, slides, scripts]);

  // Auto-trigger on enter if no scripts exist yet.
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
          <h2 className="text-xl font-semibold">Scripts</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            AI-generated narration scripts in your voice style. Edit per slide and save explicitly.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleRegenerateAll()}
          disabled={isGenerating}
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors disabled:opacity-40"
        >
          ↺ Regenerate all
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {skippedCount !== null && skippedCount > 0 && (
        <p className="text-xs text-[var(--color-muted-foreground)]">
          {skippedCount} slide{skippedCount !== 1 ? "s" : ""} with manual edits{" "}
          {skippedCount !== 1 ? "were" : "was"} skipped.
        </p>
      )}

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

      {/* Per-slide editor — shown once scripts exist */}
      {hasScripts && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4">
          <SlideEditor
            projectId={projectId}
            slides={slides}
            scripts={scripts}
            onScriptSaved={onComplete}
          />
        </div>
      )}

      {/* Placeholder while scripts are generating for the first time */}
      {!hasScripts && scripts.length > 0 && jobIds.length === 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-amber-700">
            ⚠ {scripts.length} / {slides.length} scripts ready — waiting for the rest.
          </p>
        </div>
      )}
    </div>
  );
}
