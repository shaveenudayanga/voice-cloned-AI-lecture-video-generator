// SPDX-License-Identifier: Apache-2.0
// Dashboard — lists existing projects and provides the "Create new lecture video" entry point.
// Phase 7 wires the create button to POST /api/v1/projects and redirects into the wizard.
export default function DashboardPage() {
  return (
    <main className="p-8">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">My Lectures</h1>
          <button
            className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-2 text-[var(--color-primary-foreground)] font-medium hover:opacity-90 transition-opacity"
            type="button"
          >
            Create new lecture video
          </button>
        </div>
        <div className="mt-8 text-[var(--color-muted-foreground)]">
          No lectures yet. Create your first one above.
        </div>
      </div>
    </main>
  );
}
