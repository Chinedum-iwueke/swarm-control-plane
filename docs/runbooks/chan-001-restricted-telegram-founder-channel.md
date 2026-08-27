# CHAN-001 Restricted Telegram Founder Channel

## Boundary

The Telegram gateway is a founder-only mobile intake and notification surface. It can collect plain-English turns, present clarification questions and carry digest-bound review handoffs. It cannot execute shell commands, receive sudo credentials, read application secrets, bypass task readiness or grant authority outside a reviewed proposal or approval.

Both the Telegram sender ID and private chat ID must match the configured founder identity. Nonmatching updates are discarded before classification. Secret-shaped and oversized messages are rejected before control-plane submission and only a redacted event classification is retained.

## Durable behavior

- Telegram update offsets survive restarts and advance only after an update is handled.
- Founder intake is bounded by a durable sliding rate window.
- Edited messages never mutate accepted turns.
- Handoff tokens are random, hashed at rest, expiring, single-use and bound to the current entity digest.
- Clarification-only proposals never expose approval actions.
- Outbox delivery is recorded after Telegram accepts a message and before the control plane is acknowledged. A failed acknowledgement is retried without sending a second Telegram message.
- Spoof, flood and prohibited-input events form a hash-chained local audit containing no message body or credential-derived digest.
- Dependency outages back off in-process. No action is inferred while Telegram or the control plane is unavailable.

## Operations

Install or upgrade on VM1, where the restricted gateway runs:

```bash
cd /home/omenka/Projects/swarm-control-plane/telegram-gateway
sudo ./systemd/install.sh
sudo systemctl reset-failed hermes-telegram-gateway.service
sudo systemctl restart hermes-telegram-gateway.service
systemctl is-active hermes-telegram-gateway.service
sudo journalctl -u hermes-telegram-gateway.service -n 30 --no-pager --output=cat
```

Verify the local redacted evidence chain:

```bash
cd /home/omenka/Projects/swarm-control-plane/telegram-gateway
sudo -u swarm-telegram .venv/bin/python scripts/chan001_audit.py
```

## Failure and rollback

An invalid credential or configuration is a terminal startup error. A retryable Telegram/control-plane outage remains inside bounded backoff and is visible through the gateway service and fleet observability. Rollback disables mutating approval commands while retaining read-only status and alert delivery; it must not delete the SQLite state, polling offset, handoffs or redacted audit chain.

Never paste a secret into Telegram. If one is pasted, rotate it even when Hermes reports that intake was blocked.
