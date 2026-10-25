# One image for the API, the arq worker and migrations; docker-compose.prod.yml picks the command.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Run as an unprivileged user. storage/ is created here so the named volume inherits its owner.
RUN useradd --system --uid 10001 --home /app docbot \
    && mkdir -p /app/storage \
    && chown docbot /app/storage
USER docbot

EXPOSE 8000

# --proxy-headers: take the client IP from Caddy's X-Forwarded-For (rate limits are per IP).
# Trusting any forwarder is safe only because port 8000 is never published; Caddy is the sole way in.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
