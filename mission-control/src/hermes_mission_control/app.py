from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
    Request,
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
    ConversationCreateRequest,
    ConversationTransitionRequest,
    ConversationTurnRequest,
    IntakeRequest,
    KnowledgeIngestRequest,
    ProposalDecision,
    ResearchCycleDecision,
)
from .research_copilot import (
    AnswerGenerator,
    CodexAnswerGenerator,
    CopilotError,
    CopilotQuestion,
    ResearchCopilot,
)
from .research_graph import GraphExplorerQuery
from .research_inbox import sync_research_inbox
from .research_upload import (
    ResearchUploadError,
    digest,
    safe_filename,
)

_STATIC = Path(__file__).parent / "static"


def create_app(
    settings: MissionControlSettings,
    *,
    control_plane: ControlPlaneClient | None = None,
    knowledge: KnowledgeStore | None = None,
    copilot_generator: AnswerGenerator | None = None,
) -> FastAPI:
    settings.prepare()
    store = knowledge or KnowledgeStore(
        settings.database_path, settings.allowed_knowledge_roots
    )
    store.initialize()
    client = control_plane or ControlPlaneClient(settings)
    copilot = ResearchCopilot(
        client,
        copilot_generator
        or CodexAnswerGenerator(
            binary=settings.research_codex_binary,
            codex_home=settings.research_codex_home,
            model=settings.research_codex_model,
            timeout_seconds=settings.research_codex_timeout_seconds,
        ),
    )

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

    @app.middleware("http")
    async def prevent_stale_interface_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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

    @app.exception_handler(CopilotError)
    async def copilot_error(_, exc: CopilotError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

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
        result["mission_control"] = {
            "machine": "mac-founder-control",
            "display_name": "Mac",
            "role": "Founder control",
            "presence": "online",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        return result

    @app.post("/api/research/scientific-fidelity/adjudications")
    async def scientific_adjudication(request: Request) -> dict:
        return await client.adjudicate_scientific_representation(await request.json())

    @app.post(
        "/api/research/alpha-discovery/mandates/{mandate_id}/approve",
        dependencies=[Depends(_mutation_intent)],
    )
    async def approve_alpha_mandate(mandate_id: str, request: Request) -> dict:
        return await client.approve_alpha_mandate(mandate_id, await request.json())

    @app.get("/api/research/backtests")
    async def backtest_activity(
        category: Annotated[
            str, Query(pattern="^(all|waiting|running|finished)$")
        ] = "all",
        tier: Annotated[str, Query(pattern="^(all|Tier2A|Tier2B|Tier3)$")] = "all",
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        return await client.backtest_activity(
            category=category, tier=tier, offset=offset
        )

    @app.get("/api/research/scientific-fidelity/review-context/{representation_id}")
    async def scientific_review_context(representation_id: str) -> dict:
        return await client.scientific_review_context(representation_id)

    @app.get("/api/research/dossiers/{dossier_id}")
    async def evidence_dossier(dossier_id: str) -> dict:
        return await client.get_evidence_dossier(dossier_id)

    @app.get("/api/research/dossiers/{dossier_id}/replay")
    async def replay_evidence_dossier(dossier_id: str) -> dict:
        return await client.replay_evidence_dossier(dossier_id)

    @app.get("/api/research/evidence/{object_id}/lifecycle")
    async def evidence_lifecycle(object_id: str) -> dict:
        return await client.get_evidence_lifecycle(object_id)

    @app.post(
        "/api/research/evidence/{object_id}/lifecycle",
        dependencies=[Depends(_mutation_intent)],
    )
    async def transition_evidence_lifecycle(object_id: str, payload: dict) -> dict:
        return await client.transition_evidence_lifecycle(object_id, payload)

    @app.get("/api/research/surveillance/{publication_id}/replay")
    async def replay_surveillance_candidate(publication_id: str) -> dict:
        return await client.replay_surveillance_candidate(publication_id)

    @app.get("/api/conversations")
    async def conversations() -> list[dict]:
        return await client.conversations()

    @app.get("/api/conversations/{conversation_id}/workspace")
    async def conversation_workspace(conversation_id: str) -> dict:
        return await client.conversation_workspace(conversation_id)

    @app.post("/api/conversations", dependencies=[Depends(_mutation_intent)])
    async def new_conversation(payload: ConversationCreateRequest) -> dict:
        return await client.create_conversation(payload.title, payload.message)

    @app.post(
        "/api/conversations/{conversation_id}/turns",
        dependencies=[Depends(_mutation_intent)],
    )
    async def conversation_turn(
        conversation_id: str, payload: ConversationTurnRequest
    ) -> dict:
        return await client.add_conversation_turn(conversation_id, payload.message)

    @app.post(
        "/api/conversations/{conversation_id}/transitions",
        dependencies=[Depends(_mutation_intent)],
    )
    async def conversation_transition(
        conversation_id: str, payload: ConversationTransitionRequest
    ) -> dict:
        return await client.transition_conversation(
            conversation_id, payload.action, payload.reason
        )

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
        "/api/observability/alerts/{alert_id}",
        dependencies=[Depends(_mutation_intent)],
    )
    async def transition_service_alert(alert_id: str, payload: dict) -> dict:
        return await client.transition_service_alert(alert_id, payload)

    @app.post(
        "/api/research/cycles/{cycle_id}/decision",
        dependencies=[Depends(_mutation_intent)],
    )
    async def decide_research_cycle(
        cycle_id: str, payload: ResearchCycleDecision
    ) -> dict:
        return await client.decide_research_cycle(
            cycle_id,
            payload.expected_question_digest,
            payload.decision,
            payload.rationale,
        )

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
        media_type = {
            ".pdf": "application/pdf",
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".txt": "text/plain",
        }.get(Path(filename).suffix.lower())
        if media_type is None:
            raise ResearchUploadError(
                "Only PDF, Markdown, and text sources are accepted."
            )
        content_digest = digest(content)
        source_root = settings.data_root / "research-sources"
        source_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        source_path = source_root / f"{content_digest}-{filename}"
        source_path.write_bytes(content)
        source_path.chmod(0o600)
        job = await client.create_scientific_ingestion(
            {
                "schema_version": "scientific-ingestion-v1.0.0",
                "project": domain,
                "filename": filename,
                "media_type": media_type,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "content_digest": content_digest,
                "access_class": "internal",
                "source": {
                    "title": title,
                    "origin": f"mission-control-upload://{content_digest}/{filename}",
                    "rights": "founder-provided research source",
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                    "edition_label": content_digest[:12],
                },
                "requested_by": "founder-mission-control",
            }
        )
        if job["status"] != "published":
            job = await client.process_scientific_ingestion(job["id"])
        disposition = "canonical" if job["status"] == "published" else "quarantined"
        sync = await client.reconcile_corpus(
            {
                "schema_version": "corpus-sync-v1.0.0",
                "project": domain,
                "source_kind": "founder_inbox",
                "source_root": "mission-control-upload",
                "requested_by": "founder-mission-control",
                "items": [
                    {
                        "source_locator": f"{content_digest}/{filename}",
                        "content_digest": content_digest,
                        "classification": {
                            "document_type": document_type,
                            "evidence_type": evidence_type,
                        },
                        "access_class": "internal",
                        "disposition": disposition,
                        "ingestion_job_id": job["id"],
                    }
                ],
            }
        )
        projection = await client.rebuild_corpus_projections(domain)
        return {
            "document_id": job["published_object_ids"][0]
            if disposition == "canonical"
            else None,
            "document_key": f"canonical-{content_digest[:24]}",
            "content_digest": content_digest,
            "passages": max(0, len(job["published_object_ids"]) - 3),
            "domain": domain,
            "original_retained": True,
            "disposition": disposition,
            "corpus_sync_run_id": sync["id"],
            "projection": projection["evidence"],
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
        return await client.knowledge_graph(limit=100)

    @app.post("/api/knowledge/graph/query")
    async def query_graph(query: GraphExplorerQuery) -> dict:
        return await client.query_knowledge_graph(query.model_dump(mode="json"))

    @app.post("/api/research/copilot/questions")
    async def ask_research_copilot(question: CopilotQuestion) -> dict:
        return await copilot.ask(question)

    @app.get("/api/research/copilot/citations/{object_id}")
    async def replay_research_citation(object_id: str) -> dict:
        return await client.replay_research_citation(object_id)

    return app


def _mutation_intent(
    # FastAPI evaluates this annotation on Python 3.9 at runtime.
    value: Annotated[Optional[str], Header(alias="X-Hermes-Intent")] = None,  # noqa: UP045
) -> None:
    if value != "founder-action":
        raise HTTPException(status_code=403, detail="Founder action header required.")
