# ALPHA-007 integration evidence

2026-09-15: implementation in progress; production closure is not claimed.

The native full-lake inventory accounts for raw, canonical and manifest objects,
supports legacy and market-specific paths, streams content SHA-256, records
Parquet footer bounds and fields, and retains corrupt/non-Parquet/symlink objects
with explicit dispositions. The protected CLI receipt grants no execution or
capital authority. Native inventory/admission/producer suite: 14 passed.

Hermes registers only the exact native inventory producer under DATA-002,
verifies content bindings and object accounting, rejects inferred execution
admission, and exposes a receipt-backed full-lake summary. An orchestrator-only
operation report binds the native VM1 inventory workload rather than allowing
arbitrary workload replacement. The discovery output schema now requires the
canonical hyphenated domain/cluster keys; context carries mandate liquidity
requirements and explicitly treats historic universe labels as optional metadata.

Full worker suite: 289 passed. Registry/discovery focused suite: 49 passed.
The full extended backend suite passed 831 tests with one optional database
test skipped, including the operation-report regression. Earlier PostgreSQL
transaction proof remains separate evidence.

Live inspection found 2,768 canonical Parquet files and approximately 185 GiB
across raw and canonical trees. No full content scan, production inventory
registration, DATA-003 quality admission, mixed-basket execution, expanded
mandate activation or two-job BT-009 closure is inferred from these local tests.
Next: supervised scan with periodic ledger heartbeat, immutable publication,
native coverage/quality receipts and hypothesis-specific basket eligibility.

Pre-landing review identified silent subtree omission, unsafe path reopening,
special-file blocking, nested-column timestamp indexing, unvalidated summaries,
and report lifecycle races. Follow-up fixes use explicit traversal failure,
no-follow directory descriptors and one regular file descriptor for hash/metadata,
scalar timezone-aware timestamp bounds, device/inode/size/mtime/ctime stability,
derived disposition/assets validation, immutable input bindings and row-locked
terminal transitions. Fresh verification: 834 backend tests passed (one optional
database skip); 19 native inventory/admission/producer tests passed.
Hermes PR #268 and Bulletproof PR #307 are open with CI running. No production
scan, quality admission, expanded execution scope or backtest is claimed.
