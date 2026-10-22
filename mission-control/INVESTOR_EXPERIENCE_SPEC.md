# Mission Control Product and Experience Specification

**Status:** product specification; target behavior is not yet fully implemented.
**Audience:** founder, investors, operators, researchers, and engineers.
**Product:** Hermes Mission Control, the operator-facing window into the Invariance Research system.

**Implementation task breakdown:** [INVESTOR_EXPERIENCE_TASKS.md](INVESTOR_EXPERIENCE_TASKS.md).

## Product Promise

Mission Control must make the real state of the research and trading system understandable without requiring a visitor to read source code, shell logs, or internal runbooks. A user must be able to answer, from the interface:

- What is running now, on which machine, in which workflow, and at what stage?
- What evidence proves that status, and how fresh is it?
- Which agent or service owns the work, what can it do, and what has it done before?
- What is waiting, blocked, failed, stale, or asking for a decision?
- What research question was tested, on what data and window, with which implementation and costs, and what was the terminal result?
- For a demo execution, what exact venue event occurred, where can I verify it in Bybit, and what is explicitly not authorized?
- What does the research library contain, and how do I inspect the source text and its relationships?

Mission Control is an operational product, not a marketing dashboard. It must show negative results and uncertainty as clearly as success. The interface must never make an unverified inference look like a canonical fact or make demo activity look like live trading.

## Current-State Audit

The following is an implementation audit of the current repository, not a statement of future intent.

| Area | Present today | Material gap |
| --- | --- | --- |
| Visual shell | Invariance Research primary logo; white header and navigation; ivory canvas; IBM Plex Sans/Mono and Instrument Serif; compact operational styling. | This is a visual foundation only. It does not make the product's state or evidence complete. |
| Command / Activity | Dashboard snapshot contains tasks, agents, operations, approvals, machine and service summaries. The browser refreshes the dashboard about every 15 seconds while visible. | Not a continuous event stream. A stale snapshot can be mistaken for present state unless freshness is kept prominent. Some machine/service summaries are derived and must be distinguished from direct probes. |
| Workflow visibility | Activity rows show operation title, phase, owner, machine, heartbeat and determinate progress when supplied. Conversation workspaces can show task, proposal, approval, event and artifact timelines. | No unified workflow catalog or end-to-end visual trace spanning discovery, review, engineering, backtest, shadow, demo and terminal publication. |
| Agents | Agent cards show role, machine, heartbeat age, capabilities, active package/charter, grants/scopes and a task inferred from the dashboard task list. | No complete agent detail API/view for durable task history, workflow participation, reporting relationships, tool/model identity, or per-agent event timeline. Reporting lines must not be guessed from names. |
| Research | Research view includes mandate/cycle, discovery, campaigns, signal surveillance, utilization and backtest queue/activity. Backtest activity refreshes about every 15 seconds while the Research view is active. | Broad, dense surface. Queue labels can still confuse task success with a scientific terminal result unless receipt status is shown inline and prominently. |
| Execution / venues | Execution telemetry is a canonical replay projection with venue, environment, pseudonymous account, observed time, status, digests and projection data. Overview is part of the dashboard snapshot. | It is not a live order/fill event tape. No guarantee of venue event latency or direct exchange links. A projected episode must not be presented as an exchange-confirmed event unless the source evidence says so. |
| Knowledge library | Paginated title filtering covers canonical sources and opaque-ID Mac-private Markdown/text sources. The in-page reader retrieves bounded line/page ranges, can load all available stored text, builds structural/page outlines, finds text, deep-links exact citations, preserves list position and compares source identity with parser lineage and uncertainty. Original PDF pages remain unavailable unless an explicitly authorized same-origin page asset is published. | Private local indexing remains Markdown/UTF-8 text. Extracted PDF text is not represented as a facsimile, and no original-page viewer appears when the authorized asset is unavailable. |
| Knowledge graph | Canonical and Mac-private graphs have explicitly separate, bounded APIs. Both support deterministic neighborhood/subgraph/path traversal, query-bound cursor pages, relation/type/direction/depth filters, stable identities, provenance and explicit truncation. Canonical authorization is reapplied by the control plane; private graph facts and identifiers remain local-only. Current UI has an SVG/list view, find, zoom/pan, node selection, neighbors and evidence replay. | Not Obsidian parity. The UI does not yet provide a persistent graph workspace, pinned layouts, polished global/local switching, measured large-graph rendering, saved filters, path emphasis, or a dedicated edge inspector. API readiness is not renderer qualification. |
| Conversations | Threads persist messages/specification and link to proposals, tasks, approvals, events and artifacts. Work view refreshes conversation data about every 10 seconds while open. | It is not a live conversational workspace: no streamed assistant response, explicit tool/agent activity stream, reliable inline progress for every action, or polished recovery for long-running planning. Telegram and Mission Control do not yet feel like one continuous Codex-style thread. |
| Evidence | Artifact and evidence surfaces expose records and provenance in several workflows. | Evidence is scattered across detail routes and list views; the user cannot consistently move from a claim to its source, run, logs, exact code revision and replay. |

**Conclusion:** the current UI is an early operational console with a newly strengthened brand shell. It is not yet an investor-ready, fully observable representation of the whole system. Source reading and bounded graph data contracts now exist, but Obsidian-like graph interaction, complete agent histories/relationships, live venue event observability, and a streaming conversational workbench are not complete.

## Design Method

This work should use product-design methods that expose real user and system problems rather than rely on taste alone:

1. **System and content inventory:** map every page, state, data source, authority boundary, and API contract. Mark fields as canonical, derived, cached, inferred, or unavailable.
2. **Task analysis and service blueprint:** walk real user goals from first click to evidence and recovery. Include backend events, human decisions, notifications, and failure paths, not only the happy-path screens.
3. **Heuristic evaluation:** assess visibility of system status, user control, consistency, error prevention, recognition over recall, and clear recovery. Errors must say what happened and the next safe action.
4. **Task-based usability testing:** test with a founder who did not build the system and with an investor unfamiliar with its internals. Give them realistic tasks and observe where they hesitate or misinterpret state. Do not teach the screen during the test.
5. **Accessibility and responsive audit:** test keyboard, screen reader semantics, contrast, focus, reduced motion, zoom, mobile and desktop. Use automated checks as a floor and manual interaction tests for the actual flows.
6. **Telemetry and performance review:** measure time to first useful status, data freshness, query latency, long-list rendering, graph interactions and failed actions. Track UI errors separately from backend operation failures.

The governing UX principle is visibility of system status: progress must be timely and truthful, particularly for long-running work. Use WCAG 2.2 AA as the baseline, including visible focus and sufficient text/non-text contrast. These are requirements, not polish tasks deferred until after visual styling.

## Experience Principles

### Truth before atmosphere

“Alive” means that real work, fresh heartbeats, event changes and agent activity are visible. It does not mean decorative breathing dots, fake counters, simulated log text, or continuous motion that suggests activity without evidence. Every status has an observed-at time, source, freshness rule and clear stale/unknown state.

### Freshness and provenance contract

Every dashboard projection now includes `provenance` with schema version
`mission-control-provenance-v1`. It identifies the dashboard as a derived
Mission Control projection and supplies its generation time, aggregate
freshness state, threshold, reason and a source entry for each freshness-bearing
control-plane input. A source entry carries `source_identity`, fact class,
threshold, source timestamp, freshness and reason.

`current` means a valid, non-future timestamp is inside the documented source
threshold. `stale` means it is outside that threshold. `unknown` means no valid
timestamp exists, including timestamps in the future. `unavailable` means an
optional endpoint could not supply the projection. `partial` means the aggregate
contains one or more unknown or unavailable required inputs. A successful HTTP
response alone never establishes freshness. Browser connection copy must say
“reachable” until the source freshness is `current`.

### Follow the work, not the database

The top-level information architecture follows what the user is trying to understand: system readiness, work in progress, research outcomes, agents, knowledge, execution and decisions. Internal service names and schema terms remain inspectable in details but do not dominate headings.

### Claims open into evidence

Every consequential claim links to the evidence supporting it: the source object, task/campaign, exact attempt, commit, dataset manifest, time window, costs, logs, report, independent review and terminal receipt. When any link is unavailable, show “not available” with the missing dependency; never manufacture a complete-looking chain.

### Separate signal from authority

Research evidence, operational readiness, approval authority and capital/order authority remain separate dimensions. A successful UI action or task is not a profitability claim. Demo and live are unmistakable environment labels.

### Calm institutional visual language

Continue the Invariance Research identity: full primary logo, white navigation surfaces, ivory main canvas, locally bundled IBM Plex interface/technical typography and Instrument Serif only for restrained page-level editorial emphasis. Use a restrained red brand/selection accent and distinct semantic green, amber, red and blue states. Keep dense data aligned and scannable. Avoid ornamental cards, gradients, glows, oversized heroes and animation used as decoration. Make detail pages feel like instruments, not marketing pages.

## Information Architecture

The navigation should be organized into the following user-facing destinations. Names may be tuned after task testing, but concepts must remain distinct.

1. **Command:** current fleet, system health, actionable attention, active workflows and latest outcomes.
2. **Workflows:** live workflow map, active instances, stages, waits, retries, terminal outcomes and workflow definitions.
3. **Research Lab:** research questions, mandates, hypothesis cards, representation decisions, screenings, backtests by tier, candidate gates and negative-result memory.
4. **Agents:** directory, availability, current assignment, capabilities, history, workflow membership, governance and evidence.
5. **Knowledge:** source library and reader, search, canonical graph, local graph, citations and ingestion/reconstruction quality.
6. **Execution:** shadow/demo/live environment, venues, market/account connectivity, orders, fills, positions, incidents, latency and replay.
7. **Conversations:** Codex-like threads where founder requests, clarifications, plans, tools, progress, results and evidence remain together.
8. **Approvals:** actionable decisions with immutable digest, scope, reason, risk, effect, expiry, blockers and receipt.
9. **Evidence:** searchable artifact/evidence registry with provenance and replay.
10. **Fleet & Services:** machine/service health, resources, deployment identity, heartbeat, SLO and incidents.

The current UI may keep some destinations grouped until their APIs are ready, but should not place all research mechanisms into one indefinitely long page. Deep links must preserve the selected view and entity. Back navigation returns to the prior list and scroll position.

## Screen Specifications

### 1. Command: one-minute operating picture

The first viewport answers whether the system is genuinely operating and what needs attention.

- A compact header reports API connectivity, last successful snapshot/event time and stale/degraded state.
- Machine strip shows each registered machine, role, heartbeat age, CPU/memory/disk where measured, service summary, and source timestamp. Distinguish direct probe from inferred/unknown state.
- Attention queue leads with approvals, stalled/failed workflows, missing/stale telemetry and unresolved incidents. Each item has one contextual next action.
- Live work lane shows workflow instances with current stage, owner/agent, machine, elapsed time, last heartbeat and progress evidence. “Running” without heartbeat freshness is rendered as stale or uncertain.
- Recent outcomes include both positive and negative terminal receipts, not only successes.
- A pause/resume control states its exact scope, whether active tasks drain or stop, and the event/receipt proving the transition.

### 2. Workflow map and instance trace

The purpose is to make the full system legible without reading Book XI first.

- Definitions are drawn as named stages and typed transitions, with human labels plus technical identifiers in detail.
- An instance view highlights completed, current, waiting, blocked, retrying and future stages. Each stage opens its source task/event/evidence.
- Show entry condition, exit condition, owner, expected artifact, timeout/heartbeat rule, retry limit, authority gate and failure destination.
- A timeline and stage map are two synchronized views of the same canonical event sequence. Selecting a stage selects its timeline range and inspector.
- Explicitly distinguish “waiting for founder,” “waiting for worker,” “waiting for data,” “backtest running,” and “terminal result published.” A campaign phase named `campaign` is not evidence that a backtest is currently running.
- History includes superseded, retried, cancelled, invalid, failed and successful paths. Do not hide the failure branch.

### 3. Agent directory and inspector

Agent card is a navigable entry point, not an avatar-only decoration.

**Directory row/card:** display name, role, machine, presence with heartbeat age, active/idle/stale state, current task or “none,” latest task result, and a small capability summary.

**Inspector tabs:**

- **Overview:** identity, role, model/runtime/provider where known, package revision, charter, risk ceiling, permissions/scopes and source of each field.
- **Now:** current lease/task, workflow and stage, start time, last heartbeat, progress, child processes or delegated agents when exposed by canonical events.
- **History:** filterable attempts and terminal outcomes, including failed/rejected/cancelled work; open task events, logs and artifacts.
- **Workflows:** explicit workflow membership and current/recent instances.
- **Governance:** charter, grants, workload identity and granted scopes; secrets are never shown.
- **Relationships:** reporting line/team only when represented by an authoritative relationship. If no reporting relationship is registered, say so rather than infer one from role/name.

Agent presence must be based on heartbeat policy, not merely a running systemd unit or a recent task assignment.

### 4. Research Lab and backtest result cards

Every trial/result card must make it possible to decide what happened without opening a raw JSON report first.

- Question and falsifiable prediction, authorship/proposer and independent reviewer.
- Hypothesis/specification version and digest; native strategy commit and artifact bundle.
- Dataset universe and selected assets, venue, eligibility snapshot, representation/resampling, time range, timezone, splits and point-in-time rules.
- Tier, parameter grid and count of runs, worker allocation and compute usage.
- Gross/net results, realistic costs, stress case, trade count, drawdown, uncertainty intervals, selection-bias and leakage status.
- Gate-by-gate decision with explicit failed/unrun/blocked distinctions.
- Terminal classification: positive, negative, invalid, interrupted or failed engineering; retain all classes.
- Promotion status and exact next gate. “Succeeded” is not a substitute for “scientifically qualified.”

Queue status, running attempts and terminal cards are separate tabs or filters with accurate counts. Count only native terminal BT-009 receipts as completed backtests.

### 5. Knowledge Library and source reader

The library must let users inspect the text actually stored or extracted, not only its title.

- Searchable/paginated catalog with title, document type, source class, project/domain, ingestion state, access class, date, content digest, page/passage count and extraction quality.
- Filters for canonical/private, textbooks/papers/reports, domain, ingestion/review state and format.
- Selecting a source opens a stable reader route. For text, render the complete source with headings/outline, page or line navigation, find-in-document, citation anchors and a visible digest. For PDF sources, show page rendering and extracted text side-by-side when both are retained.
- Label source-original content separately from normalized text, OCR/transcription, parser output, LLM explanation and mathematical verification. Show parser/version, page/region, confidence/uncertainties and adjudication status.
- Canonical source passages navigate to the source reader and exact page/region. Private Mac content remains private; the interface must explain whether content is local-only or canonical.
- Large documents are virtualized/paginated and loaded by range. Never put the full corpus in one API response or browser DOM.
- Access-denied or unavailable source text is explicit. A metadata catalog entry must not imply that the source body is readable.

### 6. Knowledge graph explorer

The current graph should not be described as “like Obsidian” until these interaction requirements pass.

- **Global graph:** filterable overview of allowed nodes and typed edges with a node cap/scale indicator and progressive expansion.
- **Local graph:** open around the selected source/entity; user-controlled depth, direction and relation filters; preserve camera/selection while exploring.
- **Direct manipulation:** zoom, pan, keyboard navigation, select node, drag node, fit selection, reset view, and focus/expand one-hop neighbors.
- **Relationship inspection:** selecting an edge shows predicate, direction, provenance/source, confidence/authority class, creation/version and a link to its evidence. Selecting a node shows summary, source type, content digest, access class and neighbors.
- **Path exploration:** select start and target and show the actual typed evidence path; emphasize the path while muting unrelated edges. “No path found” is a valid result.
- **Search and filters:** title/content/entity search, node type, source/project, relation, evidence status, date and access policy; filters are visible and reversible.
- **Saved views:** persist named query/camera/filter state only as UI state; do not mutate canonical graph facts.
- **Accessible alternative:** synchronized relationship table/list, keyboard operation, selected-node announcement and textual path summary.
- **Scale:** benchmark against the actual expected graph size before selecting the renderer. The initial recommendation is Cytoscape.js for typed graph events, layouts and expected direct interactions. If corpus-scale exploration exceeds its measured interaction budget, evaluate Sigma.js/WebGL for rendering while retaining a graph model/API independent of the renderer. Do not continue adding bespoke SVG gesture code as the graph product grows.

Graph visualization is not graph truth. The backend remains authoritative; local/private and canonical graphs must be explicitly separated in labels and filters.

### 7. Execution and venue observability

For a demo trade walkthrough, the user needs a trace from signal decision to venue-confirmed state.

- Persistent environment badge: `SHADOW`, `DEMO` or `LIVE`, with venue/account pseudonym and permission boundary.
- Event timeline: signal/candidate decision, risk decision, OMS command, venue acknowledgement, amend/cancel, partial/full fill, position update, reconciliation and flatten/kill where present.
- Each event shows venue timestamp and system-observed timestamp, latency, symbol, side, order type, requested/accepted quantity and price, filled quantity/average price, status, correlation/client-order ID and venue order ID when available.
- Clearly distinguish locally requested command, venue acknowledgement, fill, and reconciled position. A command is not a fill.
- Click opens the raw canonical replay projection and evidence digest; copy order ID/account pseudonym; provide an exchange deep link only when a correct environment-specific URL is available and validated.
- Show stale feed, connection loss, duplicate suppression, mismatch and recovery states at the top. Preserve exact events during reconnect and restart reconciliation.
- For the investor demonstration, use a real Bybit demo account event and show the same order ID in the Bybit demo interface. Never present synthetic/demo-mode UI data as a live exchange event.

The current telemetry object is a replay projection. Until an event source and freshness contract are implemented, the interface must call it “latest published replay” rather than “live.”

### 8. Conversations: continuous workbench

The target is a persistent, product-grade thread experience inspired by the interaction pattern the founder requested, not a claim of feature parity with another product.

- Thread list supports search, unread/attention state, active work, archive, rename and resume. A thread is the durable context for one objective, not a dump of unrelated chat messages.
- Conversation canvas presents messages and structured work blocks in one chronological stream. User can continue the thread while seeing current plan, active stage, agent, latest event, elapsed time and next decision.
- Assistant responses stream when the underlying runtime genuinely emits chunks. If work is asynchronous, show “request accepted,” task ID, current stage and poll/event subscription; never show fabricated token streaming.
- Tool/work cards show action, owner, input/output summary, start/end, status and evidence links. Raw logs remain collapsible and redacted.
- Plans are inspectable and editable before materialization when policy allows. Changes update plan digest and approval state visibly.
- Clarification, execution approval, strategy approval and capital/order approval are distinct message types and decision surfaces. Approval state appears in-thread and in the global queue.
- Stop, pause, resume and archive are separate actions. Stopping a thread does not imply stopping a worker unless the exact linked operation is stopped and acknowledged.
- Responses use plain language, cite linked evidence, separate fact from inference, call out stale or missing evidence and say what the system cannot do.
- Telegram and Mission Control should share thread identity and event state. Message IDs and reply relationships must be explicit; expired notification links can be reissued from the thread without duplicating the underlying decision.

Current endpoints return persisted conversation state and linked workspace records. The overview now has a loopback-session-scoped SSE notification stream; it emits bounded non-secret change notices and the browser then refreshes its ordinary authoritative snapshot. Conversation-level streamed work remains a future requirement dependent on persisted conversation event contracts.

### 9. Approvals, authority and evidence

- Approval list separates actionable, blocked, expired, decided and superseded records.
- Decision detail shows action, target, immutable plan/review digest, risk/scope, prerequisites, expected side effects, expiry, accountable actor and current policy.
- Cancel/close is always available, even if reason/acknowledgement fields are incomplete. Invalid submissions show inline correction and never trap the user in a dialog.
- Resending a notification issues a new delivery link only; it must not mutate the approval, create a second task or extend authority unless the canonical workflow explicitly records that effect.
- Evidence inspector shows verification status, source commit, producer identity, workflow version, inputs, artifact hashes, retention class and cross-links.
- Missing or expired authority is a blocked state, never silently bypassed.

## System Feedback and Motion

- Every status has a text label, icon/shape where useful, and freshness/source. Color is supplemental.
- Use event-driven updates for meaningful transitions and modest polling as a documented fallback. Add jitter/backoff and visibility-aware refresh; preserve scroll/focus during refresh.
- Use inline progress for determinate work. For indeterminate stages, show what is waiting on and last observed event, not a fake percentage.
- Motion is limited to state transitions, focus movement and graph navigation. No continuous decorative pulsing. Respect reduced-motion preference.
- Keep list and detail layout stable while data changes. Do not re-render or auto-scroll the user's current view on background refresh.
- Errors are contextual: what failed, whether work may still be running, last known fresh state, safe recovery action and evidence/log link.

## Visual and Interaction System

- Keep the existing white navigation/header and ivory canvas as the base. Build on the just-landed logo, IBM Plex and Instrument Serif assets.
- Primary UI text uses readable sans; monospace is reserved for IDs, digests, values and timestamps; Instrument Serif is used sparingly for major page titles only.
- Keep compact operational rows and aligned numeric columns, but provide deliberate hierarchy. Do not shrink body text below legibility to fit more data; use progressive disclosure, filters and detail inspectors.
- Use semantic tokens for background, surface, border, text, focus, selection, success, warning, error, research and demo/live environment.
- Controls use familiar controls: tabs for modes, filters as selects, checkboxes/toggles for binary states, text buttons for commands and icon buttons only with accessible names and tooltips.
- Target 44px minimum primary touch targets; dense desktop-only data rows may be smaller only when the full control hit area remains usable and keyboard-accessible.
- Meet WCAG 2.2 AA text contrast, visible keyboard focus, logical landmarks/headings, dialog focus management, non-color status cues, zoom/reflow and reduced-motion support.

## Data and API Requirements

The current browser polls one aggregate dashboard snapshot; it cannot derive full activity from code that the API does not expose. Backend/API work is part of the UI project.

### Canonical overview and event feed

The versioned `mission-control-overview-event-v1` local overview stream is implemented as a loopback-session-scoped SSE notification channel. It has numeric IDs, bounded replay, heartbeats, cursor-expiry signaling, deduplication, visibility-aware reconnect and exponential-backoff polling fallback. It deliberately sends only aggregate change notices; the regular provenance-bearing dashboard response remains the authoritative snapshot. Its current operational budget is 128 retained events, 12 subscribers, a 16-event queue per subscriber and 4 KiB payloads. Keep entity projections bounded and paginated. Future entity streams must be idempotently ordered and map to canonical operation/task/agent/execution IDs.

### Workflow instance projection

`mission-control-workflow-projection-v1` is now a read-only local projection
from canonical operation records, campaign records and the receipt-truthful
backtest activity projection. Every instance carries its declared workflow,
current leaf, owner, machine, heartbeat, blockers, retry status, entry/exit
evidence and explicit source event IDs when the underlying record provides
them. A parent campaign may remain active while engineering or review is in
progress; Mission Control calls native Bulletproof execution `running` only
when a matching execute-stage task is actually `running` or `leased`.

The Command surface and the dedicated Workflow view render this one projection
instead of each inferring status independently. The compact Command map makes
active, waiting, stalled and terminal work scannable; selecting an item opens
the Workflow inspector with the current leaf, owner, machine, heartbeat age,
blocker, next action and evidence boundary. This is an operational explanation
surface, not workflow mutation authority.

### Agent detail projection

`mission-control-agent-detail-v1` provides a source-bound inspector contract
for a single agent: identity, active deployment, charter, grants, workload
identity, current lease, bounded canonical assignment history, workflow
membership, artifact/log references and available heartbeat observations. It
excludes credentials, lease tokens, signatures and secret references. An agent
does not acquire a reporting line because another record names an accountable
owner: reporting remains `unknown` until an authoritative relationship record
exists. Likewise, the current control-plane source supplies a latest heartbeat
rather than an invented history series.

### Agent detail projection

Provide a single detail query for agent identity, active deployment/package, charter/grants/scopes, current lease, recent/full paginated history, workflow relationships, heartbeats, logs/artifacts and explicit reporting relationship when registered. Avoid requiring the browser to join arbitrary dashboard slices.

### Knowledge source retrieval

Add read-only source detail/content APIs keyed by canonical object ID or safe private source ID. Enforce access class server-side. Return metadata, page/line ranges, extracted text, original asset references where permitted, parser provenance and digest. Support range/pagination and source-level versioning. Do not accept arbitrary filesystem paths from the browser.

### Graph query

The graph API now expands beyond a fixed overview through bounded,
query-bound cursor pages for neighborhoods, subgraphs and paths. It returns
stable node/edge identities, edge provenance, access class, source replay
references and explicit truncation reasons. Canonical authorization and
filters remain server-side; the private projection executes only in Mission
Control and cannot be mixed with canonical identifiers. Source timestamps are
still supplied through source replay rather than duplicated into every graph
node.

### Venue event projection

Expose normalized append-only order, fill, position, risk and connectivity events with idempotency/correlation IDs, exchange timestamps and source sequence. Link them to the immutable raw event/evidence receipts and reconciled projections. Define stale thresholds per feed and venue; the UI consumes those thresholds rather than inventing its own.

### Conversation work events

Expose queued/planning/clarification/proposal/approval/agent lease/tool start/progress/tool result/terminal event types under the thread. A stream event must be persisted or replayable, with a cursor and deduplication key. Provide a real status while awaiting an LLM/worker; do not block the chat request until a long-running task finishes.

## Investor Demonstration Script

The demo is successful when a visitor can follow one real, auditable chain without engineering narration:

1. Open Command and identify connected machines, current work, one real blocker/attention item and last update time.
2. Open an active research workflow and follow its stages to the currently running or waiting task. Open the responsible agent and see its current assignment, relevant history and permissions.
3. Open a completed backtest card and inspect hypothesis, selected universe, one-year/month window as actually run, parameter budget, cost assumptions, out-of-sample result, failed gates and terminal BT-009 receipt. Do not imply it is profitable if it did not pass.
4. Open the source library, find a source by title, read the full available text/extracted passage and jump to a graph relationship with provenance.
5. Open the conversation that created or advanced the work; inspect clarification, plan, current progress, approval and evidence in one thread.
6. Open a genuine Bybit DEMO event, follow signal/risk/order/fill/reconciliation, copy the venue order ID, and verify that exact order in Bybit's demo interface.
7. State plainly what is not qualified, what is demo-only and what cannot place live orders.

If any step depends on stale data, missing receipt, synthetic content or an unavailable source, the demo must disclose that and route to a clearly labeled prepared evidence artifact. Never stage fake live activity.

## Delivery Plan and Exit Criteria

### Phase A: Demo truth and observability

- Canonical overview freshness/source panel and truthful state labels.
- Workflow instance timeline/stage view backed by actual operation/task events.
- Agent inspector with current task, last heartbeat and recent history.
- Venue replay/event detail that clearly distinguishes published replay from live updates.
- Investor rehearsal for one real demo event and one research result.

**Exit:** a new user correctly identifies current work, its owner, freshness, blocker and evidence in a moderated test; demo event matches the Bybit demo record by order ID; no task success is misread as a qualified backtest.

### Phase B: Knowledge workspace

- Complete catalog navigation, source content reader and citation anchors.
- Canonical/private source distinction, extraction lineage and access-aware display.
- Replace/upgrade bespoke graph renderer with a measured library-backed explorer; add local graph, edge inspector, paths, search, filters and saved view state.

**Exit:** users can locate a title, read available source text, move to an exact citation, inspect its graph edge provenance and return without losing context. Graph interaction is tested against representative corpus size and keyboard/touch use.

### Phase C: Conversational workbench

- Persistent thread list, live/async task status, structured plan and in-thread event/evidence cards.
- Clarification and approval recovery, including expired-link reissue and safe cancellation.
- Shared thread identity across Telegram and Mission Control.

**Exit:** a founder can submit a hypothesis, see what the system understood, answer a clarification, inspect the proposed plan, observe real task progress, receive a terminal result and continue the same thread without shell commands.

### Phase D: Full-system experience and quality

- Dedicated research/agent/fleet/evidence views with progressive disclosure and deep links.
- Accessibility audit, responsive visual QA, performance budgets, resilient reconnect and no-scroll-jump regression tests.
- Research usability sessions, investor rehearsal and support/runbook validation.

**Exit:** all critical investor and founder tasks pass; no open severity-1/2 UI correctness defects; accessible workflows meet WCAG 2.2 AA target; stale/unavailable state is always distinguishable from healthy/current.

## Product Quality Measures

- Time to identify what is running and its owner.
- Time to find the exact evidence behind a research/venue claim.
- Task completion and misinterpretation rate in first-time investor/founder tests.
- Stale-state incidents and status-source mismatches.
- Scroll/focus disruptions during background refresh.
- Successful recovery from expired approval, API interruption and worker restart.
- Graph query, first paint, search and source-reader latency at representative data volumes.
- Accessibility defects and keyboard-only task completion.

Do not optimize for dashboard item count, animated activity, or total “succeeded” tasks. Optimize for accurate understanding, evidence traceability and safe action.

## Reference Methods and Tools

- Nielsen Norman Group, [10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) and [designing for waits and interruptions](https://www.nngroup.com/articles/designing-for-waits-and-interruptions/): status visibility, feedback and recovery for long-running work.
- W3C, [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html): accessibility baseline.
- Obsidian Help, [Graph view](https://obsidian.md/help/Plugins/Graph%2Bview): reference interaction set for global/local graph, hover connections, click-through, zoom/pan and filters. This is a benchmark, not a claim of equivalence.
- [Cytoscape.js documentation](https://js.cytoscape.org/): initial candidate graph toolkit for interaction/event/layout support; validate against our actual graph and accessibility needs before adoption.
- [D3 Zoom](https://d3js.org/d3-zoom): lower-level option for custom visualizations; avoid reimplementing mature graph interactions by hand without a specific reason.

## Decision

This specification defines the target and a realistic route to it. The current application has a useful visual foundation and several operational surfaces, but does **not** yet meet the full library, graph, agent-observability, live-venue or conversational requirements above. Each phase must be implemented and verified against its exit criteria before it is reported as complete.
