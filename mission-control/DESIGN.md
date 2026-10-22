# Hermes Mission Control Design System

> **Status note:** this file defines the visual and interaction foundation, not
> proof that every described product capability is implemented. The current
> implementation gaps and full target behavior are tracked in
> [INVESTOR_EXPERIENCE_SPEC.md](INVESTOR_EXPERIENCE_SPEC.md). In particular, a
> Obsidian-parity graph workspace, full agent history and
> reporting relationships, a live venue event stream, and a streaming
> conversational workbench are not yet complete.

## Product promise

Hermes Mission Control lets the founder understand and safely direct the
company system from one screen.

Every primary view must answer:

1. What needs my decision?
2. What is executing now?
3. What is unhealthy, blocked, or late?
4. What changed recently?
5. What actions are safe and available?

Mission Control is an operational application, not a reporting dashboard.
Information, decisions, evidence, and governed actions belong in the same
workflow.

## Design principles

### Attention before totals

The founder's queue is persistent. Approvals, failures, blocked work, and
offline machines appear before aggregate counts. Metrics provide orientation;
they do not become the page.

### Authority is visible

Every action shows its risk level, scope, and current control state. High-impact
actions require an explicit reason. The interface never makes a production
operation look as casual as opening a task.

### Evidence stays attached

Tasks, experiments, deployments, and infrastructure operations link directly to
their source commit, agent, event history, logs, reports, and hashes. Completed
work remains inspectable.

### Density with hierarchy

Hermes is used repeatedly by one operator. Prefer compact rows, stable columns,
consistent inspectors, and strong alignment. Use whitespace to separate levels
of meaning rather than turning every section into a floating card.

### Calm until something matters

Neutral surfaces dominate. Green, amber, red, blue, and cyan are reserved for
meaningful states. Color always accompanies a label or symbol.

## Information architecture

### Command

The company operating picture:

- system readiness across VM1, VM2, and Mac;
- founder attention queue;
- active objectives and task flow;
- worker fleet state;
- latest research, infrastructure, and engineering evidence;
- control-plane restrictions.

### Missions

Strategic objectives, milestone progress, dependent tasks, current risk, and
latest evidence.

### Tasks

Filterable execution ledger across queued, leased, running, approval, terminal,
and retry states.

### Approvals

Decision queue with scope, risk, planned effect, expiry, and approve/reject
actions.

### Agents

Machine, role, capabilities, risk ceiling, presence, and current assignment.

### Infrastructure

VM2 service health, backup evidence, controlled operations, and production
restrictions.

### Research

Research programs, hypotheses, experiment verdicts, audit checks, evidence
digests, and promotion gates.

### Knowledge

Paginated canonical/private source catalog, access-aware full-text reader,
citation anchors, extraction quality and provenance, private cited search,
source ingestion, and explicitly separated canonical/private knowledge graphs.
Graph traversal uses bounded query-bound cursor pages, stable identities,
filters, edge provenance and explicit truncation reasons; canonical access is
rechecked by the control plane while private traversal remains local-only.
Original PDF pages render only when the API grants a same-origin page asset;
extracted text is always labeled. The richer graph workspace and renderer are
tracked separately and are not implied by the API contract.

### Evidence

Artifacts, reports, logs, hashes, source commits, task provenance, and
verification status.

## Application shell

- Persistent 232px navigation rail on desktop.
- 64px global command bar.
- Flexible main canvas capped at 1560px with 28-32px desktop inset.
- Persistent 320px attention rail on wide screens.
- Collapsible mobile navigation and a single-column content flow at 960px;
  compact toolbar/row layouts apply at 680px and 620px.
- Detail inspector enters from the right without losing list context.

The command view is organized as full-width operational bands. Repeated entities
may use bordered rows. Avoid decorative cards and cards nested inside cards.

## Visual language

### Color

| Token | Value | Use |
| --- | --- | --- |
| `--ink` | `#1A1817` | Primary text |
| `--muted` | `#56504C` | Secondary information |
| `--quiet` | `#756E69` | Tertiary labels |
| `--canvas` | `#FBFAF7` | Ivory application background |
| `--surface`, `--nav` | `#FFFFFF` | Working surfaces and white navigation |
| `--nav-soft` | `#F4F1EC` | Selected/soft navigation surface |
| `--line`, `--line-soft` | `#DED8D1`, `#EEE9E3` | Boundaries and subtle dividers |
| `--accent` | `#B00020` | Invariance red commands and selection |
| `--accent-hover` | `#8F001A` | Hover state for primary command |
| `--green` / `--green-soft` | `#24734D` / `#E7F2EC` | Healthy/succeeded state and its surface |
| `--amber` / `--amber-soft` | `#805000` / `#F8EEDC` | Pending/attention state and its surface |
| `--red` / `--red-soft` | `#B00020` / `#F7E8EB` | Failed/offline/destructive state and its surface |
| `--cyan` / `--cyan-soft` | `#235A97` / `#E8EFF6` | Research/evidence state and its surface |

The red brand accent is not blue. `--blue` remains a compatibility alias for
older component rules; new rules use `--accent`. `--danger` aliases `--red`.
Status always pairs color with text and, where present, a symbol.

No gradient backgrounds, decorative blobs, or ornamental shadows.

### Typography

- Interface: bundled IBM Plex Sans, with Inter/system fallbacks.
- Technical data: bundled IBM Plex Mono, with SFMono/Consolas fallbacks.
- Display headings: bundled Instrument Serif, with system serif fallbacks.
- Base size: 13px; dense metadata may use 9-11px and must remain secondary.
- Page titles: 30px Instrument Serif; section titles: 13px IBM Plex Sans bold.
- Technical IDs and timestamps use monospace and tabular numerals.
- Letter spacing is always zero.

### Spacing

Use the CSS spacing tokens on a 4px base unit:

- `--space-1` / 4px: tight inline relationship;
- `--space-2` / 8px: control and row internals;
- `--space-3` / 12px: compact groups;
- `--space-4` / 16px: standard panel padding;
- `--space-6` / 24px: major sections;
- `--space-8` / 32px: page separation.

Operational rows use stable 44px, 52px, or 64px minimum heights.

### Shape and depth

- `--radius-control`: 4px; `--radius-panel`: 6px maximum for dialogs and
  inspectors; `--radius-pill`: compact state metadata only.
- Borders create structure.
- Shadows appear only on overlays.
- Status pills may be fully rounded because they are compact metadata.

## Components

### Status badge

Contains a state dot and a plain-language label. It must never rely on color
alone.

### Attention item

Shows severity, entity, reason, age, and one clear next action. The rail orders
items by urgency: critical, approval, blocked, stale, informational.

### Entity row

Stable columns, primary label, technical identifier, state, owner or agent,
updated time, and an affordance to open the inspector.

### Inspector

Uses tabs for Summary, Timeline, Evidence, and Contract. Mutating actions sit in
a fixed footer and include their risk classification.

### Approval decision

Shows requested action, target, risk, plan digest, expected effect, and expiry.
Approval and rejection require a reason before submission.

### Metric

Metrics are compact inline cells within a band. They include a label, value, and
optional trend or qualifying context.

### Empty and degraded states

Empty states state the condition and available action. When the control plane is
unavailable, the shell remains visible, identifies stale data, and offers
reconnect or explicit demonstration mode.

## Motion

- 120-180ms transitions for selection, drawers, and status updates.
- No looping decoration.
- Respect `prefers-reduced-motion`.
- Loading retains layout dimensions to prevent movement.

## Accessibility

- WCAG AA contrast minimum.
- Complete keyboard navigation.
- Visible `:focus-visible` treatment.
- Semantic tables, headings, forms, and dialogs.
- Icon-only buttons require accessible names and tooltips.
- Primary decision controls are at least 44px; dense desktop navigation and
  secondary controls currently use 34-36px minimums and are a documented gap
  for touch-first responsive qualification.
- Status and risk always include text.

## Safety requirements

- The orchestrator token never reaches browser code.
- Browser mutations retain the founder-intent header.
- Task intake remains structured and cannot include commands.
- Destructive or production-impacting actions require explicit confirmation and
  a bounded reason.
- Demo data is labeled and never mixed with live control-plane state.
- Research findings visibly retain their production-eligibility gate.
- Raw secrets, authorization headers, and lease tokens are never rendered.

## Prototype scope (design target, not a completion claim)

The first high-fidelity prototype implements:

- redesigned application shell and command view;
- live attention queue;
- missions and task ledger;
- approval workflow;
- agent and machine views;
- infrastructure and research summaries derived from tasks;
- evidence registry;
- private knowledge explorer;
- entity inspector;
- global search and keyboard shortcut;
- representative M8 demonstration mode.

Later releases can add dedicated mission, event, infrastructure-health, and
research-program APIs without redesigning the shell.
