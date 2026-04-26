# --- web build stage ---
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# --- runtime stage ---
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}"

# Node + Claude Code CLI: claude-agent-sdk spawns the CLI as a subprocess
# in real mode. Without it, setting ANTHROPIC_API_KEY crashes the agent
# worker with "ProcessError: Command failed with exit code 1" at connect().
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --no-dev --frozen

COPY server/ ./server/
COPY --from=web /web/dist ./web/dist

COPY alembic.ini .
COPY alembic/ ./alembic/
COPY db/ ./db/

EXPOSE 8080
# Use absolute venv paths so the entrypoint doesn't depend on PATH,
# which has been bitten by docker layer caching during this build.
# Migrations run before uvicorn so the schema is ready when workers boot.
CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && /app/.venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8080"]
