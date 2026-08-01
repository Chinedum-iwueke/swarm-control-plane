# M15 Point-in-Time Data And Feature Contracts

## Purpose

M15 makes a dataset an immutable research input rather than a filename. It records
what provider and revision supplied the data, when every source object was observable
and available, the permitted `as_of` boundary, each transformation, every feature's
lookback and availability lag, quality thresholds, corporate-action semantics, and
the exact output digest.

The registry does not grant research, promotion, deployment, or trading authority.

## Contract Boundary

Each dataset manifest binds:

- provider, dataset, venue, asset class, retrieval method, and terms version;
- instruments, timeframe, date window, UTC timezone, and `as_of` timestamp;
- every source URI, SHA-256 digest, revision, row count, observation time, and
  availability time;
- exact-revision or latest-known-as-of revision semantics;
- an explicitly forbidden fallback or a named fallback provider and reason;
- corporate-action mode and, when applicable, a separate event digest;
- contiguous ordered transformations with typed parameters and column lineage;
- feature expressions, inputs, lookbacks, availability lags, and null policy;
- output columns and bounded data-quality assertions.

Validation rejects sources unavailable at `as_of`, future observations, unordered
transforms, duplicate feature or quality keys, undeclared provider fallback, and
unbound raw corporate-action events.

Each build record then binds the manifest ID to the builder repository and commit,
runtime, output URI, row count, timestamps, quality results, content digest, and an
independent rebuild digest. Registration fails unless both digests match and every
declared quality assertion passes.

## Pilot Datasets

The M15 pilot reads, but never modifies, two independent canonical market-data files
already held by Bulletproof:

- Binance BTCUSDT perpetual one-minute OHLCV;
- Binance ETHUSDT perpetual one-minute OHLCV.

For each source it selects the UTC 2025 window, aggregates complete rows into hourly
OHLCV, then constructs `lagged_return_1` only from completed prior bars with a declared
two-bar lookback and one-bar availability lag. The builder writes a canonical CSV
twice and requires byte equality.

The source files contain observations after 2025. The manifest therefore binds the
complete current source revision and uses the explicit pilot `as_of` timestamp; it
does not claim the files were frozen at the end of the selected window.

## Rehearsal

After deploying migration `f2d5b8c31a74`, run on VM1:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker

sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

exec .venv/bin/python scripts/m15_pilot.py \
  --source-commit <FULL_SWARM_CONTROL_PLANE_COMMIT> \
  --bulletproof-root /home/omenka/Projects/bulletproof_bt \
  --output-root /home/omenka/Projects/swarm-agent-workspaces/m15-data-contracts \
  --as-of 2026-08-01T23:30:00Z
'
```

The script is resumable. Existing immutable keys are accepted only when their
manifest or build content matches exactly. Output files are mode `0600`; neither the
Bulletproof source files nor its primary checkout are modified.

## Security And Scientific Limits

- No network access or provider fallback occurs during the pilot.
- Source and output paths are operator-selected local paths, not task input.
- Provider identity is never erased during transformation.
- `as_of` validation prevents sources from becoming available retroactively.
- Feature availability lag is distinct from statistical purging and embargo. Those
  stronger trial-aware controls belong to M16.
- Crypto perpetual bars declare equity corporate actions not applicable. Funding,
  contract changes, and exchange-specific mechanics require separate future contracts.
- Passing two rebuilds proves deterministic construction, not predictive usefulness.

## Exit Evidence

M15 exits only after VM2 stores two manifest and build pairs whose content and rebuild
digests match, all quality checks pass, Mission Control displays both as verified, and
the IDs and digests are appended below without credentials.
