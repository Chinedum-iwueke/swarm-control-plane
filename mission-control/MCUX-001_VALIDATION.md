# MCUX-001 Validation: User Tasks and Service Blueprint

**Status:** desk-based repository walkthrough complete; moderated user study not run.
**Reviewed:** 2026-10-21
**Scope:** current Mission Control UI, local API routes, control-plane client calls,
and the evidence boundaries visible in the inspected implementation.

## Method and limits

This is an implementation-backed cognitive walkthrough, not a usability study.
The review traced the visible navigation and representative founder/investor
tasks through `static/index.html`, `static/app.js`, `app.py`, and
`control_plane.py`. It records whether each claim has an identifiable source and
whether that source is canonical, derived, cached, inferred, or unavailable.
No first-time founder or investor was recruited, observed, or timed; therefore
there are no user timings or observed-user quotes. These remain a release gate
in MCUX-024.

“Canonical” means a control-plane record or receipt is the authority, not that
the underlying claim is scientifically qualified. A local aggregate, projection,
or UI-derived status is never upgraded to canonical merely because it appears
on screen.

## Current task walkthroughs

| User task | Current route through the UI | Source and classification | Walkthrough result / risk |
|---|---|---|---|
| Establish whether the system is operating and what needs attention | Command / Activity overview | `/api/dashboard` combines control-plane health, tasks, agents, approvals, fleet health, observability, utilization, research activity, execution telemetry and authority. Most records are canonical inputs; the merged dashboard is a **derived, cached** snapshot. Mac presence is **locally asserted** by Mission Control. | Useful operational overview, but a cached aggregate and polling do not prove a process is currently progressing. Source time/freshness is not a uniform contract. Do not narrate “alive now” without a leaf heartbeat/run and freshness evidence. |
| Find what a research campaign is doing and whether a backtest finished | Research / backtest activity | `/api/research/backtests` proxies `/v1/research/alpha-campaigns/backtests/activity`; dashboard embeds the same endpoint. Campaign and task data are **canonical records**; UI categorization/counts are **derived**. BT-009 terminal receipt is the authoritative completion evidence. | A campaign phase or successful engineering task is not proof a native backtest ran. The screen needs explicit leaf-run state and receipt-bound outcome cards (MCUX-005/009). |
| Inspect an agent, its current work, authority and history | Agents / agent cards | `/api/dashboard` combines `/v1/agents`, `/v1/tasks`, package deployments, charters, grants, identities and heartbeats. Those are **canonical inputs**; “current/recent task” association is **derived** from available task/lease state. | Basic identity and scopes are inspectable. A complete paginated history, workflow membership and authoritative reporting line are **unavailable** in the current projection; inferred relationships must not be presented as fact (MCUX-007/008). |
| Locate a book, inspect its content and follow a knowledge relation | Knowledge catalog/search/graph | `/api/knowledge/catalog` gets canonical source metadata from `/v1/research/evidence/objects` and local private metadata from `KnowledgeStore`. `/api/knowledge/search` searches only the local private Markdown/text index and returns excerpts. `/api/knowledge/graph` returns a bounded canonical graph; graph query delegates a typed bounded query. | Titles/metadata and excerpts are available, not a full source reader for canonical corpus text. The graph supports bounded exploration but is not yet a complete source-to-edge provenance workspace. Full text reader is **unavailable** (MCUX-013/014); richer graph tasks remain open (MCUX-015/017). |
| Trace a Bybit demo event and distinguish decision, order, fill and position | Execution / venue replay | Dashboard calls `/v1/execution/overview`. The published execution overview/replay is a **canonical projection/receipt-backed record** with an explicit claim boundary; rendered summaries are **derived**. | This is replay/telemetry, not necessarily a live stream. A replayed/latest publication must not be described as a live order or current feed. Normalized event sequence and venue-confirmed lifecycle need MCUX-010/011. |
| Start or continue a conversation and understand its work | Chat & Work / conversation workspace | `/api/conversations` and `/api/conversations/{id}/workspace` proxy persistent conversation and linked event/task/approval/artifact records. These are **canonical records** as returned; rendered stage summaries are **derived**. | Threads and linked work are inspectable, but there is no durable streaming/event cursor contract in this surface; the UI polls. A queued/running label is not model token streaming. Event replay and truthful progress are MCUX-018/019. |
| Review, approve or cancel an action | Approvals / proposal/task review | `/api/dashboard` sources approval center and pending approvals. Decision mutation routes require `X-Hermes-Intent: founder-action`; approval records and immutable digests are **canonical**. | Approval is an authority-bearing mutation, not a display preference. Review must bind exact digest/scope/expiry and preserve an accessible cancel path. Resend/expiry/recovery remains MCUX-021. |
| Recover from stale, failed or partially unavailable services | Command / Activity and relevant detail views | `/api/dashboard` includes optional endpoints with fallback payloads; control-plane errors may be converted to empty/unavailable-shaped data. These fallback states are **derived/unavailable**, not zero activity. | A fallback empty list can look like “nothing exists” unless availability is visible. Freshness/error provenance is inconsistent; MCUX-003 and MCUX-022 must make unknown, stale and unavailable distinct. |

## Claim-to-source inventory

| Surface | Primary source(s) in current code | Current representation | Classification and boundary |
|---|---|---|---|
| Command | `GET /health`, `/v1/tasks`, `/v1/agents`, `/v1/approval-center`, `/v1/fleet/health`, `/v1/observability/overview`, `/v1/research/alpha-campaigns/backtests/activity` | `/api/dashboard` aggregate | Mixed canonical inputs; aggregate is cached/derived. Locally asserted Mac presence is not remote machine telemetry. |
| Workflows / Missions | `/v1/missions`, `/v1/tasks`, `/v1/research-programs`, `/v1/research-programs/cycles` | Aggregate cards and activity | Canonical source records; workflow stage/leaf association is partly derived. No unified workflow instance contract yet. |
| Agents | `/v1/agents`, `/v1/packages/deployments`, `/v1/agent-governance/charters`, `/v1/agent-governance/grants`, `/v1/workload-identities/overview`, task/heartbeat data | Agent cards and governance details | Canonical inputs; complete history/reporting/workflow membership unavailable or inferred. |
| Research | `/v1/research/alpha-campaigns`, `/v1/research/alpha-discovery/overview`, `/v1/research/alpha-campaigns/backtests/activity`, research datasets, evidence dossiers and lifecycle routes | Campaign, queue, dossier and result views | Canonical records plus derived summaries. “Completed backtest” requires native terminal BT-009 evidence; task success alone is insufficient. |
| Knowledge | `/v1/research/evidence/objects?object_type=source`, `/v1/research/graph/overview`, typed graph query; local `KnowledgeStore` catalog/search | Canonical source metadata, private local excerpts, bounded graph | Metadata/excerpts are available; full canonical source content is unavailable in UI. Private and canonical stores are distinct. |
| Execution | `/v1/execution/overview` | Venue telemetry/replay projection | Canonical published projection and receipts; display is derived. Not an unconditional live-feed claim. |
| Conversations | `/v1/conversations`, `/v1/conversations/{id}/workspace` | Persistent thread plus linked work | Canonical records; stage presentation derived. No streaming guarantee; polling only. |
| Approvals | `/v1/approvals`, `/v1/approval-center` plus approval decision routes | Pending/actionable/blocked/decided records and review dialogs | Canonical authority records. UI must preserve digest, role, scope, expiry and decision reason. |
| Evidence | `/v1/artifacts`, evidence dossier/replay/lifecycle and campaign/backtest terminal records | Artifact lists, dossiers, replay and lifecycle | Canonical artifacts/receipts; summaries derived. Missing evidence must remain unavailable, not be synthesized. |

## Service blueprint summary

| Stage | User action | Frontstage | Backstage / source | Failure signal required |
|---|---|---|---|---|
| Orient | Ask “what is running?” | Command snapshot and attention list | Control-plane aggregate plus per-source freshness | Show snapshot time, source freshness, unavailable inputs, and distinguish active leaf execution from parent campaign state. |
| Inspect | Open workflow, agent or research item | Stage map, owner/agent inspector, research card | Workflow instance, lease/heartbeat, campaign/spec/dataset and terminal receipt | Show exact blocker/next action; missing leaf or terminal receipt cannot be green-completed. |
| Verify | Open evidence or venue event | Receipt, artifact, source reader, replay timeline | Immutable receipt/artifact and venue event IDs | Show provenance and environment; replay is labeled replay; source text unavailable is explicit. |
| Decide | Approve, reject, cancel or request recovery | Digest-bound review dialog and explicit cancel | Approval authority, policy and immutable decision | Expired/used link, missing role, stale digest or unavailable service receives recoverable explanation; no silent no-op. |
| Learn / continue | Continue thread or inspect result | Conversation workbench and retained outcome | Durable ordered thread/task/tool events and BT-009 outcome | Reconnect restores events without duplicates; failure explains whether work continues and where evidence lives. |

## Findings for implementation sequencing

1. MCUX-003/004/005 must precede claims of real-time freshness or synchronized
   workflow progress. The current dashboard is a cached snapshot refreshed in
   the background; visible polling is not a durable event stream.
2. MCUX-007/008 are required before claiming complete agent history, reporting
   structure or workflow membership.
3. MCUX-013/014 are required before claiming the user can read all uploaded
   library text. Current catalog/search does not expose the canonical full text.
4. MCUX-010/011 are required before a venue demonstration can claim a complete
   decision-to-venue-confirmed-fill lifecycle from normalized event evidence.
5. MCUX-018/019 are required before describing Chat & Work as Codex-style live
   streaming progress.
6. Human comprehension, task completion and timing are unmeasured. MCUX-024 is
   an explicit release prerequisite; this desk review is not a substitute.

## Implementation references inspected

- `mission-control/src/hermes_mission_control/app.py`: local HTTP route surface,
  Knowledge APIs, conversation APIs, mutation intent guard and dashboard route.
- `mission-control/src/hermes_mission_control/control_plane.py`: dashboard
  source inventory, cache/refresh behavior, backtest activity, execution
  overview and conversation workspace requests.
- `mission-control/src/hermes_mission_control/static/index.html` and
  `static/app.js`: navigation, rendered interaction and refresh behavior.
- `mission-control/src/hermes_mission_control/knowledge.py` and
  `research_graph.py`: local private index and bounded canonical graph/query
  behavior.
