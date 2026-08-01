from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one deterministic M15 dataset")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instrument", required=True)
    args = parser.parse_args()
    source_digest = sha256(args.source)
    source = pd.read_parquet(args.source)
    required = {"ts", "open", "high", "low", "close", "volume"}
    if not required.issubset(source.columns):
        raise RuntimeError("Canonical source is missing required OHLCV columns.")
    if str(source["ts"].dt.tz) != "UTC":
        raise RuntimeError("Canonical source timestamps must be UTC.")
    if set(source["symbol"].dropna().unique()) != {args.instrument}:
        raise RuntimeError("Canonical source contains an unexpected instrument.")
    window = source.loc[
        (source["ts"] >= "2025-01-01T00:00:00Z")
        & (source["ts"] < "2026-01-01T00:00:00Z"),
        ["ts", "open", "high", "low", "close", "volume"],
    ].copy()
    window = window.sort_values("ts", kind="mergesort")
    raw_duplicates = int(window["ts"].duplicated().sum())
    raw_out_of_order = int((window["ts"].diff().dropna().dt.total_seconds() <= 0).sum())
    hourly = (
        window.set_index("ts")
        .resample("1h", label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .reset_index()
    )
    missing = int(
        hourly[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
    )
    non_positive = int(
        (hourly[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()
    )
    non_finite = int(
        hourly[["open", "high", "low", "close", "volume"]]
        .map(lambda value: not math.isfinite(float(value)))
        .any(axis=1)
        .sum()
    )
    hourly["lagged_return_1"] = hourly["close"].pct_change().shift(1)
    output = hourly.dropna().copy()
    output["ts"] = output["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.to_csv(
        args.output,
        index=False,
        columns=["ts", "open", "high", "low", "close", "volume", "lagged_return_1"],
        float_format="%.10g",
        lineterminator="\n",
    )
    args.output.chmod(0o600)
    quality = {
        "duplicate_timestamp_count": raw_duplicates,
        "missing_bar_count": missing,
        "non_finite_value_count": non_finite,
        "non_positive_price_count": non_positive,
        "out_of_order_timestamp_count": raw_out_of_order,
    }
    print(
        json.dumps(
            {
                "instrument": args.instrument,
                "source_digest": source_digest,
                "source_rows": len(source),
                "source_observed_at": source["ts"].max().isoformat(),
                "window_rows": len(window),
                "hourly_rows_before_feature_nulls": len(hourly),
                "rows": len(output),
                "content_digest": sha256(args.output),
                "quality": quality,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
