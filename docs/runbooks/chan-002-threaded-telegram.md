# CHAN-002 Threaded Telegram Founder Channel

## Boundary

Telegram is a restricted transport over OPS-006 canonical conversations. It does not
store authoritative specifications, grant permissions, execute commands, collect sudo
passwords, or replace proposal and task approval. The configured founder user and chat
remain the only accepted sender boundary.

## Durable processing

The gateway persists `telegram-update-offset` in its protected SQLite store. It sorts
updates numerically, skips already committed IDs, handles one update at a time, and
commits the next offset only after the update succeeds. A failed update is retried after
restart rather than acknowledged and lost.

Message IDs are mapped to canonical conversation IDs for both accepted founder turns
and thread-bound Hermes replies. Telegram reply metadata takes precedence over the
locally selected thread. Unknown or closed reply targets fail closed and request an
explicit `/switch` or `/resume`.

Edited messages produce one bounded warning and cannot rewrite an accepted turn.
Telegram provides no dependable deletion update for ordinary bot conversations;
deleting chat content therefore has no effect on the canonical audit record.

## Founder controls

```text
/new [title]
/threads
/switch <short-id>
/context
/finish
/stop
/resume <short-id>
/status
/approvals
/research
/notes [query]
```

Clarification notifications name unresolved schema fields and accepted formats. Reply
to the notification to bind the answer to its source thread. Proposal review selects
the proposal thread; approval refuses a mismatched selected thread and revalidates the
proposal digest and state before materialization.

## Install and verify

Run on VM1, where the Telegram gateway is currently hosted:

```bash
cd /home/omenka/Projects/swarm-control-plane/telegram-gateway
sudo ./systemd/install.sh
sudo systemctl restart hermes-telegram-gateway.service
systemctl is-active hermes-telegram-gateway.service
sudo journalctl -u hermes-telegram-gateway.service -n 50 --no-pager --output=cat
```

The API must already expose the OPS-006 conversation routes. Verify without printing
tokens:

```bash
curl -fsS http://100.112.117.59:8787/openapi.json | python3 -c '
import json, sys
paths = json.load(sys.stdin)["paths"]
print(sum("conversations" in path for path in paths))
'
```

Exercise two named threads, restart the service, reply to an older thread-bound
message, request `/context`, and retain the resulting conversation IDs/revisions plus
redacted service logs.

## Recovery and rollback

On polling failure, preserve the SQLite store and inspect the credential-free journal.
Do not reset the offset to skip a problematic update. Correct the bounded parser or
control-plane problem, restart, and confirm the same update is accepted once.

Rollback stops the gateway or returns it to status-only operation. Preserve the store,
canonical conversations, proposal/task records and notification receipts. Never delete
conversation evidence to make Telegram state look consistent.
