// SPDX-License-Identifier: Apache-2.0
"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { VideoArtifactResponse } from "@/lib/schemas";

export interface RenderStepProps {
  projectId: string;
  videoArtifact: VideoArtifactResponse | null;
  onComplete: () => void;
}

export function RenderStep({
  projectId,
  videoArtifact,
  onComplete,
}: RenderStepProps) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAssembling, setIsAssembling] = useState(false);
  const hasFiredAutoRef = useRef(false);
  const onCompleteFiredRef = useRef(false);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.jobs.get(jobId!),
    enabled: !!jobId,
    refetchInterval: (q: { state: { data?: { status: string } } }) => {
      const s = q.state.data?.status;
      return s === "complete" || s === "failed" ? false : 2000;
    },
    staleTime: 0,
  });

  // Auto-trigger assembly if no video exists yet
  useEffect(() => {
    if (!hasFiredAutoRef.current && !videoArtifact) {
      hasFiredAutoRef.current = true;
      setIsAssembling(true);
      api.video
        .assemble(projectId)
        .then((resp) => setJobId(resp.job_id))
        .catch((e: unknown) =>
          setError(e instanceof Error ? e.message : "Assembly failed")
        )
        .finally(() => setIsAssembling(false));
    }
  }, [videoArtifact, projectId]);

  // Job error derived from query data — no setState in effect body.
  const jobError =
    jobQuery.data?.status === "failed"
      ? (jobQuery.data.error_message ?? "Assembly failed")
      : null;
  // 'error' covers the case where the assemble() call itself fails before a job is created.
  const displayError = error ?? jobError;

  // Fire onComplete exactly once when the assembly job finishes.
  // No setState here — onComplete is a prop callback, not a state setter.
  useEffect(() => {
    if (
      jobQuery.data?.status === "complete" &&
      !onCompleteFiredRef.current
    ) {
      onCompleteFiredRef.current = true;
      onComplete();
    }
  }, [jobQuery.data, onComplete]);

  const retry = () => {
    setError(null);
    onCompleteFiredRef.current = false;
    hasFiredAutoRef.current = false;
    setJobId(null);
    setIsAssembling(true);
    api.video
      .assemble(projectId)
      .then((resp) => setJobId(resp.job_id))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Assembly failed")
      )
      .finally(() => setIsAssembling(false));
  };

  const pct = jobQuery.data?.progress_pct ?? 0;
  const status = jobQuery.data?.status;

  if (videoArtifact) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Video assembled ✓</h2>
        <p className="text-sm text-green-700">
          Your video is ready. Continue to the Done step to download it.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Assembling your video</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          Combining slides and audio into an MP4. This usually takes under a minute.
        </p>
      </div>

      {displayError && (
        <div className="space-y-3">
          <p className="text-sm text-red-600">{displayError}</p>
          <button
            type="button"
            onClick={retry}
            className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {(isAssembling || status === "queued" || status === "running") && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm text-[var(--color-muted-foreground)]">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
            {isAssembling
              ? "Enqueueing assembly job…"
              : status === "queued"
                ? "Waiting for worker…"
                : "Assembling…"}
          </div>
          {status === "running" && (
            <div className="h-2 w-full rounded-full bg-[var(--color-muted)] overflow-hidden">
              <div
                className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
