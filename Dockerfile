# Trida AI Blueprint — aidnn Month-End Close, Deployed
#
# Multi-stage: the builder resolves the locked environment with uv;
# the runtime stage carries only the venv, the package, the
# definition pack, and the migrations — no build tooling, no test
# suite. The process runs as a non-root user and keeps NO local
# state: with DATABASE_URL / S3_* set (the compose stack sets
# them) batches, runs, packs, and graph checkpoints live in
# PostgreSQL and raw extracts in object storage. Without them it
# serves on in-memory test doubles, which the /readiness payload
# names.
#
# Build:  docker build -t aidnn-month-end-close .
# Run:    docker run --rm -p 8000:8000 aidnn-month-end-close
#
# FINANCE_ENGINE defaults to the labelled offline engine.
# Selecting aidnn without AIDNN_WORKSPACE_URL fails startup
# honestly rather than serving offline answers as aidnn's.

# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml README.md uv.lock constraints.txt ./
COPY src ./src
# --frozen installs exactly uv.lock; --no-dev keeps the test
# toolchain (pytest & friends) out of the production image.
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations

ENV PYTHONPATH=/app/src \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Liveness only: /health answers without touching dependencies.
# (Readiness — engine, store, definition pack — is /readiness,
# for the orchestrator's readiness probe.)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "aidnn_close_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
