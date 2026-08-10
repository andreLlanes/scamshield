"use client";

import { useCallback, useRef, useState } from "react";

import { ACCEPTED_AUDIO, MAX_UPLOAD_MB } from "@/lib/constants";
import { classNames, formatBytes } from "@/lib/format";

export function AudioDropzone({
  file,
  onSelect,
  disabled,
}: {
  file: File | null;
  onSelect: (file: File | null) => void;
  disabled?: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;

      const extension = `.${candidate.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!ACCEPTED_AUDIO.includes(extension)) {
        setLocalError(`${extension} is not a supported audio format.`);
        return;
      }
      if (candidate.size > MAX_UPLOAD_MB * 1024 * 1024) {
        setLocalError(
          `That file is ${formatBytes(candidate.size)}; the limit is ${MAX_UPLOAD_MB} MB.`,
        );
        return;
      }
      setLocalError(null);
      onSelect(candidate);
    },
    [onSelect],
  );

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          if (!disabled) accept(event.dataTransfer.files[0]);
        }}
        className={classNames(
          "rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          isDragging
            ? "border-indigo-400 bg-indigo-500/10"
            : "border-[var(--color-hairline)] bg-slate-500/[0.03]",
          disabled && "opacity-60",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_AUDIO.join(",")}
          className="sr-only"
          disabled={disabled}
          onChange={(event) => accept(event.target.files?.[0])}
        />

        <WaveMark />

        {file ? (
          <div className="mt-4">
            <p className="text-sm font-semibold text-slate-100">{file.name}</p>
            <p className="mt-0.5 text-xs muted">{formatBytes(file.size)}</p>
            <button
              type="button"
              disabled={disabled}
              onClick={() => {
                onSelect(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="mt-3 text-xs font-medium text-indigo-300 hover:text-indigo-200"
            >
              Choose a different file
            </button>
          </div>
        ) : (
          <div className="mt-4">
            <p className="text-sm text-slate-300">
              Drag a call recording here, or{" "}
              <button
                type="button"
                disabled={disabled}
                onClick={() => inputRef.current?.click()}
                className="font-semibold text-indigo-300 underline-offset-2 hover:underline"
              >
                browse your files
              </button>
            </p>
            <p className="mt-1.5 text-xs muted">
              MP3, WAV, M4A, OGG, FLAC, WEBM · up to {MAX_UPLOAD_MB} MB
            </p>
          </div>
        )}
      </div>

      {localError ? <p className="mt-2 text-xs text-rose-300">{localError}</p> : null}
    </div>
  );
}

function WaveMark() {
  const bars = [10, 20, 32, 24, 40, 28, 16, 22, 12];
  return (
    <div className="flex h-12 items-end justify-center gap-1.5" aria-hidden="true">
      {bars.map((height, index) => (
        <span
          key={index}
          className="w-1.5 rounded-full bg-gradient-to-t from-indigo-500/40 to-sky-300/80"
          style={{ height }}
        />
      ))}
    </div>
  );
}
