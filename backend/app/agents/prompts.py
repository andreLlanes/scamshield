"""Role definitions and task prompts for the CrewAI agents.

Kept out of ``crew.py`` so prompts can be reviewed and tuned without touching
orchestration code.

Every task asks for raw JSON. CrewAI's ``output_pydantic`` is not used on
purpose: it can add a second LLM round-trip to repair output, which is exactly
what small local models like Llama 3.1 8B are worst at. Asking for JSON and
parsing tolerantly (see ``app.agents.parsing``) fails softer.
"""

from __future__ import annotations

from app.core.constants import TACTIC_DESCRIPTIONS, TacticType

TACTIC_VOCABULARY = "\n".join(
    f"- {tactic.value}: {description}" for tactic, description in TACTIC_DESCRIPTIONS.items()
)

# ---------------------------------------------------------------------------
# Agent roles
# ---------------------------------------------------------------------------

ORCHESTRATOR = {
    "role": "Scam Analysis Orchestrator",
    "goal": (
        "Coordinate the specialist agents analysing a suspicious phone call and ensure "
        "every conclusion is traceable to something the caller actually said."
    ),
    "backstory": (
        "You lead a fraud analysis unit. You do not analyse calls yourself; you decide "
        "which specialist looks at what, and you reject any finding that is not grounded "
        "in the transcript."
    ),
}

FACT_CHECKER = {
    "role": "Claim Verification Specialist",
    "goal": (
        "Extract the caller's checkable factual claims and verify each one against the "
        "knowledge base of bank, government and vendor procedures."
    ),
    "backstory": (
        "You spent years in a bank's fraud investigation team. You know exactly what real "
        "institutions do and do not do on a phone call, and you never mark a claim "
        "verified without a supporting passage from the knowledge base. When the knowledge "
        "base is silent, 'unverified' is the honest answer and you use it."
    ),
}

SOCIAL_ENGINEER_ANALYST = {
    "role": "Social Engineering Analyst",
    "goal": (
        "Identify the psychological manipulation tactics the caller uses and quote the "
        "exact line that demonstrates each one."
    ),
    "backstory": (
        "You are a behavioural analyst who trains bank staff to recognise coercion "
        "scripts. You can tell the difference between an ordinary customer service call "
        "and a scripted pressure campaign, and you never claim a tactic without a quote."
    ),
}

REPORT_WRITER = {
    "role": "Scam Report Writer",
    "goal": (
        "Turn the analysis into a short, calm, concrete report that a non-technical "
        "person — often an older adult — can act on immediately."
    ),
    "backstory": (
        "You write consumer fraud advisories. You avoid jargon, you never speculate "
        "beyond the evidence you were given, and you always tell the reader what to do "
        "next in plain language."
    ),
}

# ---------------------------------------------------------------------------
# Task prompts
# ---------------------------------------------------------------------------

FACT_CHECK_TASK = """\
Analyse the following transcript of a phone call and verify the caller's factual claims.

TRANSCRIPT (with [mm:ss] timestamps):
{transcript}

Steps:
1. Extract every checkable factual claim the CALLER makes. A checkable claim asserts
   something about the world: who they are, what happened to an account, what the law
   requires, what a payment is for, what the recipient has won. Ignore pleasantries and
   questions.
2. For each claim, use the "Knowledge Base Search" tool at least once with a short
   question about that claim to retrieve relevant policy passages.
3. Decide a verdict for each claim using ONLY the retrieved passages:
   - "contradicted": the passages state this cannot happen or is not how it works.
   - "verified": the passages confirm this matches legitimate practice.
   - "unverified": the passages do not settle it. Use this for identity claims — a
     recording can never confirm who a caller works for.

Return ONLY raw JSON, no prose, no markdown fences, in exactly this shape:
{{
  "summary": "one or two sentences on what the claims add up to",
  "claims": [
    {{
      "claim": "the claim restated in one plain sentence",
      "quote": "the exact sentence from the transcript",
      "timestamp": "mm:ss or null",
      "category": "identity|procedure|payment|legal|offer|general",
      "verdict": "contradicted|verified|unverified",
      "confidence": 0.0,
      "explanation": "why, referring to what the knowledge base said"
    }}
  ]
}}
Include at most 8 claims, most important first."""

SOCIAL_ENGINEERING_TASK = """\
Analyse the following transcript for psychological manipulation tactics.

TRANSCRIPT (with [mm:ss] timestamps):
{transcript}

Recognised tactics — use these identifiers exactly:
{tactics}

Rules:
- Only report a tactic when you can quote the line that demonstrates it, verbatim.
- Do not report a tactic that is not in the list above.
- An ordinary, polite call may legitimately have zero tactics. Return an empty list
  rather than inventing one.
- "severity" is how aggressively the tactic is used (0.0 mild, 1.0 extreme).
- "confidence" is how sure you are the tactic is present at all.

Return ONLY raw JSON, no prose, no markdown fences, in exactly this shape:
{{
  "summary": "one sentence describing the manipulation profile of this call",
  "tactics": [
    {{
      "tactic": "authority",
      "confidence": 0.0,
      "severity": 0.0,
      "evidence": [
        {{"quote": "exact sentence from the transcript",
          "timestamp": "mm:ss or null",
          "explanation": "how this line applies pressure"}}
      ]
    }}
  ]
}}"""

REPORT_TASK = """\
Write the final scam assessment report for the person who received this call.

CALL TRANSCRIPT:
{transcript}

EVIDENCE COLLECTED BY THE OTHER AGENTS:
- ML scam classifier: {classifier_summary}
- Claim verification: {fact_summary}
- Social engineering: {social_summary}

COMPUTED RISK SCORE: {risk_score}/100 ({risk_level})
This score was calculated by the system. Do not change it, argue with it, or restate a
different number.

Write for a non-technical reader, often an older adult, who needs to decide what to do
in the next five minutes. Be calm and specific. Never invent a detail that is not in the
evidence above. Every red flag must quote the transcript.

Return ONLY raw JSON, no prose, no markdown fences, in exactly this shape:
{{
  "verdict": "one line, e.g. 'Likely a bank impersonation scam'",
  "summary": "2-4 sentences explaining the assessment in plain language",
  "red_flags": [
    {{"title": "short label",
      "detail": "one sentence on why this matters",
      "severity": "critical|high|medium|low",
      "quote": "exact transcript sentence or null",
      "timestamp": "mm:ss or null"}}
  ],
  "recommended_actions": ["concrete next step", "another concrete next step"],
  "caller_claims": ["what the caller claimed, one per line"]
}}
Include at most 6 red flags and at most 5 recommended actions."""


def social_engineering_prompt(transcript: str) -> str:
    return SOCIAL_ENGINEERING_TASK.format(transcript=transcript, tactics=TACTIC_VOCABULARY)


def fact_check_prompt(transcript: str) -> str:
    return FACT_CHECK_TASK.format(transcript=transcript)


def report_prompt(
    *,
    transcript: str,
    classifier_summary: str,
    fact_summary: str,
    social_summary: str,
    risk_score: float,
    risk_level: str,
) -> str:
    return REPORT_TASK.format(
        transcript=transcript,
        classifier_summary=classifier_summary,
        fact_summary=fact_summary,
        social_summary=social_summary,
        risk_score=f"{risk_score:.0f}",
        risk_level=risk_level,
    )


VALID_TACTICS = {tactic.value for tactic in TacticType}
