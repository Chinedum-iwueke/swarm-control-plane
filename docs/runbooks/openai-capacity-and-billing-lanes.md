# OpenAI capacity and billing lanes

## Contract

Quota exhaustion is infrastructure deferral, not scientific failure. Preserve the
task, immutable approvals and workspace; restore its consumed attempt and stop
new model calls on the affected billing lane. Deterministic workers continue.
One notification is deduplicated per circuit generation.

Workers advertise `model_providers` in heartbeats. Subscription workers share the
`codex` circuit, including discovery, representation, engineering and review.
Explicit API-credit workers use `openai-api`. A quota incident schedules the next
probe six hours later, including when the diagnostic states a later reset date.
The original reset diagnostic is retained; an ambiguous local time is not silently
converted into UTC. Additional in-flight failures cannot postpone that schedule.

Before leasing new work, a matching worker atomically claims a due probe and sends
a bounded read-only READY request. It has no research task or repository context,
a 90-second timeout and no instruction to use tools. Only a successful process
with the exact expected final response closes the circuit. Failed checks wait
another six hours. A database row lock prevents concurrent probe claims.
Workers poll the control plane regularly; these polls are not LLM calls.

The shared subprocess runner also checks permission before each Codex step, so an
already-running task cannot begin a correction/review call after another worker
opens the circuit. In-flight model calls are allowed to settle; they are not
abruptly killed and their artifacts are not deleted. No scientific approval,
mandate renewal or capital authority is implied by quota recovery.

## Future API-credit routing

Default: `SWARM_OPENAI_BILLING_LANE=subscription`. No API key is loaded and no
automatic paid fallback is enabled. Select the lane per supervised worker service
(and thus per assigned role/task pool), not by an LLM-authored task field.

To provision an API-credit pool later, configure its protected service environment:

```ini
SWARM_OPENAI_BILLING_LANE=api
SWARM_OPENAI_API_KEY_FILE=/etc/invariance-swarm/credentials/openai-api.key
SWARM_OPENAI_API_CODEX_HOME=/var/lib/invariance-swarm/codex-api-runtime
SWARM_CODEX_MODEL=<approved API-supported model>
```

Provision the key file with restrictive permissions and the separate runtime home
with the service user's ownership. Add the home to the systemd writable-path
allowlist. The router uses the official OpenAI Responses endpoint through Codex's
named-provider configuration, disables subscription authentication for that
provider, and injects the key only into the Codex process environment, never
command arguments or deterministic test subprocesses. Never reuse the subscription
home. Give the API project a spend limit before enabling this pool.

Keep separate reviewer identities, source contracts and approval boundaries. A
billing route does not make an evaluator independent or approve a task. Do not
silently change an in-flight worker's lane; drain it, configure and restart it.

API routing is fixture-tested, not yet live-certified: no API credential or paid
API request was provisioned for this change. The current lane remains subscription.

## Coverage boundaries

The shared worker path covers alpha discovery, representation, engineering and
independent review. Founder-intake planning also checks the gate and defers quota
failures. Backend-local optional OCR advice falls back to deterministic recovery
while the subscription circuit is open. Authentication monitoring skips model
probes while it is open; the claimed worker probe owns recovery. Independently
hosted clients not using these entry points still require integration before
claiming universal system-wide quota coverage.

References: https://developers.openai.com/codex/auth and
https://developers.openai.com/codex/config-reference.
