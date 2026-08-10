import { Card, CardHeader } from "@/components/ui/primitives";
import { AGENT_LABELS } from "@/lib/constants";
import { classNames } from "@/lib/format";
import type { AgentTrace } from "@/lib/types";

const DOT_COLOURS: Record<string, string> = {
  completed: "bg-emerald-400",
  skipped: "bg-slate-500",
  failed: "bg-rose-400",
};

/** Per-agent execution record — the "explainable intermediate outputs" claim, made visible. */
export function AgentTimeline({ traces }: { traces: AgentTrace[] }) {
  if (traces.length === 0) return null;

  const total = Math.max(...traces.map((trace) => trace.started_at + trace.duration_seconds), 0.001);

  return (
    <Card>
      <CardHeader
        eyebrow="Pipeline"
        title="Agent execution"
        subtitle="What each agent did, and how long it took."
      />
      <ul className="card-pad space-y-3">
        {traces.map((trace) => {
          const left = (trace.started_at / total) * 100;
          const width = Math.max((trace.duration_seconds / total) * 100, 2);
          return (
            <li key={trace.agent}>
              <div className="flex items-baseline justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span
                    className={classNames(
                      "h-1.5 w-1.5 rounded-full",
                      DOT_COLOURS[trace.status] ?? "bg-slate-500",
                    )}
                  />
                  <span className="text-sm text-slate-200">
                    {AGENT_LABELS[trace.agent] ?? trace.agent}
                  </span>
                </div>
                <span className="font-mono text-[11px] text-slate-500">
                  {trace.duration_seconds.toFixed(2)}s
                </span>
              </div>

              <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-700/40">
                <div
                  className="h-full rounded-full bg-indigo-400/70"
                  style={{ marginLeft: `${left}%`, width: `${width}%` }}
                />
              </div>

              {trace.detail ? (
                <p className="mt-1 text-xs muted">{trace.detail}</p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
