"""The SENTRA service: commands are POSTs, updates arrive over server-sent events (PRD §12).

One Uvicorn worker serves the API and the built console from the same origin.
A cookie names the visitor's sandbox; there is no sign-in. The engine's own routes
stay available under ``/api/v1``.

Errors are always ``{"error": "<code>", "message": "<plain sentence>"}``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from sentra.api.sessions import (
    MAX_STREAMS_PER_SESSION,
    RateLimited,
    Sandbox,
    SessionManager,
    SessionsFull,
)
from sentra.api.snapshot import channel, snapshot
from sentra.decisions.service import DecisionError
from sentra.interpret.readback import read_back_decision
from sentra.recovery.service import RecoveryError
from sentra_core.api.routes import router as engine_router

COOKIE = "sentra_session"
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


class ConfirmBody(BaseModel):
    #: The read-back revision the operator saw. Omitted only by older clients.
    revision: str | None = None


#: Failures a command can meet that are the operator's to fix, not a server fault.
_EXPECTED = (DecisionError, RecoveryError, ValueError, KeyError, ToolError)


def create_app(
    manager: SessionManager | None = None, static_dir: str | Path | None = None
) -> FastAPI:
    sessions = manager if manager is not None else SessionManager()
    app = FastAPI(
        title="SENTRA API",
        version="1.0.0",
        summary="Approvals tied to conditions, enforced at an MCP gateway, with dictated recovery.",
    )
    origins = [o for o in os.getenv("SENTRA_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Last-Event-ID"],
        )
    app.include_router(engine_router, prefix="/api/v1")

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

    async def require_sandbox(sentra_session: SessionCookie = None) -> Sandbox:
        """Resolved before any response starts, so a stream can still answer 404."""
        return sandbox_for(sentra_session)

    def interpret_slot(sandbox: Sandbox) -> None:
        try:
            sessions.check_interpret_rate(sandbox)
        except RateLimited:
            raise ApiError(429, "rate_limited", "Too many requests. Wait a minute.") from None

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
        response: Response, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        try:
            sandbox = sessions.create(replacing=sentra_session)
        except SessionsFull:
            raise ApiError(
                503,
                "sandbox_full",
                "Every live sandbox is in use right now. Try again in a few minutes, "
                "or open the recorded replay.",
            ) from None
        except RateLimited:
            raise ApiError(429, "rate_limited", "Too many new sessions. Wait a minute.") from None
        response.set_cookie(
            COOKIE, sandbox.session.session_id, httponly=True, samesite="lax", max_age=6 * 3600
        )
        return snapshot(sandbox.session)

    @app.get("/api/state")
    async def state(sentra_session: SessionCookie = None) -> dict[str, Any]:
        return snapshot(sandbox_for(sentra_session).session)

    async def stream_slot(sandbox: Sandbox = Depends(require_sandbox)) -> Sandbox:
        if sandbox.session.ledger.subscriber_count >= MAX_STREAMS_PER_SESSION:
            raise ApiError(429, "too_many_streams", "Close another tab of this sandbox first.")
        return sandbox

    @app.get("/api/events", response_class=EventSourceResponse)
    async def events(
        follow: bool = True,
        sandbox: Sandbox = Depends(stream_slot),
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterator[ServerSentEvent]:
        session = sandbox.session
        after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        history = session.ledger.events()
        if history and after > history[-1].seq:
            after = 0  # an id from an earlier session: replay this one from the start
        queue = session.ledger.subscribe()
        try:
            for event in session.ledger.events():
                if event.seq > after:
                    after = event.seq
                    yield ServerSentEvent(
                        data=event.model_dump(), event=channel(event), id=str(event.seq)
                    )
            while follow:
                live = await queue.get()
                if live is None:
                    return  # the session was reset or evicted: end this stream
                if live.seq <= after:
                    continue
                after = live.seq
                yield ServerSentEvent(data=live.model_dump(), event=channel(live), id=str(live.seq))
        finally:
            session.ledger.unsubscribe(queue)

    @app.get("/api/ledger.jsonl", response_class=PlainTextResponse)
    async def ledger(sentra_session: SessionCookie = None) -> str:
        return sandbox_for(sentra_session).session.ledger.to_jsonl()

    @app.get("/api/record")
    async def record(sentra_session: SessionCookie = None) -> dict[str, Any]:
        current = snapshot(sandbox_for(sentra_session).session)["record"]
        if current is None:
            raise ApiError(404, "not_found", "The record closes after verification.")
        return dict(current)

    # -- storyline ------------------------------------------------------------

    @app.post("/api/story/step")
    async def story_step(sentra_session: SessionCookie = None) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        async with sandbox.lock:
            if sandbox.session.at_end:
                raise ApiError(
                    409, "story_finished", "The storyline is finished. Reset to replay it."
                )
            try:
                await sandbox.session.step()
            except _EXPECTED as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/story/play")
    async def story_play(sentra_session: SessionCookie = None) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        async with sandbox.lock:
            try:
                while not sandbox.session.at_end:
                    await sandbox.session.step()
            except _EXPECTED as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/story/reset")
    async def story_reset(
        response: Response, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        return await create_session(response, sentra_session)

    # -- approvals ------------------------------------------------------------

    @app.post("/api/decisions/interpret")
    async def interpret_decision(
        body: TextBody, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        text = text_of(body)
        interpret_slot(sandbox)
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
        decision_id: str, verb: str, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        if verb not in {"confirm", "reject", "renew", "withdraw"}:
            raise ApiError(404, "not_found", f"No decision command {verb!r}.")
        return await decision_command(sentra_session, decision_id, verb)

    # -- recovery -------------------------------------------------------------

    @app.post("/api/recovery/interpret")
    async def interpret_recovery(
        body: TextBody, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        text = text_of(body)
        s = sandbox.session
        pending = s.recovery.pending()
        if pending is not None and s.grammar.is_confirmation(text):
            async with sandbox.lock:
                try:
                    return (await s.recovery.confirm(pending.id)).model_dump()
                except _EXPECTED as exc:
                    raise failed(exc) from exc
        interpret_slot(sandbox)
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
        plan_id: str, body: TextBody, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        text = text_of(body)
        interpret_slot(sandbox)
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
        plan_id: str,
        verb: str,
        body: ConfirmBody | None = None,
        sentra_session: SessionCookie = None,
    ) -> dict[str, Any]:
        if verb not in {"confirm", "abandon"}:
            raise ApiError(404, "not_found", f"No recovery command {verb!r}.")
        sandbox = sandbox_for(sentra_session)
        async with sandbox.lock:
            s = sandbox.session
            try:
                if verb == "confirm":
                    revision = body.revision if body else None
                    plan = await s.recovery.confirm(plan_id, revision)
                else:
                    plan = s.recovery.abandon(plan_id)
            except _EXPECTED as exc:
                raise failed(exc) from exc
            return plan.model_dump()

    @app.post("/api/items/{item_id}/human-edit")
    async def human_edit(
        item_id: str, body: EditBody, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        async with sandbox.lock:
            try:
                sandbox.session.human_edit(item_id, body.content)
            except KeyError as exc:
                raise ApiError(404, "not_found", f"No item {item_id!r}.") from exc
            return snapshot(sandbox.session)

    @app.post("/api/conflicts/{conflict_id}/resolve")
    async def resolve_conflict(
        conflict_id: str, body: ChoiceBody, sentra_session: SessionCookie = None
    ) -> dict[str, Any]:
        sandbox = sandbox_for(sentra_session)
        async with sandbox.lock:
            try:
                sandbox.session.recovery.resolve_conflict(conflict_id, body.choice)
            except RecoveryError as exc:
                raise failed(exc) from exc
            return snapshot(sandbox.session)

    @app.post("/api/findings/{finding_id}/explain")
    async def explain(finding_id: str, sentra_session: SessionCookie = None) -> dict[str, str]:
        finding = sandbox_for(sentra_session).session.bridge.finding(finding_id)
        if finding is None:
            raise ApiError(404, "not_found", f"No open finding {finding_id!r}.")
        return {"text": finding.explanation, "uncertainty": finding.uncertainty}

    static = Path(static_dir or os.getenv("SENTRA_STATIC_DIR") or ".")
    if (static_dir or os.getenv("SENTRA_STATIC_DIR")) and static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="console")
    return app


app = create_app()
