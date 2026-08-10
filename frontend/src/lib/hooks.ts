"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "./api";
import type { AnalysisDetail, AnalysisSummary, HealthResponse } from "./types";

const TERMINAL = new Set(["completed", "failed"]);

/**
 * Polls one analysis until it reaches a terminal state.
 *
 * The interval backs off from 1s to 5s: a short transcript finishes in under a
 * second, while a 10-minute recording on CPU Whisper does not, and hammering
 * the API for minutes is pointless.
 */
export function useAnalysis(id: string | null) {
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(id));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!id) {
      setAnalysis(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    let attempt = 0;

    const poll = async () => {
      try {
        const detail = await api.getAnalysis(id);
        if (cancelled) return;

        setAnalysis(detail);
        setError(null);
        setIsLoading(false);

        if (!TERMINAL.has(detail.status)) {
          attempt += 1;
          const delay = Math.min(1000 + attempt * 250, 5000);
          timer.current = setTimeout(poll, delay);
        }
      } catch (caught) {
        if (cancelled) return;
        setError(caught instanceof ApiError ? caught.message : "Failed to load the analysis.");
        setIsLoading(false);
      }
    };

    setIsLoading(true);
    void poll();

    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id]);

  return { analysis, error, isLoading };
}

/** Recent analyses, with a manual refresh for after an upload or delete. */
export function useAnalysisList(limit = 10) {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await api.listAnalyses({ limit });
      setItems(response.items);
      setTotal(response.total);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to load history.");
    } finally {
      setIsLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, total, isLoading, error, refresh };
}

/** Backend component readiness, used by the status strip. */
export function useHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((response) => !cancelled && setHealth(response))
      .catch((caught: unknown) => {
        if (cancelled) return;
        setError(caught instanceof ApiError ? caught.message : "Backend unreachable.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { health, error };
}
