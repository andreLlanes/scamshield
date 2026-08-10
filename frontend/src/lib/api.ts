/**
 * Typed client for the ScamShield API.
 *
 * Requests go to a relative `/api/v1` path, which `next.config.ts` rewrites to
 * the FastAPI service. That keeps the browser on one origin in development and
 * lets deployment point the rewrite anywhere without rebuilding components.
 */

import type {
  AnalysisAccepted,
  AnalysisDetail,
  AnalysisListResponse,
  AnalysisStatus,
  HealthResponse,
  TacticReference,
} from "./types";

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "error") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Cannot reach the ScamShield API. Is the backend running on port 8000?",
      0,
      "network_error",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.error ?? payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : (detail?.message ?? `Request failed with status ${response.status}`);
    throw new ApiError(message, response.status, detail?.code ?? "error");
  }

  return payload as T;
}

export const api = {
  health: () => request<HealthResponse>("/health/components"),

  uploadAudio: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<AnalysisAccepted>("/analyses", { method: "POST", body });
  },

  analyzeTranscript: (transcript: string, filename = "pasted-transcript.txt") =>
    request<AnalysisAccepted>("/analyses/text", {
      method: "POST",
      body: JSON.stringify({ transcript, filename }),
    }),

  getAnalysis: (id: string) => request<AnalysisDetail>(`/analyses/${id}`),

  listAnalyses: (params: { limit?: number; offset?: number; status?: AnalysisStatus } = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    if (params.status) query.set("status", params.status);
    const suffix = query.toString() ? `?${query}` : "";
    return request<AnalysisListResponse>(`/analyses${suffix}`);
  },

  deleteAnalysis: (id: string) =>
    request<void>(`/analyses/${id}`, { method: "DELETE" }),

  tactics: () => request<TacticReference[]>("/knowledge/tactics"),
};
