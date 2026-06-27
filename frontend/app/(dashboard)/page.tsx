// SPDX-License-Identifier: Apache-2.0
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import type { ProjectResponse } from "@/lib/schemas";

const STEP_BADGE: Record<string, string> = {
  upload: "Upload",
  voice: "Voice",
  scripts: "Scripts",
  audio: "Audio",
  render: "Render",
  done: "Done ✓",
};

function ProjectCard({ project }: { project: ProjectResponse }) {
  const router = useRouter();
  const step = project.wizard_step;
  const label = STEP_BADGE[step] ?? step;
  const isDone = step === "done";

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-[var(--color-foreground)] text-base leading-tight">
            {project.title}
          </h2>
          <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
            Created {new Date(project.created_at).toLocaleDateString()}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isDone
              ? "bg-green-100 text-green-800"
              : "bg-blue-100 text-blue-700"
          }`}
        >
          {label}
        </span>
      </div>
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() =>
            router.push(
              `/projects/${project.id}/wizard?step=${project.wizard_step}`
            )
          }
          className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-1.5 text-sm font-medium text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity"
        >
          {isDone ? "View" : "Continue"}
        </button>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects.list(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.projects.create({ title: `Lecture ${new Date().toLocaleDateString()}` }),
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}/wizard?step=upload`);
    },
  });

  const projects = projectsQuery.data ?? [];
  const isCreating = createMutation.isPending;

  return (
    <main className="p-8">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">My Lectures</h1>
          <button
            type="button"
            disabled={isCreating}
            onClick={() => createMutation.mutate()}
            className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-2 text-[var(--color-primary-foreground)] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            {isCreating ? "Creating…" : "Create new lecture video"}
          </button>
        </div>

        {createMutation.isError && (
          <p className="mt-3 text-sm text-red-600">
            Failed to create project. Please try again.
          </p>
        )}

        <div className="mt-8">
          {projectsQuery.isLoading && (
            <p className="text-[var(--color-muted-foreground)]">Loading…</p>
          )}
          {projectsQuery.isError && (
            <p className="text-red-600">Failed to load projects.</p>
          )}
          {!projectsQuery.isLoading && projects.length === 0 && (
            <p className="text-[var(--color-muted-foreground)]">
              No lectures yet. Create your first one above.
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
