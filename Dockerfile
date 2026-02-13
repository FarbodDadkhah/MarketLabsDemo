# ============================================================
# Stage 1: Build — install dependencies in an isolated layer
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata first for dependency caching
COPY pyproject.toml ./

# Install dependencies into a virtualenv (isolated from system Python)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies only — this layer is cached as long as
# pyproject.toml doesn't change. Code changes won't bust this cache.
RUN pip install --no-cache-dir --upgrade pip && \
    python -c "import tomllib; deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; print('\n'.join(deps))" > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Now copy source code (changes frequently)
COPY src/ ./src/

# Install the package itself — deps already satisfied, just builds the wheel
RUN pip install --no-cache-dir --no-deps .

# ============================================================
# Stage 2: Runtime — minimal image with only what's needed
# ============================================================
FROM python:3.11-slim AS runtime

# Install only runtime system dependencies (no compiler)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy virtualenv from builder stage (no build tools in final image)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
WORKDIR /app
COPY src/ ./src/

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Health check: hit the /health endpoint every 30 seconds
# Start checking after 10 seconds, allow 5 seconds per check, fail after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn — 4 workers for production, graceful shutdown
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
