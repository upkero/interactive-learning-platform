FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project --extra embeddings-local --extra embeddings-voyage

ENV HF_HOME="/app/.cache/huggingface" \
    TIKTOKEN_CACHE_DIR="/app/.cache/tiktoken"
RUN mkdir -p "$TIKTOKEN_CACHE_DIR" /app/artifacts && \
    .venv/bin/docling-tools models download --output-dir /app/artifacts layout tableformer && \
    .venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("o200k_base")'

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME="/app/.cache/huggingface" \
    HF_HUB_OFFLINE=1 \
    TIKTOKEN_CACHE_DIR="/app/.cache/tiktoken" \
    INGEST_DOCLING_ARTIFACTS_PATH="/app/artifacts"

WORKDIR /app

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser && \
    mkdir -p /models && \
    chown -R appuser:appgroup /app /models

COPY --from=builder --chown=appuser:appgroup /app/.venv .venv
COPY --from=builder --chown=appuser:appgroup /app/.cache /app/.cache
COPY --from=builder --chown=appuser:appgroup /app/artifacts /app/artifacts
COPY --chown=appuser:appgroup alembic.ini ./
COPY --chown=appuser:appgroup migrations/ migrations/
COPY --chown=appuser:appgroup src/ src/
COPY --chown=appuser:appgroup resources/ resources/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
