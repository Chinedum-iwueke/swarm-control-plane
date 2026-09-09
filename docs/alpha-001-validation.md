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
tests. Bulletproof passed 1,337 tests with 27 declared skips; the two warnings are
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

The finalized receipt was regenerated from the merged Bulletproof source revision.
Dataset digest
`9a211d8818c5ab8ec82ad5a7d38957e63eb387ea83d4b00541922a0eeca4aacb`
and receipt digest
`4d89df21046a461a454825a72d870a432a88522702eb40673e4b6edc5b39a06c`
are retained outside source control.

## Production activation

On 2026-09-09, VM2 deployed control-plane merge
`b10d96e80b0ef3f3fed96ab21972402a69002dea`, migrated to
`e3f7a1c94b20`, rebuilt the API and exposed the ALPHA-001 routes. The exact panel was
registered as DATA build `fbb81c42-953b-42fb-8fe1-89c75b45e1aa`, DATA-002 catalog
`d0eb1ad0-98ed-4bce-ad80-649fa3b0b85a` and DATA-003 governance snapshot
`2827b9ed-b6a0-4462-80bd-7d224c4c2d52`. Their dataset, catalog and governance
digests are respectively `9a211d8818c5ab8ec82ad5a7d38957e63eb387ea83d4b00541922a0eeca4aacb`,
`edf31ca2812a662f5eaf5a46eeb3a34a504140df9113708d725bcfd855473492`
and `103ad1109363592bd73e1145977bd851cfefd1bd1839bd7e12a89fec9b1997de`.
The DATA-003 read admission passed with no reason codes.

Campaign `0d6453e5-7274-4807-8027-10bd9ec2c666` was digest-activated and the VM2
director was enabled and observed active with zero restarts. Its first selected
question reached a terminal BT-009 compilation attempt
`f5bcbfeb-ba32-4411-9bd1-93e47dfbfe92`. The attempt failed closed because no exact
registered hypothesis implements the weekend-liquidity by short-horizon-momentum
interaction. It executed zero trials and retained attempt digest
`153acd813afb0bc2e6da6971a38b180099d0cc34199557989efe9d44be4236ad`
and evidence digest
`2ddf966c7d289567852635daa2bab7e885bccd19575a4fdda5c10fe0c499c6ed`.
This proves real-data admission, orchestration, terminal failure retention and restart
reconciliation. It does not prove an executed strategy, alpha, shadow eligibility,
demo readiness or live readiness. The campaign remains `running` at the next
hypothesis action with one retained hypothesis and zero trials.

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
