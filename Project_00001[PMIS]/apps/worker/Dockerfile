# Multi-stage build for Worker
FROM python:3.11-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY apps/worker/pyproject.toml apps/worker/poetry.lock* /app/
RUN pip install --no-cache-dir "poetry>=1.4" && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction

# Production stage
FROM python:3.11-slim
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy worker and shared code
COPY apps/worker/worker.py /app/worker.py
COPY apps/worker/db.py /app/db.py
COPY apps/api/app /app/app
COPY apps/common /app/common

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check - verify celery worker is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 5672), timeout=5)" || exit 1

CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
