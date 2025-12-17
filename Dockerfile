
FROM python:3.12-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install build dependencies for packages that need compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (better layer caching)
COPY pyproject.toml ./

# Install dependencies (without dev dependencies)
# Use CPU-only PyTorch to significantly reduce image size
RUN uv venv /app/.venv && \
    uv pip install --no-cache \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchvision --index-strategy unsafe-best-match && \
    uv pip install --no-cache -r pyproject.toml


FROM python:3.12-slim AS runtime

# Labels for container registry
LABEL org.opencontainers.image.title="Vyloc Backend API" \
    org.opencontainers.image.description="AI-Powered Product Localization Platform" \
    org.opencontainers.image.version="0.1.0" \
    org.opencontainers.image.vendor="Vyloc"

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    # Disable GPU for PyTorch (we're using CPU-only)
    CUDA_VISIBLE_DEVICES="" \
    # FastAPI/Uvicorn settings
    PORT=8000 \
    HOST=0.0.0.0 \
    # Python optimizations
    PYTHONOPTIMIZE=2

# Copy application code
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup main.py ./

# Copy the model file (required for watermark removal)
COPY --chown=appuser:appgroup model.pth ./

# Copy service account credentials for Google Cloud (Application Default Credentials)
COPY --chown=appuser:appgroup vyloc-479312-3866732f745d.json /app/credentials.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# Copy entrypoint script
COPY --chown=appuser:appgroup entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check for Cloud Run / container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV SERVICE=api

ENTRYPOINT ["./entrypoint.sh"]
