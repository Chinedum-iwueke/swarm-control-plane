# ALPHA-008 Selected-Panel Admission

## Purpose

Continuous discovery reads the immutable native manifest catalog. It does not reopen
every lake object each cycle. When an approved candidate names exact panels, the
dedicated admission worker opens only those files, verifies their bytes, identity,
schema, continuity and lineage, retains content-addressed recovery evidence, and
registers the resulting DATA-001/002/003 records before execution.

Catalog visibility is not data admission. Admission is not execution authority and
does not establish alpha.

## Prerequisites

1. The reviewed Bulletproof admission implementation is merged into the canonical
   `/home/omenka/Projects/bulletproof_bt` checkout and its virtual environment exists.
2. The matching control-plane commit is merged into
   `/home/omenka/Projects/swarm-control-plane`.
3. `/etc/invariance-swarm/pilot-operator.env` is root-owned mode `0600` and contains
   the existing operator bootstrap credentials.

## Register And Install On VM1

```bash
cd /home/omenka/Projects/swarm-control-plane

sudo bash <<'ROOT'
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a

root=/home/omenka/Projects/swarm-control-plane
commit="$(git -C "$root" rev-parse HEAD)"

"$root/worker/.venv/bin/python" \
  "$root/worker/scripts/alpha002_bootstrap.py" \
  --package vm1-alpha-data-admission \
  --state /etc/invariance-swarm/alpha-data-admission-state.json \
  --environment /etc/invariance-swarm/alpha-data-admission.env \
  --source-commit "$commit"

bash "$root/worker/systemd/install-alpha-data-admission.sh"

systemctl is-enabled invariance-swarm-alpha-data-admission.service
systemctl is-active invariance-swarm-alpha-data-admission.service
ROOT
```

An existing partial registration must be recovered explicitly with the bootstrap
command's `--recover-registration` option after its immutable identity is inspected.
Do not rotate or silently replace a different active identity.

## Verification

```bash
systemctl show invariance-swarm-alpha-data-admission.service \
  --property=ActiveState,SubState,NRestarts
sudo journalctl \
  -u invariance-swarm-alpha-data-admission.service \
  -n 50 --no-pager --output=cat
```

An idle worker may report `no_work`; this is healthy only when Mission Control shows
no queued `alpha_data_admission` task. A queued task plus repeated `no_work` is an
authority, package or lease-routing fault and must remain visible.

## Rollback

```bash
sudo systemctl disable --now invariance-swarm-alpha-data-admission.service
```

Rollback stops new admission leases. It does not delete immutable candidates,
receipts, DATA records, recovery evidence or terminal failure records.
