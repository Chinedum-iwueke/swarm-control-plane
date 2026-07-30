# Hermes Restricted Telegram Gateway

The gateway is a narrow founder channel. It accepts plain-English requests from
one configured Telegram user in one configured chat, submits structured
`founder_request` records, reports status changes, and presents expiring
digest-bound review links.

It does not hold the orchestrator token. Its dedicated founder-channel
credential can only create intake requests, read task/proposal/approval status,
and record founder proposal or approval decisions. It cannot register agents,
deploy packages, pause the fleet, rotate credentials, or call worker lifecycle
routes.

## Protected configuration

Create these root-owned mode-0600 files on VM2:

- `/etc/invariance-swarm/telegram-bot.token`: BotFather token.
- `/etc/invariance-swarm/founder-channel.token`: random 32-byte-or-longer
  control-plane credential.
- `/etc/invariance-swarm/telegram-gateway.env`: non-secret configuration:

```text
HERMES_TELEGRAM_API_URL=http://100.112.117.59:8787
HERMES_TELEGRAM_FOUNDER_USER_ID=123456789
HERMES_TELEGRAM_FOUNDER_CHAT_ID=123456789
HERMES_TELEGRAM_DATA_ROOT=/srv/invariance/swarm/telegram-gateway
```

The same founder-channel value must be mounted into the API container at
`/run/secrets/founder_channel_secret`.

## Commands

```bash
hermes-telegram-gateway check
hermes-telegram-gateway once
hermes-telegram-gateway run
```

The systemd installer validates credentials, the dedicated system user,
virtualenv, unit hardening, and data-directory permissions. It does not enable
or start the service.

## Founder interaction

- Send a plain-English request to create structured intake.
- Send `/status` for a bounded task summary.
- Open a `t.me` review link to see the exact digest and risk.
- Use the generated `/approve TOKEN` or `/reject TOKEN` command once.

Tokens expire after 15 minutes, are stored only as SHA-256 digests, and are
consumed after one decision. Any proposal or approval digest change invalidates
the handoff.
