# SEC-001 validation

SEC-001 is complete when:

- all canonical PLAT-001 services have owned threat coverage;
- injection, exfiltration, privilege escalation, supply-chain tampering, and capital
  mutation hostile fixtures fail closed;
- report serialization contains no synthetic secret;
- every threat has detection, containment, rollback, and residual-risk statements;
- tampered artifacts and capital-authority mutations make the suite fail;
- CI retains the digest-bound security-assurance report for 90 days; and
- the focused tests and full worker suite pass.

The canonical evidence is `docs/evidence/sec001-report.json`. Its `model_digest`
binds the exact threat model and its `report_digest` binds coverage, scenario results,
and accepted residual risks.
