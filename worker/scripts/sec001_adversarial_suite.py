from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarm_worker.security_assurance import build_report, load_threat_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(load_threat_model(args.model), args.catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
