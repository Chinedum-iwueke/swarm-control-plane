from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import yaml

WORKER = Path(__file__).resolve().parents[1]
DEFAULT_PROGRAM = WORKER / "research-programs/m14-daily.yaml"


def request(
    client: httpx.Client, method: str, path: str, payload: dict | None = None
) -> Any:
    response = client.request(method, path, json=payload)
    if not response.is_success:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}: {detail}")
    return response.json()


def load_program(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("Research program must be a YAML mapping.")
    return document


def register(client: httpx.Client, path: Path) -> dict:
    payload = load_program(path)
    existing = request(client, "GET", "/v1/research-programs")
    match = next(
        (item for item in existing if item["program_key"] == payload["program_key"]),
        None,
    )
    if match is not None:
        comparable = {key: match[key] for key in payload}
        if comparable != payload:
            raise RuntimeError("Registered research program differs from local manifest.")
        return {"created": False, "program": match}
    return {
        "created": True,
        "program": request(client, "POST", "/v1/research-programs", payload),
    }


def pilot(client: httpx.Client) -> dict:
    cycles = request(client, "POST", "/v1/research-programs/reconcile")
    today = datetime.now(UTC).date().isoformat()
    digest = request(client, "GET", f"/v1/research-programs/digest/{today}")
    monday = datetime.now(UTC).date() - timedelta(days=datetime.now(UTC).weekday())
    weekly = request(client, "GET", f"/v1/research-programs/weekly/{monday.isoformat()}")
    if not digest["cycles"]:
        raise RuntimeError("M14 pilot did not create or recover today's cycle.")
    cycle = digest["cycles"][0]
    if cycle["status"] != "duplicate_avoided":
        raise RuntimeError("M14 first cycle did not detect the completed M13 hypothesis.")
    return {"created_cycles": cycles, "daily_digest": digest, "weekly_metrics": weekly}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("register", "pilot", "status", "all"))
    parser.add_argument("--program", type=Path, default=DEFAULT_PROGRAM)
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=30,
    ) as client:
        output: dict[str, Any] = {}
        if args.command in {"register", "all"}:
            output["registration"] = register(client, args.program)
        if args.command in {"pilot", "all"}:
            output["pilot"] = pilot(client)
        if args.command == "status":
            output["programs"] = request(client, "GET", "/v1/research-programs")
            output["cycles"] = request(client, "GET", "/v1/research-programs/cycles")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
