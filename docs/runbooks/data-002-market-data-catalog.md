# DATA-002 Immutable Market-Data Catalog

## Purpose

DATA-002 registers immutable raw and curated market-data partitions, effective universe
membership, source availability, and correction ancestry against an exact DATA-001
reference snapshot. It does not copy, repair, mutate, or grant write access to source
data.

## Admission boundary

Every partition declares stable instrument, listing and venue identity, event coverage,
observation and availability clocks, content and schema digests, row count, read-only
URI, source, and revision ancestry. Registration verifies the catalog digest and every
identity edge against the bound DATA-001 snapshot.

Resolution requires dataset, layer, venue symbol, timeframe, effective time and
knowledge cutoff. It admits only the latest correction present in the selected immutable
catalog and available by the cutoff. Optional universe membership must also be known and
effective. Missing coverage, delayed/unavailable sources, conflicting partitions,
unknown identity and future information fail closed.

## Operations

- Register: `POST /v1/research/market-data-catalog/snapshots`
- List/get immutable snapshots: `GET /v1/research/market-data-catalog/snapshots`
- Resolve a point-in-time input: `POST /v1/research/market-data-catalog/resolve`
- Rollback: pin a prior `catalog_digest`; never rewrite a snapshot.

DATA-003 owns continuous quality SLOs, entitlements, retention, storage operations and
recovery. DATA-002 grants no write, execution, order or capital authority.
