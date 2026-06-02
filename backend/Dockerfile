# Multi-stage build for Python FastAPI backend
# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build-args from cloudbuild.yaml so the running container can self-report
# what version it is. Promoted to ENV so app/main.py can read them via
# os.getenv("BUILD_SHA") / os.getenv("BUILD_TIME") and surface them at
# /health. Defaults to "unknown" for local docker builds without these
# build-args set.
ARG BUILD_SHA=unknown
ARG BUILD_TIME=unknown
ENV BUILD_SHA=${BUILD_SHA}
ENV BUILD_TIME=${BUILD_TIME}

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Make init script executable
RUN chmod +x scripts/init_db.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["sh", "-c", "python scripts/init_db.py; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
