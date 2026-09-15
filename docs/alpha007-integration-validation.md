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

Production pass: Hermes PR #268 merged at e9ef1696e and VM2 API rebuilt/recreated.
Running image sha256:0606f0664916a02c0fbd4fb0c1e6f0e133ffec53d85ed2064e4f5a529b886353
was healthy and exposed the scoped inventory route. Real operation
d3dfa5fd-924a-4574-a301-3aa005240686 acknowledged before its scanner started;
live API inspection confirmed heartbeat, PID and more than 27,000 accounted
objects. Exact filesystem counts revealed 1,846,467 raw files and 2,769 canonical
files, exceeding the 250,000-object single-envelope contract. The operator stopped
the attempt explicitly for this engineering mismatch, not an observation timeout.
The ledger retained its terminal failed receipt at 2026-09-15T21:03:46.496137Z and
process inspection confirmed both supervisor and scanner were gone. No complete
inventory publication occurred. Native bounded 10,000-object shards and window
quality are now under implementation; shard custody must be verified before the
next full scan. Initial combined native inventory/quality/admission tests: 29 passed.

The corrective implementation now emits bounded native shards, orders partition
paths globally (including directory/file prefix collisions), and binds a v2 root
to every shard. Hermes validates source/run/index/content bindings, completeness,
non-overlap and summaries before accepting the root. Incremental supervisor
publication preserves completed shard custody. Native quality streams verified
shards, keeps panel metrics rather than duplicating millions of raw-object records,
and reports non-panel adapters as unresolved. A dedicated quality CLI consumes the
same shard files; its protected-output handoff test passes. Quality registration
requires the bound inventory and content identity and grants no execution admission.
Fresh full suites: 847 backend passed (one optional database skip), 295 worker
passed. Native inventory/quality/admission/producer suite: 32 passed; lint passed.
The expanded shard pipeline is not yet production-replayed; the two concurrent
native backtests and wider approved research scope remain open.
