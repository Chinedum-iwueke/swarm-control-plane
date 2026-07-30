from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import MissionControlSettings
from .control_plane import ControlPlaneClient, ControlPlaneError
from .knowledge import KnowledgePolicyError, KnowledgeStore
from .models import ApprovalDecision, IntakeRequest, KnowledgeIngestRequest

_STATIC = Path(__file__).parent / "static"


def create_app(
    settings: MissionControlSettings,
    *,
    control_plane: ControlPlaneClient | None = None,
    knowledge: KnowledgeStore | None = None,
) -> FastAPI:
    settings.prepare()
    store = knowledge or KnowledgeStore(
        settings.database_path, settings.allowed_knowledge_roots
    )
    store.initialize()
    client = control_plane or ControlPlaneClient(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await client.close()

    app = FastAPI(
        title="Hermes Mission Control",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )
    app.state.control_plane = client
    app.state.knowledge = store
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.exception_handler(ControlPlaneError)
    async def control_error(_, exc: ControlPlaneError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(KnowledgePolicyError)
    async def knowledge_error(_, exc: KnowledgePolicyError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/status")
    async def status() -> dict:
        return {
            "service": "Hermes Mission Control",
            "scope": "loopback-only",
            "knowledge": store.stats(),
        }

    @app.get("/api/dashboard")
    async def dashboard() -> dict:
        result = await client.dashboard()
        result["knowledge"] = store.stats()
        return result

    @app.post("/api/intake", dependencies=[Depends(_mutation_intent)])
    async def intake(payload: IntakeRequest) -> dict:
        return await client.create_intake(payload)

    @app.post(
        "/api/approvals/{approval_id}/{action}",
        dependencies=[Depends(_mutation_intent)],
    )
    async def decide(
        approval_id: str,
        action: str,
        payload: ApprovalDecision,
    ) -> dict:
        if action not in {"approve", "reject"}:
            raise HTTPException(status_code=404, detail="Unknown approval action.")
        return await client.decide_approval(approval_id, action, payload)

    @app.post("/api/control/{action}", dependencies=[Depends(_mutation_intent)])
    async def control(
        action: str,
        payload: dict,
    ) -> dict:
        if action not in {"pause", "resume"}:
            raise HTTPException(status_code=404, detail="Unknown control action.")
        allowed = {"scope_type", "scope_key", "reason"}
        if set(payload) != allowed:
            raise HTTPException(status_code=422, detail="Invalid control payload.")
        if not isinstance(payload["reason"], str) or len(payload["reason"]) < 10:
            raise HTTPException(status_code=422, detail="A reason is required.")
        return await client.set_pause(
            paused=action == "pause",
            scope_type=payload["scope_type"],
            scope_key=payload["scope_key"],
            reason=payload["reason"],
        )

    @app.post("/api/knowledge/ingest", dependencies=[Depends(_mutation_intent)])
    async def ingest(payload: KnowledgeIngestRequest) -> dict:
        return store.ingest(
            payload.path, confidentiality=payload.confidentiality
        ).model_dump()

    @app.get("/api/knowledge/search")
    async def search(
        q: Annotated[str, Query(min_length=2, max_length=500)],
        limit: Annotated[int, Query(ge=1, le=50)] = 12,
    ) -> dict:
        return {"query": q, "results": [item.model_dump() for item in store.search(q, limit=limit)]}

    @app.get("/api/knowledge/graph")
    async def graph() -> dict:
        return store.graph().model_dump()

    return app


def _mutation_intent(
    # FastAPI evaluates this annotation on Python 3.9 at runtime.
    value: Annotated[Optional[str], Header(alias="X-Hermes-Intent")] = None,  # noqa: UP045
) -> None:
    if value != "founder-action":
        raise HTTPException(status_code=403, detail="Founder action header required.")
