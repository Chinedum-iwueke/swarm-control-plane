# ALPHA-001 Validation Record

## Source result

ALPHA-001 adds an immutable no-capital campaign ledger, digest-bound activation,
selected-question queue, attempt and event evidence, budget reconciliation, a
continuous VM2 director, Mission Control visibility and a Bulletproof-owned real-data
admission receipt contract.

The source acceptance suite proves:

- synthetic/test-labelled data is rejected;
- the dataset build, catalog partition, lake policy and Bulletproof receipt must agree;
- the campaign freezes one allocated DISC-009 selection and source commit;
- attempts bind an exact selected question, dataset and source revision;
- duplicate attempt publication is idempotent and question reuse is rejected;
- negative, invalid and failed outcomes remain retained;
- only a complete, independently reviewed BT-009 publication may become a shadow
  candidate;
- exhaustion closes without inventing a candidate; and
- every authority field remains false for allocation, capital, orders and promotion.

The repository-wide validation passed 702 Hermes backend tests and 72 Mission Control
tests. Bulletproof passed 1,336 tests with 27 declared skips; the two warnings are
pre-existing pandas deprecation/future warnings outside ALPHA-001. The Bible
requirement-ledger suite passed 7 tests and 11 subtests. Ruff, JavaScript syntax,
Python compilation, Alembic-head, OpenAPI-route, shell-syntax, systemd-unit and
whitespace checks passed.

## Live-data preflight

On 2026-09-09, the Bulletproof producer inspected the local canonical panel
`canonical/perp/bybit/BTCUSDT/timeframe=1m/research_panel.parquet`. It observed
2,827,851 rows and passed canonical-path, field, identity, strict-time-order,
duplicate, coverage-manifest, fetch-manifest and fetch-success checks. This is a
read-only local lineage observation, not proof of exchange cryptographic provenance,
strategy merit, alpha or live readiness.

The finalized receipt ID and digests are intentionally recorded after the corrected
UTC timestamp representation is regenerated. Dataset digest
`9a211d8818c5ab8ec82ad5a7d38957e63eb387ea83d4b00541922a0eeca4aacb`
and receipt digest
`fbc73f7b0896ce7f64f97e677b9e6a19bd530968197ec2f290cab08aeb64f6ff`
are retained outside source control. VM2 migration, API deployment, matching
DATA-002/003 registration, campaign activation and the first BT-009 attempt remain the
production pass and must be appended here before the milestone can be described as
production-active.

## Test commands

```bash
cd backend
POSTGRES_PASSWORD_FILE=/path/to/test-secret .venv/bin/python -m pytest -q \
  tests/test_alpha_campaign.py tests/test_quantitative_receipts.py

cd ../mission-control
.venv/bin/python -m pytest -q tests/test_control_plane.py

cd /home/omenka/Projects/bulletproof_bt
.venv/bin/python -m pytest -q tests/test_alpha_data_admission.py
```

## Claim boundary

Source completion establishes the governed loop and real-data admission contract. It
does not establish that arbitrary new hypotheses can already be compiled and executed
without a supported BT-009 strategy path. Unsupported questions must end as retained
failures or await bounded strategy engineering; they must never be squeezed into the
nearest existing strategy or reported as tested.
