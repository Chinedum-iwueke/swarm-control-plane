# AGT-006 Independent Evaluator Routing and Anti-Collusion

AGT-006 turns evaluator independence into a machine-enforced routing decision. A producer submits an immutable subject digest, its identity and runtime dimensions, required review kinds, and a correlation ceiling. The router chooses only active, capability-bearing evaluator profiles backed by active role-package deployments.

## Separation contract

The router fails closed on any shared:

- agent identity;
- role-package manifest digest; or
- context group.

Machine, provider, model family, and runtime are correlation dimensions. They are scored, retained in every assignment, and constrained by the requested pairwise ceiling. Sharing one of these dimensions is never silently described as independence. This distinction lets the current two-VM fleet operate honestly while preserving a path to stronger provider and host diversity.

Each route assigns a different evaluator profile to every required review kind. Only the assigned agent may bind a review ID and digest to that assignment. Completion of every assignment issues an immutable independence receipt over the subject, producer, policy, assignments, review digests, and disclosed correlations. The assertion endpoint returns HTTP 409 until that receipt exists, so downstream promotion must remain blocked.

## Lifecycle

1. Register versioned evaluator profiles from enabled agents with active package deployments.
2. Submit a digest-bound route request.
3. Deterministically rank eligible profiles by producer and pairwise correlation.
4. Block when no eligible profile satisfies hard separation or the correlation ceiling.
5. Accept digest-only completion from each routed agent.
6. Issue the chained independence receipt only after all required reviews complete.

Profiles and routes are append-only evidence. Registering a new profile version retires the prior active version; it does not rewrite prior assignments. Evaluation receipts carry no execution, capital, deployment, or promotion authority.

## Production activation

After migration `d5a9c3e72f10` and API deployment, run on VM1:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker

sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

exec .venv/bin/python scripts/agt006_pilot.py \
  --roles /etc/invariance-swarm/m13-role-state.json \
  --output /var/lib/invariance-swarm/agt006/report.json
'
```

The retained pilot must show a completed statistical/adversarial route, two distinct agents and packages, a receipt digest, a blocked zero-correlation route, and `action_authority: false`.
