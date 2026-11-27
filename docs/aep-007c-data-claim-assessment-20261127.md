# AEP-007C: Retained BTC Data-Claim Assessment

Status: operator-prepared assessment, not independently accepted or execution authority.
Inspection date: November 27, 2026, UTC. No historical record was modified.

## Bound Subject and Evidence

- Candidate: `bfefd78f-113e-4383-beeb-1ba964a8622d`.
- Candidate digest: `6a898c4ff9cd928c7de2074fe4123a1cc6e21c7dfa0928a2ec0432ae6d12bb88`.
- Bulletproof source: `b9b19c2ce109392196e272920355af10f53a544e`.
- Assessed campaign: `68ec2ce6-c99d-4d0c-99ef-e0458812daa9`, now `completed_no_candidate`.
- Retained observations digest: `38c8a3f45a26340fa0af6cbcd5114a99139ed5aa3193c84c836ff5db103e63b8`.
- Registered producer receipt: `2bf717d6-7337-4112-be6d-0b402ba43794`.
- Receipt digest: `a0f9d8031a664e2cfe910f376db94a717a54e123a08b48e5fde32eb54e503745`.
- Catalog: `ca3ed0ee-41d2-4009-ab2b-7f715e106eb8`.
- Catalog digest: `4f007cc5c0a77dfc3a338508b49a849e7fd953c66f33d2cf5c6af67dee594141`.
- Panel digest: `9a211d8818c5ab8ec82ad5a7d38957e63eb387ea83d4b00541922a0eeca4aacb`.

The receipt and catalog were fetched again through their read-only API endpoints.
This inspection did not rehash or rescan the entire lake. Assertions below about
panel quality are assertions supported by the registered admission receipt,
not a new independent physical-file verification.

A read-only live-resolver probe exercised the local all-checkpoint collector
through the existing production resolution API. Both checkpoints used effective
time May 18, 2025 at 20:00 UTC. At that same knowledge clock, resolution failed:
`No market-data catalog was known at that time.` At knowledge time November 27,
2026 at 21:00 UTC, resolution succeeded with the bound partition. The combined
report remained blocked: one resolved checkpoint, one blocked checkpoint,
`execution_authority=false`, `scientific_certification=false`. This was not a
deployment of the new endpoint, a changed experimental clock, or a backtest.

## Claim Assessment

| Claim | Finding and evidence | Boundary | Disposition and recovery condition |
| --- | --- | --- | --- |
| Retained BTC archive contains a continuous minute grid over its recorded interval | Receipt reports 2,827,851 rows, zero missing bars, zero duplicate timestamps, and interval January 1, 2021 through May 18, 2026 at 18:50 UTC. Catalog binds the same panel digest. | Supports admitted archive contents and internal lineage. Neither exchange cryptographic attestation nor historical trading eligibility follows. Additional columns have their own coverage; OHLCV admission does not certify every feature. | Supported within the receipt's scope; preserve the binding and check the required columns for each experiment. |
| Instrument identity and launch date are recorded | Receipt `instrument_reference` identifies BTCUSDT, Bybit perpetual, reported `first_seen_ts` March 15, 2020, and later `Trading` status with `last_seen_ts` August 8, 2026. Instruments manifest digest is `392232e9020ee50eb17f6a1a83f9c3e5436f6e7e0bc60917e17d644a4d0d218e`. | Supports the existence of those recorded observations. It does not independently authenticate the original exchange response or establish continuous status between the two timestamps. | Supported as a recorded observation only. Stronger source claims require original payload/acquisition custody. |
| BTC was uninterruptedly tradable over the frozen historical experiment | No status-event history or continuity ledger is established by the retained evidence. Prices, reported launch date and a later `Trading` observation are insufficient. | Absence of proof is not proof of a trading interruption. It is an unresolved accepted requirement. | `await_data`; owner: data admission. Reconsider only after provenance-bound historical status evidence covers the required interval and passes independent assessment. No authoring repair can invent this evidence. |
| Contemporaneous research-universe membership is established | Catalog contains `alpha-preregistered-selection`, effective January 1, 2021 through May 18, 2026, but observed/available May 18, 2026. Admission code generates this membership from panel boundaries. | A generated retrospective selection is not an independently observed historical membership ledger. Its effective dates cannot be treated as acquisition dates. | `await_data`; owner: data admission. Reconsider when evidence supports the required membership at the frozen knowledge clocks, or under a separately authorized and reviewed change of scientific scope. |
| This catalog was available at the scientific training-start knowledge clock | Catalog `as_of` is September 25, 2026 at 12:17:31 UTC, later than training start May 18, 2025 at 20:00 UTC. | Later archive access cannot prove catalog availability at that earlier clock. This does not imply the underlying market bars did not exist then. | `await_data`; owner: data admission. Supply an appropriate trusted historical record or explicitly authorize a different retrospective contract; never backdate catalog registration. |

## Decision

The accepted scientific requirements remain unchanged. Historical tradability
and contemporaneous membership remain **unresolved data prerequisites**. This
assessment does not authorize engineering, calibration, smoke, backtests or
promotion. The candidate must not advance on the strength of archive admission
alone. No additional reviewer allowance has been consumed for this assessment.

The completed campaign and its disagreeing review receipts remain immutable.
This document is a prospective assessment for a separately authorized handoff,
not a replacement review receipt or a mutation of the candidate's live status.

## General Recovery Rule

For every candidate, separate content integrity, temporal availability,
instrument-status history and universe-membership claims. Bind each claim to
specific evidence, state what that evidence does not prove, and assign missing
data to admission with an explicit recovery condition. A successful checkpoint
resolution cannot certify continuity across an interval. A failed provenance
claim must not automatically schedule code-authoring repairs.

Relevant implementation: `backend/app/services/alpha_data_admission.py`
constructs catalog partitions and membership; `alpha_data_prerequisites.py`
checks declared clocks and bindings; `market_data_catalog.py` resolves trusted
catalog records. The all-checkpoint assessment was deployed from `1b42371` and
verified against the production catalog after 371 passing regression tests.
It does not automatically prove completeness of scientific claims.
