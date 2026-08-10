import { RiskGauge } from "@/components/report/RiskGauge";
import { Badge } from "@/components/ui/primitives";
import { RISK_STYLES } from "@/lib/constants";
import { classNames, formatDateTime, formatDuration } from "@/lib/format";
import type { AnalysisDetail } from "@/lib/types";

export function ReportHeader({ analysis }: { analysis: AnalysisDetail }) {
  const report = analysis.report!;
  const style = RISK_STYLES[report.risk.level];

  return (
    <section
      className={classNames(
        "card card-pad ring-1",
        style.border,
        style.ring,
        "bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-surface-2)]",
      )}
    >
      <div className="flex flex-col items-center gap-7 sm:flex-row sm:items-center sm:gap-9">
        <RiskGauge score={report.risk.score} level={report.risk.level} />

        <div className="flex-1 text-center sm:text-left">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
            <Badge className={classNames(style.bg, style.border, style.text)}>
              {style.label}
            </Badge>
            <Badge title="Scam category inferred from the transcript">
              {report.category.replaceAll("_", " ")}
            </Badge>
            {report.is_fallback ? (
              <Badge title="Written by the deterministic report builder — no LLM was configured">
                rule-based report
              </Badge>
            ) : (
              <Badge title="Written by the CrewAI report agent">agent-written</Badge>
            )}
          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
            {report.verdict}
          </h1>
          <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-slate-300">
            {report.summary}
          </p>

          <dl className="mt-5 flex flex-wrap justify-center gap-x-7 gap-y-2 text-xs sm:justify-start">
            <Fact label="Recording" value={analysis.filename} />
            <Fact label="Length" value={formatDuration(analysis.duration_seconds)} />
            <Fact label="Language" value={(analysis.language ?? "—").toUpperCase()} />
            <Fact label="Analysed" value={formatDateTime(analysis.completed_at)} />
            <Fact
              label="Processing"
              value={
                analysis.processing_seconds
                  ? `${analysis.processing_seconds.toFixed(1)}s`
                  : "—"
              }
            />
          </dl>
        </div>
      </div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-medium text-slate-300">{value}</dd>
    </div>
  );
}
