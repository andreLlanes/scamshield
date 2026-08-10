# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg is what Whisper uses to decode arbitrary audio containers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer first so application edits do not reinstall the world.
COPY pyproject.toml README.md ./
RUN mkdir -p app scripts && touch app/__init__.py scripts/__init__.py \
    && pip install --upgrade pip \
    && pip install -e ".[ml,rag,postgres,aws]"

COPY . .

# Build the model artifact and the vector index into the image so the container
# is useful the moment it starts.
RUN python -m scripts.train_classifier \
    && python -m scripts.seed_knowledge_base

RUN useradd --create-home --uid 1000 scamshield \
    && mkdir -p /app/var /app/data/chroma \
    && chown -R scamshield:scamshield /app
USER scamshield

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
