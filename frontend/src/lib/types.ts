/**
 * TypeScript mirrors of the backend Pydantic schemas.
 *
 * Kept hand-written rather than generated so the shapes stay readable; they
 * correspond 1:1 to `backend/app/schemas`. If you change a schema there,
 * change it here.
 */

export type AnalysisStatus =
  | "pending"
  | "transcribing"
  | "analyzing"
  | "completed"
  | "failed";

export type RiskLevel = "safe" | "low" | "medium" | "high" | "critical";

export type ClaimVerdict = "verified" | "contradicted" | "unverified";

export type TacticId =
  | "authority"
  | "urgency"
  | "fear"
  | "scarcity"
  | "trust"
  | "pressure"
  | "reward"
  | "isolation";

export interface TranscriptSegment {
  index: number;
  start: number;
  end: number;
  text: string;
  speaker: string | null;
}

export interface Transcript {
  text: string;
  language: string;
  duration_seconds: number;
  segments: TranscriptSegment[];
  model: string;
  backend: string;
}

export interface FeatureContribution {
  feature: string;
  weight: number;
  occurrences: number;
}

export interface ClassificationResult {
  scam_probability: number;
  label: string;
  model_name: string;
  is_fallback: boolean;
  top_features: FeatureContribution[];
}

export interface RetrievedDocument {
  doc_id: string;
  title: string;
  source: string;
  content: string;
  score: number;
}

export interface FactualClaim {
  claim: string;
  quote: string;
  timestamp: string | null;
  category: string;
}

export interface ClaimVerification {
  claim: FactualClaim;
  verdict: ClaimVerdict;
  confidence: number;
  explanation: string;
  evidence: RetrievedDocument[];
}

export interface FactCheckResult {
  verifications: ClaimVerification[];
  summary: string;
  is_fallback: boolean;
}

export interface TacticEvidence {
  quote: string;
  timestamp: string | null;
  explanation: string;
}

export interface TacticDetection {
  tactic: TacticId;
  confidence: number;
  severity: number;
  evidence: TacticEvidence[];
}

export interface SocialEngineeringResult {
  tactics: TacticDetection[];
  summary: string;
  manipulation_score: number;
  is_fallback: boolean;
}

export interface EvidenceWeight {
  source: string;
  label: string;
  raw_score: number;
  weight: number;
  weighted_points: number;
  rationale: string;
}

export interface RiskBreakdown {
  score: number;
  level: RiskLevel;
  components: EvidenceWeight[];
}

export interface RedFlag {
  title: string;
  detail: string;
  severity: RiskLevel;
  quote: string | null;
  timestamp: string | null;
  source_agent: string;
}

export interface ScamReport {
  verdict: string;
  risk: RiskBreakdown;
  category: string;
  summary: string;
  red_flags: RedFlag[];
  recommended_actions: string[];
  caller_claims: string[];
  is_fallback: boolean;
}

export interface AnalysisEvidence {
  classification: ClassificationResult | null;
  fact_check: FactCheckResult | null;
  social_engineering: SocialEngineeringResult | null;
}

export interface AgentTrace {
  agent: string;
  status: string;
  started_at: number;
  duration_seconds: number;
  detail: string;
}

export interface AnalysisSummary {
  id: string;
  filename: string;
  status: AnalysisStatus;
  risk_score: number | null;
  risk_level: string | null;
  verdict: string | null;
  duration_seconds: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface AnalysisDetail extends AnalysisSummary {
  language: string | null;
  error: string | null;
  processing_seconds: number | null;
  transcript: Transcript | null;
  evidence: AnalysisEvidence | null;
  report: ScamReport | null;
  traces: AgentTrace[];
}

export interface AnalysisListResponse {
  items: AnalysisSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AnalysisAccepted {
  id: string;
  status: AnalysisStatus;
  filename: string;
  poll_url: string;
}

export interface ComponentHealth {
  ready: boolean;
  detail: string;
  degraded_to: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  components: Record<string, ComponentHealth>;
}

export interface TacticReference {
  id: TacticId;
  label: string;
  description: string;
}
