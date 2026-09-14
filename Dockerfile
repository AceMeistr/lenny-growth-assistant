# Multi-stage lean production Dockerfile for The Lenny Growth Assistant
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    DATABASE_URL=sqlite:///./data/lenny.db

WORKDIR /app

# Install minimal runtime dependencies including curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application assets, database, and codebase
COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY .env.example ./.env.example
COPY README.md .

# Create non-root user and grant ownership
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Docker healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start ASGI application server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
