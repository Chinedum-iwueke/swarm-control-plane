# RI-005 Corpus Security and Recovery Runbook

## Purpose

Operate the canonical Research Intelligence corpus without treating external content
as authority or treating derived retrieval projections as primary data. All commands
use the authenticated corpus API. Never place tokens in command arguments or logs.

## Service levels

The initial service-level contract is:

- every canonical artifact reference is readable and digest-valid;
- the retrieval projection matches the current canonical corpus digest;
- a digest-bound metadata backup exists from the previous 24 hours;
- a successful empty-corpus restore proof exists from the previous 30 days;
- fewer than 100 ingestion jobs await processing or remediation.

`GET /v1/research/corpus/health?project=<project>` reports each condition separately.
An unhealthy report is evidence of degraded operation, not permission to bypass a gate.

## Security response

Injection, authority spoofing, malware, active content, archives, parser-limit events,
missing artifacts, and integrity failures create bounded security findings. Findings
contain codes, severity, disposition, and remediation class. They never contain source
text, filenames, extracted protected content, credentials, or token values.

Raw captured artifacts remain content-addressed quarantine evidence. Do not delete or
rewrite them during investigation. Corpus content cannot approve work, expand tool
scope, change policy, or become a system instruction.

## Backup

1. Confirm corpus health and investigate missing artifacts before backup.
2. Call `POST /v1/research/corpus/backups` with a structured `project` and `created_by`.
3. Retain the returned backup UUID, manifest digest, corpus digest, object count,
   artifact count, byte size, and timestamp in the operations evidence record.
4. Verify the backup age metric and alert if the 24-hour objective is breached.

The backup manifest contains canonical object, alias, and lineage metadata plus
content-addressed artifact references. Artifact bytes remain in the protected object
store and must be covered by its storage-level backup policy.

## Projection recovery

Call `POST /v1/research/corpus/projections/recover` with the project and requester.
The service deletes only RI-003 derived projection rows, rebuilds them from canonical
evidence, and records the resulting corpus digest, object count, duration, and evidence
digest. Canonical objects, aliases, edges, artifacts, and dossiers are not deleted.

## Queue recovery

Call `POST /v1/research/corpus/queue/recover` with the project, requester, and bounded
stale threshold. Available digest-addressed artifacts return to `quarantined` for the
normal worker. Missing artifacts remain `remediation_required` and create a security
finding. The recovery service never fabricates or silently skips missing source bytes.

## Restore drill

1. Provision an empty database at the same migration head and an isolated object-store
   adapter containing the referenced artifacts and backup manifest.
2. Copy only the selected backup registry record into the isolated database.
3. Call `POST /v1/research/corpus/backups/{backup_id}/restore` with the literal
   confirmation `RESTORE_EMPTY_CORPUS` and the accountable requester.
4. Verify restored object, alias, and edge counts; manifest and corpus digests;
   rebuilt projection digest; measured RPO and RTO; exact citation replay; and
   protected-access denial.
5. Destroy the isolated drill environment after retaining the digest-bound report.

Restore refuses a project with any existing canonical object. A malformed manifest,
digest mismatch, missing artifact, or incompatible schema fails closed before the
corpus becomes usable.

## Rollback

Application rollback may leave RI-005 tables in place. The database downgrade removes
security findings, backup registry records, and recovery-run records only; it does not
remove canonical evidence or object-store bytes. Export operational evidence before a
database downgrade. Never use downgrade as corpus deletion or incident cleanup.
