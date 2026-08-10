# ScamShield — backend

FastAPI service hosting the five-agent analysis pipeline. See the
[root README](../README.md) for the architecture and the full setup guide.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[ml]"

python -m scripts.train_classifier        # Agent 2 model artifact
python -m scripts.seed_knowledge_base     # Agent 3 vector index

uvicorn app.main:app --reload             # http://localhost:8000/docs
```

## Layout

| Path | Responsibility |
|------|----------------|
| `app/core/` | Settings, logging, exceptions, domain constants |
| `app/schemas/` | Pydantic contracts shared by the agents, DB and API |
| `app/db/` | ORM models, async session, repository |
| `app/ml/transcription/` | Agent 1 — Whisper engines and backend selection |
| `app/ml/classifier/` | Agent 2 — TF-IDF/XGBoost pipeline, lexicon fallback |
| `app/ml/rag/` | Agent 3 — chunking, embeddings, Chroma/TF-IDF stores |
| `app/agents/` | Orchestrator, CrewAI crew, prompts, deterministic heuristics |
| `app/services/` | Analysis pipeline, risk scoring, storage backends |
| `app/api/v1/` | HTTP endpoints |
| `scripts/` | Training and knowledge-base seeding entry points |

## Optional extras

```bash
pip install -e ".[ml]"       # XGBoost classifier
pip install -e ".[asr]"      # faster-whisper (audio upload)
pip install -e ".[rag]"      # ChromaDB + bge-small embeddings
pip install -e ".[agents]"   # CrewAI + LLM agents
pip install -e ".[dev]"      # pytest, ruff, mypy
```

Anything not installed degrades to a deterministic analyzer; check
`GET /api/v1/health/components` to see which path is active.

## Tests

```bash
pytest          # unit tests + full API round-trips, LLM disabled
ruff check .
mypy app
```
