# GOV-003 lifecycle consequences

Deploy migration `a8d3f1c52b90`, rebuild the VM2 API, reinstall Mission Control and run
`worker/scripts/gov003_pilot.py` with the protected operator environment. Retain the
response and independently query the four GOV-002 projections plus consequence rows.

Consequences are additive decisions, not mutable labels. Rollback and expiry create a
new authority-bound lifecycle event restoring the declared prior state. Restore the
prior API to disable new commands while retaining tables and event history. Never drop
the additive table after canonical consequences exist without exporting its records.
