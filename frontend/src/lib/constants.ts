import type { AnalysisStatus, ClaimVerdict, RiskLevel, TacticId } from "./types";

/**
 * Risk presentation. Colours are Tailwind class strings rather than raw hex so
 * every surface (badge, gauge, border) stays on the same palette.
 */
export const RISK_STYLES: Record<
  RiskLevel,
  { label: string; text: string; bg: string; border: string; ring: string; stroke: string }
> = {
  safe: {
    label: "No indicators",
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    ring: "ring-emerald-500/30",
    stroke: "stroke-emerald-400",
  },
  low: {
    label: "Low risk",
    text: "text-teal-300",
    bg: "bg-teal-500/10",
    border: "border-teal-500/30",
    ring: "ring-teal-500/30",
    stroke: "stroke-teal-400",
  },
  medium: {
    label: "Medium risk",
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    ring: "ring-amber-500/30",
    stroke: "stroke-amber-400",
  },
  high: {
    label: "High risk",
    text: "text-orange-300",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    ring: "ring-orange-500/30",
    stroke: "stroke-orange-400",
  },
  critical: {
    label: "Critical risk",
    text: "text-rose-300",
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    ring: "ring-rose-500/30",
    stroke: "stroke-rose-400",
  },
};

export const TACTIC_LABELS: Record<TacticId, string> = {
  authority: "Authority",
  urgency: "Urgency",
  fear: "Fear",
  scarcity: "Scarcity",
  trust: "False Trust",
  pressure: "Pressure",
  reward: "Reward",
  isolation: "Isolation",
};

export const VERDICT_STYLES: Record<
  ClaimVerdict,
  { label: string; text: string; bg: string; border: string; icon: string }
> = {
  contradicted: {
    label: "Contradicted",
    text: "text-rose-300",
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    icon: "✕",
  },
  unverified: {
    label: "Unverified",
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    icon: "?",
  },
  verified: {
    label: "Verified",
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    icon: "✓",
  },
};

/** The pipeline stages, in the order the user sees them progress. */
export const PIPELINE_STAGES: { status: AnalysisStatus; label: string; detail: string }[] = [
  { status: "pending", label: "Queued", detail: "Recording received" },
  { status: "transcribing", label: "Transcribing", detail: "Whisper large-v3" },
  { status: "analyzing", label: "Analysing", detail: "Classifier · Fact check · Tactics" },
  { status: "completed", label: "Report ready", detail: "Assessment generated" },
];

export const AGENT_LABELS: Record<string, string> = {
  transcription: "Speech to text",
  classifier: "Scam classifier",
  fact_check: "Fact verification",
  social_engineering: "Social engineering",
  report: "Report generator",
};

export const MAX_UPLOAD_MB = 50;

export const ACCEPTED_AUDIO = [
  ".mp3",
  ".wav",
  ".m4a",
  ".ogg",
  ".flac",
  ".webm",
  ".mp4",
  ".aac",
];
