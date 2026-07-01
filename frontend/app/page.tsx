// SPDX-License-Identifier: Apache-2.0
"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";

export default function HomePage() {
  const router = useRouter();

  const createMutation = useMutation({
    mutationFn: () =>
      api.projects.create({ title: `Lecture ${new Date().toLocaleDateString()}` }),
    onSuccess: (project) => {
      router.push(`/projects/${project.id}/wizard?step=upload`);
    },
  });

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">LectureVoice</h1>
        <p className="mt-3 text-lg text-[var(--color-muted-foreground)]">
          Turn your lecture slides into narrated videos — in your own voice.
        </p>
      </div>

      <button
        type="button"
        disabled={createMutation.isPending}
        onClick={() => createMutation.mutate()}
        className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-6 py-3 text-[var(--color-primary-foreground)] font-semibold shadow hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {createMutation.isPending ? "Creating…" : "Create new lecture video"}
      </button>

      {createMutation.isError && (
        <p className="text-sm text-red-600">Failed to create project. Please try again.</p>
      )}

      <p className="text-sm text-[var(--color-muted-foreground)]">
        Self-hosted · Open-source · Your voice stays on your machine
      </p>
    </main>
  );
}
