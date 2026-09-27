# Shared Codex Authentication Recovery

The VM1 alpha agents share the writable runtime at
`/var/lib/invariance-swarm/codex-discovery-runtime`. Install the watcher only after the
API migration and rebuilt control plane are healthy:

```bash
sudo bash worker/systemd/install-codex-auth-watcher.sh
```

The watcher checks local login state and periodically performs a minimal real Codex
request under `credential-refresh.lock`. A confirmed authentication failure creates a
durable recovery record and starts `codex login --device-auth`. The founder receives
the official URL and 15-minute code in Telegram, and sees the same recovery under
Mission Control **Command -> Codex sign-in**.

Use `/codex-login` in Telegram to inspect state. If a code expires, use
`/codex-login retry`, or select `New code` in Mission Control. Both commands update the
same incident; the watcher advances the attempt generation and posts the replacement
code. It does not send or persist OpenAI access, refresh or identity tokens outside the
root-owned Codex runtime.

Verify operation with:

```bash
systemctl is-active invariance-swarm-codex-auth-watcher.service
journalctl -u invariance-swarm-codex-auth-watcher.service -n 50 --no-pager -o cat
```

A healthy report means the real Codex probe returned the exact expected response. It
does not establish that a campaign task succeeded, and it grants no capital or order
authority.
