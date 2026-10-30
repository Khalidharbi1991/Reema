# =============================================================================
# REEMA - Khalid's IT company
# =============================================================================
# The allowlist in .dockerignore excludes all private reference material.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install Python dependencies into a virtual environment
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build-time system dependencies required by WeasyPrint and lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment for clean isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies first (cache-friendly layer)
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# ---------------------------------------------------------------------------
# Stage 2: Runtime — lean image with only what is needed to run
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="Khalid Alharbi"
LABEL description="REEMA - Khalid's IT company (SOP documentation, coordination, home design side service)"
LABEL version="2.0.0"

WORKDIR /app

# Install runtime system dependencies for WeasyPrint and PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# A model key, if used, must be supplied at runtime; no key is embedded here.

# Copy configuration files
COPY config/ ./config/

# Customer references are optional read-only mounts at /app/references.
# Do not copy them into image layers.

# Copy source code
COPY src/ ./src/

# Create output directory
RUN useradd --create-home --uid 10001 reema \
    && mkdir -p /app/output /app/logs /app/references \
    && chown -R reema:reema /app/output /app/logs

# Default output directory
ENV REEMA_OUTPUT_DIR="/app/output"
ENV REFERENCES_DIR="/app/references"
ENV ALLOW_EXTERNAL_AI="false"
USER reema

# Expose no ports — REEMA is a CLI tool, not a server

# Starting a container must not launch paid generation automatically.
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["status"]
