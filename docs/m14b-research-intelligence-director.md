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

The Mac folder named `imported-prior-results` is only for legacy or external
reports that do not already exist in Hermes or Bulletproof. Routine quantitative
results must not be copied into that folder.

## Bulletproof research-memory bridge

`bulletproof_bt` on VM1 remains the authoritative computational memory. Hermes
does not write to its SQLite database. The `invariance-research-memory-sync`
command opens that database read-only and creates a `ResearchMemoryExportV1`
projection containing:

- the Bulletproof repository commit and complete quiescent SQLite SHA-256;
- trade, invalid-trade, state-bucket, candidate, and recommendation counts;
- bounded strongest and weakest state summaries;
- bounded candidate verdicts and human-approval state;
- bounded recommendations plus run and hypothesis identifiers.

The control plane independently verifies the canonical export digest and stores
the structured record immutably. A compact prior-result document is also indexed
for Director retrieval. Full trade rows remain in Bulletproof; successful,
rejected, invalid, and negative evidence are represented without turning the
knowledge index into a second execution database. Repeating a sync resolves both
records by digest and creates no duplicate.

After deploying the API migration, synchronize from VM1 with:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
. .venv/bin/activate
python -m pip install -e '.[dev]'
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
invariance-research-memory-sync \
  --repository /home/omenka/Projects/bulletproof_bt \
  --database /home/omenka/Projects/bulletproof_bt/research_db/research.sqlite \
  --output /home/omenka/Projects/swarm-agent-workspaces/research-memory-exports/hermes-export.json
```

The bridge fails closed when a WAL writer is active or the database changes while
being read. The database is currently large, so the full content digest is
intentionally a periodic synchronization operation rather than a per-query
operation.

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
