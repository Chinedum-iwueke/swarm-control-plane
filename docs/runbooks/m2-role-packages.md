# M2 Versioned Role Package Runbook

## Security Model

Role-package manifests describe authorization and compatibility. They never
contain commands. Executable steps remain in reviewed, server-local workflow
YAML, and the worker verifies each workflow's SHA-256 before heartbeat or lease.

The registry stores immutable package versions and their canonical digest,
HMAC-SHA256 signature, source commit, profiles, and agent deployment inventory.
The signing secret and orchestrator token must be separate root-owned mode-0600
files. Neither secret is deployed into workflow subprocesses.

## Deployment Order

1. Merge the reviewed package and workflow on VM1.
2. Pull the reviewed commit on VM2 and VM1.
3. Add `package_signing_secret` to VM2's existing secret mechanism.
4. Apply migration `e7a2b6c91f30`.
5. Rebuild and restart the control-plane API.
6. Reinstall worker `0.2.x` on VM1.
7. Register the package, then bind it to the intended agent.
8. Run `invariance-swarm-worker check` before restarting the daemon.

## Register

Load a protected operator environment containing `SWARM_API_URL`,
`SWARM_ORCHESTRATOR_TOKEN`, and `SWARM_PACKAGE_SIGNING_SECRET`, then run:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
.venv/bin/python scripts/package_registry.py register \
  --manifest role-packages/restricted-code-validator/manifest.yaml \
  --source-repository swarm-control-plane \
  --source-commit "$(git rev-parse HEAD)"
```

Use the returned package ID and the agent ID from the operator agent inventory:

```bash
.venv/bin/python scripts/package_registry.py deploy \
  --agent-id AGENT_UUID \
  --package-id PACKAGE_UUID
```

Inspect with `package_registry.py inventory`. Revoke a binding with
`package_registry.py revoke --deployment-id DEPLOYMENT_UUID`.

Registration fails for a changed digest or invalid signature. Deployment fails
when machine, capabilities, or risk ceiling conflict with the immutable
manifest. Publish a new semantic version for every package change.
