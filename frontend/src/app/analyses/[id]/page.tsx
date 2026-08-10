"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { AgentTimeline } from "@/components/report/AgentTimeline";
import { ClaimList } from "@/components/report/ClaimList";
import { ClassifierCard } from "@/components/report/ClassifierCard";
import { ProcessingView } from "@/components/report/ProcessingView";
import { RecommendedActions } from "@/components/report/RecommendedActions";
import { RedFlagList } from "@/components/report/RedFlagList";
import { ReportHeader } from "@/components/report/ReportHeader";
import { RiskBreakdownCard } from "@/components/report/RiskBreakdownCard";
import { TacticGrid } from "@/components/report/TacticGrid";
import { TranscriptViewer } from "@/components/report/TranscriptViewer";
import { Alert, Card, Spinner } from "@/components/ui/primitives";
import { useAnalysis } from "@/lib/hooks";

export default function AnalysisPage() {
  const params = useParams<{ id: string }>();
  const id = typeof params?.id === "string" ? params.id : null;
  const { analysis, error, isLoading } = useAnalysis(id);

  if (isLoading && !analysis) {
    return (
      <Card className="card-pad">
        <div className="flex items-center gap-2 text-sm muted">
          <Spinner /> Loading analysis…
        </div>
      </Card>
    );
  }

  if (error || !analysis) {
    return (
      <div className="space-y-4">
        <Alert title="Analysis not available">
          {error ?? "We could not find that analysis."}
        </Alert>
        <Link href="/" className="text-sm font-medium text-indigo-300 hover:text-indigo-200">
          ← Analyse another call
        </Link>
      </div>
    );
  }

  if (analysis.status === "failed") {
    return (
      <div className="space-y-4">
        <Alert title="This analysis could not be completed">
          <p>{analysis.error ?? "The pipeline failed for an unknown reason."}</p>
        </Alert>
        <Link href="/" className="text-sm font-medium text-indigo-300 hover:text-indigo-200">
          ← Try another recording
        </Link>
      </div>
    );
  }

  if (analysis.status !== "completed" || !analysis.report) {
    return <ProcessingView status={analysis.status} filename={analysis.filename} />;
  }

  const { report, evidence } = analysis;

  return (
    <div className="space-y-6">
      <Link href="/" className="inline-block text-sm font-medium text-indigo-300 hover:text-indigo-200">
        ← Analyse another call
      </Link>

      <ReportHeader analysis={analysis} />

      <RecommendedActions actions={report.recommended_actions} />

      <RedFlagList flags={report.red_flags} />

      <div className="grid gap-6 lg:grid-cols-2">
        <RiskBreakdownCard risk={report.risk} />
        {evidence?.classification ? (
          <ClassifierCard classification={evidence.classification} />
        ) : null}
      </div>

      {evidence?.social_engineering ? (
        <TacticGrid social={evidence.social_engineering} />
      ) : null}

      {evidence?.fact_check ? <ClaimList factCheck={evidence.fact_check} /> : null}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        {analysis.transcript ? (
          <TranscriptViewer transcript={analysis.transcript} flags={report.red_flags} />
        ) : null}
        <AgentTimeline traces={analysis.traces} />
      </div>
    </div>
  );
}
