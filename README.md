# ScamShield

**An agentic AI system for audio scam detection and scam explainability.**

Upload a recording of a suspicious phone call. ScamShield transcribes it, scores it,
verifies the caller's factual claims against documented bank and government
procedures, identifies the psychological tactics used, and produces an
**explainable assessment report** — not just a "scam" / "not scam" label.

---

## Why an agentic workflow

A single prompt doing transcription, detection, fact-checking and report writing is
hard to explain, hard to improve one piece at a time, and expensive. ScamShield
splits the problem across five specialists, each with one responsibility and an
inspectable output:

| # | Agent | Technology | Output |
|---|-------|-----------|--------|
| 1 | Speech to text | Whisper large-v3 (faster-whisper) | Timestamped transcript |
| 2 | Scam classifier | TF-IDF + XGBoost | Scam probability + the n-grams behind it |
| 3 | Fact verification | RAG · ChromaDB + bge-small | Per-claim verdict + retrieved evidence |
| 4 | Social engineering | Rules + LLM | Tactics detected, each with a quote |
| 5 | Report generation | Llama 3.1 via CrewAI | Verdict, red flags, next steps |

An **orchestrator** runs agents 2-4 concurrently, computes the risk score from their
outputs, then hands everything to the report writer.

```
                    ┌──────────────┐
   Upload audio ───►│ Whisper v3   │──── transcript + timestamps
                    └──────┬───────┘
                           ▼
                  ┌────────────────┐
                  │  Orchestrator  │
                  └───┬────┬───┬───┘
            ┌─────────┘    │   └─────────┐
            ▼              ▼             ▼
    ┌──────────────┐ ┌───────────┐ ┌──────────────┐
    │ Scam ML      │ │ Fact check│ │ Social eng.  │
    │ classifier   │ │ (RAG)     │ │ analysis     │
    └───────┬──────┘ └─────┬─────┘ └──────┬───────┘
            └──────────────┼──────────────┘
                           ▼
                  ┌─────────────────┐
                  │ Risk scoring    │  ← deterministic, not LLM-decided
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Report agent    │───► Scam score + explainable report
                  └─────────────────┘
```

### Two design decisions worth knowing

**The LLM writes the explanation; it does not choose the score.** The risk score is
computed by [`app/services/scoring.py`](backend/app/services/scoring.py) as a
weighted sum of the three agent signals. A model that misreads the evidence can
produce awkward prose, but it cannot produce a wrong verdict badge — and the same
call always scores the same.

**Every finding must quote the recording.** LLM output is grounded before it is
accepted: a quote that does not appear in the transcript is dropped, and a
contradiction with no quote behind it is downgraded to *unverified* so a
hallucination can never escalate the risk score.

---

## Quick start

Requirements: **Python 3.11+** and **Node 18+**. Nothing else is mandatory —
every heavy model is optional and the system degrades explicitly (see
[Runtime modes](#runtime-modes)).

```bash
git clone <your-repo> scamshield && cd scamshield
cp .env.example .env
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[ml]"           # API + classifier
python -m scripts.train_classifier      # tunes and trains Agent 2 on 800 transcripts
python -m scripts.seed_knowledge_base   # indexes agent 3's knowledge base

uvicorn app.main:app --reload    # http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

Open <http://localhost:3000>, switch to **Paste transcript**, click *Use a sample
scam call*, and press **Analyse call**.

---

## Runtime modes

Heavy dependencies are optional extras. Each agent falls back to a deterministic
analyzer when its runtime is missing, and the UI's status strip always shows which
path is live — a demo never silently claims to be running Whisper when it isn't.

| Extra | Install | Enables | Fallback if absent |
|-------|---------|---------|--------------------|
| — | `pip install -e .` | API, pipeline, rules, retrieval | — |
| `ml` | `pip install -e ".[ml]"` | XGBoost classifier | Logistic regression; weighted scam lexicon if untrained |
| `asr` | `pip install -e ".[asr]"` | Whisper large-v3 audio upload | Transcript-only mode (`POST /analyses/text`) |
| `rag` | `pip install -e ".[rag]"` | ChromaDB + bge-small embeddings | In-memory TF-IDF index over the same documents |
| `agents` | `pip install -e ".[agents]"` | CrewAI + Llama 3.1 | Rule-based claim verification, tactics and report |

Everything at once:

```bash
pip install -e ".[ml,asr,rag,agents,dev]"
```

`GET /api/v1/health/components` reports each subsystem and what it degraded to.

### Enabling the LLM agents

The model string carries the provider. Ollama is the default because it is local
and free, matching the "no API costs" goal:

```bash
ollama pull llama3.1:8b
# .env
SCAMSHIELD_LLM_MODEL=ollama/llama3.1:8b
SCAMSHIELD_LLM_BASE_URL=http://localhost:11434
```

Any LiteLLM-supported provider works instead — set `SCAMSHIELD_LLM_MODEL` to
`anthropic/claude-sonnet-5`, `openai/gpt-4o-mini`, etc., and export the matching
API key. If the model is unreachable, ScamShield logs the reason and runs the
deterministic analyzers rather than failing the request.

---

## Project layout

```
scamshield/
├── backend/
│   ├── app/
│   │   ├── core/          config, logging, exceptions, domain constants
│   │   ├── db/            SQLAlchemy models, session, repository
│   │   ├── schemas/       Pydantic contracts shared by agents + API
│   │   ├── ml/
│   │   │   ├── transcription/   Agent 1 — Whisper engines + selection
│   │   │   ├── classifier/      Agent 2 — TF-IDF/XGBoost + lexicon fallback
│   │   │   └── rag/             Agent 3 — chunking, embeddings, vector stores
│   │   ├── agents/
│   │   │   ├── crew.py          CrewAI agents, tasks, execution
│   │   │   ├── prompts.py       role definitions + task prompts
│   │   │   ├── orchestrator.py  runs agents 2-4, scores, then agent 5
│   │   │   ├── heuristics/      deterministic claim/tactic/report analyzers
│   │   │   └── tools/           knowledge base + classifier as CrewAI tools
│   │   ├── services/      pipeline, scoring, analysis service, storage
│   │   └── api/v1/        analyses, knowledge, health endpoints
│   ├── data/
│   │   ├── knowledge_base/   markdown corpus for Agent 3
│   │   └── training/         labelled call transcripts for Agent 2
│   ├── scripts/           train_classifier, seed_knowledge_base
│   └── tests/
└── frontend/
    └── src/
        ├── app/           routes: analyse, report, history, how-it-works
        ├── components/    upload, report, history, layout, ui
        └── lib/           API client, types, hooks, formatting
```

---

## API

Base path `/api/v1`. Interactive docs at `/docs`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/analyses` | Upload an audio recording (multipart). Returns `202` + job id. |
| `POST` | `/analyses/text` | Analyse a transcript directly, skipping Agent 1. |
| `GET` | `/analyses/{id}` | Full record: transcript, evidence, report, agent traces. |
| `GET` | `/analyses` | Paginated history. |
| `DELETE` | `/analyses/{id}` | Delete an analysis and its stored audio. |
| `GET` | `/knowledge/search?q=` | Query the RAG knowledge base directly. |
| `POST` | `/knowledge/reindex` | Rebuild the index after editing the markdown. |
| `GET` | `/knowledge/tactics` | The eight-tactic reference vocabulary. |
| `GET` | `/health/components` | Per-subsystem readiness and active fallbacks. |

Analysis is asynchronous: `POST` returns immediately with `pending`, and the client
polls the resource through `transcribing` → `analyzing` → `completed`.

```bash
curl -X POST http://localhost:8000/api/v1/analyses/text \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"This is your bank security department. Your account will be locked in 10 minutes. Do not hang up and read me the code we sent to your phone."}'
```

---

## Training and knowledge base

**Classifier.** `backend/data/training/calls.csv` is the balanced 800-transcript
Kaggle *Scam and Non-Scam Call Conversation Dataset* (400 per class), converted
to `label,category,text`. The trainer reserves a stratified 20% test set, tunes
TF-IDF and XGBoost hyperparameters with five-fold group-aware cross-validation on
the remaining 80%, evaluates once on the untouched test set, then refits the
selected pipeline on all 800 rows. Exact duplicate transcripts stay in the same
partition. Dataset checksums, attribution, license, and processing steps are
recorded in `backend/data/training/dataset_manifest.json`.

A narrow deterministic negation guardrail prevents a known bag-of-words failure:
legitimate warnings such as "we will never ask for your OTP" are not interpreted
as credential requests. The guardrail is disabled when request language appears
near a credential, so a reassuring preface cannot mask an actual request.
Inference also rejects intercept-only confidence: if the trained trees produce
almost no attributable phrase evidence, Agent 2 uses its conservative weighted
phrase scorer instead of returning a high but unsupported XGBoost probability.

```bash
python -m scripts.prepare_kaggle_dataset  # reproducibly rebuild calls.csv
python -m scripts.train_classifier        # tune, evaluate, refit, save artifact
```

Training writes `backend/artifacts/scam_classifier.joblib` and a human-readable
`classifier_training_report.json` containing held-out metrics, selected
hyperparameters, dataset checksums, and the full classification report.

**Knowledge base.** `backend/data/knowledge_base/*.md` holds the documents Agent 3
retrieves against, with `title` / `category` frontmatter. They are chunked on
headings so each passage covers one topic. Add or edit a file and re-run:

```bash
python -m scripts.seed_knowledge_base --query "do banks ask for OTPs?"
```

Replace these documents with your own institution's published policies before
deploying — the bundled set is written from widely documented industry practice
and is not a legal source.

---

## Configuration

All settings live in [`backend/app/core/config.py`](backend/app/core/config.py) and
are read from the repo-root `.env` with the `SCAMSHIELD_` prefix. See
[`.env.example`](.env.example) for the full list. The ones you are most likely to
change:

| Variable | Default | Notes |
|----------|---------|-------|
| `SCAMSHIELD_DATABASE_URL` | SQLite file | Swap for `postgresql+asyncpg://…` in production |
| `SCAMSHIELD_STORAGE_BACKEND` | `local` | `s3` for AWS or any S3-compatible endpoint |
| `SCAMSHIELD_TRANSCRIPTION_BACKEND` | `auto` | `faster-whisper`, `transformers`, `openai-whisper`, `stub` |
| `SCAMSHIELD_WHISPER_DEVICE` | `auto` | `cuda` if you have a GPU |
| `SCAMSHIELD_LLM_MODEL` | `ollama/llama3.1:8b` | Any LiteLLM model string |
| `SCAMSHIELD_AGENTS_ENABLED` | `true` | `false` forces the deterministic path |
| `SCAMSHIELD_WEIGHT_*` | 0.40 / 0.35 / 0.25 | Evidence weights; normalised automatically |

---

## Testing

```bash
cd backend
pip install -e ".[ml,dev]"
pytest              # 47 tests: scoring, analyzers, parsing, full API round-trips
ruff check .
mypy app
```

```bash
cd frontend
npm run typecheck && npm run lint && npm run build
```

The API tests run the whole pipeline end to end against a temporary SQLite
database with the LLM disabled, so they are deterministic and finish in seconds.

---

## Docker

```bash
docker compose up --build
```

Brings up PostgreSQL, the FastAPI backend on `:8000`, and the Next.js frontend on
`:3000`. The backend image installs the `ml` and `rag` extras; uncomment the
`ollama` service in `docker-compose.yml` to run the LLM agents in the same stack.

---

## Limitations

- **ScamShield cannot confirm who called you.** Caller ID is trivially spoofed and
  a recording contains no proof of identity. Affiliation claims are reported as
  *unverified*, never *verified*.
- **A low score is not a guarantee.** It means nothing matched a known scam
  pattern. When money or credentials are involved, hang up and call the
  organisation on its published number.
- **The knowledge base is finite.** Claims outside the indexed documents come back
  unverified rather than guessed at.
- **The classifier dataset is research-scale and partly augmented.** Its 800
  English transcripts support a strong prototype evaluation, not unrestricted
  production deployment. Test with real, consented, multilingual call data and
  monitor drift before operational use. A low probability is not proof that a
  call is safe.
- Schema changes are applied with `create_all` on start-up; introduce Alembic
  before the schema changes under real data.

---

## Team

Balajadia, John · Chan, Sidney · Gan, Kyle · Llanes, Andre · Pua, Daniel
