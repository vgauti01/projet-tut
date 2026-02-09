# Multi-stage build for security
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy only the files needed for installation
COPY pyproject.toml uv.lock ./

# Install dependencies without the project itself
RUN uv sync --frozen --no-install-project --no-dev

# =============================================================================
# Final stage
# =============================================================================
FROM python:3.11-slim-bookworm

# Security updates only
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r ingestuser && \
    useradd -r -g ingestuser -u 1001 -m -s /bin/bash ingestuser

# Copy installed environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=ingestuser:ingestuser . /app/

# Switch to non-root user
USER ingestuser

# Run ingestion using the installed script
CMD ["ingest"]
