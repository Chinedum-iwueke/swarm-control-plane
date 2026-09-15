"""Supervise a read-only native inventory through the existing operator session."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from uuid import uuid4


REMOTE = '''set -a
source "$HOME/Library/Application Support/Hermes Mission Control/mission-control.env"
set +a
"$HOME/Library/Application Support/Hermes Mission Control/venv/bin/python" -c '
import asyncio, json, sys
from hermes_mission_control.config import MissionControlSettings
from hermes_mission_control.control_plane import ControlPlaneClient
request = json.load(sys.stdin)
if request["path"] not in {"/v1/operations/lake-inventory/report", "/v1/research/quantitative-receipts"}:
    raise ValueError("Unsupported inventory endpoint")
async def send():
    client = ControlPlaneClient(MissionControlSettings())
    try:
        return await client._request("POST", request["path"], json=request["payload"])
    finally:
        await client.close()
result = asyncio.run(send())
print(json.dumps({key: result.get(key) for key in ("id", "receipt_digest", "state")}))
'
'''


def publish(host, path, payload):
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, REMOTE],
        input=json.dumps({"path": path, "payload": payload}),
        text=True, capture_output=True, timeout=90, check=True,
    )
    return json.loads(result.stdout)


def latest_progress(path):
    with path.open("rb") as handle:
        handle.seek(0, 2)
        handle.seek(max(0, handle.tell() - 65536))
        lines = handle.read().splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(event, dict) and event.get("event") == "lake_inventory_progress":
            return {key: event[key] for key in ("objects_completed", "partition_id") if key in event}
    return {}


def new_events(path, offset):
    events = []
    with path.open("rb") as handle:
        handle.seek(offset)
        while True:
            before = handle.tell()
            line = handle.readline()
            if not line.endswith(b"\n"):
                return events, before
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(event, dict):
                events.append(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-repo", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--operator-host", default="mac2")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    args = parser.parse_args()
    repo = args.native_repo.resolve()
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True):
        raise RuntimeError("Native checkout must be clean before source binding")
    run_id = str(uuid4())
    directory = args.output_dir / run_id
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    output = directory / "receipt.json"
    binding = {"source_commit": commit, "data_root": str(args.data_root.resolve()), "run_id": run_id}
    operation = {
        "operation_key": "lake-inventory:" + run_id,
        "kind": "full_lake_inventory", "title": "Full Binance/Bybit lake inventory",
        "project": "bulletproof-bt", "machine": "vm1-developer",
        "owner_type": "system", "owner_id": "founder-operator",
        "state": "running", "phase": "inventory", "cancellable": False,
        "input_digest": hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest(),
        "detail": binding,
    }
    # The ledger must acknowledge the operation before any large scan begins.
    publish(args.operator_host, "/v1/operations/lake-inventory/report", operation)
    environment = dict(os.environ, PYTHONPATH=str(repo / "src"))
    process = None
    offset = 0
    shard_receipts = set()

    def publish_shards(log_path):
        nonlocal offset
        events, offset = new_events(log_path, offset)
        for event in events:
            if event.get("event") != "lake_inventory_shard_ready":
                continue
            path = Path(event["path"]).resolve(strict=True)
            if path.parent != directory.resolve() or path.suffix != ".json":
                raise RuntimeError("Native shard path escapes the operation directory")
            document = json.loads(path.read_text(encoding="utf-8"))
            if (document.get("receipt_digest") != event.get("receipt_digest")
                    or document["result"].get("run_id") != run_id):
                raise RuntimeError("Native shard event conflicts with its receipt")
            if document["receipt_digest"] not in shard_receipts:
                publish(args.operator_host, "/v1/research/quantitative-receipts",
                        {"receipt": document, "registered_by": "founder-operator"})
                shard_receipts.add(document["receipt_digest"])
                operation["detail"]["shards_registered"] = len(shard_receipts)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Supervisor interrupted by signal {signum}")

    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        with (directory / "progress.jsonl").open("x", encoding="utf-8") as log:
            os.chmod(log.name, 0o600)
            process = subprocess.Popen([
                str(args.python), str(repo / "scripts/inventory_full_lake.py"),
                "--data-root", str(args.data_root), "--source-commit", commit,
                "--run-id", run_id, "--output", str(output),
            ], stdout=log, stderr=subprocess.STDOUT, env=environment)
            started = time.monotonic()
            operation["detail"]["pid"] = process.pid
            while process.poll() is None:
                if time.monotonic() - started > args.timeout_seconds:
                    raise TimeoutError("Inventory exceeded its bounded runtime")
                operation["detail"]["elapsed_seconds"] = int(time.monotonic() - started)
                operation["detail"].update(latest_progress(Path(log.name)))
                publish_shards(Path(log.name))
                publish(args.operator_host, "/v1/operations/lake-inventory/report", operation)
                time.sleep(10)
            if process.returncode:
                raise RuntimeError(f"Native inventory exited {process.returncode}; see {log.name}")
            publish_shards(Path(log.name))
        operation["phase"] = "publication"
        publish(args.operator_host, "/v1/operations/lake-inventory/report", operation)
        receipt = json.loads(output.read_text(encoding="utf-8"))
        registered = publish(args.operator_host, "/v1/research/quantitative-receipts",
                             {"receipt": receipt, "registered_by": "founder-operator"})
        operation.update(state="succeeded", phase="complete", links=registered)
        publish(args.operator_host, "/v1/operations/lake-inventory/report", operation)
        print(json.dumps({"run_id": run_id, "output": str(output), "registered": registered}))
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        operation.update(state="failed", phase="inventory_or_publication", retryable=True,
                         error_summary=f"{type(error).__name__}: {error}"[:4000])
        try:
            publish(args.operator_host, "/v1/operations/lake-inventory/report", operation)
        except Exception:
            pass
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    main()
