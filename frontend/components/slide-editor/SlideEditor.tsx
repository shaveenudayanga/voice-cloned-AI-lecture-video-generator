// SPDX-License-Identifier: Apache-2.0
// Phase 8 — Per-slide script editor.
// Two-pane: left = slide image + nav, right = script textarea + controls.
// Save is ALWAYS explicit (no autosave). Slide navigation with unsaved changes
// shows a confirmation dialog — never silently discards.
"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { AudioClipItem, ScriptListItem, SlideItem } from "@/lib/schemas";
import { useBlobUrl } from "@/lib/hooks/use-blob-url";
import { JobProgress } from "@/components/wizard/job-progress/JobProgress";

export interface SlideEditorProps {
  projectId: string;
  slides: SlideItem[];
  scripts: ScriptListItem[];
  /** Called after a save or regeneration completes — parent should refetch scripts. */
  onScriptSaved: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatReadingTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `~${mins} min ${secs} sec`;
}

// ---------------------------------------------------------------------------
// Slide image pane
// ---------------------------------------------------------------------------

interface SlideImageProps {
  blobKey: string;
  alt: string;
  isZoomed: boolean;
  onToggleZoom: () => void;
}

function SlideImage({ blobKey, alt, isZoomed, onToggleZoom }: SlideImageProps) {
  const url = useBlobUrl(blobKey);

  if (!url) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded bg-[var(--color-muted)] text-sm text-[var(--color-muted-foreground)] animate-pulse">
        Loading image…
      </div>
    );
  }

  return (
    <div
      className={`flex h-full w-full items-center justify-center overflow-auto rounded bg-gray-50 ${isZoomed ? "cursor-zoom-out" : "cursor-zoom-in"}`}
      onClick={onToggleZoom}
      title={isZoomed ? "Click to fit" : "Click to zoom"}
    >
      <img
        src={url}
        alt={alt}
        className={isZoomed ? "max-w-none" : "max-h-full max-w-full object-contain"}
        draggable={false}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirmation dialog for unsaved changes on slide switch
// ---------------------------------------------------------------------------

interface UnsavedDialogProps {
  fromSlideNum: number;
  onDiscard: () => void;
  onCancel: () => void;
}

function UnsavedDialog({ fromSlideNum, onDiscard, onCancel }: UnsavedDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="unsaved-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="mx-4 w-full max-w-sm rounded-[var(--radius-lg)] bg-white p-6 shadow-lg space-y-4">
        <h3
          id="unsaved-dialog-title"
          className="text-base font-semibold text-[var(--color-foreground)]"
        >
          Unsaved changes
        </h3>
        <p className="text-sm text-[var(--color-muted-foreground)]">
          You have unsaved changes on slide {fromSlideNum}. Discard them?
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
          >
            Go back and save
          </button>
          <button
            type="button"
            onClick={onDiscard}
            className="rounded-[var(--radius-md)] bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            Discard
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main SlideEditor
// ---------------------------------------------------------------------------

export function SlideEditor({
  projectId,
  slides,
  scripts,
  onScriptSaved,
}: SlideEditorProps) {
  const [currentIdx, setCurrentIdx] = useState(0);

  // Editor state
  const [draftText, setDraftText] = useState("");
  const [draftHints, setDraftHints] = useState("");
  const [savedText, setSavedText] = useState("");
  const [savedHints, setSavedHints] = useState("");

  // Save state
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Zoom
  const [isZoomed, setIsZoomed] = useState(false);

  // Unsaved navigation confirmation
  const [pendingNavIdx, setPendingNavIdx] = useState<number | null>(null);

  // Per-slide regeneration
  const [regenJobId, setRegenJobId] = useState<string | null>(null);
  const [regenError, setRegenError] = useState<string | null>(null);

  // Audio preview
  const [previewJobId, setPreviewJobId] = useState<string | null>(null);
  const [previewBlobKey, setPreviewBlobKey] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isLaunchingPreview, setIsLaunchingPreview] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Stable refs so keyboard handler never sees stale closures — updated via useLayoutEffect
  const currentIdxRef = useRef(currentIdx);
  const slidesLenRef = useRef(slides.length);
  const isDirtyRef = useRef(false);

  // Derived
  const currentSlide: SlideItem | undefined = slides[currentIdx];
  const currentScript: ScriptListItem | undefined =
    scripts.find((s) => s.slide_id === currentSlide?.id);

  const isDirty =
    draftText !== savedText || draftHints !== savedHints;

  // -------------------------------------------------------------------------
  // Init/reset editor when slide changes
  // -------------------------------------------------------------------------

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const script = scripts.find((s) => s.slide_id === slides[currentIdx]?.id);
    const text = script?.text ?? "";
    const hints = script?.pronunciation_hints ?? "";
    setDraftText(text);
    setDraftHints(hints);
    setSavedText(text);
    setSavedHints(hints);
    setSaveError(null);
    setRegenJobId(null);
    setRegenError(null);
    setPreviewJobId(null);
    setPreviewBlobKey(null);
    setPreviewError(null);
    setIsZoomed(false);
  }, [currentIdx]); // eslint-disable-line react-hooks/exhaustive-deps
  /* eslint-enable react-hooks/set-state-in-effect */
  // Intentionally omit scripts + slides from deps: only reset on slide nav,
  // not on every parent refresh. Parent-triggered updates go through onScriptSaved.

  // -------------------------------------------------------------------------
  // Keyboard navigation (ArrowLeft/ArrowRight when textarea not focused)
  // -------------------------------------------------------------------------

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement === textareaRef.current) return;
      const idx = currentIdxRef.current;
      const len = slidesLenRef.current;
      const dirty = isDirtyRef.current;

      if (e.key === "ArrowRight" && idx < len - 1) {
        if (dirty) {
          setPendingNavIdx(idx + 1);
        } else {
          setCurrentIdx(idx + 1);
        }
      } else if (e.key === "ArrowLeft" && idx > 0) {
        if (dirty) {
          setPendingNavIdx(idx - 1);
        } else {
          setCurrentIdx(idx - 1);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []); // stable refs — no deps needed

  // -------------------------------------------------------------------------
  // Navigation helpers
  // -------------------------------------------------------------------------

  const tryNavigate = useCallback(
    (newIdx: number) => {
      if (isDirtyRef.current) {
        setPendingNavIdx(newIdx);
      } else {
        setCurrentIdx(newIdx);
      }
    },
    []
  );

  const confirmDiscard = useCallback(() => {
    if (pendingNavIdx === null) return;
    setCurrentIdx(pendingNavIdx);
    setPendingNavIdx(null);
  }, [pendingNavIdx]);

  // -------------------------------------------------------------------------
  // Save
  // -------------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    if (!currentScript) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await api.scripts.patch(projectId, currentScript.id, {
        text: draftText,
        pronunciation_hints: draftHints || undefined,
      });
      // Update local saved state immediately so dirty flag clears
      setSavedText(draftText);
      setSavedHints(draftHints);
      onScriptSaved();
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }, [currentScript, draftText, draftHints, projectId, onScriptSaved]);

  // -------------------------------------------------------------------------
  // Regenerate this slide
  // -------------------------------------------------------------------------

  const slidesRef = useRef(slides);

  // Keep all stable refs in sync after every render (synchronous before paint)
  useLayoutEffect(() => {
    currentIdxRef.current = currentIdx;
    slidesLenRef.current = slides.length;
    isDirtyRef.current = isDirty;
    slidesRef.current = slides;
  });

  const handleRegen = useCallback(async () => {
    if (!currentSlide) return;
    setRegenError(null);
    try {
      const resp = await api.scripts.regenerateSlide(projectId, currentSlide.id);
      setRegenJobId(resp.job_id);
    } catch (e: unknown) {
      setRegenError(e instanceof Error ? e.message : "Regeneration failed");
    }
  }, [currentSlide, projectId]);

  const handleRegenComplete = useCallback(async () => {
    setRegenJobId(null);
    onScriptSaved(); // triggers parent TanStack Query invalidation
    // Fetch fresh scripts to update editor — parent refetch may lag
    try {
      const freshScripts = await api.scripts.list(projectId);
      const slide = slidesRef.current[currentIdxRef.current];
      if (!slide) return;
      const script = freshScripts.find((s) => s.slide_id === slide.id);
      if (script) {
        setDraftText(script.text);
        setDraftHints(script.pronunciation_hints ?? "");
        setSavedText(script.text);
        setSavedHints(script.pronunciation_hints ?? "");
      }
    } catch {
      // Best-effort; parent refetch will eventually catch up
    }
  }, [onScriptSaved, projectId]);

  // -------------------------------------------------------------------------
  // Audio preview — TanStack Query polls the preview job
  // -------------------------------------------------------------------------

  const previewJobQuery = useQuery({
    queryKey: ["preview-job", previewJobId],
    queryFn: () => api.jobs.get(previewJobId!),
    enabled: previewJobId !== null,
    refetchInterval: (query: { state: { data?: { status?: string } } }) => {
      const s = query.state.data?.status;
      return s === "complete" || s === "failed" ? false : 2000;
    },
    staleTime: 0,
  });

  // When preview job completes, fetch audio list to find the blob key
  useEffect(() => {
    if (previewJobQuery.data?.status !== "complete") return;
    const slide = slides[currentIdx];
    if (!slide) return;
    api.audio
      .list(projectId)
      .then((clips: AudioClipItem[]) => {
        const clip = clips.find((c) => c.slide_id === slide.id);
        if (clip) setPreviewBlobKey(clip.audio_blob_key);
        else setPreviewError("Audio clip not found after synthesis");
      })
      .catch(() => setPreviewError("Could not load audio preview"));
  }, [previewJobQuery.data?.status, projectId, currentIdx, slides]);

  // Failed preview job
  useEffect(() => {
    if (previewJobQuery.data?.status !== "failed") return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewError(
      previewJobQuery.data.error_message ?? "Audio synthesis failed"
    );
  }, [previewJobQuery.data?.status, previewJobQuery.data?.error_message]);

  const previewBlobUrl = useBlobUrl(previewBlobKey);

  const handlePreview = useCallback(async () => {
    if (!currentSlide) return;
    setIsLaunchingPreview(true);
    setPreviewBlobKey(null);
    setPreviewError(null);
    try {
      const resp = await api.audio.synthesizeSlide(projectId, currentSlide.id);
      setPreviewJobId(resp.job_id);
    } catch (e: unknown) {
      setPreviewError(e instanceof Error ? e.message : "Could not start preview");
    } finally {
      setIsLaunchingPreview(false);
    }
  }, [currentSlide, projectId]);

  const previewIsRunning =
    previewJobId !== null &&
    previewJobQuery.data?.status !== "complete" &&
    previewJobQuery.data?.status !== "failed";

  // -------------------------------------------------------------------------
  // Render guards
  // -------------------------------------------------------------------------

  if (slides.length === 0) {
    return (
      <p className="text-sm text-[var(--color-muted-foreground)]">
        No slides available.
      </p>
    );
  }

  if (!currentSlide) return null;

  const isLastSlide = currentIdx === slides.length - 1;
  const isFirstSlide = currentIdx === 0;
  const slideNum = currentIdx + 1;
  const slideTotal = slides.length;

  const btnBase =
    "rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--color-muted)] disabled:opacity-40";

  return (
    <>
      {/* Unsaved-changes dialog */}
      {pendingNavIdx !== null && (
        <UnsavedDialog
          fromSlideNum={slideNum}
          onDiscard={confirmDiscard}
          onCancel={() => setPendingNavIdx(null)}
        />
      )}

      <div className="flex gap-6" style={{ minHeight: "520px" }}>
        {/* ---------------------------------------------------------------- */}
        {/* LEFT PANE — slide image + navigation                             */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex w-1/2 flex-col gap-3">
          {/* Nav row */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => tryNavigate(currentIdx - 1)}
              disabled={isFirstSlide}
              aria-label="Previous slide"
              className={btnBase}
            >
              ←
            </button>
            <span className="text-sm font-medium text-[var(--color-foreground)]">
              Slide {slideNum} of {slideTotal}
            </span>
            <button
              type="button"
              onClick={() => tryNavigate(currentIdx + 1)}
              disabled={isLastSlide}
              aria-label="Next slide"
              className={btnBase}
            >
              →
            </button>
          </div>

          {/* Image */}
          <div className="flex-1 overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)]">
            <SlideImage
              blobKey={currentSlide.image_blob_key}
              alt={`Slide ${slideNum}`}
              isZoomed={isZoomed}
              onToggleZoom={() => setIsZoomed((z) => !z)}
            />
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* RIGHT PANE — script editor + controls                           */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex w-1/2 flex-col gap-3">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            className="flex-1 resize-none rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-3 text-sm text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] placeholder:text-[var(--color-muted-foreground)]"
            placeholder={
              currentScript
                ? "Edit the narration script…"
                : "Script not yet generated for this slide."
            }
            disabled={!currentScript}
            aria-label="Script text"
          />

          {/* Char count + reading time */}
          <div className="flex items-center justify-between text-xs text-[var(--color-muted-foreground)]">
            <span>{draftText.length} chars</span>
            {currentScript && (
              <span>
                {formatReadingTime(currentScript.estimated_reading_seconds)}
              </span>
            )}
          </div>

          {/* Pronunciation hints */}
          <input
            type="text"
            value={draftHints}
            onChange={(e) => setDraftHints(e.target.value)}
            placeholder="Pronunciation hints, e.g. SQL = ess-cue-el, GAN = gan"
            disabled={!currentScript}
            className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-3 py-1.5 text-xs text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] placeholder:text-[var(--color-muted-foreground)] disabled:opacity-50"
            aria-label="Pronunciation hints"
          />

          {/* Unsaved indicator */}
          {isDirty && (
            <p className="text-xs font-medium text-orange-600">
              Unsaved changes
            </p>
          )}

          {/* Save error */}
          {saveError && (
            <p className="text-xs text-red-600">{saveError}</p>
          )}

          {/* Save button */}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={!isDirty || isSaving || !currentScript}
            className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {isSaving ? "Saving…" : "Save"}
          </button>

          {/* Divider */}
          <div className="border-t border-[var(--color-border)]" />

          {/* Regenerate this slide */}
          {regenError && (
            <p className="text-xs text-red-600">{regenError}</p>
          )}

          {regenJobId ? (
            <JobProgress
              job_ids={[regenJobId]}
              label="Regenerating script for this slide…"
              onAllComplete={() => void handleRegenComplete()}
              onAnyFailed={(_, err) => {
                setRegenJobId(null);
                setRegenError(`Regeneration failed: ${err}`);
              }}
            />
          ) : (
            <button
              type="button"
              onClick={() => void handleRegen()}
              disabled={isDirty || !currentSlide}
              title={
                isDirty
                  ? "Save your changes before regenerating"
                  : "Regenerate the AI script for this slide only"
              }
              className={`${btnBase} text-[var(--color-foreground)]`}
            >
              ↺ Regenerate this slide
            </button>
          )}

          {/* Preview audio */}
          {previewError && (
            <p className="text-xs text-red-600">{previewError}</p>
          )}

          {previewBlobUrl ? (
            <div className="space-y-2">
              <audio controls src={previewBlobUrl} className="w-full h-8" />
              <button
                type="button"
                onClick={() => void handlePreview()}
                disabled={isLaunchingPreview || previewIsRunning}
                className={`${btnBase} text-[var(--color-foreground)] text-xs`}
              >
                ↺ Re-generate preview
              </button>
            </div>
          ) : previewIsRunning || isLaunchingPreview ? (
            <button
              type="button"
              disabled
              className={`${btnBase} text-[var(--color-foreground)] opacity-60`}
            >
              Generating audio…
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handlePreview()}
              disabled={!currentScript || isDirty}
              title={
                isDirty
                  ? "Save your changes before previewing audio"
                  : "Synthesise audio for this slide only"
              }
              className={`${btnBase} text-[var(--color-foreground)]`}
            >
              ▶ Preview audio (this slide)
            </button>
          )}
        </div>
      </div>
    </>
  );
}
