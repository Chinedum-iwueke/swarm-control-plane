# Hermes Swarm Delivery Plan

**Organization:** Invariance Research  
**Document status:** Proposed execution plan  
**Planning baseline:** Phase 1 validated  
**Last updated:** 2026-07-30

## 1. Objective

The next objective is to turn the validated control-plane and VM1 worker kernel
into a useful, continuously operating swarm.

The swarm must support:

- founder prompts from VM1, VM2, and the Mac;
- continued engineering against approved PRDs and milestones while the founder
  is away;
- approved VM2 infrastructure runbooks;
- Mac knowledge, research-intelligence, and second-brain capabilities;
- research and experiment execution;
- centralized status, evidence, approvals, and interruption.

The platform must become reusable before the agent catalog becomes large.

## 2. Core Operating Decision

### 2.1 Prompt everywhere, author on VM1

Each machine may expose a Hermes prompt and supervision interface. That does
not mean each machine receives unrestricted coding authority.

```text
Mac prompt -----\
VM2 prompt ------> Control Plane -> Engineering Mission -> VM1 code workers
VM1 prompt -----/
```

All source-authoring tasks execute in isolated VM1 worktrees. VM2 and the Mac
may request, inspect, approve, and consume engineering work, but they do not
edit Hermes or product source locally.

This preserves:

```text
VM1 -> GitHub -> VM2 pull
               -> Mac pull
```

### 2.2 Execute machine-local responsibilities locally

Some work must run on the machine that owns the resource:

- VM2 infrastructure operations execute on VM2;
- Mac knowledge ingestion and founder workflows execute on the Mac;
- VM1 engineering and research workloads execute on VM1.

Machine-local execution uses reviewed workflows and machine-specific
credentials. It does not turn task prompts into shell commands.

### 2.3 Autonomous missions are bounded

"Continue while I am away" means:

- continue an approved milestone;
- select the next ready task from a dependency graph;
- work within repository, branch, risk, cost, and time limits;
- stop at approval, ambiguity, repeated failure, exhausted budget, or milestone
  completion;
- preserve evidence and notify the founder.

It does not mean an agent invents its own roadmap, merges unreviewed work,
changes production, or expands its permissions.

## 3. Minimum Early Agent Set

The following agents create the smallest useful swarm.

| Agent | Execution machine | Primary responsibility | Early mode |
| --- | --- | --- | --- |
| Founder Mission Controller | Mac-facing, control-plane service | prompt intake, task status, approvals, pause/resume | supervised |
| Engineering Mission Planner | VM1 | convert approved PRDs/milestones into task DAGs | propose, then auto-plan low-risk work |
| Repository Coding Worker | VM1 | implement one bounded engineering task in a worktree | branch and commit only |
| Code Validation Worker | VM1 | compile, lint, test, and verify evidence | already validated |
| Code Review Worker | VM1 | independent correctness/security review | read-only review |
| VM2 Infrastructure Operator | VM2 | execute approved infrastructure runbooks | inspect first, gated mutation later |
| VM2 Health and Backup Verifier | VM2 | health checks, backup evidence, restore-test scheduling | read-only/low-risk |
| Mac Knowledge Steward | Mac | ingest, normalize, index, and govern founder knowledge | local and private |
| Mac Research Intelligence Agent | Mac | answer sourced questions and produce research briefs | read/search first |
| Research Mission Planner | VM1 | translate research PRDs into experiments | propose |
| Research Execution Worker | VM1 | run allowlisted research and simulation workflows | isolated execution |
| Research Auditor | VM1 | bias, robustness, reproducibility, and evidence review | independent review |

Do not begin with one "coder agent" identity shared across all machines. Use one
worker framework with separate identities, tokens, policies, and execution
locations.

## 4. Platform Primitives Required First

The current worker can execute one validated task. Unattended missions and
high-risk infrastructure require additional control-plane primitives.

### 4.1 Workflow package registry

Every deployable role must be described by a versioned package:

```text
role-package/
  manifest.yaml
  task-contract.schema.json
  workflows/
  policies/
  permissions/
  evidence.schema.json
  tests/
  runbook.md
  rollback.md
```

The control plane records:

- package name and immutable version;
- source repository and commit;
- compatible worker versions;
- task types and schemas;
- required capabilities;
- allowed machines and repositories;
- risk class and approval policy;
- evidence and rollback contract.

Workers still load local reviewed definitions. The registry proves which
version was deployed and executed.

### 4.2 Agent and permission profiles

Separate the following concepts:

- **identity:** who is executing;
- **capabilities:** what task classes it can accept;
- **permission profile:** which host resources and privileged operations it can
  use;
- **workflow allowlist:** which reviewed procedures it can run;
- **repository profile:** which repositories and paths it can read/write;
- **risk ceiling:** which tasks it may run without further approval.

Capability discovery should report deployed package versions and health, not
accept arbitrary capabilities from task input.

### 4.3 Approval engine

Approval must become a first-class state rather than free-form JSON.

Minimum model:

- requested operation and immutable plan digest;
- risk level;
- approver identity;
- approved scope and parameters;
- issue and expiry times;
- one-time execution nonce;
- approval, rejection, expiry, revocation, and consumption events.

Changing a plan or parameter invalidates its approval.

### 4.4 Scheduler and task dependencies

Add:

- `not_before` and optional deadline;
- recurring schedule definition;
- dependency edges and milestone grouping;
- blocked/ready projections;
- retry policy with bounded backoff;
- dead-letter terminal state;
- concurrency keys for exclusive resources;
- per-agent and per-project concurrency limits;
- mission cost/time/task budgets.

PostgreSQL remains the authority. Redis may provide wakeups and ephemeral
transport, but it must not become the only task record.

### 4.5 Artifact and evidence registry

Register:

- type, size, digest, producer, task, attempt, workflow version, and commit;
- local/object-storage location;
- confidentiality and retention class;
- creation and expiry;
- verification status.

Large artifacts belong in object storage. PostgreSQL stores manifests,
provenance, state, and integrity metadata.

### 4.6 Operator API and pause controls

The founder needs:

- create mission from approved project/milestone;
- inspect task graph and evidence;
- approve/reject;
- pause globally, by machine, project, agent, or mission;
- cancel queued work;
- request graceful stop of running work;
- retry or dead-letter with a recorded operator reason;
- rotate/revoke agent credentials;
- inspect health and stale workers.

## 5. VM2 Infrastructure Operator

### 5.1 Responsibility

The VM2 Infrastructure Operator executes approved, version-controlled runbooks
covering:

- PostgreSQL and PgBouncer;
- Redis;
- Docker and Compose;
- storage and capacity;
- backups and restore verification;
- certificates;
- service health;
- controlled restarts;
- infrastructure verification.

It never writes application source and never converts arbitrary prompt text
into shell execution.

### 5.2 Runbook ingestion model

A Markdown runbook is source material, not executable authority. VM1 converts
it into reviewed operations with typed parameters.

The referenced
[`ON_PREM_POSTGRES_RUNBOOK.md`](https://github.com/Chinedum-iwueke/invariance_research/blob/main/deploy/ON_PREM_POSTGRES_RUNBOOK.md)
defines a broad production lifecycle: hardened Docker Postgres, PgBouncer,
TLS, role separation, firewall policy, schema bootstrap, cutover, backup,
restore, monitoring, and disaster recovery. The runbook explicitly treats
PostgreSQL as operational truth and places large artifacts in object storage
rather than the database.

It must be decomposed into small operations such as:

| Operation | Default risk | Automatic? | Evidence |
| --- | --- | --- | --- |
| inspect service/container health | 0 | yes | status, versions, health output |
| inspect disk and backup freshness | 0 | yes | capacity and backup manifest |
| verify TLS certificate dates/mode | 0 | yes | certificate metadata |
| create logical backup | 1 | yes when policy permits | digest, size, duration, destination |
| verify backup integrity | 1 | yes | restore/list verification result |
| restart one unhealthy service | 3 | approval required | plan, pre/post health, logs |
| renew/deploy certificate | 3 | approval required | old/new fingerprints, expiry |
| apply reviewed Compose change | 3 | approval required | diff digest, pull/build, health |
| database schema migration | 4 | approval required | migration ID, backup, checks |
| firewall change | 4 | approval required | exact rule diff and connectivity proof |
| restore production backup | 5 | dual confirmation | backup digest, target, recovery evidence |
| destructive storage/database action | 5 | disabled by default | exceptional break-glass procedure |

Risk levels are policy defaults and must be ratified in the approval design.

### 5.3 Operation contract

Example task:

```json
{
  "task_type": "infrastructure_operation",
  "input_contract": {
    "runbook": "on-prem-postgres",
    "runbook_version": "git-sha-or-release",
    "operation": "verify-backup",
    "target": "vm2-postgres-primary",
    "parameters": {
      "backup_id": "registered-artifact-id"
    }
  },
  "allowed_machines": ["vm2-deployment"],
  "required_capabilities": [
    "postgres-operations",
    "backup-verification"
  ],
  "risk_level": 1
}
```

No command, secret, environment value, filesystem path, host, port, image tag,
or Compose file may be supplied unless the operation schema explicitly types
and validates it.

### 5.4 Privilege architecture

The worker service must remain unprivileged and must not run `sudo`.

Privileged operations use a separate root-owned execution broker:

1. the worker submits an approved operation ID and exact typed parameters;
2. the broker reloads the immutable workflow/package definition;
3. it validates approval digest, machine, expiry, nonce, and parameter schema;
4. it runs only the corresponding root-owned argument-array operation;
5. it returns bounded status and stores complete root-side evidence;
6. it consumes the approval nonce.

Suitable implementations include a narrowly scoped root systemd service/socket
or equivalent broker. Do not grant the worker Docker-group membership as a
shortcut; Docker access is effectively root authority.

### 5.5 Execution transaction

Every mutating operation follows:

```text
inspect
  -> produce immutable plan
  -> classify risk
  -> approve when required
  -> capture pre-state
  -> ensure rollback/backup
  -> execute exact reviewed operation
  -> verify health and invariants
  -> register evidence
  -> complete or enter incident state
```

Failure does not trigger speculative repair. The operator either executes a
reviewed rollback operation or stops for human intervention.

### 5.6 Infrastructure Operator rollout gates

1. **Observer:** health, versions, capacity, backup freshness, certificate
   expiry.
2. **Verifier:** backup creation/integrity and non-mutating configuration
   verification.
3. **Controlled operator:** approved restart and certificate deployment.
4. **Deployment operator:** approved reviewed Compose releases and rollback.
5. **Database operator:** approved migrations and restore drills.
6. **Infrastructure operator:** narrowly approved storage/network changes.

Production restore, firewall mutation, and destructive operations are never the
first rollout stage.

## 6. Engineering Mission System

### 6.1 Goal

Engineering work should continue against accepted PRDs and milestones without
requiring the founder to prompt every implementation step.

### 6.2 Project manifests

Each development repository should contain or reference:

```text
docs/
  PRD.md
  ARCHITECTURE.md
  MILESTONES.yaml
  DECISIONS/
  RUNBOOKS/
```

`MILESTONES.yaml` is structured and version-controlled. Each milestone records:

- immutable ID and objective;
- source PRD/decision references;
- dependencies;
- acceptance criteria;
- allowed repositories and optional path boundaries;
- validation commands/workflows;
- risk and approval policy;
- deliverables and evidence;
- stop/escalation conditions.

The agent does not treat prose PRDs as permission to implement anything it can
imagine. The accepted milestone manifest defines executable scope.

### 6.3 Engineering mission lifecycle

```text
Founder approves milestone
  -> Planner proposes task DAG
  -> policy/schema validation
  -> ready task leased to VM1 coder
  -> isolated branch/worktree implementation
  -> validation worker
  -> independent review worker
  -> fix loop within budget
  -> PR or review bundle
  -> merge approval/policy
  -> next dependency becomes ready
  -> milestone acceptance
```

### 6.4 Coding-worker policy

The coding worker may:

- read the selected repository and linked design context;
- edit only its isolated worktree;
- create a task branch;
- run approved local development and validation tools;
- produce commits, patches, tests, documentation, and evidence;
- open a PR when GitHub integration is approved.

It may not:

- edit primary checkouts;
- access production credentials;
- deploy;
- merge its own changes;
- modify protected branches directly;
- weaken tests, policy, or security controls to make a task pass;
- expand repository scope without a new task;
- continue after lease loss or budget exhaustion.

### 6.5 Access to all development projects

Use one framework, not one omnipotent credential.

Create project profiles for:

- `swarm-control-plane`;
- `invariance_research`;
- `bulletproof_bt`;
- future approved repositories.

An engineering planner may see the milestone status of all projects. A coding
attempt receives access only to the repository or explicitly declared
multi-repository set required by that task. Cross-repository work must identify
all commits and preserve independent validation.

### 6.6 Unattended continuation

The scheduler may continue when:

- the milestone is approved and active;
- a dependency-free task exists;
- risk is within the auto-execution ceiling;
- budgets remain;
- the worker and required repository are healthy;
- the preceding task passed validation/review;
- no pause, incident, or approval gate is active.

It stops when:

- requirements are ambiguous;
- acceptance criteria conflict;
- the same failure repeats;
- tests reveal a design issue outside task scope;
- review finds a high-severity issue;
- a secret, deployment, migration, or infrastructure decision is required;
- time, token, cost, task-count, or attempt budget is exhausted;
- no ready task remains.

## 7. Prompt and Supervision Surfaces

### 7.1 One control-plane conversation model

Prompts become one of:

- question: read-only answer from registered evidence/knowledge;
- task request: one bounded task;
- mission request: approved milestone execution;
- infrastructure request: reviewed runbook operation;
- approval decision;
- control command: pause, resume, cancel, inspect, retry.

The system returns a proposed structured contract before any mutating or
high-risk action.

### 7.2 VM1 interface

Engineering console for:

- designs and PRDs;
- mission creation;
- repository and milestone status;
- diffs, tests, review findings, and PRs;
- worker/package development.

### 7.3 VM2 interface

Operations console for:

- infrastructure health;
- pending runbook plans and approvals;
- deployments, backups, certificates, incidents, and rollback;
- worker and control-plane health.

It may request engineering changes, but those requests execute on VM1.

### 7.4 Mac interface

Founder Mission Control for:

- natural-language task/mission intake;
- portfolio view across projects;
- approvals and pause controls;
- worker, research, deployment, and infrastructure status;
- evidence and artifact browsing;
- alerts and executive reports;
- knowledge and research-intelligence queries.

## 8. Mac Knowledge and Second-Brain Platform

### 8.1 Separation of concerns

The Mac hosts knowledge data and founder interaction. Software for the Mac
platform is still developed and validated on VM1, promoted through Git, and
pulled/deployed to the Mac.

### 8.2 Knowledge Steward

Responsibilities:

- ingest approved local documents, repositories, notes, research, and business
  sources;
- preserve original source, checksum, timestamps, ownership, and access class;
- normalize and deduplicate;
- extract entities, projects, people, organizations, decisions, claims, dates,
  tasks, and citations;
- maintain embeddings/search index and knowledge graph;
- detect stale/conflicting assertions;
- support deletion and re-indexing.

It does not silently rewrite source documents.

### 8.3 Research Intelligence Agent

Responsibilities:

- answer with citations and evidence dates;
- compare claims across sources;
- build dossiers, timelines, literature maps, and decision briefs;
- distinguish source fact, model inference, and open question;
- register reusable research artifacts;
- hand engineering or research proposals to the control plane.

### 8.4 Minimum data model

- source;
- document/version;
- chunk;
- entity;
- relationship;
- claim;
- citation;
- project;
- decision;
- task/milestone link;
- confidentiality and retention labels;
- ingestion and transformation provenance.

### 8.5 Privacy boundary

Local/private knowledge does not automatically enter cloud prompts or worker
tasks. Every connector and model route declares:

- data classes it may read;
- where content is processed;
- what is retained;
- which machine owns the resulting index/artifact;
- whether the founder approved external transmission.

## 9. Research Swarm

Research agents should follow the engineering mission pattern:

```text
Research PRD
  -> research program
  -> hypothesis
  -> experiment specification
  -> isolated execution
  -> robustness and bias audit
  -> artifact registration
  -> review
  -> accepted/rejected finding
```

Early roles:

1. Research Mission Planner
2. Data/Feature Preparation Worker
3. Bulletproof/Experiment Runner
4. Robustness and Selection-Bias Auditor
5. Research Reporting Agent

Later roles include meta-labelling, regime detection, portfolio construction,
cost/execution simulation, shadow trading, and performance attribution.

No research agent promotes a strategy into live execution. That requires a
separate governance and approval design.

## 10. Delivery Waves

### Wave 0: operate the validated kernel

- supervise the VM1 daemon;
- add worker/control-plane health metrics and alerts;
- record worker version in evidence;
- define workspace retention;
- verify backup and restore of control-plane PostgreSQL;
- establish global and per-machine pause procedures.

**Exit:** the current worker can run continuously and fail safely without
requiring terminal babysitting.

### Wave 1: mission and policy foundation

- workflow package/version registry;
- permission and agent profiles;
- approval engine;
- scheduler, dependencies, budgets, retries, and dead-letter state;
- artifact/evidence registry;
- operator API and pause/cancel controls;
- minimal founder task/approval console.

**Exit:** the control plane can safely coordinate a multi-step bounded mission.

### Wave 2A: engineering swarm

- project and milestone manifests;
- Engineering Mission Planner;
- restricted coding executor and Git branch/commit lifecycle;
- independent validation and review agents;
- GitHub PR integration;
- unattended ready-task progression.

**Exit:** one approved milestone in one repository progresses from plan to
review-ready PR without founder step-by-step prompting.

### Wave 2B: VM2 Infrastructure Operator

Develop in parallel with Wave 2A after approval/package foundations exist:

- import the PostgreSQL runbook as typed operations;
- deploy VM2 observer and health/backup verifier;
- implement privileged execution broker;
- test all operations against a disposable environment;
- run backup and restore drills;
- enable approved controlled restart;
- later enable reviewed Compose deployment and rollback.

**Exit:** the founder can prompt "verify PostgreSQL backups" and receive
auditable evidence; an approved restart can execute with pre/post checks and no
arbitrary command path.

### Wave 3: Mac Mission Control and knowledge

- founder dashboard;
- approval center and alerts;
- project/milestone/worker views;
- evidence and artifact browser;
- Knowledge Steward ingestion pipeline;
- cited search and Research Intelligence Agent.

**Exit:** the Mac is the daily control and knowledge surface without becoming a
source-authoring or production host.

### Wave 4: research swarm

- research program and experiment schemas;
- Bulletproof and experiment workflow packages;
- dataset/artifact provenance;
- research planner, executor, auditor, and reporter;
- research dashboard.

**Exit:** one accepted research program progresses reproducibly from hypothesis
to audited report.

### Wave 5: production and business expansion

- deployment, monitoring, backup, database, security, certificate, and
  container-lifecycle roles;
- executive reporting, Invictus, business operations, meetings, proposals, and
  knowledge-base workflows;
- cross-project portfolio reporting.

**Exit:** new roles are introduced through reviewed packages and configuration,
not architectural exceptions.

## 11. Risk and Approval Matrix

| Risk | Example | Default handling |
| --- | --- | --- |
| 0 | inspect, search, compile, read-only health | automatic |
| 1 | tests, local branch edits, backups, research experiments | automatic within mission budget |
| 2 | PR creation, dependency update, large compute/cost | policy or lightweight approval |
| 3 | restart, deployment, certificate installation | explicit time-bounded approval |
| 4 | migration, firewall/network, credential rotation | explicit approval plus rollback proof |
| 5 | restore over production, destructive storage/database action | dual confirmation or break-glass only |

An agent cannot lower a task's risk classification. The control plane may raise
it based on operation, target, data class, blast radius, or policy.

## 12. Initial Milestones

### M1: Continuous control and visibility

- VM1 daemon supervised;
- worker/control-plane metrics;
- pause/stop controls;
- worker-version evidence;
- retention and control-plane backup runbook.

**Source status:** complete on `feat/restricted-vm1-worker`. Operational
completion requires migration/API deployment on VM2, worker package/service
deployment on VM1, Prometheus rule installation, and one supervised
pause/metrics/backup validation.

### M2: Versioned role packages

- package schema;
- workflow registry;
- agent/permission profiles;
- deployment inventory;
- compatibility and signature/digest checks.

**Source status:** complete on `feat/restricted-vm1-worker`. Operational
completion requires migration/API deployment, protected signing-secret
installation, package registration, agent binding, and a supervised attestation
check.

### M3: Approvals and artifacts

- approval state machine;
- plan digest and one-time nonce;
- artifact registry and storage interface;
- operator inspection endpoints.

**Source status:** complete on `feat/restricted-vm1-worker`. Operational
completion requires migration/API and worker deployment plus supervised
approval-consumption, rejection, reapproval, and artifact-digest validation.

### M4: Engineering mission pilot

- milestone manifest;
- planner;
- coding worker;
- validation/review;
- PR bundle;
- unattended progression for one low-risk milestone.

**Source status:** complete on `feat/restricted-vm1-worker`. Operational
completion requires migration and role-package deployment, a dedicated coding
credential, and the supervised no-push pilot in the M4 runbook.

### M5: VM2 Infrastructure Observer

- PostgreSQL/Redis/Docker/storage/certificate health;
- backup freshness and integrity;
- no mutation;
- dashboard/evidence integration.

**Status:** operationally complete. The API ticket secret, VM2 broker and
worker, package binding, and supervised read-only observation were validated.
The evidence digest is recorded in `docs/m5-m6-validation.md`.

### M6: VM2 Controlled Operator

- privileged broker;
- approval consumption;
- restart transaction;
- pre/post verification;
- disposable-environment tests and rollback drill.

**Status:** operationally complete for the first narrow operation. An explicit
approval was bound to the task plan, consumed once at lease, and used for a
supervised control-plane API restart with successful pre/post health checks.
The continuous worker remains disabled; evidence is recorded in
`docs/m5-m6-validation.md`.

### M7: Mac Mission Control and knowledge pilot

- prompt/task intake;
- approvals;
- status and evidence;
- first private document corpus;
- cited search and knowledge graph.

**Status:** operationally complete for the bounded Mac pilot. Mission Control
is installed loopback-only, private cited retrieval and explicit graph
relationships were validated, and one structured founder request remained
ineligible for all deployed workers. Evidence and limitations are recorded in
`docs/m7-validation.md`.

### M8: Research mission pilot

- research program schema;
- one Bulletproof/experiment package;
- planner/executor/auditor;
- reproducible evidence and report.

## 13. Definition of Functional Swarm

Hermes is operationally functional when:

- prompts from any machine become structured control-plane requests;
- all coding work executes on VM1 from approved milestones;
- one engineering mission can continue unattended to a review gate;
- VM2 can run read-only infrastructure verification and an approved controlled
  operation;
- the Mac provides mission status, approvals, alerts, and cited knowledge;
- every task records agent, machine, workflow/package version, commit, evidence,
  and terminal outcome;
- pause and lease-loss behavior stops work safely;
- no agent can deploy, mutate infrastructure, merge, or expose private data
  outside its explicit policy.
