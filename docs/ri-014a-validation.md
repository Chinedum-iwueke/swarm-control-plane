# RI-014A Structure-Aware Scientific Reconstruction

RI-014A introduces immutable `scientific-fidelity-v2.0.0` representations.
Historical v1.0 and v1.1 records and negative manifests remain unchanged.

Implemented contracts:

- tables require at least two column-consistent structured rows;
- equation regions collect bounded continuation lines for open delimiters and
  trailing operators;
- layout normalization repairs presentation ligatures, control separators and
  discretionary word-wrap hyphens without changing mathematical glyphs;
- equation trees represent binary precedence, sets, vectors, tuples, indexed
  symbols, implicit products and bounded operator nodes;
- incomplete syntax remains lossless and `review_required`;
- the live pilot targets v2 and refuses single-row historical table guesses.

Validation: 663 backend tests pass, including born-digital/scanned ingestion,
multi-line equations, multi-row tables, layout normalization, symbol-preserving
tokenization and structured AST fixtures.

Production activation requires an API rebuild followed by affected-artifact
reconstruction under v2. A v2 manifest must not qualify if the live corpus lacks
genuine multi-row tables or any required stratum.
