from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import MissionControlSettings
from .control_plane import ControlPlaneClient, ControlPlaneError
from .knowledge import KnowledgePolicyError, KnowledgeStore
from .models import (
    ApprovalDecision,
    IntakeRequest,
    KnowledgeIngestRequest,
    ProposalDecision,
)
from .research_inbox import sync_research_inbox
from .research_upload import (
    ResearchUploadError,
    digest,
    extract_passages,
    safe_filename,
)

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

    @app.exception_handler(ResearchUploadError)
    async def upload_error(_, exc: ResearchUploadError):
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
            "research_inbox": str(settings.research_inbox),
        }

    @app.get("/api/dashboard")
    async def dashboard() -> dict:
        result = await client.dashboard()
        result["knowledge"] = store.stats()
        return result

    @app.get("/api/research/dossiers/{dossier_id}")
    async def evidence_dossier(dossier_id: str) -> dict:
        return await client.get_evidence_dossier(dossier_id)

    @app.get("/api/research/dossiers/{dossier_id}/replay")
    async def replay_evidence_dossier(dossier_id: str) -> dict:
        return await client.replay_evidence_dossier(dossier_id)

    @app.post("/api/intake", dependencies=[Depends(_mutation_intent)])
    async def intake(payload: IntakeRequest) -> dict:
        return await client.create_intake(payload)

    @app.post(
        "/api/research/memory-sync/proposals",
        dependencies=[Depends(_mutation_intent)],
    )
    async def propose_research_memory_sync() -> dict:
        return await client.propose_research_memory_sync()

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

    @app.post(
        "/api/missions/{mission_id}/approve",
        dependencies=[Depends(_mutation_intent)],
    )
    async def approve_mission(mission_id: str, payload: ProposalDecision) -> dict:
        return await client.approve_mission(mission_id, payload.reason)

    @app.post(
        "/api/proposals/{proposal_id}/{action}",
        dependencies=[Depends(_mutation_intent)],
    )
    async def decide_proposal(
        proposal_id: str,
        action: str,
        payload: ProposalDecision,
    ) -> dict:
        if action not in {"materialize", "reject"}:
            raise HTTPException(status_code=404, detail="Unknown proposal action.")
        return await client.decide_proposal(proposal_id, action, payload)

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

    @app.post(
        "/api/operational-notes/{note_id}/transitions",
        dependencies=[Depends(_mutation_intent)],
    )
    async def transition_operational_note(note_id: str, payload: dict) -> dict:
        action = payload.get("action")
        reason = payload.get("reason")
        if action not in {"assign", "defer", "resolve", "reopen"}:
            raise HTTPException(status_code=422, detail="Invalid note action.")
        if not isinstance(reason, str) or len(reason) < 10:
            raise HTTPException(
                status_code=422, detail="A decision reason is required."
            )
        return await client.transition_operational_note(note_id, payload)

    @app.post(
        "/api/operational-notes/{note_id}/proposal-request",
        dependencies=[Depends(_mutation_intent)],
    )
    async def request_operational_note_proposal(note_id: str, payload: dict) -> dict:
        if set(payload) != {"objective"}:
            raise HTTPException(status_code=422, detail="Invalid proposal request.")
        objective = payload["objective"]
        if not isinstance(objective, str) or len(objective) < 10:
            raise HTTPException(status_code=422, detail="An objective is required.")
        return await client.request_operational_note_proposal(note_id, objective)

    @app.post("/api/knowledge/ingest", dependencies=[Depends(_mutation_intent)])
    async def ingest(payload: KnowledgeIngestRequest) -> dict:
        return store.ingest(
            payload.path, confidentiality=payload.confidentiality
        ).model_dump()

    @app.post("/api/research/sources/upload", dependencies=[Depends(_mutation_intent)])
    async def upload_research_source(
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form(min_length=3, max_length=300)],
        domain: Annotated[str, Form(pattern=r"^[a-z0-9][a-z0-9_-]{1,149}$")],
        document_type: Annotated[
            str, Form(pattern=r"^(textbook|paper|prior_report|prd)$")
        ],
        evidence_type: Annotated[
            str,
            Form(
                pattern=r"^(method|empirical_evidence|prior_result|governing_requirement)$"
            ),
        ],
    ) -> dict:
        filename = safe_filename(file.filename or "")
        content = await file.read(settings.upload_max_bytes + 1)
        if len(content) > settings.upload_max_bytes:
            raise ResearchUploadError("The source exceeds the configured upload limit.")
        content_digest = digest(content)
        passages = extract_passages(filename, content)
        source_root = settings.data_root / "research-sources"
        source_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        source_path = source_root / f"{content_digest}-{filename}"
        source_path.write_bytes(content)
        source_path.chmod(0o600)
        document_key = f"upload-{content_digest[:24]}"
        document_payload = {
            "document_key": document_key,
            "title": title,
            "document_type": document_type,
            "evidence_type": evidence_type,
            "version": content_digest[:12],
            "source_uri": f"mission-control-upload://{content_digest}/{filename}",
            "content_digest": content_digest,
            "metadata": {"domains": [domain], "original_filename": filename},
            "ingested_by": "founder-mission-control",
        }
        bundle = await client.register_research_bundle(
            {
                "document": document_payload,
                "chunks": [
                    {
                        "ordinal": passage.ordinal,
                        "section": passage.section,
                        "page": passage.page,
                        "line_start": passage.line_start,
                        "line_end": passage.line_end,
                        "text": passage.text,
                        "text_digest": digest(passage.text.encode()),
                        "metadata": {"domain": domain},
                    }
                    for passage in passages
                ],
            }
        )
        document = bundle["document"]
        return {
            "document_id": document["id"],
            "document_key": document_key,
            "content_digest": content_digest,
            "passages": len(passages),
            "domain": domain,
            "original_retained": True,
        }

    @app.post("/api/research/inbox/sync", dependencies=[Depends(_mutation_intent)])
    async def sync_inbox() -> dict:
        return await sync_research_inbox(settings, client)

    @app.get("/api/knowledge/search")
    async def search(
        q: Annotated[str, Query(min_length=2, max_length=500)],
        limit: Annotated[int, Query(ge=1, le=50)] = 12,
    ) -> dict:
        return {
            "query": q,
            "results": [item.model_dump() for item in store.search(q, limit=limit)],
        }

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
