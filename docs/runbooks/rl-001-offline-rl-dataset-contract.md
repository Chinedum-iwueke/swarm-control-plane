# RL-001 Offline-RL Dataset and Evaluation Contract

RL-001 registers immutable offline-reinforcement-learning dataset contracts. It reuses a
verified DATA-002 build and Bulletproof's sealed SHADOW-001 journal/replay digests. Raw
transitions stay in the canonical data layer; the control plane retains their typed
contract, admissibility audit, limitations, and exact replay identity.

## Gate

Each contract declares the behavior policy and propensity source, state-feature
availability, complete action space and support, reward formula/horizon/rebuild,
episodes, confounders, and the later off-policy evaluation protocol. Unsupported actions
must abstain. Model selection and final evaluation datasets must remain separate.

The server quarantines contracts with dataset drift, quality failure, excess transition
counts, temporal or reward leakage, missing propensities, low action support, propensity
below the declared floor, or importance weights above the declared cap. Proxy and
unobserved confounders are retained as explicit limitations. Qualification never implies
causal identification, policy improvement, deployment, order, or capital authority.

## Deployment and replay

Apply migration `e7d2b5a94c30`, rebuild the API, and run:

```bash
python worker/scripts/rl001_pilot.py --output /var/lib/invariance-swarm/rl001/report.json
```

## Rollback

Stop registering new RL-001 datasets and quarantine affected contract identities. Raw
DATA-002 builds and SHADOW-001 journals are untouched. Existing records remain immutable
evidence and no learned policy can execute from this layer.
