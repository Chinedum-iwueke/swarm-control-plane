# RI-014 Validation

RI-014 is complete in source when:

- schema, service, route, migration, and OpenAPI tests pass;
- golden tests preserve Greek symbols, subscripts, integral and relation tokens;
- independent matching parsers accept a representation;
- parser disagreement and OCR-only equations enter review;
- table payloads cannot omit their cell grid;
- immutable source/version conflicts are rejected;
- corpus manifests bind exact representation digests and cannot qualify when review work exists or held-out thresholds fail.

Production activation still requires migration `fae4c6b93d20`, API rebuild, and a live digest-bound pilot against held-out source regions.

## Production evidence, 2026-09-05

Migration `fae4c6b93d20` and API commit `935e8c5` were deployed on VM2. The
bounded live pilot evaluated 20 PDF equation regions with independent PyPDF and
PDFium extraction. Three representations were accepted, 17 were retained as
`review_required`, and four additional candidates were skipped for empty
independent regions. Manifest `73f09651-5f97-4eb0-9122-37aeadfe6706` is bound
by digest `43e31d9d5d91b47e3703f593604c43b6bf67d1b2a289d73d0d115a8e657adf11`
and correctly records `not_qualified` with equation replay, token precision and
token recall of `0.15`.

This is a successful safety-gate exercise and a failed fidelity qualification.
No review-required representation may be treated as mathematically understood.
The reported table-cell score was not measured by this equation-only pilot and
must not be cited as evidence of table fidelity; a subsequent version must use
separate equation, table and figure strata with non-applicable metrics represented
explicitly.

Version `scientific-fidelity-v1.1.0` corrects that harness defect. It aligns a
bounded source line independently in PyPDF and PDFium, compares equation token
sequences without erasing symbol differences, compares normalized table grids,
and replays figure captions. Qualification now requires 10 equations, five tables
and five figures; absent or failed strata score zero. Version 1.0 records and its
negative manifest remain immutable.
