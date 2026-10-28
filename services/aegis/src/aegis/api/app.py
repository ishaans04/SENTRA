"""The HAEGIS service: commands are POSTs, updates arrive over server-sent events (PRD §12).

One Uvicorn worker serves the API and the built console from the same origin.
A cookie names the visitor's sandbox; there is no sign-in. HIVE's own routes
stay available under ``/api/v1``.

Errors are always ``{"error": "<code>", "message": "<plain sentence>"}``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Cookie, FastAPI, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aegis.api.sessions import RateLimited, Sandbox, SessionManager
from aegis.api.snapshot import channel, snapshot
from aegis.decisions.service import DecisionError
from aegis.interpret.readback import read_back_decision
from aegis.recovery.service import RecoveryError
from hive_core.api.routes import router as hive_router

COOKIE = "haegis_session"
MAX_TEXT = 2000
SessionCookie = Annotated[str | None, Cookie(alias=COOKIE)]


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class TextBody(BaseModel):
    text: str = Field(min_length=1)
    finding_id: str | None = None


class EditBody(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_TEXT)


class ChoiceBody(BaseModel):
    choice: str


def create_app(
    manager: SessionManager | None = None, static_dir: str | Path | None = None
) -> FastAPI:
    sessions = manager if manager is not None else SessionManager()
    app = FastAPI(
        title="HAEGIS API",
        version="1.0.0",
        summary="Approvals tied to conditions, enforced at an MCP gateway, with dictated recovery.",
    )
    origins = [o for o in os.getenv("AEGIS_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Last-Event-ID"],
        )
    app.include_router(hive_router, prefix="/api/v1")

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)

    def sandbox_for(session_id: str | None) -> Sandbox:
        sandbox = sessions.get(session_id)
        if sandbox is None:
            raise ApiError(404, "no_session", "Your sandbox has expired. Start a new session.")
        return sandbox

    def text_of(body: TextBody) -> str:
        if len(body.text) > MAX_TEXT:
            raise ApiError(413, "text_too_long", f"Keep it under {MAX_TEXT} characters.")
        return body.text

    def failed(exc: Exception) -> ApiError:
        message = str(exc.args[0]) if exc.args else str(exc)
        if message.startswith(("No ", "There is no")):
            return ApiError(404, "not_found", message)
        return ApiError(409, "not_allowed", message)

    # -- service --------------------------------------------------------------

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session")
    async def create_session(
        response: Response, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sessions.create(haegis_session)
        response.set_cookie(
            COOKIE, sandbox.session.session_id, httponly=True, samesite="lax", max_age=6 * 3600
        )
        return snapshot(sandbox.session)

    @app.get("/api/state")
    async def state(haegis_session: SessionCookie = None) -> dict[str, Any]:
        return snapshot(sandbox_for(haegis_session).session)

    @app.get("/api/events", response_class=EventSourceResponse)
    async def events(
        haegis_session: SessionCookie = None,
        follow: bool = True,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterator[ServerSentEvent]:
        session = sandbox_for(haegis_session).session
        after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        queue = session.ledger.subscribe()
        try:
            for event in session.ledger.events():
                if event.seq > after:
                    after = event.seq
                    yield ServerSentEvent(
                        data=event.model_dump(), event=channel(event), id=str(event.seq)
                    )
            while follow:
                event = await queue.get()
                if event.seq <= after:
                    continue
                after = event.seq
                yield ServerSentEvent(
                    data=event.model_dump(), event=channel(event), id=str(event.seq)
                )
        finally:
            session.ledger.unsubscribe(queue)

    @app.get("/api/ledger.jsonl", response_class=PlainTextResponse)
    async def ledger(haegis_session: SessionCookie = None) -> str:
        return sandbox_for(haegis_session).session.ledger.to_jsonl()

    @app.get("/api/record")
    async def record(haegis_session: SessionCookie = None) -> dict[str, Any]:
        current = snapshot(sandbox_for(haegis_session).session)["record"]
        if current is None:
            raise ApiError(404, "not_found", "The record closes after verification.")
        return dict(current)

    # -- storyline ------------------------------------------------------------

    @app.post("/api/story/step")
    async def story_step(haegis_session: SessionCookie = None) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        async with sandbox.lock:
            if sandbox.session.at_end:
                raise ApiError(
                    409, "story_finished", "The storyline is finished. Reset to replay it."
                )
            try:
                await sandbox.session.step()
            except (DecisionError, RecoveryError, ValueError) as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/story/play")
    async def story_play(haegis_session: SessionCookie = None) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        async with sandbox.lock:
            while not sandbox.session.at_end:
                await sandbox.session.step()
            return snapshot(sandbox.session)

    @app.post("/api/story/reset")
    async def story_reset(
        response: Response, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        return await create_session(response, haegis_session)

    # -- approvals ------------------------------------------------------------

    @app.post("/api/decisions/interpret")
    async def interpret_decision(
        body: TextBody, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        text = text_of(body)
        try:
            sessions.check_interpret_rate(sandbox)
        except RateLimited:
            raise ApiError(429, "rate_limited", "Too many requests. Wait a minute.") from None
        async with sandbox.lock:
            s = sandbox.session
            try:
                proposal, used = await s.interpreter.approval(text)
            except ValueError as exc:
                raise ApiError(422, "not_understood", str(exc)) from exc
            decision = s.decisions.propose(proposal, text)
            labels = {n.id: n.label for n in s.bridge.manifest.nodes}
            return {
                "decision": decision.model_dump(),
                "read_back": read_back_decision(proposal, labels, used),
                "interpreted_by": used,
            }

    async def decision_command(
        session_id: str | None, decision_id: str, verb: str
    ) -> dict[str, Any]:
        sandbox = sandbox_for(session_id)
        async with sandbox.lock:
            decisions = sandbox.session.decisions
            try:
                getattr(decisions, verb)(decision_id)
            except DecisionError as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/decisions/{decision_id}/{verb}")
    async def decision_verb(
        decision_id: str, verb: str, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        if verb not in {"confirm", "reject", "renew", "withdraw"}:
            raise ApiError(404, "not_found", f"No decision command {verb!r}.")
        return await decision_command(haegis_session, decision_id, verb)

    # -- recovery -------------------------------------------------------------

    @app.post("/api/recovery/interpret")
    async def interpret_recovery(
        body: TextBody, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        text = text_of(body)
        s = sandbox.session
        pending = next((p for p in s.recovery.plans.values() if p.status == "read_back"), None)
        if pending is not None and s.grammar.is_confirmation(text):
            async with sandbox.lock:
                try:
                    return (await s.recovery.confirm(pending.id)).model_dump()
                except RecoveryError as exc:
                    raise failed(exc) from exc
        try:
            sessions.check_interpret_rate(sandbox)
        except RateLimited:
            raise ApiError(429, "rate_limited", "Too many requests. Wait a minute.") from None
        async with sandbox.lock:
            try:
                plan = await s.recover(text)
            except ValueError as exc:
                raise ApiError(
                    422,
                    "not_understood",
                    f"{exc} I can't establish a safe automatic recovery from that.",
                ) from exc
            return plan.model_dump()

    @app.post("/api/recovery/{plan_id}/correct")
    async def correct_recovery(
        plan_id: str, body: TextBody, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        text = text_of(body)
        async with sandbox.lock:
            s = sandbox.session
            try:
                steps, used = await s.interpreter.recovery(text)
                return s.recovery.correct(
                    plan_id, steps, text=text, interpreted_by=used
                ).model_dump()
            except RecoveryError as exc:
                raise failed(exc) from exc
            except ValueError as exc:
                raise ApiError(422, "not_understood", str(exc)) from exc

    @app.post("/api/recovery/{plan_id}/{verb}")
    async def recovery_verb(
        plan_id: str, verb: str, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        if verb not in {"confirm", "abandon"}:
            raise ApiError(404, "not_found", f"No recovery command {verb!r}.")
        sandbox = sandbox_for(haegis_session)
        async with sandbox.lock:
            s = sandbox.session
            try:
                if verb == "confirm":
                    plan = await s.recovery.confirm(plan_id)
                else:
                    plan = s.recovery.abandon(plan_id)
            except RecoveryError as exc:
                raise failed(exc) from exc
            return plan.model_dump()

    @app.post("/api/items/{item_id}/human-edit")
    async def human_edit(
        item_id: str, body: EditBody, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        async with sandbox.lock:
            try:
                sandbox.session.human_edit(item_id, body.content)
            except KeyError as exc:
                raise ApiError(404, "not_found", f"No item {item_id!r}.") from exc
            return snapshot(sandbox.session)

    @app.post("/api/conflicts/{conflict_id}/resolve")
    async def resolve_conflict(
        conflict_id: str, body: ChoiceBody, haegis_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(haegis_session)
        async with sandbox.lock:
            try:
                sandbox.session.recovery.resolve_conflict(conflict_id, body.choice)
            except RecoveryError as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/findings/{finding_id}/explain")
    async def explain(finding_id: str, haegis_session: SessionCookie = None) -> dict[str, str]:
        finding = sandbox_for(haegis_session).session.bridge.finding(finding_id)
        if finding is None:
            raise ApiError(404, "not_found", f"No open finding {finding_id!r}.")
        return {"text": finding.explanation, "uncertainty": finding.uncertainty}

    static = Path(static_dir or os.getenv("AEGIS_STATIC_DIR") or ".")
    if (static_dir or os.getenv("AEGIS_STATIC_DIR")) and static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="console")
    return app


app = create_app()
