FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=America/Lima

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-dev --no-install-project

COPY app /app/app
COPY backend /app/backend

EXPOSE 8040

CMD ["uv", "run", "gunicorn", "--preload", "--timeout", "30", "--workers", "4", "--bind", "0.0.0.0:8040", "app.app:create_app()"]