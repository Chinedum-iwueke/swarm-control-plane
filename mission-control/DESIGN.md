# Hermes Mission Control Design System

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

Private cited search, source ingestion, and explicit knowledge graph.

### Evidence

Artifacts, reports, logs, hashes, source commits, task provenance, and
verification status.

## Application shell

- Persistent 216px navigation rail on desktop.
- 52px global command bar.
- Flexible main canvas constrained to a readable operational width.
- Persistent 320px attention rail on wide screens.
- Compact mobile tab rail and a single-column content flow below 960px.
- Detail inspector enters from the right without losing list context.

The command view is organized as full-width operational bands. Repeated entities
may use bordered rows. Avoid decorative cards and cards nested inside cards.

## Visual language

### Color

| Token | Value | Use |
| --- | --- | --- |
| `ink` | `#171A19` | Primary text |
| `muted` | `#68716D` | Secondary information |
| `canvas` | `#F4F6F5` | Application background |
| `surface` | `#FFFFFF` | Working surfaces |
| `nav` | `#171B1A` | Navigation and command surfaces |
| `line` | `#D9DFDC` | Dividers and boundaries |
| `blue` | `#2563EB` | Commands and selected state |
| `green` | `#15805D` | Healthy and succeeded |
| `amber` | `#B76A00` | Pending and attention |
| `red` | `#C23832` | Failed, offline, and destructive |
| `cyan` | `#087E8B` | Research and evidence |

No gradient backgrounds, decorative blobs, or ornamental shadows.

### Typography

- Interface: Inter, system UI fallback.
- Technical data: IBM Plex Mono, SFMono fallback.
- Base size: 13px.
- Page titles: 22px.
- Section titles: 13px with strong weight.
- Technical IDs and timestamps use monospace and tabular numerals.
- Letter spacing is always zero.

### Spacing

Use a 4px base unit:

- 4px: tight inline relationship;
- 8px: control and row internals;
- 12px: compact groups;
- 16px: standard panel padding;
- 24px: major sections;
- 32px: page separation.

Operational rows use stable 44px, 52px, or 64px minimum heights.

### Shape and depth

- Radius: 4px for controls, 6px maximum for dialogs and inspectors.
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
- Touch targets are at least 36px.
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

## First prototype scope

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
