import { Badge, Card, CardHeader, EmptyState, Meter } from "@/components/ui/primitives";
import { TACTIC_LABELS } from "@/lib/constants";
import { formatPercent } from "@/lib/format";
import type { SocialEngineeringResult } from "@/lib/types";

export function TacticGrid({ social }: { social: SocialEngineeringResult }) {
  return (
    <Card>
      <CardHeader
        eyebrow="Agent 4"
        title="Psychological tactics detected"
        subtitle={social.summary || "How the caller tried to influence the decision."}
        action={
          <Badge title="Combined manipulation score across all detected tactics">
            {formatPercent(social.manipulation_score)} manipulation
          </Badge>
        }
      />

      {social.tactics.length === 0 ? (
        <EmptyState
          title="No manipulation tactics detected"
          description="The caller did not use pressure, urgency, fear, or secrecy patterns."
        />
      ) : (
        <div className="card-pad grid gap-4 sm:grid-cols-2">
          {social.tactics.map((detection) => (
            <article
              key={detection.tactic}
              className="rounded-xl border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-100">
                  {TACTIC_LABELS[detection.tactic] ?? detection.tactic}
                </h3>
                <span className="font-mono text-[11px] text-slate-500">
                  {formatPercent(detection.confidence)} confident
                </span>
              </div>

              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Severity</span>
                  <span className="tabular-nums">{formatPercent(detection.severity)}</span>
                </div>
                <Meter
                  value={detection.severity * 100}
                  className="bg-violet-400"
                  label={`${detection.tactic} severity`}
                />
              </div>

              {detection.evidence.length > 0 ? (
                <div className="mt-3 space-y-2.5">
                  {detection.evidence.map((item, index) => (
                    <figure key={index}>
                      <blockquote className="quote">“{item.quote}”</blockquote>
                      <figcaption className="mt-1 pl-3 text-xs muted">
                        {item.timestamp ? (
                          <span className="font-mono text-slate-500">{item.timestamp} · </span>
                        ) : null}
                        {item.explanation}
                      </figcaption>
                    </figure>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}
