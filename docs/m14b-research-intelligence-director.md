# M14B Research Intelligence Director

## Decision

M14B separates **question discovery** from research execution. The Research
Intelligence Director may retrieve the approved corpus, identify gaps, propose
multiple cited questions, and rank them. It cannot approve a question, register
a trial, lease an execution task, change a repository, or promote a finding.

## Source intake

Mission Control accepts PDF, Markdown, and UTF-8 text sources up to the configured
size limit. It sanitizes filenames, computes SHA-256 before registration, retains
the original under its private `0700` data root with mode `0600`, extracts PDF
text with page boundaries, and submits the document plus all chunks in one atomic
control-plane request. Raw books and papers are not served by the control plane.
Only bounded passages and citations are available to research roles.

Duplicate content is immutable and rejected by digest. A changed edition is a new
document version. Scanned PDFs without embedded text are rejected; OCR is outside
M14B because it requires a separately sandboxed parser pipeline.

## Domain brains

A Senior Quantitative Research Specialist gains a domain brain through a
versioned, evaluated curriculum rather than an untestable persona prompt:

1. Curate governing documents, canonical books, peer-reviewed papers, and prior
   accepted and rejected trials into a named domain.
2. Tag every source by evidence class and preserve page or line citations.
3. Define a domain profile that pins exact document keys and a domain corpus
   digest.
4. Run retrieval examinations covering methodology, failure modes, and prior
   evidence. A profile cannot activate unless the exam passes against the current
   corpus.
5. Authorize the Senior role for that active profile. Every material source claim
   remains citation-bound; agent inference must be labeled as inference.
6. Re-run the exam whenever the corpus changes. A stale exam cannot qualify a new
   profile.

This is the initial expertise mechanism. Fine-tuning is intentionally deferred:
retrieval, provenance, negative-result memory, and measured examinations are more
auditable and easier to correct.

## Director contract

Each run contains 2-10 candidates. Every candidate includes a question,
rationale, proposed mechanism, data requirements, falsification conditions,
citations from the active domain, information-value score, and feasibility score.
The control plane adds the similarity score against registered hypotheses and
ranks candidates deterministically:

`0.45 information value + 0.35 feasibility + 0.20 novelty`

The selected candidate is a proposal only. M14 daily supervision or a founder
approval must materialize it into a prospectively registered trial.

## Security boundaries

- Uploads are founder actions on the loopback-only Mac application.
- The orchestrator token never enters source metadata, logs, or model context.
- No arbitrary filesystem path, executable, shell string, URL fetch, or archive
  extraction is accepted through upload.
- Domain qualification is digest-bound and expires logically when its corpus or
  evaluation no longer matches.
- The Director is read-only and has neither execution nor approval authority.
- Copyrighted source files stay in the founder's private store; the system exposes
  citations and bounded passages, not a download library.

## Operating sequence

Upload sources in Mission Control, create and pass a retrieval evaluation, create
the domain profile, then invoke the Director for that profile. Review the selected
proposal before dispatch. The first production domain is
`systematic-research`; market microstructure, portfolio construction, ML for
finance, and causal inference should be added as separate tested profiles.
