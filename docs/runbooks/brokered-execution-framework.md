# Brokered Execution Framework

Hermes handles complex operational requests as signed mission manifests. A
mission is a dependency-ordered set of typed phases, not a generated shell
script.

## Trust boundaries

- Founder intake may interpret plain English, but it has no execution authority.
- Mission Control and Telegram show the exact plan digest and collect decisions.
- The control plane creates one task and approval record per phase.
- Workers lease only tasks matching their signed role package and capabilities.
- The root broker accepts short-lived HMAC tickets for compiled operation names.
- Broker operations use fixed argument arrays and internally rendered templates.
- Sudo passwords, bearer tokens, private keys, and database passwords never enter
  prompts, Telegram messages, task payloads, results, or logs.

## Execution lifecycle

1. Parse a request into a strict mission schema.
2. Validate operation names, targets, risk levels, dependencies, and budgets.
3. Sign and store the canonical manifest.
4. Materialize phase tasks and dependency edges.
5. Create explicit approvals for mutating phases.
6. Lease only approved phases whose dependencies succeeded.
7. Issue a short-lived, plan-bound broker ticket.
8. Execute one compiled broker primitive.
9. Register bounded evidence and its SHA-256 digest.
10. Continue to the next dependency or block the mission on failure.

Approving a mission defines its structure. It does not preapprove every
privileged phase. Risk 2 and risk 3 phases require separate decisions for their
exact task plan digests.

## Generalization

The mission engine, approval system, dependency scheduler, broker tickets,
evidence, and recovery behavior are shared across runbooks. New operational
capability is added as a reviewed primitive with:

- a strict parameter model;
- a fixed risk and approval policy;
- a fixed machine and target class;
- explicit preconditions and stop conditions;
- bounded evidence;
- idempotency or replay protection;
- a tested rollback path where mutation occurs.

Arbitrary commands, uploaded scripts, task-provided executable paths, and sudo
password forwarding are outside the design.

## First workflow

`worker/missions/vm2-postgres-rollout.yaml` is the first infrastructure mission.
It covers preflight, staging, private startup, schema initialization, backup and
restore validation, private verification, and cutover-readiness checks.

The public cutover is intentionally a readiness gate until trusted PgBouncer
client TLS, DNS ownership, Vercel configuration access, source database export,
and rollback inputs are available. Readiness failure blocks the mission without
weakening network policy.
