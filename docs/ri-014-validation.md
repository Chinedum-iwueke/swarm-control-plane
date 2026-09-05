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
