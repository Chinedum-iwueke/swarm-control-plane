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
