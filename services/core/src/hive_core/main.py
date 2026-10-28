"""ASGI application for the HIVE core service.

Local-first by construction: the service binds to loopback, reads only checked-in
fictional fixtures, and makes no outbound network calls of any kind. The browser
origins below are the local console in development and preview; nothing else is
permitted to call the API with credentials.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hive_core.api.routes import router

#: Local console origins. Wildcards are avoided deliberately: a permissive CORS
#: policy on a security tool is the kind of detail a reviewer is right to flag.
_DEFAULT_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
)


def _allowed_origins() -> list[str]:
    configured = os.getenv("HIVE_CORS_ORIGINS", "").strip()
    if not configured:
        return list(_DEFAULT_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(
    title="HIVE Core API",
    version="1.0.0",
    summary="Population-level security analysis for autonomous agent estates.",
    description=(
        "HIVE compares a declared architecture against observed agent interactions, "
        "reports capability compositions the architecture forbids, and evaluates "
        "pre-authorised containment actions against the live graph.\n\n"
        "This service runs entirely locally against fictional fixtures. It contacts "
        "no external system and all controls are simulated."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def index() -> dict[str, str]:
    return {
        "service": "HIVE Core API",
        "docs": "/docs",
        "health": "/api/v1/health",
        "mode": "local-simulation",
    }
