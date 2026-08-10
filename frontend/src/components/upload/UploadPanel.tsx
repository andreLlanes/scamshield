"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AudioDropzone } from "@/components/upload/AudioDropzone";
import { Alert, Button, Card, CardHeader, Spinner } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import { classNames } from "@/lib/format";

type Mode = "audio" | "text";

const SAMPLE_TRANSCRIPT = `Good afternoon, this is the security department of your bank.
We detected an unauthorized transaction of fifteen thousand pesos on your account this morning.
Your account will be permanently locked within the next 10 minutes unless we reverse it now.
Please do not hang up and stay on the line while I process this.
To confirm your identity I need you to read me the six digit verification code we just sent to your phone.
Do not tell anyone about this call, it is a confidential security investigation.`;

export function UploadPanel({ onSubmitted }: { onSubmitted?: () => void }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("audio");
  const [file, setFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    !isSubmitting && (mode === "audio" ? Boolean(file) : transcript.trim().length >= 10);

  const submit = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const accepted =
        mode === "audio"
          ? await api.uploadAudio(file as File)
          : await api.analyzeTranscript(transcript.trim());
      onSubmitted?.();
      router.push(`/analyses/${accepted.id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.",
      );
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader
        eyebrow="Step 1"
        title="Analyse a suspicious call"
        subtitle="Upload the recording, or paste a transcript if you already have one."
      />

      <div className="card-pad space-y-5">
        <div
          className="inline-flex rounded-xl border border-[var(--color-hairline)] p-1"
          role="tablist"
          aria-label="Input type"
        >
          {(
            [
              ["audio", "Upload audio"],
              ["text", "Paste transcript"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              role="tab"
              aria-selected={mode === value}
              disabled={isSubmitting}
              onClick={() => setMode(value)}
              className={classNames(
                "rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors",
                mode === value
                  ? "bg-indigo-500/20 text-indigo-200"
                  : "text-slate-400 hover:text-slate-200",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "audio" ? (
          <AudioDropzone file={file} onSelect={setFile} disabled={isSubmitting} />
        ) : (
          <div>
            <label htmlFor="transcript" className="mb-2 block text-sm font-medium text-slate-300">
              Call transcript
            </label>
            <textarea
              id="transcript"
              rows={9}
              value={transcript}
              disabled={isSubmitting}
              onChange={(event) => setTranscript(event.target.value)}
              placeholder="Paste what the caller said…"
              className="w-full resize-y rounded-xl border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-500/60 focus:outline-none"
            />
            <div className="mt-2 flex items-center justify-between">
              <p className="text-xs muted">{transcript.trim().length} characters</p>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => setTranscript(SAMPLE_TRANSCRIPT)}
                className="text-xs font-medium text-indigo-300 hover:text-indigo-200"
              >
                Use a sample scam call
              </button>
            </div>
          </div>
        )}

        {error ? <Alert title="Could not start the analysis">{error}</Alert> : null}

        <div className="flex items-center justify-between gap-4">
          <p className="text-xs muted">
            Recordings are processed locally by your ScamShield instance.
          </p>
          <Button onClick={submit} disabled={!canSubmit}>
            {isSubmitting ? (
              <>
                <Spinner /> Starting…
              </>
            ) : (
              "Analyse call"
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
}
