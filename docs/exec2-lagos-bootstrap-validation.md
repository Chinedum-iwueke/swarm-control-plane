# EXEC2 Lagos bootstrap validation

The 2026-09-13 admission preflight observed public egress `176.97.192.188` from the
server itself. IPinfo mapped it to Lagos, Nigeria on AS8849, consistent with independent
prefix data for `176.97.192.0/24`. Bybit mainnet and demo plus Binance spot and futures
public time endpoints returned HTTP 200. This proves network reachability, not trading
authority, profitability, authenticated API correctness, or regulatory eligibility.

The host foundation requires key-only SSH, locked root login, firewall, fail2ban,
unattended upgrades, chrony, Docker, swap, a dedicated unprivileged execution account,
Tailscale, Nigerian egress revalidation, and fail-closed venue preflight. Its immutable
state records `capital_authority`, `order_authority`, `venue_credentials_installed`, and
`execution_runtime_enabled` as false.

Production closure additionally requires governed fleet registration, three accepted
telemetry samples, Mission Control visibility, EXEC1 watchdog coverage, a new active
service catalog, and venue-observed DEMO-001 certification. No exchange secret or order
belongs in this host-foundation pass.
