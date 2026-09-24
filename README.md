# Hermes Swarm Control Plane

Hermes is the governed operating layer for Invariance Research. It coordinates
specialized agents, human approvals, research evidence, quantitative work, and
machine operations across the founder workstation and four Linux hosts.

This repository is the **control and evidence plane**. It does not implement a
second backtesting or trading engine. Quantitative computation belongs to
[`bulletproof_bt`](https://github.com/Chinedum-iwueke/bulletproof_bt); Hermes
selects and authorizes bounded work, records provenance, routes independent
review, and retains the resulting immutable receipts.

## North Star

The system is being built to run a continuous, evidence-grounded research loop:

1. observe literature, prior results, market data, execution degradation, and
   portfolio gaps;
2. form predictive and falsifiable hypotheses;
3. choose point-in-time eligible instruments and causal data representations;
4. compile bounded native Bulletproof experiments;
5. test, falsify, and independently evaluate them;
6. retain positive, negative, invalid, and failed outcomes;
7. promote only qualified candidates into prospective shadow monitoring;
8. expose capital only through separate deterministic risk and founder gates;
9. feed every result back into institutional memory and the next research cycle.

Autonomy here means continuous bounded work with evidence and recovery, not an
agent granting itself more data, code, risk, order, or capital authority.

## Repository Ownership

| Surface | Authoritative owner | Responsibility |
| --- | --- | --- |
| Governance and authority | Hermes | Decision rights, delegations, approvals, lifecycle state, audit chains |
| Agent runtime | Hermes | Charters, grants, workload identities, packages, leases, heartbeats, retries |
| Research orchestration | Hermes | Mandates, discovery portfolios, hypothesis intake, reviewer routing, campaign state |
| Institutional evidence | Hermes | Ingestion, citations, retrieval, graph projections, provenance, adjudication |
| Quantitative research | Bulletproof | Data panels, transformations, strategies, grids, backtests, ML/RL evaluation |
| Execution and risk computation | Bulletproof | Market/order events, OMS, venue adapters, calibration, deterministic risk, replay |
| Operational presentation | Mission Control | Founder command, approvals, fleet health, research, backtests, venue replay |
| Restricted founder channel | Telegram gateway | Conversation, notifications, digest-bound approval handoffs |

Hermes registries may validate and replay Bulletproof receipts. They must not
quietly reproduce Bulletproof's analytics or claim quantitative authority from
control-plane fixtures.

## Fleet Topology

| Machine identity | Current role | Explicit boundary |
| --- | --- | --- |
| `mac-founder-control` | Loopback-only Mission Control, founder intake, approvals, private research inbox | No unattended worker or venue execution |
| `vm1-developer` | Source development, Research Intelligence agents, data-representation work, Bulletproof lake and bounded compute | No production control-plane ownership or live venue role |
| `vm2-deployment` | FastAPI control plane, PostgreSQL, Redis, directors, Telegram gateway, backups and observability | Pulls reviewed code; does not originate quantitative results |
| `exec1-execution` | Independent fleet observer and watchdog | US egress is venue-restricted; no venue credentials or orders |
| `exec2-lagos` | Nigerian venue-facing demo host and intended micro-live host | No control-plane database, research lake, or self-authorized trading |

Management traffic uses the private Tailscale network. Venue traffic is kept on
the dedicated eligible execution host. Loss of `exec2-lagos` freezes execution;
it does not fail over to VM1 or VM2.

## What Is Implemented

The repository currently contains:

- a FastAPI control plane backed by PostgreSQL and Redis;
- task graphs, leases, attempts, heartbeats, bounded retries, cancellation, and
  recovery receipts;
- agent charters, capability grants, workload identities, package manifests,
  delegation records, and independent evaluator routing;
- append-only governance, policy, lifecycle, and quantitative receipt evidence;
- research ingestion, corpus search, knowledge graph projections, curricula,
  scientific representations, and derived-state freshness orchestration;
- continuous ALPHA discovery, data admission, strategy engineering, review,
  capacity scheduling, campaign execution, publication, and negative-result
  retention;
- typed outcome-blind multi-asset representation plans whose causal transforms are
  compiled by Bulletproof and bound to the exact strategy fields that consume them;
- platform, research, fleet, execution, risk, portfolio, shadow, demo, and venue
  telemetry registries;
- a restricted Telegram founder gateway and a Mac-local Mission Control app;
- VM1/VM2/EXEC1/EXEC2 systemd installers, fleet probes, backup jobs, and recovery
  runbooks.

The Bybit demo and canonical venue-replay paths have produced retained
certification/publication evidence. That evidence proves operational behavior,
not profitability and not live capital authority.

## Current Qualification Boundary

The platform can run real-data, no-capital research and preserve complete
evidence. It must still be described honestly:

- no strategy is profitable merely because the loop or demo path works;
- a research result cannot admit itself to shadow or live trading;
- whole-corpus equation/table fidelity is not assumed; equation-dependent work
  requires deterministic or genuinely independent assurance;
- institutional reasoning is evaluated through RI-015 evidence rather than
  inferred from fluent model output;
- `LIVE-001` remains blocked until a genuine candidate survives the registered
  out-of-sample, cost, leakage, drawdown, reproducibility, shadow, operational,
  and environment-specific live gates;
- live credentials must remain trade-only, withdrawal-disabled, IP-restricted,
  environment-specific, and outside Git.

## Main Components

```text
backend/           FastAPI API, database models, migrations, services, registries
worker/            Restricted agents, planners, directors, executors, systemd units
mission-control/   Mac-local founder application and operational views
telegram-gateway/  Restricted Telegram conversation and approval channel
schemas/           Shared machine-verifiable contracts
docs/              Validation records, architecture notes, and operator runbooks
ops/               Deployment and operational support assets
```

Start with:

- [System design](docs/hermes-swarm-system-design.md)
- [Delivery plan](docs/hermes-swarm-delivery-plan.md)
- [Mission Control](mission-control/README.md)
- [Real-data alpha campaign](docs/runbooks/alpha-001-real-data-campaign.md)
- [Scientific executor](docs/runbooks/alpha-002-scientific-executor.md)
- [EXEC2 Lagos bootstrap](docs/runbooks/exec2-lagos-host-bootstrap.md)
- [LLM runtime register](docs/book-xi-llm-runtime-register.md)

Some older milestone documents describe the system at the time they were
written. Validation records are historical evidence, not a substitute for
current service health or a fresh production receipt.

## Development

Use isolated virtual environments for each component. A typical backend check
is:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
POSTGRES_PASSWORD_FILE=/etc/hostname \
  .venv/bin/pytest -q tests
```

Worker, Mission Control, and Telegram tests have their own dependency files and
should be run from their component directories. Production rollout is always
performed from a reviewed Git revision with the relevant runbook; do not treat
local test success as deployment evidence.

## Machine-Verifiable Baseline

The read-only `implementation-baseline-v1` collector records the Git pin and
dirty state, sanitized origin, runtime versions, dependency state, tracked
schema hashes, declared acceptance commands, and controlled claim vocabulary.
It does not read credentials, ignored files, or raw datasets.

```bash
python worker/scripts/implementation_baseline.py collect \
  --repository . \
  --output /tmp/swarm-control-plane-baseline.json
python worker/scripts/implementation_baseline.py validate \
  /tmp/swarm-control-plane-baseline.json
```

Collection fails closed on a dirty worktree. `--allow-dirty` records affected
paths for audits but does not create a release-quality baseline. The schema is
[`schemas/implementation-baseline-v1.schema.json`](schemas/implementation-baseline-v1.schema.json).

## Security

Never commit operator tokens, workload tokens, model credentials, venue keys,
private source documents, or production environment files. Structured task
input is data, not shell authority. Any workflow that can mutate infrastructure,
code, shadow state, orders, or capital must bind the exact digest, actor,
prerequisites, expiry, and allowed effect before execution.
