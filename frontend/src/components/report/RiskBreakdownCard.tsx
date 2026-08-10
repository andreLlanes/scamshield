import { Card, CardHeader, Meter } from "@/components/ui/primitives";
import type { RiskBreakdown } from "@/lib/types";

const BAR_COLOURS: Record<string, string> = {
  classifier: "bg-sky-400",
  social_engineering: "bg-violet-400",
  fact_check: "bg-amber-400",
};

/**
 * Shows the arithmetic behind the headline score. This is the difference
 * between "the model said 86" and an explainable assessment: the user can see
 * which agent contributed what, and check the sum themselves.
 */
export function RiskBreakdownCard({ risk }: { risk: RiskBreakdown }) {
  const weighted = risk.components.filter((component) => component.source !== "override");
  const overrides = risk.components.filter((component) => component.source === "override");

  return (
    <Card>
      <CardHeader
        eyebrow="Explainability"
        title="How this score was calculated"
        subtitle="Each agent contributes a weighted share of the 100 points."
      />
      <div className="card-pad space-y-5">
        {weighted.map((component) => (
          <div key={component.source}>
            <div className="flex items-baseline justify-between gap-4">
              <p className="text-sm font-medium text-slate-200">{component.label}</p>
              <p className="text-sm tabular-nums text-slate-400">
                <span className="font-semibold text-slate-200">
                  {component.weighted_points.toFixed(1)}
                </span>
                <span className="mx-1 text-slate-600">/</span>
                {(component.weight * 100).toFixed(0)} pts
              </p>
            </div>
            <div className="mt-2">
              <Meter
                value={component.raw_score * 100}
                className={BAR_COLOURS[component.source] ?? "bg-indigo-400"}
                label={`${component.label} signal strength`}
              />
            </div>
            <p className="mt-1.5 text-xs muted">{component.rationale}</p>
          </div>
        ))}

        {overrides.map((component) => (
          <div
            key={component.source}
            className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3"
          >
            <p className="text-sm font-semibold text-rose-200">{component.label}</p>
            <p className="mt-1 text-xs text-rose-200/80">{component.rationale}</p>
          </div>
        ))}

        <div className="flex items-center justify-between border-t border-[var(--color-hairline)] pt-4">
          <p className="text-sm font-semibold text-slate-200">Total risk score</p>
          <p className="text-lg font-bold tabular-nums text-slate-100">
            {risk.score.toFixed(1)}
            <span className="ml-1 text-sm font-normal text-slate-500">/ 100</span>
          </p>
        </div>
      </div>
    </Card>
  );
}
