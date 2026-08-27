# CHAN-001 Validation

## Contract evidence

- Sender and private-chat allowlists are enforced before any planner call.
- Credential, private-key, sudo-password and oversized inputs are blocked before transcript persistence.
- Flood protection is bounded and durable across gateway restarts.
- Telegram update replay is ordered and offset-deduplicated.
- Review links expire, are single-use and fail closed when the bound digest or state changes.
- Non-executable proposals show clarification questions without an approval action.
- Telegram-send/control-plane-ack races retain one delivery and retry only the acknowledgement.
- Security evidence is redacted and hash chained; it grants no execution authority.

## Automated evidence

The Telegram gateway suite covers transient dependency outage, spoofed users, secret input, oversized/flood behavior, duplicate/replayed updates, edited turns, stale links, clarification routing, notification delivery races and bounded alert text.

Run:

```bash
PYTHONPATH=telegram-gateway/src \
  telegram-gateway/.venv/bin/python -m pytest telegram-gateway/tests -q
telegram-gateway/.venv/bin/ruff check telegram-gateway/src telegram-gateway/tests
```

## Production acceptance

Production qualification completed on VM2 on 2026-08-27 at merged source commit `4557667ce42d1d95684f931b57d557cc0bdab42b`:

- `hermes-telegram-gateway.service` entered `active/running` at `2026-08-27T03:40:40Z`, emitted `telegram_gateway_ready` and retained `NRestarts=0` through the observation window.
- Earlier Telegram/control-plane interruptions belonged to prior service runs and used bounded in-process retry. No dependency retry followed the accepted restart.
- The local CHAN-001 audit reported `valid=true`, zero redacted security events, the all-zero genesis head and `action_authority=false`.
- A founder-owned `/status` replay returned 50 terminal/active task records, one pending approval, one queued task, zero active/attention missions and `Channel security events: none`.
- The status command created no work, made no decision and granted no authority.

The retained production summary is `docs/evidence/chan001-report.json`, SHA-256
`503b175e90e9d835860feb103c73a869f62f9345a918577cb92c31077be80c5b`.
