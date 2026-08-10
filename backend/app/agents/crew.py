"""CrewAI crew construction and execution.

Three specialists (fact checker, social engineering analyst, report writer) run
under an orchestrator. Each stage is executed as its own crew so a failure in
one specialist degrades only that section of the report — a single crew running
all three would lose everything when the weakest step fails, which on a local
8B model is a realistic scenario rather than a hypothetical one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agents import prompts
from app.agents.llm import get_llm
from app.agents.tools.classifier_tool import build_classifier_tool
from app.agents.tools.knowledge_base_tool import build_knowledge_base_tool
from app.core.logging import get_logger
from app.ml.classifier.service import ScamClassifierService
from app.ml.rag.retriever import KnowledgeRetriever

logger = get_logger(__name__)


class CrewExecutionError(RuntimeError):
    """A crew ran but did not produce usable output."""


@dataclass
class CrewContext:
    """Everything the crew needs, injected rather than imported globally."""

    retriever: KnowledgeRetriever
    classifier: ScamClassifierService


def _agent(spec: dict[str, str], *, tools: list[Any] | None = None) -> Any:
    from crewai import Agent  # noqa: PLC0415  — optional extra

    return Agent(
        role=spec["role"],
        goal=spec["goal"],
        backstory=spec["backstory"],
        llm=get_llm(),
        tools=tools or [],
        allow_delegation=False,
        verbose=False,
        max_iter=6,
        cache=False,
    )


def _run_single_task(agent: Any, description: str, expected_output: str) -> str:
    """Execute a one-agent, one-task crew and return the raw string output."""
    from crewai import Crew, Process, Task  # noqa: PLC0415  — optional extra

    task = Task(description=description, expected_output=expected_output, agent=agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    raw = getattr(result, "raw", None) or str(result)
    if not raw.strip():
        raise CrewExecutionError("Crew returned empty output")
    return raw


def run_fact_check(context: CrewContext, transcript_text: str) -> str:
    """Fact-verification agent, with the knowledge base wired in as a tool."""
    agent = _agent(
        prompts.FACT_CHECKER,
        tools=[
            build_knowledge_base_tool(context.retriever),
            build_classifier_tool(context.classifier),
        ],
    )
    return _run_single_task(
        agent,
        prompts.fact_check_prompt(transcript_text),
        "A raw JSON object with 'summary' and a 'claims' array.",
    )


def run_social_engineering(context: CrewContext, transcript_text: str) -> str:
    """Social engineering agent. No tools — this is pure transcript reading."""
    agent = _agent(prompts.SOCIAL_ENGINEER_ANALYST)
    return _run_single_task(
        agent,
        prompts.social_engineering_prompt(transcript_text),
        "A raw JSON object with 'summary' and a 'tactics' array.",
    )


def run_report(
    context: CrewContext,
    *,
    transcript_text: str,
    classifier_summary: str,
    fact_summary: str,
    social_summary: str,
    risk_score: float,
    risk_level: str,
) -> str:
    """Report-writing agent. Receives the computed score; it does not set one."""
    agent = _agent(prompts.REPORT_WRITER)
    return _run_single_task(
        agent,
        prompts.report_prompt(
            transcript=transcript_text,
            classifier_summary=classifier_summary,
            fact_summary=fact_summary,
            social_summary=social_summary,
            risk_score=risk_score,
            risk_level=risk_level,
        ),
        "A raw JSON object with verdict, summary, red_flags and recommended_actions.",
    )


def is_crew_available() -> bool:
    """True when a crew can actually be constructed right now."""
    try:
        get_llm()
    except Exception as exc:  # LLMUnavailable, a missing import, or a bad config
        logger.info("crew_unavailable", reason=str(exc))
        return False
    return True
