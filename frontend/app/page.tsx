// SPDX-License-Identifier: Apache-2.0
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">LectureVoice</h1>
        <p className="mt-3 text-lg text-[var(--color-muted-foreground)]">
          Turn your lecture slides into narrated videos — in your own voice.
        </p>
      </div>

      {/* Phase 7 will wire this button to POST /api/v1/projects then redirect */}
      <button
        className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-6 py-3 text-[var(--color-primary-foreground)] font-semibold shadow hover:opacity-90 transition-opacity"
        type="button"
      >
        Create new lecture video
      </button>

      <p className="text-sm text-[var(--color-muted-foreground)]">
        Self-hosted · Open-source · Your voice stays on your machine
      </p>
    </main>
  );
}
