// SPDX-License-Identifier: Apache-2.0
// Wizard shell — single route that renders every step based on ?step= query param.
//
// TWO DIFFERENT THINGS (§constraints):
//   ?step=           → what renders RIGHT NOW (URL state)
//   project.wizard_step → the FURTHEST step ever reached (DB-persisted for resume)
//
// Back always changes URL only. Advancing past wizard_step also PATCHes the project.
"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { api } from "@/lib/api-client";
import type { WizardProjectState } from "@/lib/wizard-state";
import {
  STEP_LABELS,
  STEP_ORDER,
  canAdvanceTo,
  getNextStep,
  getPrevStep,
  isStepComplete,
  isValidStep,
  type WizardStep,
} from "@/lib/wizard-state";
import type {
  AudioClipItem,
  ProjectResponse,
  ScriptListItem,
  SlideItem,
  VideoArtifactResponse,
} from "@/lib/schemas";

import { UploadStep } from "@/components/wizard/steps/UploadStep";
import { VoiceStep } from "@/components/wizard/steps/VoiceStep";
import { ScriptsStep } from "@/components/wizard/steps/ScriptsStep";
import { AudioStep } from "@/components/wizard/steps/AudioStep";
import { RenderStep } from "@/components/wizard/steps/RenderStep";
import { DoneStep } from "@/components/wizard/steps/DoneStep";

// ---------------------------------------------------------------------------
// Stepper header
// ---------------------------------------------------------------------------

interface StepperProps {
  currentStep: WizardStep;
  project: WizardProjectState;
}

function Stepper({ currentStep, project }: StepperProps) {
  return (
    <nav aria-label="Wizard progress" className="flex items-center gap-1">
      {STEP_ORDER.map((step, idx) => {
        const complete = isStepComplete(step, project);
        const isActive = step === currentStep;
        const stepIdx = STEP_ORDER.indexOf(currentStep);
        const isPast = idx < stepIdx;

        return (
          <div key={step} className="flex items-center">
            <div
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
                  : complete || isPast
                    ? "bg-green-100 text-green-800"
                    : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)]"
              }`}
            >
              <span
                className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${
                  isActive
                    ? "bg-white text-[var(--color-primary)]"
                    : complete || isPast
                      ? "bg-green-500 text-white"
                      : "bg-[var(--color-border)] text-[var(--color-muted-foreground)]"
                }`}
              >
                {complete && !isActive ? "✓" : idx + 1}
              </span>
              {STEP_LABELS[step]}
            </div>
            {idx < STEP_ORDER.length - 1 && (
              <div className="mx-1 h-px w-4 bg-[var(--color-border)]" />
            )}
          </div>
        );
      })}
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Prerequisite tooltips for locked Next button
// ---------------------------------------------------------------------------

const PREREQ_HINTS: Record<WizardStep, string> = {
  upload: "",
  voice: "Upload slides first",
  scripts: "Select a voice profile first",
  audio: "Generate scripts for all slides first",
  render: "Synthesise audio for all slides first",
  done: "Assemble the video first",
};

// ---------------------------------------------------------------------------
// Inner wizard (needs Suspense for useSearchParams)
// ---------------------------------------------------------------------------

function WizardInner() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  // --- Fetch project + prerequisite counts (parallel) ---
  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.projects.get(projectId),
    enabled: !!projectId,
  });

  const slidesQuery = useQuery({
    queryKey: ["slides", projectId],
    queryFn: () => api.slides.list(projectId),
    enabled: !!projectId,
  });

  const scriptsQuery = useQuery({
    queryKey: ["scripts", projectId],
    queryFn: () => api.scripts.list(projectId),
    enabled: !!projectId,
  });

  const audioQuery = useQuery({
    queryKey: ["audio", projectId],
    queryFn: () => api.audio.list(projectId),
    enabled: !!projectId,
  });

  const videoQuery = useQuery({
    queryKey: ["video", projectId],
    queryFn: async (): Promise<VideoArtifactResponse | null> => {
      try {
        return await api.video.get(projectId);
      } catch (e) {
        if (e instanceof Error && e.message.includes("404")) return null;
        throw e;
      }
    },
    enabled: !!projectId,
    retry: 0,
  });

  const project = projectQuery.data;
  const slidesList: SlideItem[] = slidesQuery.data?.slides ?? [];
  const scriptsList: ScriptListItem[] = scriptsQuery.data ?? [];
  const audioList: AudioClipItem[] = audioQuery.data ?? [];
  const videoArtifact: VideoArtifactResponse | null = videoQuery.data ?? null;

  // --- Build WizardProjectState ---
  const projectState: WizardProjectState = {
    wizard_step: project?.wizard_step ?? "upload",
    voice_profile_id: project?.voice_profile_id ?? null,
    slide_count: slidesList.length,
    script_count: scriptsList.length,
    audio_clip_count: audioList.length,
    has_video_artifact: videoArtifact !== null,
  };

  // --- Resolve current step from URL (or default to furthest reached) ---
  const stepParam = searchParams.get("step");
  const currentStep: WizardStep = isValidStep(stepParam)
    ? stepParam
    : (project?.wizard_step ?? "upload");

  // On first load: if URL has no ?step=, replace with the project's wizard_step
  useEffect(() => {
    if (!project) return;
    if (!stepParam) {
      router.replace(
        `/projects/${projectId}/wizard?step=${project.wizard_step}`
      );
    }
  }, [project, stepParam, projectId, router]);

  // --- Navigation ---
  const handleBack = () => {
    const prev = getPrevStep(currentStep);
    if (prev) {
      router.push(`/projects/${projectId}/wizard?step=${prev}`);
    }
  };

  const handleNext = async () => {
    const next = getNextStep(currentStep);
    if (!next || !canAdvanceTo(next, projectState)) return;

    // Advance wizard_step in DB when moving past the current furthest step
    const currentIdx = STEP_ORDER.indexOf(currentStep);
    const furthestIdx = STEP_ORDER.indexOf(
      project?.wizard_step ?? "upload"
    );
    if (currentIdx >= furthestIdx) {
      try {
        await api.projects.patch(projectId, { wizard_step: next });
        await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      } catch {
        // Non-fatal — navigation still proceeds
      }
    }

    router.push(`/projects/${projectId}/wizard?step=${next}`);
  };

  // Callback for step components that want to refresh prerequisite counts
  const refreshCounts = () => {
    void queryClient.invalidateQueries({ queryKey: ["slides", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["scripts", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["audio", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["video", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
  };

  // -------------------------------------------------------------------------

  // Wait for the prerequisite queries too, not just the project. Step components
  // auto-trigger work when their inputs look empty (ScriptsStep generates,
  // AudioStep synthesises, RenderStep assembles). If we render them before these
  // queries resolve, `scripts.length === 0` etc. is transiently true and fires a
  // spurious (and destructive/expensive) regeneration. Gate until data is loaded.
  const prerequisitesLoading =
    slidesQuery.isLoading ||
    scriptsQuery.isLoading ||
    audioQuery.isLoading ||
    videoQuery.isLoading;

  if (projectQuery.isLoading || prerequisitesLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--color-muted-foreground)]">
        Loading…
      </div>
    );
  }

  if (projectQuery.isError || !project) {
    return (
      <div className="flex min-h-screen items-center justify-center text-red-600">
        Project not found.
      </div>
    );
  }

  const prev = getPrevStep(currentStep);
  const next = getNextStep(currentStep);
  const nextBlocked = next ? !canAdvanceTo(next, projectState) : true;
  const nextHint = next ? (PREREQ_HINTS[next] ?? "") : "";

  const renderStep = () => {
    switch (currentStep) {
      case "upload":
        return (
          <UploadStep
            projectId={projectId}
            slides={slidesList}
            onComplete={refreshCounts}
          />
        );
      case "voice":
        return (
          <VoiceStep
            projectId={projectId}
            project={project as ProjectResponse}
            onComplete={refreshCounts}
          />
        );
      case "scripts":
        return (
          <ScriptsStep
            projectId={projectId}
            slides={slidesList}
            scripts={scriptsList}
            onComplete={refreshCounts}
          />
        );
      case "audio":
        return (
          <AudioStep
            projectId={projectId}
            slides={slidesList}
            audioClips={audioList}
            onNavigate={(step) =>
              router.push(`/projects/${projectId}/wizard?step=${step}`)
            }
            onComplete={refreshCounts}
          />
        );
      case "render":
        return (
          <RenderStep
            projectId={projectId}
            videoArtifact={videoArtifact}
            onComplete={() => {
              refreshCounts();
              router.push(`/projects/${projectId}/wizard?step=done`);
            }}
          />
        );
      case "done":
        return (
          <DoneStep
            projectId={projectId}
            project={project as ProjectResponse}
            videoArtifact={videoArtifact}
          />
        );
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-[var(--color-border)] bg-white px-6 py-4">
        <div className="mx-auto max-w-5xl">
          <div className="flex items-center justify-between">
            <Link
              href="/"
              className="text-sm font-medium text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            >
              ← Dashboard
            </Link>
            <span className="text-sm font-medium text-[var(--color-foreground)]">
              {project.title}
            </span>
          </div>
          <div className="mt-4 overflow-x-auto">
            <Stepper currentStep={currentStep} project={projectState} />
          </div>
        </div>
      </header>

      {/* Step content */}
      <main className="flex-1 bg-[var(--color-muted)] px-6 py-8">
        <div className="mx-auto max-w-5xl">{renderStep()}</div>
      </main>

      {/* Footer navigation */}
      <footer className="border-t border-[var(--color-border)] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <button
            type="button"
            onClick={handleBack}
            disabled={!prev}
            className="flex items-center gap-1 rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-foreground)] hover:bg-[var(--color-muted)] transition-colors disabled:opacity-40"
          >
            <ChevronLeft size={16} />
            Back
          </button>

          {next && (
            <div className="relative group">
              <button
                type="button"
                onClick={() => void handleNext()}
                disabled={nextBlocked}
                className="flex items-center gap-1 rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                Next
                <ChevronRight size={16} />
              </button>
              {nextBlocked && nextHint && (
                <div className="pointer-events-none absolute bottom-full right-0 mb-2 hidden rounded bg-gray-900 px-2 py-1 text-xs text-white group-hover:block whitespace-nowrap">
                  {nextHint}
                </div>
              )}
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export — Suspense required for useSearchParams
// ---------------------------------------------------------------------------

export default function WizardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-[var(--color-muted-foreground)]">
          Loading…
        </div>
      }
    >
      <WizardInner />
    </Suspense>
  );
}
