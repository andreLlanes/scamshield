"use client";

import Link from "next/link";

import { AnalysisList } from "@/components/history/AnalysisList";
import { Card, CardHeader } from "@/components/ui/primitives";
import { UploadPanel } from "@/components/upload/UploadPanel";
import { useAnalysisList } from "@/lib/hooks";

const AGENTS = [
  {
    step: "1",
    title: "Speech to text",
    body: "Whisper large-v3 transcribes the recording with timestamps, in English or Filipino.",
  },
  {
    step: "2",
    title: "Scam classifier",
    body: "A TF-IDF + XGBoost model returns a scam probability and the exact phrases behind it.",
  },
  {
    step: "3",
    title: "Fact verification",
    body: "Claims are checked against a knowledge base of real bank and agency procedures.",
  },
  {
    step: "4",
    title: "Social engineering",
    body: "Authority, urgency, fear, pressure and isolation tactics are identified and quoted.",
  },
  {
    step: "5",
    title: "Report generation",
    body: "A plain-language verdict with red flags, evidence, and what to do next.",
  },
];

export default function HomePage() {
  const { items, isLoading, refresh } = useAnalysisList(5);

  return (
    <div className="space-y-10">
      <section className="pt-2 text-center sm:pt-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-400">
          Agentic AI for audio scam detection
        </p>
        <h1 className="mx-auto mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">
          Find out what that caller was really doing
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
          Upload a recording of a suspicious phone call. ScamShield transcribes it, verifies the
          caller&apos;s claims, identifies the manipulation tactics used, and explains its verdict —
          instead of just saying &ldquo;scam&rdquo; or &ldquo;not scam&rdquo;.
        </p>
      </section>

      <UploadPanel onSubmitted={refresh} />

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
          Five specialist agents
        </h2>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {AGENTS.map((agent) => (
            <li
              key={agent.step}
              className="rounded-xl border border-[var(--color-hairline)] bg-[var(--color-surface)]/60 p-4"
            >
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-500/15 text-xs font-bold text-indigo-300">
                {agent.step}
              </span>
              <h3 className="mt-2.5 text-sm font-semibold text-slate-100">{agent.title}</h3>
              <p className="mt-1 text-xs leading-relaxed muted">{agent.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <Card>
        <CardHeader
          title="Recent analyses"
          subtitle="Your most recent reports."
          action={
            <Link
              href="/history"
              className="text-sm font-medium text-indigo-300 hover:text-indigo-200"
            >
              View all
            </Link>
          }
        />
        <AnalysisList items={items} isLoading={isLoading} />
      </Card>
    </div>
  );
}
