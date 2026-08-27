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

Production qualification requires the merged source to be installed on VM1, `hermes-telegram-gateway.service` to remain active, `hermes-telegram-gateway check` to succeed, the local audit chain to verify, and one founder-owned `/status` request to return without creating a task. Record the source commit, service activation timestamp and audit head digest here after deployment.
