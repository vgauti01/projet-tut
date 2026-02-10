# Stage 1: Build & Lock
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a multi-stage build
ENV UV_LINK_MODE=copy

# Install build dependencies (for llama-cpp-python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev --all-extras

# Stage 2: Final Image
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 -m appuser
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Copy source code (using src layout)
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml /app/

# On installe le projet lui-même si nécessaire (facultatif si on utilise PYTHONPATH)
ENV PYTHONPATH="/app/src"

USER appuser
EXPOSE 8000

# Health check (requires curl)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run the API using the entry point defined in pyproject.toml
CMD ["api"]
