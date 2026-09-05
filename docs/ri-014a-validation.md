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

## Live replay correction

The first production v2.0 replay evaluated equations and figures but reported
zero tables because its held-out matcher normalized each candidate to one line
before applying the multi-row gate. That `not_qualified` manifest remains valid
negative evidence about the harness used for that run; it is not evidence that
the corpus contains no tables.

`scientific-fidelity-v2.1.0` corrects the harness by selecting table regions from
immutable source coordinates and independently matching structural multi-row
blocks. It also installs `fontTools` so CFF Type1 encodings are fully available
to PDF extraction. The thresholds are unchanged. A v2.1 result remains
unqualified until every stratum is present and independent adjudications meet
the configured gates.
