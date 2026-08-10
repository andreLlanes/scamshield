"use client";

import { useMemo, useState } from "react";

import { Badge, Card, CardHeader } from "@/components/ui/primitives";
import { classNames } from "@/lib/format";
import type { RedFlag, Transcript } from "@/lib/types";

/**
 * The transcript with flagged lines highlighted, so the user can read the call
 * back and see exactly where each finding came from.
 */
export function TranscriptViewer({
  transcript,
  flags,
}: {
  transcript: Transcript;
  flags: RedFlag[];
}) {
  const [showAll, setShowAll] = useState(false);

  const flaggedText = useMemo(
    () =>
      new Set(
        flags
          .map((flag) => flag.quote?.trim().toLowerCase())
          .filter((quote): quote is string => Boolean(quote)),
      ),
    [flags],
  );

  const segments = transcript.segments.length
    ? transcript.segments
    : [{ index: 0, start: 0, end: 0, text: transcript.text, speaker: null }];

  const visible = showAll ? segments : segments.slice(0, 12);

  return (
    <Card>
      <CardHeader
        eyebrow="Agent 1"
        title="Transcript"
        subtitle={`${transcript.backend} · ${transcript.model} · ${transcript.language.toUpperCase()}`}
        action={<Badge>{segments.length} segments</Badge>}
      />

      <div className="scroll-region max-h-[28rem] overflow-y-auto px-5 py-4 sm:px-6">
        <ol className="space-y-2">
          {visible.map((segment) => {
            const isFlagged = flaggedText.has(segment.text.trim().toLowerCase());
            return (
              <li
                key={segment.index}
                className={classNames(
                  "flex gap-3 rounded-lg px-2 py-1.5 transition-colors",
                  isFlagged && "bg-rose-500/10 ring-1 ring-rose-500/20",
                )}
              >
                <span className="mt-0.5 shrink-0 font-mono text-[11px] text-slate-600">
                  {formatTimestamp(segment.start)}
                </span>
                <p
                  className={classNames(
                    "text-sm leading-relaxed",
                    isFlagged ? "text-rose-100" : "text-slate-300",
                  )}
                >
                  {segment.text}
                </p>
              </li>
            );
          })}
        </ol>

        {segments.length > 12 ? (
          <button
            type="button"
            onClick={() => setShowAll((current) => !current)}
            className="mt-3 text-xs font-medium text-indigo-300 hover:text-indigo-200"
          >
            {showAll ? "Show less" : `Show all ${segments.length} segments`}
          </button>
        ) : null}
      </div>
    </Card>
  );
}

function formatTimestamp(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}
