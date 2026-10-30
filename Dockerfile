# SENTRA in one container.
#
# Stage 1 builds the console. Stage 2 installs the service from the frozen
# lockfile and serves the API and the built console from one Uvicorn worker
# on port 8765.

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
COPY services/sentra services/sentra
COPY fixtures fixtures
RUN cd services/sentra && uv sync --frozen --no-dev && chown -R sentra /app
COPY --from=console /app/apps/console/dist apps/console/dist

ENV SENTRA_STATIC_DIR=/app/apps/console/dist \
    SENTRA_FIXTURES=/app/fixtures/reporting \
    SENTRA_INTERPRETER=chain \
    PYTHONUNBUFFERED=1
USER sentra
EXPOSE 8765
CMD ["/app/services/sentra/.venv/bin/uvicorn", "sentra.api.app:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
