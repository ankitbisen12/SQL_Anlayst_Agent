# ---------- 1) Build the React frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Optional build-time settings (empty = same origin as the API)
ARG VITE_API_URL=""
ARG VITE_API_KEY=""
RUN npm run build

# ---------- 2) Python runtime: FastAPI serves the API and the built frontend ----------
FROM python:3.13-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY agents ./agents
COPY api ./api
COPY guardrails ./guardrails
COPY Models ./Models
COPY utils ./utils
COPY db ./db
COPY evals ./evals
COPY main.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*'"]
