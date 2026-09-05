# RI-014 Scientific Representation Fidelity

RI-014 stores versioned derived representations beside, never over, canonical scientific objects. Original artifact bytes, extracted text, coordinates, and ingestion evidence remain authoritative provenance.

## Contract

- Unicode is normalized with NFC without substituting uncertain glyphs.
- Equations retain ordered semantic tokens, scoped symbol definitions, and unit dimensions.
- Tables retain explicit row/cell grids; figures retain captions and canonical cross-references.
- Acceptance requires two independent parsers, identical normalized content, confidence of at least 0.90, and at least one non-OCR method.
- Material disagreement, OCR-only evidence, or low confidence produces `review_required`; it never silently publishes an accepted representation.
- Fidelity manifests bind the exact derived record digests to precision, recall, cell accuracy, and expression-replay measurements.

## Deployment

Deploy migration `fae4c6b93d20`, rebuild the API, then run the RI-014 pilot. Rollback drops only RI-014 derived tables and never mutates source evidence.

## Operator review

List review work with `GET /v1/research/scientific-fidelity/representations?status=review_required`. Compare `parser_outputs`, `uncertainties`, `source_region_digest`, and source evidence before publishing a later representation version.
