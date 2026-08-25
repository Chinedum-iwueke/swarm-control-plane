# PLAT-005 validation

PLAT-005 is source-complete when:

- every evaluated signal binds a PLAT-001 service key and owner;
- absent telemetry and absent restore evidence are visible and never reported healthy;
- alerts require three consecutive breaches, deduplicate per generation, recover after
  three healthy samples and reopen with a new generation;
- acknowledgement, silence, unsilence and recovery retain routing events;
- secret-shaped evidence is redacted and evidence cardinality/size is bounded;
- Telegram and Mission Control show service, indicator, severity, owner, route and
  freshness;
- Prometheus labels are limited to catalog service, indicator, state and severity; and
- migration, backend, gateway, Mission Control and JavaScript checks pass.

Production completion additionally requires migration `c5e8a2f41d70`, a rebuilt VM2
API, updated VM2 Telegram gateway, updated Mac Mission Control and a live breach,
silence and recovery replay. Source evidence must not be described as that production
replay.
