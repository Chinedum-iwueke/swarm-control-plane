# RI-014C Mathematics-Aware Retrieval and Reasoning Utility

RI-014C makes qualified scientific representations usable without granting an LLM authority to guess notation or execute arbitrary mathematics.

## Runtime path

1. `/mathematics/search` ranks only v2 representations that are parser-accepted or independently adjudicated `equivalent`. It matches semantic tokens, scoped symbols and definitions, dimensions, captions, tables, cross-references and expression structure.
2. `/mathematics/context-packs` freezes selected representations, canonical source IDs, exact source-region and representation digests, symbols, units, ASTs/grids, uncertainties and an abstention rule.
3. Mission Control Research Copilot attaches this registered pack to ordinary canonical evidence. Formula claims cite the canonical source object; the answer retains both ordinary and mathematics context digests.
4. `/mathematics/calculations` evaluates a deliberately small Decimal AST. The supplied context pack must exist and contain the representation. Missing substitutions, unresolved evidence, unsupported operators, division by zero and non-integral exponents fail closed.
5. `/mathematics/capabilities` records immutable per-agent, corpus-bound demonstrated tasks, limitations and utility metrics. A role is `qualified` only when every declared independent threshold passes.

The calculator has no network, filesystem, code execution, approval, strategy deployment, order or capital authority.

## Coordinated production pass

After deploying migrations `fbe7d2a41c90` and `fce8a3b52d10`, run the v2 reconstruction pilot, then:

```bash
docker compose exec -T api python -m app.ri014_abc_pilot prepare
```

Mission Control then presents the digest-bound independent review queue. After every sampled representation has one non-conflicting adjudication:

```bash
docker compose exec -T api python -m app.ri014_abc_pilot finalize
```

The final command either emits a qualified benchmark with an immutable evaluation digest or an honest `not_qualified` result. Agent mathematics capability profiles remain `not_demonstrated` until held-out utility tasks are independently scored; benchmark fidelity alone does not qualify reasoning.
