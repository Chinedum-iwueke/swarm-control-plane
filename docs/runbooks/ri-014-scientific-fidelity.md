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

The first VM2 live manifest is `not_qualified` (`3/20` accepted). Preserve it as
negative evidence. Do not manually relabel its 17 disagreements; inspect source
regions, distinguish layout-only differences from material symbol changes, and
publish corrections only under a new representation version.

## Version 2 reconstruction

`scientific-fidelity-v2.0.0` introduced structure-aware multi-row table detection,
bounded multi-line equation spans, symbol-preserving layout normalization and
expanded deterministic AST nodes. Rebuild affected artifacts through normal
ingestion/recovery; never rewrite v1.0/v1.1 objects. A missing scientific class
is a failed coverage gate, not a perfect or non-applicable score.

The production live pilot now writes `scientific-fidelity-v2.1.0`; it never
overwrites v1.0, v1.1, or v2.0 evidence. Version 2.1 preserves multi-line table
regions during held-out replay, uses source coordinates plus independent
structural block matching, and includes CFF Type1 font decoding support. The
live pilot requires equation, table and figure strata before comparing semantic
tokens, cell grids and captions. Qualification still requires the independent
adjudication benchmark; pilot acceptance rates are diagnostic only.
