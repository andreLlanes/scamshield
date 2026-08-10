import { Card, Spinner } from "@/components/ui/primitives";
import { PIPELINE_STAGES } from "@/lib/constants";
import { classNames } from "@/lib/format";
import type { AnalysisStatus } from "@/lib/types";

/** Shown while the pipeline runs, so the wait explains itself. */
export function ProcessingView({
  status,
  filename,
}: {
  status: AnalysisStatus;
  filename: string;
}) {
  const currentIndex = PIPELINE_STAGES.findIndex((stage) => stage.status === status);

  return (
    <Card className="card-pad">
      <div className="flex items-center gap-3">
        <Spinner className="text-indigo-300" />
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Analysing your call</h1>
          <p className="text-sm muted">{filename}</p>
        </div>
      </div>

      <ol className="mt-7 space-y-4">
        {PIPELINE_STAGES.map((stage, index) => {
          const isDone = currentIndex > index;
          const isActive = currentIndex === index;

          return (
            <li key={stage.status} className="flex gap-3.5">
              <div className="flex flex-col items-center">
                <span
                  className={classNames(
                    "flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                    isDone && "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
                    isActive && "border-indigo-400/60 bg-indigo-500/20 text-indigo-200",
                    !isDone && !isActive && "border-[var(--color-hairline)] text-slate-600",
                  )}
                >
                  {isDone ? "✓" : index + 1}
                </span>
                {index < PIPELINE_STAGES.length - 1 ? (
                  <span
                    className={classNames(
                      "mt-1 w-px flex-1 self-stretch",
                      isDone ? "bg-emerald-500/40" : "bg-[var(--color-hairline)]",
                    )}
                    style={{ minHeight: 18 }}
                  />
                ) : null}
              </div>

              <div className="pb-1">
                <p
                  className={classNames(
                    "text-sm font-medium",
                    isActive ? "text-slate-100" : isDone ? "text-slate-300" : "text-slate-500",
                  )}
                >
                  {stage.label}
                  {isActive ? <span className="ml-2 text-xs text-indigo-300">running…</span> : null}
                </p>
                <p className="text-xs muted">{stage.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-6 text-xs muted">
        A long recording transcribed on CPU can take several minutes. This page updates on its
        own — you can leave it open.
      </p>
    </Card>
  );
}
