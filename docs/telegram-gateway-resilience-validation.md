# Telegram Gateway Resilience Validation

## Incident finding

The VM2 gateway had exhausted systemd's five-start burst on 2026-08-24 after dependency calls raised `TelegramError` and `ChannelError`. The prior CLI logged only the exception class, discarding the already-sanitized diagnostic, and every transient HTTP/network failure terminated the daemon. On 2026-08-25 the founder restarted the unit successfully; it remained `active/running` with zero restarts, confirming that the SQLite state and protected credentials were not corrupt.

## Correction

- Telegram and founder-channel failures now carry a token-free dependency, method, HTTP status and retryability classification.
- Network errors, HTTP 429 and HTTP 5xx responses retry inside the daemon with bounded exponential backoff from 5 to 300 seconds.
- Authentication, authorization and other permanent HTTP 4xx responses still terminate the daemon so systemd and fleet monitoring show a hard failure.
- The daemon emits `telegram_gateway_ready`, `telegram_gateway_dependency_retry` and a sanitized terminal `telegram_gateway_error` record.
- Restart-safe polling semantics are unchanged: the durable update offset advances only after successful update handling.

## Evidence

The Telegram gateway suite passes 36 tests, including token-redaction and 401/429/503 classification plus an in-process transient outage/recovery replay. Ruff passes across gateway source and tests.

This improves single-host durability but does not make Telegram an independent outage channel. Fleet/Mission Control remain the other visibility surfaces; the deferred external VPS watchdog is still required for simultaneous VM or home-network loss.
