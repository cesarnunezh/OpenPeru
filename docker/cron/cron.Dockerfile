FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=America/Lima

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
        chromium-driver \
        cron \
        curl \
        make \
        tesseract-ocr \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-dev \
    && uv run playwright install --with-deps chromium

COPY backend /app/backend
COPY Makefile /app/Makefile
COPY docker/cron /app/docker/cron

RUN chmod +x /app/docker/cron/entrypoint.sh /app/docker/cron/run-job.sh

ENTRYPOINT ["/app/docker/cron/entrypoint.sh"]
