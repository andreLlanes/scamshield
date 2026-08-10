import { Badge, Card, CardHeader, Meter } from "@/components/ui/primitives";
import { classNames, formatPercent } from "@/lib/format";
import type { ClassificationResult } from "@/lib/types";

/**
 * Agent 2's output. The signed feature contributions come from XGBoost's exact
 * SHAP values, so "why 91%?" has a concrete answer rather than a shrug.
 */
export function ClassifierCard({ classification }: { classification: ClassificationResult }) {
  const positive = classification.top_features.filter((feature) => feature.weight > 0);
  const negative = classification.top_features.filter((feature) => feature.weight < 0);
  const isScam = classification.scam_probability >= 0.5;

  return (
    <Card>
      <CardHeader
        eyebrow="Agent 2"
        title="ML scam classifier"
        subtitle={`Trained model: ${classification.model_name}`}
        action={
          classification.is_fallback ? (
            <Badge
              className="border-amber-500/30 bg-amber-500/10 text-amber-300"
              title="No trained artifact was found, so the weighted scam lexicon scored this call"
            >
              fallback scorer
            </Badge>
          ) : undefined
        }
      />

      <div className="card-pad space-y-5">
        <div>
          <div className="flex items-baseline justify-between">
            <p className="text-sm text-slate-300">Scam probability</p>
            <p
              className={classNames(
                "text-2xl font-bold tabular-nums",
                isScam ? "text-rose-300" : "text-emerald-300",
              )}
            >
              {formatPercent(classification.scam_probability, 1)}
            </p>
          </div>
          <div className="mt-2">
            <Meter
              value={classification.scam_probability * 100}
              className={isScam ? "bg-rose-400" : "bg-emerald-400"}
              label="Scam probability"
            />
          </div>
        </div>

        {positive.length > 0 ? (
          <FeatureGroup
            title="Pushed towards scam"
            tone="text-rose-300 border-rose-500/25 bg-rose-500/10"
            features={positive}
          />
        ) : null}

        {negative.length > 0 ? (
          <FeatureGroup
            title="Pushed towards legitimate"
            tone="text-emerald-300 border-emerald-500/25 bg-emerald-500/10"
            features={negative}
          />
        ) : null}

        {classification.top_features.length === 0 ? (
          <p className="text-xs muted">
            No individual term contributed strongly enough to report.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

function FeatureGroup({
  title,
  tone,
  features,
}: {
  title: string;
  tone: string;
  features: ClassificationResult["top_features"];
}) {
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {features.map((feature) => (
          <li key={feature.feature}>
            <span
              title={`Contribution ${feature.weight > 0 ? "+" : ""}${feature.weight.toFixed(4)}`}
              className={classNames(
                "inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 font-mono text-xs",
                tone,
              )}
            >
              {feature.feature}
              <span className="opacity-60">
                {feature.weight > 0 ? "+" : ""}
                {feature.weight.toFixed(3)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
