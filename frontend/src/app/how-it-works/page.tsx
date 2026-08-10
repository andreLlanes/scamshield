import type { Metadata } from "next";

import { Card, CardHeader } from "@/components/ui/primitives";
import { TACTIC_LABELS } from "@/lib/constants";

export const metadata: Metadata = {
  title: "How ScamShield works",
  description:
    "The five-agent pipeline behind ScamShield's explainable scam assessments, and the limits of what it can tell you.",
};

const TACTIC_DESCRIPTIONS: Record<keyof typeof TACTIC_LABELS, string> = {
  authority:
    "The caller claims to represent a bank, government agency, or other institution in order to borrow its credibility.",
  urgency:
    "The caller imposes an artificial deadline so you act before you can verify anything.",
  fear: "The caller threatens arrest, account closure, legal action, or loss of money.",
  scarcity:
    "The caller frames the offer as limited or one-time-only to discourage reflection.",
  trust:
    "The caller name-drops personal details or fake reference numbers to appear legitimate.",
  pressure:
    "The caller refuses to let you hang up, call back, or consult someone else.",
  reward: "The caller dangles a prize, refund, rebate, or guaranteed return as bait.",
  isolation:
    "The caller tells you to keep the call secret from family, staff, or the police.",
};

const PIPELINE = [
  {
    agent: "Agent 1 — Speech to text",
    model: "Whisper large-v3",
    body: "The recording is transcribed with timestamps. Whisper handles English and Filipino, and runs locally so recordings never leave your instance.",
  },
  {
    agent: "Agent 2 — Scam classifier",
    model: "TF-IDF + XGBoost",
    body: "A supervised model trained on labelled call transcripts returns a scam probability. Because it is a tree model, we can extract exact per-phrase contributions rather than guessing at what drove the score.",
  },
  {
    agent: "Agent 3 — Fact verification",
    model: "RAG · ChromaDB + bge-small",
    body: "Checkable claims are extracted, then each is looked up against a knowledge base of documented bank, agency, and vendor procedures. A claim is only marked contradicted when a retrieved passage says it cannot happen.",
  },
  {
    agent: "Agent 4 — Social engineering",
    model: "Rules + LLM",
    body: "The call is scanned for eight manipulation tactics. Every finding must quote the line it came from; a tactic with no quote is discarded.",
  },
  {
    agent: "Agent 5 — Report generation",
    model: "Llama 3.1 via CrewAI",
    body: "The evidence is written up in plain language. The risk score itself is computed by the system, not the model, so the wording can vary but the verdict cannot drift.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
          How ScamShield works
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
          Rather than asking a single model to do everything, ScamShield splits the problem across
          five specialist agents. Each one has a single responsibility and produces an output you
          can inspect, which is what makes the final report explainable.
        </p>
      </header>

      <Card>
        <CardHeader title="The pipeline" subtitle="Upload → transcript → evidence → report" />
        <ol className="divide-y divide-[var(--color-hairline)]">
          {PIPELINE.map((stage) => (
            <li key={stage.agent} className="px-5 py-4 sm:px-6">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-sm font-semibold text-slate-100">{stage.agent}</h2>
                <span className="font-mono text-xs text-indigo-300">{stage.model}</span>
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{stage.body}</p>
            </li>
          ))}
        </ol>
      </Card>

      <Card>
        <CardHeader
          title="The eight tactics"
          subtitle="What Agent 4 looks for in a recording."
        />
        <dl className="card-pad grid gap-4 sm:grid-cols-2">
          {Object.entries(TACTIC_LABELS).map(([id, label]) => (
            <div key={id}>
              <dt className="text-sm font-semibold text-slate-100">{label}</dt>
              <dd className="mt-1 text-sm leading-relaxed muted">
                {TACTIC_DESCRIPTIONS[id as keyof typeof TACTIC_LABELS]}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card className="border-amber-500/25 bg-amber-500/[0.05]">
        <CardHeader title="What ScamShield cannot tell you" />
        <div className="card-pad space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            <strong className="text-slate-100">It cannot confirm who called you.</strong> Caller ID
            is trivially spoofed and a recording contains no proof of identity. Claims about the
            caller&apos;s employer are reported as <em>unverified</em>, never as verified.
          </p>
          <p>
            <strong className="text-slate-100">It is a decision aid, not a verdict.</strong> A low
            score means nothing matched a known scam pattern — not that the call was genuine. When
            money or credentials are involved, hang up and call the organisation back on its
            published number.
          </p>
          <p>
            <strong className="text-slate-100">Its knowledge base is finite.</strong> Claims outside
            the indexed documents come back unverified rather than being guessed at.
          </p>
        </div>
      </Card>
    </div>
  );
}
