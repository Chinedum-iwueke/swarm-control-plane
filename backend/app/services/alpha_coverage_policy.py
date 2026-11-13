"""Catalogue discovery is not an assertion of scientific execution eligibility."""


def discovery_panels(catalog: dict) -> list[dict]:
    records = catalog.get("availability")
    if records is None:
        return list(catalog.get("one_year_coverage_candidates", []))
    return [
        dict(
            item,
            venue=item.get("exchange", item.get("venue")),
            instrument=item.get("symbol", item.get("instrument")),
        )
        for item in records
        if item.get("dataset") == "ohlcv"
        and item.get("timeframe") == "1m"
        and int(item.get("actual_rows") or 0) > 0
    ]


def coverage_window(specification: dict) -> dict[str, str]:
    policy = (specification.get("historical_window_policy") or {}).get(
        "coverage_replanning"
    )
    if policy:
        return {"start": policy["envelope_start"], "end": policy["envelope_end"]}
    return {
        "start": specification["execution_window_start"],
        "end": specification["execution_window_end"],
    }
