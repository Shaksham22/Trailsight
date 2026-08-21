# syntax=docker/dockerfile:1

FROM node:22-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig*.json frontend/vite.config.ts ./
COPY frontend/src ./src
RUN npm run build


FROM python:3.12-slim AS application

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TRAILSIGHT_DB_PATH=/app/data/runtime/trailsight.duckdb \
    TRAILSIGHT_STATIC_DIR=/app/frontend/dist \
    TRAILSIGHT_TRACE_PATH=/app/data/traces/investigations.jsonl

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY prompts ./prompts
RUN uv sync --frozen --no-dev

COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
RUN mkdir -p /app/data/runtime /app/data/traces

EXPOSE 8000
CMD ["uvicorn", "trailsight.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
