#!/usr/bin/env python3
"""Print a bounded, offline sensitivity report. Never reads the market lake."""
import argparse
import json

from swarm_worker.scientific_precision import PrecisionDesign, sensitivity_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, required=True)
    parser.add_argument("--controls", type=int, required=True)
    parser.add_argument("--design-effects", type=float, nargs="+", default=[1, 2.25, 4])
    parser.add_argument("--effects", type=float, nargs="+", default=[0, 0.1, 0.25, 0.5, 0.75, 1])
    parser.add_argument("--family-size", type=int, default=4)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.8)
    parser.add_argument("--replicates", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--subject-digest")
    args = parser.parse_args()
    try:
        report = sensitivity_report(
            designs=[PrecisionDesign(args.events, args.controls, args.alpha,
                      args.family_size, args.target_power, deff) for deff in args.design_effects],
            effects=args.effects, replicates=args.replicates, seed=args.seed,
            subject_digest=args.subject_digest,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
