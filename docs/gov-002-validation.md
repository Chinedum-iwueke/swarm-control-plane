# GOV-002 validation

GOV-002 is source-complete when:

- each governed subject owns four separate projections named `research`, `evidence`,
  `operations` and `capital`;
- every dimension has a closed transition graph and rejects undeclared commands;
- one command changes exactly one projection and never infers another transition;
- operational progression requires, but is not caused by, succeeded research and
  admissible evidence;
- capital progression requires, but is not caused by, live operations and admissible
  evidence;
- every transition binds an active GOV-001 authority decision, subject digest,
  evidence digests, actor, reason, effective time and optimistic version;
- stale versions, command-ID content changes, ambiguous concurrent registration and
  projection/event drift fail closed;
- event digests chain per dimension and a fresh replay reconstructs every projection;
- Mission Control displays all four states and versions without collapsing them into
  a single maturity badge; and
- migration, backend, Mission Control, lint and JavaScript checks pass.

Production completion additionally requires migration `f7c2a9d41e80`, a rebuilt VM2
API, updated Mac Mission Control, and a live pilot showing research success and evidence
admission leave operations and capital unchanged until a separate authorized command.
