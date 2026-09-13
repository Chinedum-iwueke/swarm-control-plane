# EXEC1 bootstrap validation

Source implementation adds `exec1-execution` to the immutable platform catalog and
OPS-004 observer bootstrap without introducing capital or order authority. Mission
Control already renders arbitrary canonical fleet observations, so no parallel host
registry or hard-coded UI list was added.

Production closure requires key-only SSH, locked root login, host firewall, time sync,
automatic security updates, swap, Tailscale enrollment, a dedicated service account,
the read-only fleet probe, three fresh control-plane observations, Mission Control
visibility, and independent watchdog coverage. Venue execution remains disabled until
the separate DEMO-001 and runtime-safety gates are satisfied.

The 2026-09-13 provisioning pass established key-only operator access, disabled root
and password SSH, enabled UFW/fail2ban/unattended upgrades/chrony, added 2 GiB swap,
created the unprivileged execution state boundary, and joined Tailscale. The allocated
egress geolocated to Oregon, United States. Bybit main/demo returned HTTP 403 and
Binance futures main returned HTTP 451, so venue execution is honestly blocked. No
venue credential was installed and no order was submitted. The machine remains useful
as the independent third-host watchdog and read-only fleet observer.

Validation passed 263 worker tests with the unrelated parent-branch GOV-001 stale
version assertion excluded, 783 backend tests, 75 Mission Control tests, changed-file
Ruff checks, JSON parsing, shell syntax, JavaScript syntax, and Git whitespace checks.
The GOV-001 assertion fails identically on the EXEC-011 parent: it expects manifest
`1.0.1` while that parent already contains `1.0.2`.
