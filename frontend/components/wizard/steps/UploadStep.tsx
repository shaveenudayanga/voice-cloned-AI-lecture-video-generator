// SPDX-License-Identifier: Apache-2.0
"use client";

import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { SlideItem } from "@/lib/schemas";
import { JobProgress } from "@/components/wizard/job-progress/JobProgress";
import { useBlobUrl } from "@/lib/hooks/use-blob-url";

export interface UploadStepProps {
  projectId: string;
  slides: SlideItem[];
  onComplete: () => void;
}

function SlideThumbnail({ blobKey }: { blobKey: string }) {
  const url = useBlobUrl(blobKey);
  if (!url) {
    return (
      <div className="h-24 w-full rounded bg-[var(--color-muted)] flex items-center justify-center text-xs text-[var(--color-muted-foreground)]">
        Loading…
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt="Slide thumbnail"
      className="h-24 w-full rounded object-contain bg-white border border-[var(--color-border)]"
    />
  );
}

export function UploadStep({ projectId, slides, onComplete }: UploadStepProps) {
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [isComplete, setIsComplete] = useState(slides.length > 0);
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "pdf" && ext !== "pptx") {
        setUploadError("Only PDF and PPTX files are supported.");
        return;
      }
      setUploadError(null);
      setIsUploading(true);
      setIsComplete(false);
      try {
        const resp = await api.slides.upload(projectId, file);
        setFileName(file.name);
        setJobIds([resp.job_id]);
      } catch (e: unknown) {
        setUploadError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [projectId]
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) void handleFile(file);
    },
    [handleFile]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile]
  );

  const hasSlides = slides.length > 0;
  const previewSlides = slides.slice(0, 3);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Upload your slide deck</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          PDF or PowerPoint (PPTX). Max 50 MB.
        </p>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload slide deck"
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
        className={`flex flex-col items-center justify-center rounded-[var(--radius-lg)] border-2 border-dashed p-12 cursor-pointer transition-colors ${
          isDragging
            ? "border-[var(--color-primary)] bg-blue-50"
            : "border-[var(--color-border)] hover:border-[var(--color-primary)]"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.pptx"
          className="hidden"
          onChange={onFileChange}
        />
        <p className="text-sm font-medium text-[var(--color-foreground)]">
          {isDragging ? "Drop to upload" : "Drag & drop or click to browse"}
        </p>
        <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
          PDF · PPTX
        </p>
      </div>

      {/* Upload error */}
      {uploadError && (
        <p className="text-sm text-red-600">{uploadError}</p>
      )}

      {/* Uploading spinner */}
      {isUploading && (
        <div className="flex items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
          Uploading…
        </div>
      )}

      {/* File name + job progress */}
      {jobIds.length > 0 && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4 space-y-3">
          {fileName && (
            <p className="text-sm font-medium text-[var(--color-foreground)]">
              📄 {fileName}
            </p>
          )}
          <JobProgress
            job_ids={jobIds}
            label="Processing slides…"
            onAllComplete={() => {
              setIsComplete(true);
              onComplete();
            }}
            onAnyFailed={(_, err) => setUploadError(`Processing failed: ${err}`)}
          />
        </div>
      )}

      {/* Slide thumbnails + summary after ingestion */}
      {(hasSlides || isComplete) && slides.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-green-700">
            ✓ {slides.length} slide{slides.length !== 1 ? "s" : ""} ready
          </p>
          <div className="grid grid-cols-3 gap-3">
            {previewSlides.map((slide) => (
              <div key={slide.id} className="space-y-1">
                <SlideThumbnail blobKey={slide.image_blob_key} />
                <p className="text-center text-xs text-[var(--color-muted-foreground)]">
                  Slide {slide.order_index + 1}
                </p>
              </div>
            ))}
          </div>
          {slides.length > 3 && (
            <p className="text-xs text-[var(--color-muted-foreground)]">
              +{slides.length - 3} more slides
            </p>
          )}
        </div>
      )}
    </div>
  );
}
