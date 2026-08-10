"""End-to-end API tests against the deterministic pipeline."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

PREFIX = "/api/v1"


async def _wait_for_completion(
    client: AsyncClient, analysis_id: str, timeout: float = 30.0
) -> dict:
    """Poll until the background pipeline finishes."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        response = await client.get(f"{PREFIX}/analyses/{analysis_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in ("completed", "failed"):
            return payload
        await asyncio.sleep(0.1)
    raise AssertionError(f"Analysis {analysis_id} did not finish within {timeout}s")


class TestHealth:
    async def test_liveness(self, client: AsyncClient) -> None:
        response = await client.get(f"{PREFIX}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_components_report_every_subsystem(self, client: AsyncClient) -> None:
        response = await client.get(f"{PREFIX}/health/components")
        assert response.status_code == 200
        components = response.json()["components"]

        assert set(components) == {"transcription", "classifier", "knowledge_base", "agents"}
        # Agents are disabled in tests, so this must report the degraded path.
        assert components["agents"]["ready"] is False
        assert components["agents"]["degraded_to"]


class TestTextAnalysis:
    async def test_scam_call_produces_a_high_risk_explainable_report(
        self, client: AsyncClient, scam_transcript: str
    ) -> None:
        response = await client.post(
            f"{PREFIX}/analyses/text", json={"transcript": scam_transcript}
        )
        assert response.status_code == 202
        analysis_id = response.json()["id"]

        payload = await _wait_for_completion(client, analysis_id)
        assert payload["status"] == "completed", payload.get("error")

        report = payload["report"]
        assert report["risk"]["score"] >= 65
        assert report["risk"]["level"] in ("high", "critical")
        assert report["verdict"]
        assert report["summary"]
        assert report["red_flags"], "a high-risk verdict must be justified by red flags"
        assert report["recommended_actions"]

        # The score must be reconstructable from its components.
        components = [c for c in report["risk"]["components"] if c["source"] != "override"]
        assert {c["source"] for c in components} == {
            "classifier",
            "social_engineering",
            "fact_check",
        }

        evidence = payload["evidence"]
        assert evidence["classification"]["scam_probability"] > 0.5
        assert evidence["social_engineering"]["tactics"]
        assert evidence["fact_check"]["verifications"]

        # Every quoted red flag must come from the transcript.
        transcript_text = payload["transcript"]["text"].lower()
        for flag in report["red_flags"]:
            if flag.get("quote"):
                assert flag["quote"].lower().strip(" .") in transcript_text

    async def test_legitimate_call_produces_a_low_risk_report(
        self, client: AsyncClient, legit_transcript: str
    ) -> None:
        response = await client.post(
            f"{PREFIX}/analyses/text", json={"transcript": legit_transcript}
        )
        analysis_id = response.json()["id"]
        payload = await _wait_for_completion(client, analysis_id)

        assert payload["status"] == "completed", payload.get("error")
        assert payload["report"]["risk"]["score"] < 40
        assert payload["report"]["risk"]["level"] in ("safe", "low")

    async def test_agent_traces_are_recorded(
        self, client: AsyncClient, scam_transcript: str
    ) -> None:
        response = await client.post(
            f"{PREFIX}/analyses/text", json={"transcript": scam_transcript}
        )
        payload = await _wait_for_completion(client, response.json()["id"])

        agents = {trace["agent"] for trace in payload["traces"]}
        assert agents == {"classifier", "fact_check", "social_engineering", "report"}
        assert all(trace["duration_seconds"] >= 0 for trace in payload["traces"])

    async def test_rejects_a_too_short_transcript(self, client: AsyncClient) -> None:
        response = await client.post(f"{PREFIX}/analyses/text", json={"transcript": "hi"})
        assert response.status_code == 422


class TestUploadValidation:
    async def test_rejects_unsupported_extension(self, client: AsyncClient) -> None:
        response = await client.post(
            f"{PREFIX}/analyses",
            files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "unsupported_media"

    async def test_rejects_empty_file(self, client: AsyncClient) -> None:
        response = await client.post(
            f"{PREFIX}/analyses", files={"file": ("empty.mp3", b"", "audio/mpeg")}
        )
        assert response.status_code == 415

    async def test_accepts_audio_and_queues_a_job(self, client: AsyncClient) -> None:
        response = await client.post(
            f"{PREFIX}/analyses", files={"file": ("call.mp3", b"\x00" * 2048, "audio/mpeg")}
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["poll_url"].endswith(body["id"])

        # The stub engine has no sidecar transcript, so this must fail loudly
        # rather than invent one.
        payload = await _wait_for_completion(client, body["id"])
        assert payload["status"] == "failed"
        assert "sidecar" in (payload["error"] or "").lower()


class TestListAndDelete:
    async def test_list_paginates_and_delete_removes(
        self, client: AsyncClient, legit_transcript: str
    ) -> None:
        created = await client.post(
            f"{PREFIX}/analyses/text",
            json={"transcript": legit_transcript, "filename": "to-delete.txt"},
        )
        analysis_id = created.json()["id"]
        await _wait_for_completion(client, analysis_id)

        listing = await client.get(f"{PREFIX}/analyses", params={"limit": 5})
        assert listing.status_code == 200
        body = listing.json()
        assert body["total"] >= 1
        assert len(body["items"]) <= 5
        assert any(item["id"] == analysis_id for item in body["items"])

        assert (await client.delete(f"{PREFIX}/analyses/{analysis_id}")).status_code == 204
        assert (await client.get(f"{PREFIX}/analyses/{analysis_id}")).status_code == 404

    async def test_unknown_id_returns_404(self, client: AsyncClient) -> None:
        response = await client.get(f"{PREFIX}/analyses/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestKnowledge:
    async def test_search_returns_relevant_passages(self, client: AsyncClient) -> None:
        response = await client.get(
            f"{PREFIX}/knowledge/search", params={"q": "can a bank ask for my OTP"}
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert results
        assert "otp" in results[0]["content"].lower()

    async def test_stats_report_an_indexed_store(self, client: AsyncClient) -> None:
        response = await client.get(f"{PREFIX}/knowledge/stats")
        assert response.status_code == 200
        assert response.json()["chunks"] > 0

    async def test_tactics_reference_covers_all_eight(self, client: AsyncClient) -> None:
        response = await client.get(f"{PREFIX}/knowledge/tactics")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 8
        assert {item["id"] for item in payload} >= {"authority", "urgency", "fear", "isolation"}


@pytest.mark.parametrize("path", ["/", "/docs", "/openapi.json"])
async def test_meta_endpoints_are_served(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 200
