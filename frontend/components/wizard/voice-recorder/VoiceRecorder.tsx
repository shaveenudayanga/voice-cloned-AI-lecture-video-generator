// SPDX-License-Identifier: Apache-2.0
// MediaRecorder-based voice capture. No external audio libraries.
// Level meter uses Web Audio AnalyserNode + requestAnimationFrame (never setInterval).
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

type RecorderState =
  | "idle"
  | "recording"
  | "recorded"
  | "uploading"
  | "ingesting"
  | "previewing"
  | "done"
  | "error";

export interface VoiceRecorderProps {
  /** Displayed name for the new profile (user can customise). */
  defaultDisplayName?: string;
  /** Called with the new profile's ID once ingestion + preview complete. */
  onProfileReady: (profileId: string) => void;
}

const PROMPT_TEXT =
  "Please speak naturally as you would during a lecture. Explain a concept, " +
  "describe a diagram, or read through a few slides. Aim for about 60 seconds " +
  "of clear speech.";

export function VoiceRecorder({
  defaultDisplayName = "My voice",
  onProfileReady,
}: VoiceRecorderProps) {
  // --- Core state ---
  const [state, setState] = useState<RecorderState>("idle");
  const [displayName, setDisplayName] = useState(defaultDisplayName);
  // errorMsg covers errors not visible in query data (upload fail, preview api fail)
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [ingestJobId, setIngestJobId] = useState<string | null>(null);
  const [previewJobId, setPreviewJobId] = useState<string | null>(null);

  // --- Refs ---
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  // Guard refs — prevent duplicate side-effects in React StrictMode double-invoke
  const ingestHandledRef = useRef(false);
  const profileReadyFiredRef = useRef(false);

  // Cancel any pending RAF frame on unmount
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    []
  );

  // -------------------------------------------------------------------------
  // Poll ingest job → trigger preview API call when complete
  // -------------------------------------------------------------------------
  const ingestQuery = useQuery({
    queryKey: ["job", ingestJobId],
    queryFn: () => api.jobs.get(ingestJobId!),
    enabled: !!ingestJobId && state === "ingesting",
    refetchInterval: (q: { state: { data?: { status: string } } }) => {
      const s = q.state.data?.status;
      return s === "complete" || s === "failed" ? false : 2000;
    },
    staleTime: 0,
  });

  // When ingest completes, call the preview API.
  // All setState is in .then()/.catch() (async) — satisfies react-hooks/set-state-in-effect.
  // When ingest fails, error is derived below; no setState here.
  useEffect(() => {
    if (ingestHandledRef.current || !ingestQuery.data || !profileId) return;
    if (ingestQuery.data.status === "complete") {
      ingestHandledRef.current = true;
      api.voices
        .preview(profileId)
        .then((resp) => {
          setPreviewJobId(resp.job_id);
          setState("previewing");
        })
        .catch((e: unknown) => {
          setErrorMsg(e instanceof Error ? e.message : "Preview failed");
          setState("error");
        });
    }
    if (ingestQuery.data.status === "failed") {
      ingestHandledRef.current = true;
      // effectiveState (derived below) will show "error" UI; no setState needed here.
    }
  }, [ingestQuery.data, profileId]);

  // -------------------------------------------------------------------------
  // Poll preview job → fetch full profile once complete
  // -------------------------------------------------------------------------
  const previewJobQuery = useQuery({
    queryKey: ["job", previewJobId],
    queryFn: () => api.jobs.get(previewJobId!),
    enabled: !!previewJobId && state === "previewing",
    refetchInterval: (q: { state: { data?: { status: string } } }) => {
      const s = q.state.data?.status;
      return s === "complete" || s === "failed" ? false : 2000;
    },
    staleTime: 0,
  });

  // Fetch the full profile to confirm blob key once preview job finishes
  const profileQuery = useQuery({
    queryKey: ["voice-profile", profileId],
    queryFn: () => api.voices.get(profileId!),
    enabled: !!profileId && previewJobQuery.data?.status === "complete",
  });

  // Call onProfileReady once when the profile is fully ready.
  // No setState in the effect body — onProfileReady is a prop callback, not a state setter.
  useEffect(() => {
    if (
      !profileReadyFiredRef.current &&
      profileId &&
      previewJobQuery.data?.status === "complete" &&
      profileQuery.data
    ) {
      profileReadyFiredRef.current = true;
      onProfileReady(profileId);
    }
  }, [profileQuery.data, profileId, previewJobQuery.data, onProfileReady]);

  // -------------------------------------------------------------------------
  // Derived state — error/done transitions come from query data, not setState
  // -------------------------------------------------------------------------
  const effectiveState: RecorderState = (() => {
    if (state === "ingesting" && ingestQuery.data?.status === "failed")
      return "error";
    if (state === "previewing" && previewJobQuery.data?.status === "failed")
      return "error";
    if (
      state === "previewing" &&
      profileQuery.data &&
      previewJobQuery.data?.status === "complete"
    )
      return "done";
    return state;
  })();

  const displayErrorMsg = (() => {
    if (state === "ingesting" && ingestQuery.data?.status === "failed")
      return ingestQuery.data.error_message ?? "Transcription failed";
    if (state === "previewing" && previewJobQuery.data?.status === "failed")
      return previewJobQuery.data.error_message ?? "Preview failed";
    return errorMsg;
  })();

  // Derive preview blob key — no useState needed
  const previewBlobKey =
    profileId &&
    previewJobQuery.data?.status === "complete" &&
    profileQuery.data
      ? `voices/${profileId}/preview.wav`
      : null;

  // -------------------------------------------------------------------------
  // Record
  // -------------------------------------------------------------------------
  const startRecording = useCallback(async () => {
    setErrorMsg(null);
    chunksRef.current = [];
    blobRef.current = null;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setErrorMsg("Microphone access denied. Please allow microphone access.");
      return;
    }

    // Level meter via Web Audio
    const ctx = new AudioContext();
    audioCtxRef.current = ctx;
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserRef.current = analyser;

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      blobRef.current = new Blob(chunksRef.current, {
        type: mimeType || "audio/webm",
      });
      setState("recorded");
    };

    recorder.start(100);
    startTimeRef.current = Date.now();
    setElapsed(0);
    setState("recording");

    // Named local function — recursive reference is valid for function declarations.
    // Using a local closure avoids the circular useCallback hoisting issue (ESLint:
    // no-use-before-define on a const would fire; a named function decl is fine).
    function animTick() {
      if (startTimeRef.current !== null) {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
      if (analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const avg = data.reduce((s, v) => s + v, 0) / data.length;
        setLevel(Math.min(1, avg / 128));
      }
      rafRef.current = requestAnimationFrame(animTick);
    }
    rafRef.current = requestAnimationFrame(animTick);
  }, []);

  const stopRecording = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    recorderRef.current?.stop();
    if (audioCtxRef.current) {
      void audioCtxRef.current.close();
      audioCtxRef.current = null;
      analyserRef.current = null;
    }
  }, []);

  const reRecord = useCallback(() => {
    blobRef.current = null;
    ingestHandledRef.current = false;
    profileReadyFiredRef.current = false;
    setElapsed(0);
    setLevel(0);
    setProfileId(null);
    setIngestJobId(null);
    setPreviewJobId(null);
    setErrorMsg(null);
    setState("idle");
  }, []);

  const playback = useCallback(() => {
    if (!blobRef.current) return;
    const url = URL.createObjectURL(blobRef.current);
    const audio = new Audio(url);
    playbackRef.current = audio;
    audio.onended = () => URL.revokeObjectURL(url);
    void audio.play();
  }, []);

  // -------------------------------------------------------------------------
  // Upload + ingest
  // -------------------------------------------------------------------------
  const uploadAndIngest = useCallback(async () => {
    if (!blobRef.current) return;
    setState("uploading");
    setErrorMsg(null);

    try {
      const resp = await api.voices.create(blobRef.current, displayName);
      setProfileId(resp.profile_id);
      setIngestJobId(resp.job_id);
      setState("ingesting");
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
      setState("error");
    }
  }, [displayName]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="space-y-5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-6">
      <p className="text-sm text-[var(--color-muted-foreground)] italic">
        {PROMPT_TEXT}
      </p>

      {/* Display name */}
      {(effectiveState === "idle" || effectiveState === "recorded") && (
        <div>
          <label className="block text-xs font-medium text-[var(--color-foreground)] mb-1">
            Voice profile name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-ring)]"
          />
        </div>
      )}

      {/* Level meter */}
      {effectiveState === "recording" && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-[var(--color-muted-foreground)]">
            <span>Recording…</span>
            <span className="font-mono">{fmtTime(elapsed)}</span>
          </div>
          <div className="h-3 w-full rounded-full bg-[var(--color-muted)] overflow-hidden">
            <div
              className="h-full rounded-full bg-red-500 transition-all duration-75"
              style={{ width: `${Math.round(level * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Buttons */}
      <div className="flex flex-wrap gap-3">
        {effectiveState === "idle" && (
          <button
            type="button"
            onClick={() => void startRecording()}
            className="rounded-[var(--radius-md)] bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            ● Record
          </button>
        )}

        {effectiveState === "recording" && (
          <button
            type="button"
            onClick={stopRecording}
            className="rounded-[var(--radius-md)] bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900 transition-colors"
          >
            ■ Stop
          </button>
        )}

        {effectiveState === "recorded" && (
          <>
            <button
              type="button"
              onClick={playback}
              className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
            >
              ▶ Play back
            </button>
            <button
              type="button"
              onClick={reRecord}
              className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
            >
              ↺ Re-record
            </button>
            <button
              type="button"
              onClick={() => void uploadAndIngest()}
              className="rounded-[var(--radius-md)] bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-primary-foreground)] hover:opacity-90 transition-opacity"
            >
              Use this recording
            </button>
          </>
        )}

        {(effectiveState === "uploading" ||
          effectiveState === "ingesting" ||
          effectiveState === "previewing") && (
          <div className="flex items-center gap-3 text-sm text-[var(--color-muted-foreground)]">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
            {effectiveState === "uploading" && "Uploading…"}
            {effectiveState === "ingesting" && "Transcribing your voice sample…"}
            {effectiveState === "previewing" && "Synthesising clone preview…"}
          </div>
        )}

        {effectiveState === "done" && (
          <p className="text-sm font-medium text-green-700">
            ✓ Voice profile ready — hear the clone preview below
          </p>
        )}

        {effectiveState === "error" && (
          <>
            <p className="text-sm text-red-600">{displayErrorMsg}</p>
            <button
              type="button"
              onClick={reRecord}
              className="rounded-[var(--radius-md)] border border-[var(--color-border)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-muted)] transition-colors"
            >
              Try again
            </button>
          </>
        )}
      </div>

      {/* Transcription status */}
      {effectiveState === "ingesting" && (() => {
        const r = ingestQuery.data?.result;
        const transcript = r && typeof r["transcript"] === "string" ? r["transcript"].slice(0, 120) : null;
        return transcript ? (
          <p className="text-xs text-[var(--color-muted-foreground)]">
            Transcript preview: {transcript}…
          </p>
        ) : null;
      })()}

      {/* Clone preview playback */}
      {effectiveState === "done" && previewBlobKey && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-[var(--color-foreground)]">
            Clone preview (your synthesised voice):
          </p>
          <ClonePreviewAudio blobKey={previewBlobKey} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helper: fetches preview blob as object URL for the <audio> element
// ---------------------------------------------------------------------------

function ClonePreviewAudio({ blobKey }: { blobKey: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;
    api.blobs
      .get(blobKey)
      .then((b) => {
        if (!active) return;
        createdUrl = URL.createObjectURL(b);
        setObjectUrl(createdUrl); // async .then() — not synchronous in effect body
      })
      .catch(() => null);
    return () => {
      active = false;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [blobKey]);

  if (!objectUrl) return null;
  return <audio controls src={objectUrl} className="w-full" />;
}

