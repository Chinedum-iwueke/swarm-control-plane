"""Offline event-floor sensitivity under an explicit IID binomial assumption.

This is not market evidence. A fitted quantile, serial dependence, ties and
selection can all invalidate the assumed event probability and count law.
"""
import math


def event_floor_probability(*, rows: int, floor: int, event_probability: float) -> float:
    """Probability of at least floor events; bounded log-PMF summation."""
    if type(rows) is not int or not 1 <= rows <= 100_000:
        raise ValueError("rows must be an integer between 1 and 100000")
    if type(floor) is not int or not 0 <= floor <= rows + 1:
        raise ValueError("floor must be between zero and rows+1")
    if not math.isfinite(event_probability) or not 0 <= event_probability <= 1:
        raise ValueError("event probability must be finite and between zero and one")
    if floor == 0:
        return 1.0
    if floor > rows or event_probability == 0:
        return 0.0
    if event_probability == 1:
        return 1.0
    p = event_probability
    # Sum the side excluding the mode so the complement avoids catastrophic
    # cancellation for small survival probabilities.
    complement = floor <= math.floor((rows + 1) * p)
    indices = range(floor) if complement else range(floor, rows + 1)
    log_factorial = math.lgamma(rows + 1)
    total = math.fsum(math.exp(
        log_factorial - math.lgamma(k + 1) - math.lgamma(rows - k + 1)
        + k * math.log(p) + (rows - k) * math.log1p(-p)
    ) for k in indices)
    return min(1.0, max(0.0, 1 - total if complement else total))


def joint_gate_bounds(probabilities):
    """Frechet bounds; never assume independent primary/rival or split gates."""
    values = list(probabilities)
    if not values or len(values) > 100:
        raise ValueError("require 1 to 100 gate probabilities")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("gate probabilities must be finite and between zero and one")
    return {"lower": max(0.0, math.fsum(values) - len(values) + 1), "upper": min(values)}
