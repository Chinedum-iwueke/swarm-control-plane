from __future__ import annotations

import asyncio
import base64
import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

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
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent_detail import project_agent_detail
from .config import MissionControlSettings
from .control_plane import ControlPlaneClient, ControlPlaneError
from .freshness import build_snapshot_provenance
from .investor_walkthrough import (
    WalkthroughJournal,
    project_investor_walkthrough,
)
from .knowledge import KnowledgePolicyError, KnowledgeStore, LocalGraphQueryError
from .models import (
    ApprovalDecision,
    ConversationCreateRequest,
    ConversationTransitionRequest,
    ConversationTurnRequest,
    IntakeRequest,
    KnowledgeIngestRequest,
    ProposalDecision,
    ResearchCycleDecision,
    WalkthroughObservation,
    WalkthroughSessionCreate,
    WalkthroughSessionFinish,
)
from .overview_events import (
    EVENT_SCHEMA_VERSION,
    OverviewEvent,
    OverviewEventBroker,
    SubscriberLimitExceeded,
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
from .source_content import SourceContentError, canonical_source_content
from .workflow_projection import project_workflows

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
    browser_event_session = secrets.token_urlsafe(32)
    walkthrough_journal = WalkthroughJournal(
        settings.data_root / "investor-walkthrough-sessions.json"
    )

    async def load_overview_snapshot() -> dict:
        return await client.dashboard(refresh=True)

    overview_events = OverviewEventBroker(
        load_overview_snapshot,
        poll_seconds=settings.overview_event_poll_seconds,
        heartbeat_seconds=settings.overview_event_heartbeat_seconds,
        replay_capacity=settings.overview_event_replay_capacity,
        max_subscribers=settings.overview_event_max_subscribers,
        max_payload_bytes=settings.overview_event_payload_max_bytes,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        warm_dashboard = getattr(client, "warm_dashboard", None)
        if warm_dashboard is not None:
            warm_dashboard()
        await overview_events.start()
        try:
            yield
        finally:
            await overview_events.stop()
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
    app.state.overview_events = overview_events
    app.state.walkthrough_journal = walkthrough_journal
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.exception_handler(ControlPlaneError)
    async def control_error(_, exc: ControlPlaneError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(KnowledgePolicyError)
    async def knowledge_error(_, exc: KnowledgePolicyError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(LocalGraphQueryError)
    async def local_graph_error(_, exc: LocalGraphQueryError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc)}
        )

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
        response = FileResponse(_STATIC / "index.html")
        # This HttpOnly value is only a same-origin, loopback browser-session check.
        # Control-plane credentials never enter the browser or an event payload.
        response.set_cookie(
            "hermes_overview_session",
            browser_event_session,
            httponly=True,
            samesite="strict",
            max_age=86_400,
        )
        return response

    @app.get("/api/status")
    async def status() -> dict:
        return {
            "service": "Hermes Mission Control",
            "scope": "loopback-only",
            "knowledge": store.stats(),
            "research_inbox": str(settings.research_inbox),
        }

    @app.get("/api/dashboard")
    async def dashboard(refresh: bool = False) -> dict:
        result = await client.dashboard(refresh=refresh)
        if not isinstance(result.get("provenance"), dict):
            result["provenance"] = build_snapshot_provenance(result).model_dump(
                mode="json"
            )
        observed_at = datetime.now(timezone.utc).isoformat()
        result["knowledge"] = store.stats()
        result["mission_control"] = {
            "machine": "mac-founder-control",
            "display_name": "Mac",
            "role": "Founder control",
            "presence": "online",
            "observed_at": observed_at,
        }
        provenance = result.get("provenance")
        if isinstance(provenance, dict):
            provenance.setdefault("sources", {})["mission_control"] = {
                "source_key": "mission_control",
                "source_identity": "mission-control/local-process",
                "fact_class": "derived",
                "freshness": "current",
                "freshness_threshold_seconds": 45,
                "source_timestamp": observed_at,
                "reason": "locally_observed_process",
            }
        return result

    @app.get("/api/overview/events", include_in_schema=False)
    async def overview_event_stream(
        request: Request,
        cursor: str | None = Query(default=None, max_length=32),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        session = request.cookies.get("hermes_overview_session", "")
        if not secrets.compare_digest(session, browser_event_session):
            raise HTTPException(
                status_code=401, detail="Local overview session required."
            )
        requested_cursor = last_event_id or cursor
        try:
            subscription = await overview_events.subscribe(requested_cursor)
        except SubscriberLimitExceeded as exc:
            raise HTTPException(
                status_code=503, detail="Overview stream at capacity."
            ) from exc

        async def stream() -> AsyncIterator[str]:
            try:
                yield "retry: 2000\n\n"
                if subscription.cursor_state is not None:
                    yield _sse_frame(
                        "overview.cursor_expired",
                        None,
                        {
                            "schema_version": EVENT_SCHEMA_VERSION,
                            "reason": f"cursor_{subscription.cursor_state}",
                            "snapshot_required": True,
                        },
                    )
                for event in subscription.replay:
                    yield _sse_event_frame(event)
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(
                            subscription.queue.get(),
                            timeout=overview_events.heartbeat_seconds,
                        )
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
                        continue
                    if not isinstance(event, OverviewEvent):
                        return
                    yield _sse_event_frame(event)
            finally:
                await overview_events.unsubscribe(subscription)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/tasks/{task_id}")
    async def task_detail(task_id: str) -> dict:
        return await client.task_detail(task_id)

    @app.get("/api/agents/{agent_id}/detail")
    async def agent_detail(
        agent_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> dict:
        snapshot, history = await asyncio.gather(
            client.dashboard(), client.agent_tasks(agent_id, offset=offset, limit=limit)
        )
        result = project_agent_detail(
            snapshot, agent_id, history, offset=offset, limit=limit
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        return result

    @app.get("/api/workflows")
    async def workflows(refresh: bool = False) -> dict:
        return project_workflows(await client.dashboard(refresh=refresh))

    async def load_investor_walkthrough(*, refresh: bool = False) -> dict:
        snapshot, venue_history = await asyncio.gather(
            client.dashboard(refresh=refresh),
            client.venue_event_history(environment="demo", venue="bybit"),
        )
        return project_investor_walkthrough(
            snapshot,
            project_workflows(snapshot),
            venue_history,
        )

    @app.get("/api/investor-walkthrough")
    async def investor_walkthrough(refresh: bool = False) -> dict:
        return await load_investor_walkthrough(refresh=refresh)

    @app.get("/api/investor-walkthrough/sessions")
    async def investor_walkthrough_sessions(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict:
        return {
            "schema_version": "mission-control-investor-rehearsal-journal-v1",
            "sessions": walkthrough_journal.recent(limit),
        }

    @app.post("/api/investor-walkthrough/sessions")
    async def start_investor_walkthrough(
        body: WalkthroughSessionCreate,
    ) -> dict:
        current = await load_investor_walkthrough()
        if (
            body.walkthrough_digest != current["walkthrough_digest"]
            or body.ready_steps != current["ready_steps"]
            or body.total_steps != current["total_steps"]
        ):
            raise HTTPException(
                status_code=409,
                detail="The walkthrough evidence changed. Refresh before rehearsing.",
            )
        return walkthrough_journal.start(
            body.walkthrough_digest,
            body.ready_steps,
            body.total_steps,
        )

    @app.post("/api/investor-walkthrough/sessions/{session_id}/observations")
    async def record_investor_walkthrough_observation(
        session_id: str,
        body: WalkthroughObservation,
    ) -> dict:
        try:
            return walkthrough_journal.observe(session_id, body.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Rehearsal session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/investor-walkthrough/sessions/{session_id}/finish")
    async def finish_investor_walkthrough(
        session_id: str,
        body: WalkthroughSessionFinish,
    ) -> dict:
        try:
            return walkthrough_journal.finish(
                session_id,
                status=body.status,
                elapsed_ms=body.elapsed_ms,
                summary=body.summary,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Rehearsal session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/research/scientific-fidelity/adjudications")
    async def scientific_adjudication(request: Request) -> dict:
        return await client.adjudicate_scientific_representation(await request.json())

    @app.post(
        "/api/research/alpha-discovery/mandates/{mandate_id}/approve",
        dependencies=[Depends(_mutation_intent)],
    )
    async def approve_alpha_mandate(mandate_id: str, request: Request) -> dict:
        return await client.approve_alpha_mandate(mandate_id, await request.json())

    @app.post(
        "/api/codex-auth/recoveries/{recovery_id}/retry",
        dependencies=[Depends(_mutation_intent)],
    )
    async def retry_codex_auth(recovery_id: str, request: Request) -> dict:
        return await client.retry_codex_auth(recovery_id, await request.json())

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

    @app.get("/api/execution/events")
    async def venue_event_history(
        environment: Annotated[
            str | None, Query(pattern="^(shadow|demo|live)$")
        ] = None,
        venue: Annotated[str | None, Query(pattern="^(binance|bybit)$")] = None,
        replay_id: Annotated[str | None, Query()] = None,
    ) -> dict:
        return await client.venue_event_history(
            environment=environment,
            venue=venue,
            replay_id=replay_id,
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
        "/api/tasks/{task_id}/resend-approval",
        dependencies=[Depends(_mutation_intent)],
    )
    async def resend_approval(task_id: str, payload: ProposalDecision) -> dict:
        return await client.resend_approval(task_id, payload.reason)

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

    @app.get("/api/knowledge/catalog")
    async def knowledge_catalog(
        q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        kind: Annotated[str, Query(pattern=r"^(all|canonical|private)$")] = "all",
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> dict:
        catalog_error = None
        try:
            canonical = await client.knowledge_catalog(limit=500)
        except ControlPlaneError as error:
            canonical = {"items": []}
            catalog_error = str(error)
        sources = []
        for item in canonical.get("items", []):
            payload = item.get("payload") or {}
            if item.get("object_type") != "source" or not payload.get("title"):
                continue
            sources.append(
                {
                    "id": item.get("object_id"),
                    "title": payload["title"],
                    "project": item.get("project"),
                    "origin": payload.get("origin"),
                    "content_digest": item.get("content_digest"),
                    "created_at": item.get("created_at"),
                    "access_class": item.get("access_class"),
                    "kind": "canonical",
                }
            )
        private_sources = store.catalog()
        combined = [
            *({**item, "catalog_kind": "canonical"} for item in sources),
            *({**item, "catalog_kind": "private"} for item in private_sources),
        ]
        normalized_query = (q or "").casefold().strip()
        if kind != "all":
            combined = [item for item in combined if item["catalog_kind"] == kind]
        if normalized_query:
            combined = [
                item
                for item in combined
                if normalized_query
                in " ".join(
                    str(item.get(key) or "")
                    for key in ("title", "project", "origin", "confidentiality")
                ).casefold()
            ]
        combined.sort(
            key=lambda item: (
                str(item.get("title") or "").casefold(),
                item["catalog_kind"],
                str(item.get("id") or ""),
            )
        )
        total = len(combined)
        page = combined[offset : offset + limit]
        return {
            "canonical": [item for item in page if item["catalog_kind"] == "canonical"],
            "private": [item for item in page if item["catalog_kind"] == "private"],
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more": offset + len(page) < total,
            },
            "counts": {
                "canonical": len(sources),
                "private": len(private_sources),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "canonical_error": catalog_error,
        }

    @app.get("/api/knowledge/sources/private/{opaque_id}/content")
    async def private_source_content(
        request: Request,
        opaque_id: Annotated[str, ApiPath(pattern=r"^[A-Za-z0-9_-]{20,64}$")],
        start: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> dict:
        _require_source_query_keys(request, {"start", "limit"})
        result = store.source_content(opaque_id, start=start, limit=limit)
        if result is None:
            raise HTTPException(status_code=404, detail="Private source not found.")
        return result

    @app.get("/api/knowledge/sources/canonical/{object_id}/content")
    async def canonical_content(
        request: Request,
        object_id: UUID,
        unit: Annotated[str, Query(pattern=r"^(line|page)$")] = "line",
        start: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> dict:
        _require_source_query_keys(request, {"unit", "start", "limit"})
        if unit == "page" and limit > 20:
            raise HTTPException(status_code=422, detail="Page ranges are limited to 20.")
        try:
            return await canonical_source_content(
                client, str(object_id), unit=unit, start=start, limit=limit
            )
        except SourceContentError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/knowledge/graph")
    async def graph(
        scope: Annotated[str, Query(pattern=r"^(canonical|private)$")] = "canonical",
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        cursor: Annotated[str | None, Query(min_length=8, max_length=512)] = None,
    ) -> dict:
        if scope == "private":
            return store.graph_overview(limit=limit, cursor=cursor)
        if cursor is not None:
            raise HTTPException(
                status_code=422,
                detail="Canonical overview cursors require a rooted graph query.",
            )
        result = await client.knowledge_graph(limit=limit)
        return {
            **result,
            "scope": "canonical",
            "authorization": {
                "boundary": "control-plane-evidence-access",
                "mixed_scope_allowed": False,
            },
        }

    @app.post("/api/knowledge/graph/query")
    async def query_graph(query: GraphExplorerQuery) -> dict:
        if query.scope == "private":
            return store.query_graph(query.model_dump(mode="json", exclude_none=True))
        result = await client.query_knowledge_graph(query.canonical_payload())
        return {
            **result,
            "scope": "canonical",
            "authorization": {
                "boundary": "control-plane-evidence-access",
                "mixed_scope_allowed": False,
            },
        }

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


def _require_source_query_keys(request: Request, allowed: set[str]) -> None:
    unknown = set(request.query_params) - allowed
    if unknown:
        raise HTTPException(status_code=422, detail="Unsupported source query parameter.")


def _sse_event_frame(event: OverviewEvent) -> str:
    return _sse_frame(event.event, event.event_id, event.data)


def _sse_frame(event: str, event_id: int | None, data: dict) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"
