"""Authenticated localhost API and packaged HUD."""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from jarvis.config import Settings
from jarvis.engine import Plan
from jarvis.memory import MemoryInput
from jarvis.runtime import Runtime
from jarvis.scheduler import ScheduleInput
from jarvis.security import Denied, Unavailable


class GoalInput(BaseModel):
    goal: str = Field(min_length=1, max_length=16000)
    session: str = Field(default="default", max_length=64)


class Decision(BaseModel):
    allowed: bool


class Preferences(BaseModel):
    provider: Literal["offline", "ollama", "compatible"]
    model: str = Field(max_length=150)
    model_url: str
    network_hosts: list[str]
    desktop_enabled: bool = False
    proactive: bool = False


class VoiceEvent(BaseModel):
    kind: Literal[
        "VOICE_STARTED",
        "VOICE_STOPPED",
        "VOICE_TRANSCRIPT",
        "USER_INTERRUPTED",
        "SPEAKING",
        "LISTENING",
    ]
    detail: str = Field(default="", max_length=1000)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    runtime = Runtime(settings)
    token = settings.token()
    origins = {f"http://localhost:{settings.port}", f"http://127.0.0.1:{settings.port}"}
    hosts = {f"localhost:{settings.port}", f"127.0.0.1:{settings.port}"}

    @asynccontextmanager
    async def lifespan(app):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="JARVIS AI", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.runtime = runtime

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.headers.get("host") not in hosts:
            return JSONResponse({"detail": "Unexpected host"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse(
                {"detail": "Cross-origin requests are not allowed"}, status_code=403
            )
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not supplied.isascii() or not secrets.compare_digest(supplied, token):
                return JSONResponse(
                    {"detail": "Open the authenticated launch URL printed by Jarvis"},
                    status_code=401,
                )
            try:
                if int(request.headers.get("content-length", "0")) > 256000:
                    return JSONResponse({"detail": "Request exceeds 256 KB"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 256000:
                    return JSONResponse({"detail": "Request exceeds 256 KB"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Denied)
    async def denied(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(Unavailable)
    async def unavailable(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(httpx.HTTPError)
    async def provider_error(request, exc):
        return JSONResponse(
            {
                "detail": "The external provider is unavailable or rejected this request. Check its URL, model, and credentials."
            },
            status_code=503,
        )

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)[:1000]}, status_code=422)

    @app.get("/api/status")
    async def status():
        runtime.gate.prune()
        return {
            "runs": runtime.store.runs(50),
            "approvals": [a.public() for a in runtime.gate.pending.values()],
            "telemetry": await runtime.telemetry.sample(),
            "setup_complete": settings.setup_complete,
            "capabilities": runtime.registry.catalog(),
        }

    @app.get("/api/diagnostics")
    async def diagnostics():
        return await runtime.diagnostics()

    @app.get("/api/capabilities")
    async def capabilities():
        return {"tools": runtime.registry.catalog(), "graph": runtime.registry.graph()}

    @app.get("/api/settings")
    async def get_settings():
        return settings.model_dump(mode="json", exclude={"data_dir"})

    @app.put("/api/settings")
    async def update_settings(preferences: Preferences):
        validated = Settings(
            **{**settings.model_dump(), **preferences.model_dump(), "setup_complete": True}
        )
        validated.save()
        for field in preferences.model_dump():
            setattr(settings, field, getattr(validated, field))
        settings.setup_complete = True
        runtime.tools.web.hosts = settings.network_hosts
        await runtime.bus.publish(
            "SETTINGS_UPDATED",
            {"provider": settings.provider, "desktop_enabled": settings.desktop_enabled},
        )
        return {"saved": True}

    @app.post("/api/goals")
    async def goal(body: GoalInput):
        return await runtime.goal(body.goal, body.session)

    @app.post("/api/plans")
    async def plan(body: Plan):
        return (await runtime.engine.submit(body)).model_dump()

    @app.get("/api/runs/{run_id}")
    async def run(run_id: str):
        result = runtime.store.run(run_id)
        if not result:
            raise HTTPException(404, "Unknown run")
        return result

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        await runtime.engine.cancel(run_id)
        return {"cancelled": True}

    @app.post("/api/runs/{run_id}/replan")
    async def replan(run_id: str):
        return await runtime.replan(run_id)

    @app.post("/api/approvals/{approval_id}")
    async def approve(approval_id: str, decision: Decision):
        return (await runtime.engine.decide(approval_id, decision.allowed)).model_dump()

    @app.get("/api/events")
    async def events(after: int = 0, run_id: str | None = None):
        return runtime.store.events(max(0, after), run_id)

    @app.get("/api/memory")
    async def memories(query: str = ""):
        return runtime.memory.search(query[:2000]) if query else runtime.memory.list()

    @app.post("/api/memory")
    async def add_memory(body: MemoryInput):
        result = runtime.memory.put(body, approved=True)
        await runtime.bus.publish("MEMORY_STORED", {"id": result["id"], "kind": body.kind})
        return result

    @app.put("/api/memory/{memory_id}")
    async def edit_memory(memory_id: str, body: MemoryInput):
        if not any(m["id"] == memory_id for m in runtime.memory.list()):
            raise HTTPException(404, "Unknown memory")
        return runtime.memory.put(body, approved=True, memory_id=memory_id)

    @app.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str):
        return {"deleted": runtime.memory.delete(memory_id)}

    @app.get("/api/schedules")
    async def schedules():
        return runtime.scheduler.list()

    @app.post("/api/schedules")
    async def add_schedule(body: ScheduleInput):
        return runtime.scheduler.add(body)

    @app.delete("/api/schedules/{ident}")
    async def delete_schedule(ident: str):
        return {"deleted": runtime.scheduler.delete(ident)}

    @app.post("/api/voice")
    async def voice(body: VoiceEvent):
        await runtime.bus.publish(
            body.kind,
            {
                "source": "browser",
                "detail": body.detail if body.kind != "VOICE_TRANSCRIPT" else "Transcript received",
            },
        )
        return {"accepted": True}

    @app.websocket("/api/live")
    async def live(socket: WebSocket):
        if socket.headers.get("origin") not in origins or socket.headers.get("host") not in hosts:
            await socket.close(code=1008)
            return
        await socket.accept()
        try:
            auth = await asyncio.wait_for(socket.receive_json(), 5)
            if (
                not isinstance(auth, dict)
                or not isinstance(auth.get("token"), str)
                or not secrets.compare_digest(auth["token"], token)
            ):
                await socket.close(code=1008)
                return
            async with runtime.bus.subscribe() as queue:
                cursor = max(0, int(auth.get("after", 0)))
                if not cursor:
                    latest = runtime.store.db.execute(
                        "SELECT COALESCE(MAX(seq),0) FROM events"
                    ).fetchone()[0]
                    cursor = max(0, latest - 200)
                while True:
                    history = runtime.store.events(cursor)
                    for event in history:
                        await socket.send_json(event)
                        cursor = event["seq"]
                    if len(history) < 500:
                        break
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), 15)
                        if event["seq"] > cursor:
                            for missing in runtime.store.events(cursor, limit=500):
                                await socket.send_json(missing)
                                cursor = missing["seq"]
                    except TimeoutError:
                        await socket.send_json({"kind": "HEARTBEAT", "data": {}})
        except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
            return

    frontend = Path(__file__).parent / "frontend"

    @app.get("/")
    async def index():
        return FileResponse(frontend / "index.html")

    @app.get("/assets/{name}")
    async def asset(name: str):
        if name not in {"app.js", "voice.js", "style.css", "mark.svg"}:
            raise HTTPException(404)
        return FileResponse(frontend / name)

    return app
