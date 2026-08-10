"use client";

import { useState } from "react";

import { Badge, Card, CardHeader, EmptyState } from "@/components/ui/primitives";
import { VERDICT_STYLES } from "@/lib/constants";
import { classNames, formatPercent } from "@/lib/format";
import type { ClaimVerification, FactCheckResult } from "@/lib/types";

export function ClaimList({ factCheck }: { factCheck: FactCheckResult }) {
  const counts = factCheck.verifications.reduce<Record<string, number>>((accumulator, item) => {
    accumulator[item.verdict] = (accumulator[item.verdict] ?? 0) + 1;
    return accumulator;
  }, {});

  return (
    <Card>
      <CardHeader
        eyebrow="Agent 3"
        title="Claim verification"
        subtitle={
          factCheck.summary ||
          "Each factual claim checked against the knowledge base of bank and agency procedures."
        }
        action={
          <div className="flex gap-1.5">
            {(["contradicted", "unverified", "verified"] as const).map((verdict) =>
              counts[verdict] ? (
                <Badge
                  key={verdict}
                  className={classNames(
                    VERDICT_STYLES[verdict].bg,
                    VERDICT_STYLES[verdict].border,
                    VERDICT_STYLES[verdict].text,
                  )}
                >
                  {counts[verdict]} {verdict}
                </Badge>
              ) : null,
            )}
          </div>
        }
      />

      {factCheck.verifications.length === 0 ? (
        <EmptyState
          title="No checkable claims"
          description="The caller did not make specific factual assertions that could be verified."
        />
      ) : (
        <ul className="divide-y divide-[var(--color-hairline)]">
          {factCheck.verifications.map((verification, index) => (
            <ClaimRow key={index} verification={verification} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function ClaimRow({ verification }: { verification: ClaimVerification }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const style = VERDICT_STYLES[verification.verdict];

  return (
    <li className="px-5 py-4 sm:px-6">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className={classNames(
            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold",
            style.bg,
            style.border,
            style.text,
          )}
        >
          {style.icon}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-slate-100">{verification.claim.claim}</p>
            <Badge className={classNames(style.bg, style.border, style.text)}>{style.label}</Badge>
            <Badge>{verification.claim.category}</Badge>
          </div>

          {verification.claim.quote ? (
            <figure className="mt-2">
              <blockquote className="quote">“{verification.claim.quote}”</blockquote>
              {verification.claim.timestamp ? (
                <figcaption className="mt-1 pl-3 font-mono text-[11px] text-slate-500">
                  at {verification.claim.timestamp}
                </figcaption>
              ) : null}
            </figure>
          ) : null}

          {verification.explanation ? (
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              {verification.explanation}
            </p>
          ) : null}

          <div className="mt-2 flex items-center gap-3">
            <span className="text-[11px] text-slate-500">
              {formatPercent(verification.confidence)} confidence
            </span>
            {verification.evidence.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowEvidence((current) => !current)}
                className="text-[11px] font-medium text-indigo-300 hover:text-indigo-200"
                aria-expanded={showEvidence}
              >
                {showEvidence ? "Hide" : "Show"} {verification.evidence.length} retrieved{" "}
                {verification.evidence.length === 1 ? "passage" : "passages"}
              </button>
            ) : null}
          </div>

          {showEvidence ? (
            <div className="mt-3 space-y-2">
              {verification.evidence.map((document) => (
                <article
                  key={document.doc_id}
                  className="rounded-lg border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/70 p-3"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h4 className="text-xs font-semibold text-slate-200">{document.title}</h4>
                    <span className="font-mono text-[10px] text-slate-500">
                      {document.score.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
                    {document.content}
                  </p>
                  <p className="mt-1.5 font-mono text-[10px] text-slate-600">{document.source}</p>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}
