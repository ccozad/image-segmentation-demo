# Multi-stage, production-hardened: deps build in an isolated venv, the final
# image is slim and runs as a non-root user with a HEALTHCHECK.
#
# Base image is pinned to a patch version. For full reproducibility pin to a
# digest instead, e.g.:
#   FROM python:3.12.8-slim-bookworm@sha256:<digest>
# Get the digest with: docker buildx imagetools inspect python:3.12.8-slim-bookworm
FROM python:3.12.8-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# ── final ────────────────────────────────────────────────────────────────────
FROM python:3.12.8-slim-bookworm AS final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Run as an unprivileged user.
RUN useradd --system --uid 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
