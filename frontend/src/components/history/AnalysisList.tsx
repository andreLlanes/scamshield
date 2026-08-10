"use client";

import Link from "next/link";

import { Badge, EmptyState, Spinner } from "@/components/ui/primitives";
import { RISK_STYLES } from "@/lib/constants";
import { classNames, formatRelative, toRiskLevel } from "@/lib/format";
import type { AnalysisSummary } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  pending: "border-slate-500/30 bg-slate-500/10 text-slate-300",
  transcribing: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  analyzing: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
  failed: "border-rose-500/30 bg-rose-500/10 text-rose-300",
};

export function AnalysisList({
  items,
  isLoading,
  onDelete,
}: {
  items: AnalysisSummary[];
  isLoading: boolean;
  onDelete?: (id: string) => void;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 px-6 py-12 text-sm muted">
        <Spinner /> Loading…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No analyses yet"
        description="Upload a call recording or paste a transcript to see your first report here."
      />
    );
  }

  return (
    <ul className="divide-y divide-[var(--color-hairline)]">
      {items.map((item) => {
        const isDone = item.status === "completed";
        const level = toRiskLevel(item.risk_level);
        const style = RISK_STYLES[level];

        return (
          <li key={item.id} className="group flex items-center gap-4 px-5 py-3.5 sm:px-6">
            <Link href={`/analyses/${item.id}`} className="flex min-w-0 flex-1 items-center gap-4">
              <span
                className={classNames(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border text-sm font-bold tabular-nums",
                  isDone
                    ? classNames(style.bg, style.border, style.text)
                    : "border-[var(--color-hairline)] text-slate-600",
                )}
              >
                {isDone && item.risk_score !== null ? Math.round(item.risk_score) : "—"}
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-100 group-hover:text-indigo-200">
                  {item.verdict ?? item.filename}
                </span>
                <span className="mt-0.5 block truncate text-xs muted">
                  {item.filename} · {formatRelative(item.created_at)}
                </span>
              </span>

              {isDone ? (
                <Badge className={classNames(style.bg, style.border, style.text)}>
                  {style.label}
                </Badge>
              ) : (
                <Badge className={STATUS_STYLES[item.status]}>{item.status}</Badge>
              )}
            </Link>

            {onDelete ? (
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                aria-label={`Delete analysis of ${item.filename}`}
                className="rounded-lg px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-rose-500/10 hover:text-rose-300"
              >
                Delete
              </button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
