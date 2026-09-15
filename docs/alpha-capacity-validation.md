# Native capacity-loop validation

2026-09-15: local source validation, production activation pending.

- Existing Bulletproof global capacity scheduler reused; ALPHA execution now has
  a typed native queue adapter and bounded spawned classic-engine variant pool.
- Resource estimates no longer understate requested workers. Startup reservations,
  CPU headroom/load, RAM hysteresis, exclusive leadership, orphan reservations,
  exact repository dispatch, assignment integrity, dead-owner rejection, duplicate
  refusal and already-launched pending children are covered.
- Native focused suite: 32 passed, including real classic-engine serial/parallel
  parity on two variants and 230 trades per variant; the additional shared-budget
  two-job launch test also passes (seven admission tests in the final focused rerun).
  CSV header order differs under spawned process hash ordering, but every named
  trade/equity field compares exactly, without float tolerances or dropped columns.
- Full worker suite: 276 passed. Backend discovery/conversation tests: 14 passed.
- Shell syntax and systemd unit verification passed; systemd reports unrelated
  existing snapd/netplan warnings. Ruff verification is part of final local checks.
- VM1 sampled 36 CPUs, 71 GiB total and 64 GiB available RAM. This is a point-in-time
  observation, not a guaranteed performance or calibrated memory requirement.
- No production services or credentials were changed, no backtests were queued,
  and no orders or capital actions occurred. Two-job live replay and BT-009 terminal
  publication remain required before operational closure.

See [activation runbook](runbooks/alpha-capacity-governed-execution.md).
# Activation recovery correction (2026-09-15)

Live slot-2 registration stopped at charter creation: its charter bytes duplicated
slot 1 and the registry enforces global digest uniqueness. Slot 2 exists without
a charter. Bootstrap now names the executor slot in its responsibility and
supports explicit `--recover-registration`, validating the existing agent and
deployment before reuse. Lost slot-2 credentials are replaced through scoped
workload rotation, saved mode 0600, then finalized; slot 1 is untouched.
Regression tests cover refusal of implicit recovery and successful scoped recovery.
The deployment-list fixture now matches the API's nested `{deployment, package}`
contract. It reproduced the live `KeyError: agent_id` before the bootstrap lookup
was corrected to unwrap `deployment`; deployment creation remains a flat response.
Privileged activation remains pending until the corrected script succeeds.

Activation succeeded at 2026-09-15 18:52 UTC. The capacity director and both slots
are active with zero restarts and successful authenticated idle polling. The queue
is empty; concurrent terminal BT-009 proof remains outstanding. Recent Telegram
failures predate activation: discovery cycles 019–021 crashed in Node/V8 with
SIGTRAP (-5), and older founder turns failed the reasoning contract. Discovery's
restricted subprocess environment dropped the service's jitless setting. The
executor now supplies fixed `NODE_OPTIONS=--jitless` without inheriting secrets or
arbitrary Node options. Existing discovery workers require restart to load this fix;
no failed task or old approval was replayed automatically.

## Approved mandate and discovery recovery (2026-09-15)

The founder approved `ALPHA004-CAPACITY-20260915`, mandate
`aae38741-7f41-40bc-8612-0ba266467a55`, against reviewed native commit
`a864ac0910890f98f457eb4140b28ede9921e91d`. Its immutable execution window is
2025-05-01 through 2026-05-01 and its existing data authority is Bybit BTCUSDT.
Fresh native admission receipt `09c3b6a6-b7d5-4efe-88a6-637259ab47ce` binds the
same panel to that commit. Admission does not establish complete funding coverage;
auxiliary availability remains a separate execution gate.

First intelligence task `A4-aae38741-001-I` failed three attempts because Codex
runtime initialization attempted writes on a read-only filesystem. SQLite and
log locations now use a private, mode-0700 attempt directory while credential
custody remains read-only. A subsequent live startup probe passed initialization
but failed authentication with `refresh_token_reused`; operator reauthentication
is required before productive discovery can be demonstrated.

Cycle recovery requires an explicit `task_resumed` event after its failure and
matching task/cycle/mandate/stage bindings. It preserves failure events, does not
create an approval, and cannot automatically replay an old execution instruction.
Two concurrent terminal BT-009 receipts remain outstanding, not inferred from
online services, local pool tests, or historical one-month results.

After operator reauthentication/restart, audited resume created attempt 4 on
2026-09-15 at 20:04 UTC. It still failed initialization under systemd confinement.
A matching read-only namespace trace established the remaining mandatory write:
`CODEX_HOME/installation_id` is opened read-write even with SQLite/log overrides.
The corrected units therefore use a private writable runtime home with a
read-only bind mount of the original `auth.json`, never a credential copy.
The installer creates only an empty mount target, does not truncate it on repeat,
and preserves strict filesystem confinement. Discovery disables plugin/app
integration so cached plugins cannot expand this bounded workflow.
The corrected namespace probe first reported temporary model capacity, then
completed authenticated inference with `runtime-ok` under the same read-only
credential binding. Privileged unit reinstall and productive recovery are still
required; the original and resumed failures remain retained.
