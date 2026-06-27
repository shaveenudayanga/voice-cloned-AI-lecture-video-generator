// SPDX-License-Identifier: Apache-2.0
// Polls a list of job IDs via TanStack Query (never setInterval).
// Stops polling automatically once every job is complete or failed.
"use client";

import { useQueries } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api-client";
import type { JobResponse } from "@/lib/schemas";

export interface JobProgressProps {
  /** UUIDs to poll. Can change over time (e.g., new slides added). */
  job_ids: string[];
  /** Label shown above the progress bar. */
  label: string;
  /** Called once when every job reaches "complete". */
  onAllComplete?: () => void;
  /** Called when any job reaches "failed", with its job_id and error. */
  onAnyFailed?: (failedJobId: string, error: string) => void;
}

type DotColor = "grey" | "blue" | "green" | "red";

function statusDotColor(status: JobResponse["status"] | undefined): DotColor {
  switch (status) {
    case "queued":
      return "grey";
    case "running":
      return "blue";
    case "complete":
      return "green";
    case "failed":
      return "red";
    default:
      return "grey";
  }
}

const DOT_CLASS: Record<DotColor, string> = {
  grey: "bg-gray-300",
  blue: "bg-blue-500 animate-pulse",
  green: "bg-green-500",
  red: "bg-red-500",
};

export function JobProgress({
  job_ids,
  label,
  onAllComplete,
  onAnyFailed,
}: JobProgressProps) {
  // Track which callbacks have already fired to avoid duplicate calls
  const allCompleteFired = useRef(false);
  const failedFired = useRef(new Set<string>());

  const queries = useQueries({
    queries: job_ids.map((id) => ({
      queryKey: ["job", id],
      queryFn: () => api.jobs.get(id),
      refetchInterval: (query: { state: { data?: JobResponse } }) => {
        const s = query.state.data?.status;
        return s === "complete" || s === "failed" ? false : 2000;
      },
      staleTime: 0,
      enabled: !!id,
    })),
  });

  const results: Array<JobResponse | undefined> = queries.map(
    (q) => q.data as JobResponse | undefined
  );

  const total = job_ids.length;
  const completed = results.filter((r) => r?.status === "complete").length;
  const failed = results.filter((r) => r?.status === "failed").length;
  const allDone = total > 0 && completed + failed === total;
  const allCompleted = total > 0 && completed === total;

  // Callbacks
  useEffect(() => {
    if (allCompleted && !allCompleteFired.current) {
      allCompleteFired.current = true;
      onAllComplete?.();
    }
  }, [allCompleted, onAllComplete]);

  useEffect(() => {
    if (!onAnyFailed) return;
    for (let i = 0; i < results.length; i++) {
      const r = results[i];
      const id = job_ids[i];
      if (r?.status === "failed" && id && !failedFired.current.has(id)) {
        failedFired.current.add(id);
        onAnyFailed(id, r.error_message ?? "Unknown error");
      }
    }
  }, [results, job_ids, onAnyFailed]);

  // Reset fire-guards when job_ids list changes (new generation triggered)
  useEffect(() => {
    allCompleteFired.current = false;
    failedFired.current = new Set();
  }, [job_ids.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  if (total === 0) return null;

  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-[var(--color-foreground)]">{label}</span>
        <span className="text-[var(--color-muted-foreground)]">
          {completed}/{total}
        </span>
      </div>

      {/* Overall progress bar */}
      <div className="h-2 w-full rounded-full bg-[var(--color-muted)] overflow-hidden">
        <div
          className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Per-job status dots (up to 40 shown) */}
      {total <= 40 && (
        <div className="flex flex-wrap gap-1.5">
          {results.map((r, i) => {
            const color = statusDotColor(r?.status);
            return (
              <span
                key={job_ids[i] ?? i}
                title={`Slide ${i + 1}: ${r?.status ?? "queued"}`}
                className={`h-2.5 w-2.5 rounded-full ${DOT_CLASS[color]}`}
              />
            );
          })}
        </div>
      )}

      {/* Error messages */}
      {results.map((r, i) =>
        r?.status === "failed" && r.error_message ? (
          <p key={job_ids[i] ?? i} className="text-xs text-red-600">
            Slide {i + 1}: {r.error_message}
          </p>
        ) : null
      )}

      {allDone && failed === 0 && (
        <p className="text-xs text-green-700 font-medium">All done ✓</p>
      )}
    </div>
  );
}
