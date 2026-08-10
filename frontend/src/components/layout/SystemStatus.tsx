"use client";

import { useHealth } from "@/lib/hooks";
import { classNames } from "@/lib/format";

const ORDER = ["transcription", "classifier", "knowledge_base", "agents"] as const;

const LABELS: Record<string, string> = {
  transcription: "Whisper",
  classifier: "Classifier",
  knowledge_base: "Knowledge base",
  agents: "CrewAI agents",
};

/**
 * Shows which subsystems are running at full capability and which have fallen
 * back. A demo that quietly runs on fallbacks while claiming to run Whisper and
 * Llama would be misleading, so the state is always on screen.
 */
export function SystemStatus() {
  const { health, error } = useHealth();

  if (error) {
    return (
      <div className="flex items-center gap-2 text-xs text-rose-300">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
        Backend unreachable — start the API on port 8000
      </div>
    );
  }

  if (!health) {
    return <div className="h-5 w-64 animate-pulse rounded bg-slate-700/40" />;
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      {ORDER.map((key) => {
        const component = health.components[key];
        if (!component) return null;
        return (
          <span
            key={key}
            title={
              component.ready
                ? component.detail
                : `${component.detail} — using ${component.degraded_to}`
            }
            className="flex items-center gap-1.5 text-xs text-slate-400"
          >
            <span
              className={classNames(
                "h-1.5 w-1.5 rounded-full",
                component.ready ? "bg-emerald-400" : "bg-amber-400",
              )}
            />
            {LABELS[key]}
            <span className="text-slate-500">
              {component.ready ? "ready" : "fallback"}
            </span>
          </span>
        );
      })}
    </div>
  );
}
