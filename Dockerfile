# SENTRA on a Hugging Face Space (Docker SDK, free CPU Basic).
#
# Stage 1 builds the console. Stage 2 installs the service from the frozen
# lockfile and serves the API and the built console from one Uvicorn worker,
# on the port the Space card declares (app_port: 7860 in
# deploy/huggingface/README.md, which deploy/huggingface/publish.sh installs as
# the Space's README).

FROM node:22-slim AS console
WORKDIR /app
RUN npm install -g pnpm@11.19.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/console/package.json apps/console/
RUN pnpm install --frozen-lockfile --filter @sentra/console
COPY apps/console apps/console
RUN pnpm --filter @sentra/console build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.8 /uv /bin/uv
RUN useradd --create-home --uid 1000 sentra
WORKDIR /app
COPY services/core services/core
COPY services/aegis services/aegis
COPY fixtures fixtures
RUN cd services/aegis && uv sync --frozen --no-dev && chown -R sentra /app
COPY --from=console /app/apps/console/dist apps/console/dist

ENV AEGIS_STATIC_DIR=/app/apps/console/dist \
    AEGIS_FIXTURES=/app/fixtures/aegis_reporting \
    AEGIS_INTERPRETER=chain \
    PYTHONUNBUFFERED=1
USER sentra
EXPOSE 7860
CMD ["/app/services/aegis/.venv/bin/uvicorn", "aegis.api.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
