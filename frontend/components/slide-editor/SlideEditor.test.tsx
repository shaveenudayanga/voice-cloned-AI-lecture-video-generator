// @vitest-environment jsdom
// SPDX-License-Identifier: Apache-2.0
/**
 * Unit tests for SlideEditor (Phase 8).
 *
 * Mocks: useBlobUrl, api, JobProgress.
 * No network calls, no TanStack Query server-state fetching.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SlideEditor } from "./SlideEditor";
import type { ScriptListItem, SlideItem } from "@/lib/schemas";

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/use-blob-url", () => ({
  useBlobUrl: (_key: string | null) => (_key ? "blob:fake-url" : null),
}));

vi.mock("@/lib/api-client", () => ({
  api: {
    scripts: {
      patch: vi.fn().mockResolvedValue({}),
      regenerateSlide: vi
        .fn()
        .mockResolvedValue({ job_id: "regen-job-id", slide_id: "slide-1", status: "queued" }),
      list: vi.fn().mockResolvedValue([]),
    },
    audio: {
      synthesizeSlide: vi
        .fn()
        .mockResolvedValue({ job_id: "preview-job-id", slide_id: "slide-1", status: "queued" }),
      list: vi.fn().mockResolvedValue([]),
    },
    jobs: {
      get: vi.fn().mockResolvedValue({
        job_id: "regen-job-id",
        status: "queued",
        progress_pct: 0,
        error_message: null,
        result: null,
      }),
    },
  },
}));

// Stub JobProgress so we don't need a full TanStack Query setup for nested polling
vi.mock("@/components/wizard/job-progress/JobProgress", () => ({
  JobProgress: ({
    label,
    onAllComplete,
  }: {
    label: string;
    onAllComplete?: () => void;
  }) => (
    <div data-testid="job-progress">
      {label}
      <button type="button" onClick={onAllComplete}>
        __complete__
      </button>
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SLIDES: SlideItem[] = [
  {
    id: "slide-1",
    order_index: 0,
    extracted_text: "Introduction to ML",
    image_blob_key: "lecturevoice/projects/p1/slides/0.png",
  },
  {
    id: "slide-2",
    order_index: 1,
    extracted_text: "Deep Learning",
    image_blob_key: "lecturevoice/projects/p1/slides/1.png",
  },
];

const SCRIPTS: ScriptListItem[] = [
  {
    id: "script-1",
    slide_id: "slide-1",
    order_index: 0,
    text: "This is the first slide script.",
    estimated_reading_seconds: 120,
    pronunciation_hints: null,
    version: 1,
    script_hash: "hash1",
  },
  {
    id: "script-2",
    slide_id: "slide-2",
    order_index: 1,
    text: "This is the second slide script.",
    estimated_reading_seconds: 60,
    pronunciation_hints: null,
    version: 1,
    script_hash: "hash2",
  },
];

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

function renderEditor(
  overrides: Partial<{
    slides: SlideItem[];
    scripts: ScriptListItem[];
  }> = {}
) {
  const onScriptSaved = vi.fn();
  const result = render(
    <SlideEditor
      projectId="project-1"
      slides={overrides.slides ?? SLIDES}
      scripts={overrides.scripts ?? SCRIPTS}
      onScriptSaved={onScriptSaved}
    />,
    { wrapper: makeWrapper() }
  );
  return { ...result, onScriptSaved };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SlideEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders slide image and script text for slide 1", () => {
    renderEditor();
    // Slide counter
    expect(screen.getByText("Slide 1 of 2")).toBeInTheDocument();
    // Image
    expect(screen.getByRole("img", { name: "Slide 1" })).toBeInTheDocument();
    // Script text in textarea
    expect(
      screen.getByDisplayValue("This is the first slide script.")
    ).toBeInTheDocument();
  });

  it("clicking Next renders slide 2 content", async () => {
    renderEditor();
    const nextBtn = screen.getByRole("button", { name: "Next slide" });
    await userEvent.click(nextBtn);
    expect(screen.getByText("Slide 2 of 2")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("This is the second slide script.")
    ).toBeInTheDocument();
  });

  it("Save button is disabled when text is unchanged", () => {
    renderEditor();
    const saveBtn = screen.getByRole("button", { name: "Save" });
    expect(saveBtn).toBeDisabled();
  });

  it("Save button is enabled after editing text", async () => {
    renderEditor();
    const textarea = screen.getByDisplayValue("This is the first slide script.");
    await userEvent.type(textarea, " extra");
    const saveBtn = screen.getByRole("button", { name: "Save" });
    expect(saveBtn).toBeEnabled();
  });

  it("shows 'Unsaved changes' label when text differs from saved", async () => {
    renderEditor();
    const textarea = screen.getByDisplayValue("This is the first slide script.");
    await userEvent.type(textarea, " edited");
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("switching slides with unsaved changes shows confirmation dialog", async () => {
    renderEditor();
    // Edit the textarea to create unsaved changes
    const textarea = screen.getByDisplayValue("This is the first slide script.");
    await userEvent.type(textarea, " edited");
    // Click Next → should trigger dialog, NOT navigate
    const nextBtn = screen.getByRole("button", { name: "Next slide" });
    await userEvent.click(nextBtn);
    // Dialog must appear
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/unsaved changes on slide 1/i)).toBeInTheDocument();
    // Discard button must be present
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();
    // Go back button must be present
    expect(
      screen.getByRole("button", { name: "Go back and save" })
    ).toBeInTheDocument();
  });

  it("ArrowRight keyboard event advances to next slide when textarea is not focused", async () => {
    renderEditor();
    // Move focus away from textarea
    await userEvent.click(document.body);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    await waitFor(() => {
      expect(
        screen.getByDisplayValue("This is the second slide script.")
      ).toBeInTheDocument();
    });
  });

  it("displays correct estimated reading time for 120 seconds", () => {
    renderEditor();
    // Slide 1 has estimated_reading_seconds: 120 → ~2 min 0 sec
    expect(screen.getByText("~2 min 0 sec")).toBeInTheDocument();
  });
});
