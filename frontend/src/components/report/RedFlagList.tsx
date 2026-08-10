import { Badge, Card, CardHeader, EmptyState } from "@/components/ui/primitives";
import { RISK_STYLES } from "@/lib/constants";
import { classNames } from "@/lib/format";
import type { RedFlag } from "@/lib/types";

const AGENT_LABELS: Record<string, string> = {
  fact_check: "Fact check",
  social_engineering: "Tactics",
  classifier: "Classifier",
  report: "Report agent",
  orchestrator: "Orchestrator",
};

export function RedFlagList({ flags }: { flags: RedFlag[] }) {
  return (
    <Card>
      <CardHeader
        eyebrow="Evidence"
        title="Red flags"
        subtitle="Each one is tied to something the caller actually said."
        action={
          flags.length ? (
            <Badge className="border-rose-500/30 bg-rose-500/10 text-rose-300">
              {flags.length}
            </Badge>
          ) : undefined
        }
      />

      {flags.length === 0 ? (
        <EmptyState
          title="No red flags found"
          description="Nothing in this recording matched a known scam indicator."
        />
      ) : (
        <ul className="divide-y divide-[var(--color-hairline)]">
          {flags.map((flag, index) => {
            const style = RISK_STYLES[flag.severity];
            return (
              <li key={`${flag.title}-${index}`} className="px-5 py-4 sm:px-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={classNames("h-2 w-2 shrink-0 rounded-full", style.bg, "ring-2", style.ring)} />
                  <h3 className="text-sm font-semibold text-slate-100">{flag.title}</h3>
                  <Badge className={classNames(style.bg, style.border, style.text)}>
                    {flag.severity}
                  </Badge>
                  <Badge>{AGENT_LABELS[flag.source_agent] ?? flag.source_agent}</Badge>
                </div>

                {flag.detail ? (
                  <p className="mt-2 text-sm leading-relaxed text-slate-300">{flag.detail}</p>
                ) : null}

                {flag.quote ? (
                  <figure className="mt-3">
                    <blockquote className="quote">“{flag.quote}”</blockquote>
                    {flag.timestamp ? (
                      <figcaption className="mt-1 pl-3 font-mono text-[11px] text-slate-500">
                        at {flag.timestamp}
                      </figcaption>
                    ) : null}
                  </figure>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
