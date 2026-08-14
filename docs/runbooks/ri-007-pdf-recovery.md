# RI-007 Governed PDF Recovery

## Boundary

This operation recovers only terminal rejected PDF ingestion jobs whose latest reason
is `active PDF content is forbidden` or `PDF parser rejected the artifact`. It never
changes, deletes, publishes, or replaces the original quarantine object.

The recovery worker creates an inert PDF edition, assigns it a new SHA-256 digest,
requires identical normalized extracted text, page count, and deterministic raster
samples from the first, middle, and final pages, submits it through the normal
scientific-ingestion pipeline, and records an immutable receipt linking both jobs and
digests. Any uncertainty ends in `rejected` or `remediation_required`.

## Safe concurrent operation

Recovery may run beside founder-inbox ingestion as a separate one-process container.
Use a conservative host-load ceiling and the shared evidence-object mount. The API
container is not recreated during the active inbox request.

1. Build the new image without restarting `swarm-api`.
2. Apply the additive migration with a one-off container.
3. Queue eligible recovery rows through the authenticated recovery endpoint, or use
   the worker's `--queue-project systematic-research` bootstrap while the old API stays
   online.
4. Start one bounded worker with `--load-ceiling 6 --poll-seconds 15`.
5. Inspect recovery receipts and normal ingestion statuses.
6. Reconcile the founder inbox and rebuild projections only after both flows finish.

Do not increase concurrency until CPU, memory, database latency, and ingestion time
have been measured. Do not bypass the active-content scanner.

## Continuous steward

The VM2 recovery steward continuously queues terminal PDF rejections, retries proven
inert editions, and uses an independent offline PDFium text recovery only when a
structural PDF rewrite cannot be proven safe. The fallback produces a new UTF-8
artifact and records original, recovered, text, page-sample, retrieval, and graph
digests. It never publishes the original quarantine object.

After a five-minute settled interval, the steward maps recovered editions back to the
latest founder-inbox inventory and atomically rebuilds retrieval and graph projections.
An unreadable artifact remains rejected and requires a replacement source edition.

Install and activate on VM2 only after the image and migration are deployed:

```bash
cd /srv/invariance/swarm/repositories/swarm-control-plane/worker
sudo ./systemd/install-recovery-steward.sh --enable --start
```

## Rollback

Stop the separate recovery container. Queued records remain durable. Processing rows
are reviewable and may be explicitly requeued after confirming no worker owns them.
The original artifacts and their security findings remain intact. Do not downgrade the
additive migration while recovery records are required for provenance.
