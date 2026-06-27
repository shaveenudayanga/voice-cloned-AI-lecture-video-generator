// SPDX-License-Identifier: Apache-2.0
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import type { ProjectResponse, VoiceProfileSummary } from "@/lib/schemas";
import { VoiceRecorder } from "@/components/wizard/voice-recorder/VoiceRecorder";

export interface VoiceStepProps {
  projectId: string;
  project: ProjectResponse;
  onComplete: () => void;
}

function VoiceCard({
  profile,
  isSelected,
  onSelect,
}: {
  profile: VoiceProfileSummary;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      className={`rounded-[var(--radius-lg)] border p-4 transition-colors ${
        isSelected
          ? "border-[var(--color-primary)] bg-blue-50"
          : "border-[var(--color-border)] bg-white hover:border-[var(--color-primary)]"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm text-[var(--color-foreground)] truncate">
            {profile.display_name}
            {profile.is_default && (
              <span className="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                Default
              </span>
            )}
          </p>
          {profile.has_transcript && (
            <p className="mt-1 text-xs text-[var(--color-muted-foreground)] line-clamp-2">
              &ldquo;{profile.transcript_preview}&rdquo;
            </p>
          )}
          <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
            Created {new Date(profile.created_at).toLocaleDateString()}
          </p>
        </div>
        <button
          type="button"
          onClick={onSelect}
          className={`shrink-0 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-medium transition-colors ${
            isSelected
              ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
              : "border border-[var(--color-border)] hover:bg-[var(--color-muted)]"
          }`}
        >
          {isSelected ? "Selected ✓" : "Use this voice"}
        </button>
      </div>
    </div>
  );
}

export function VoiceStep({
  projectId,
  project,
  onComplete,
}: VoiceStepProps) {
  const queryClient = useQueryClient();
  const [showRecorder, setShowRecorder] = useState(false);

  const voicesQuery = useQuery({
    queryKey: ["voices"],
    queryFn: () => api.voices.list(),
  });

  const profiles = voicesQuery.data ?? [];
  const selectedId = project.voice_profile_id;

  const selectMutation = useMutation({
    mutationFn: (profileId: string) =>
      api.projects.patch(projectId, { voice_profile_id: profileId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      onComplete();
    },
  });

  const handleProfileReady = (newProfileId: string) => {
    setShowRecorder(false);
    void queryClient.invalidateQueries({ queryKey: ["voices"] });
    selectMutation.mutate(newProfileId);
  };

  const noProfiles = profiles.length === 0 && !voicesQuery.isLoading;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Choose your voice</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          Select a saved voice profile or record a new one.
        </p>
      </div>

      {/* Existing profiles */}
      {voicesQuery.isLoading && (
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Loading voice profiles…
        </p>
      )}

      {!voicesQuery.isLoading && profiles.length > 0 && !showRecorder && (
        <div className="space-y-3">
          {profiles.map((p) => (
            <VoiceCard
              key={p.id}
              profile={p}
              isSelected={p.id === selectedId}
              onSelect={() => selectMutation.mutate(p.id)}
            />
          ))}
        </div>
      )}

      {/* Record new button */}
      {!showRecorder && (
        <button
          type="button"
          onClick={() => setShowRecorder(true)}
          className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
        >
          ● Record new voice
        </button>
      )}

      {/* Selected confirmation */}
      {selectedId && !selectMutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-green-700 font-medium">
          <span>✓</span>
          <span>
            Voice profile selected
            {profiles.find((p) => p.id === selectedId)
              ? ` — ${profiles.find((p) => p.id === selectedId)?.display_name}`
              : ""}
          </span>
        </div>
      )}

      {selectMutation.isError && (
        <p className="text-sm text-red-600">
          Failed to set voice profile. Please try again.
        </p>
      )}

      {/* Recorder */}
      {(showRecorder || noProfiles) && (
        <div className="space-y-3">
          {showRecorder && profiles.length > 0 && (
            <button
              type="button"
              onClick={() => setShowRecorder(false)}
              className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            >
              ← Back to saved profiles
            </button>
          )}
          <VoiceRecorder onProfileReady={handleProfileReady} />
        </div>
      )}
    </div>
  );
}
