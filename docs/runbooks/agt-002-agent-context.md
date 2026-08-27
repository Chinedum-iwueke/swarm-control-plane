# AGT-002 Agent Context and Working Memory

AGT-002 makes information supplied to an agent a governed execution input. It does not introduce another research-memory store.

## Contract

An orchestrator assembles a locked manifest for the next task attempt from active canonical evidence. Every item binds its immutable object and content digests, selection reason, sensitivity, expiry, prompt position, citation replay path, and known selected opposition. Items must be unique and positions contiguous. Protected, inactive, cross-project, expired, or over-budget packs fail closed.

The worker fetches the manifest only after obtaining the bound lease. Tasks opt in with `input_contract.governed_context_required=true`. The worker writes `context-manifest.json` with mode `0600` outside the repository checkout before execution. Pack and manifest digests make the exact rendered context replayable.

Working memory remains in the isolated attempt workspace. The control plane stores only its digest, safe relative path, sensitivity, expiry, and receipt digest. It never stores scratch content or lease credentials. Complete, fail, and release transitions mark every active receipt discarded while preserving canonical evidence and the immutable context manifest.

## Rollback

Stop creating governed manifests and omit `governed_context_required` on new tasks. Existing workers remain compatible. Discard task workspaces and active working-memory receipts; do not delete canonical evidence or locked context manifests.
