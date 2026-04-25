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
    SEED_ON_STARTUP=1

RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9"

COPY server/ ./server/
COPY --from=web /web/dist ./web/dist

EXPOSE 8080
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
