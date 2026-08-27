# DATA-001 Point-in-Time Reference Data

## Purpose

DATA-001 is the canonical temporal identity boundary for instruments, venue listings, venue calendars and corporate actions. Exchange symbols are attributes of effective-dated listings, never stable instrument identities. The service is reference data only: it cannot place orders, allocate capital, modify a dataset or infer fungibility across venues.

## Clocks and identity

Every snapshot has an immutable `as_of` knowledge clock and content digest. Each venue, instrument, listing and calendar revision declares:

- `valid_from` and exclusive `valid_to`, describing when the record is effective in the market;
- `observed_at` and `available_at`, describing when the source and system could know it;
- an immutable revision ID and optional corrected-revision identity.

Resolution requires `venue_id`, `symbol`, `effective_at` and `known_at`. It chooses only a snapshot whose `as_of <= known_at`, then filters effective records by both clocks. Unknown, overlapping or conflicting identity fails closed with 404/409. It never substitutes the present symbol, another venue or a later correction.

Stable `instrument_id` survives symbol changes and relistings. A listing retains venue-specific increments, multiplier and status. A delisted identity remains historically replayable and explicitly reports `delisted`; it is not silently removed from history.

## Snapshot registration

`POST /v1/research/reference-data/snapshots` verifies the canonical digest before storing an immutable snapshot. A snapshot key is idempotent only for the exact digest. A superseding snapshot must name its predecessor and advance the knowledge clock. Existing snapshots remain addressable for deterministic rollback and replay.

Read and resolution routes are:

- `GET /v1/research/reference-data/snapshots`
- `GET /v1/research/reference-data/snapshots/{snapshot_id}`
- `POST /v1/research/reference-data/resolve`

All routes require the orchestrator identity. DATA-002, BT-004 and later execution contracts consume the returned stable identity and snapshot digest; they must not fall back to raw symbol matching.

## Deployment and pilot

Apply migration `e2d7a4c91b60`, recreate the API, then run on VM1:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/data001_pilot.py
'
```

The no-capital pilot registers a digest-bound Binance perpetual fixture, replays the same stable instrument across a symbol change, checks a holiday, replays its known corporate action and proves an unknown venue fails closed.

## Rollback

Consumers pin the prior verified snapshot digest. Never edit or delete a published snapshot to roll back. If a new snapshot is defective, stop admitting it to consumers, register a corrected successor with explicit ancestry and retain the failed snapshot as evidence.
