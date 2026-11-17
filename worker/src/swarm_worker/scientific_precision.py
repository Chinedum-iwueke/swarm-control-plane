"""Offline normal-contrast sensitivity, never market evidence or approval.

This approximates a fixed two-group residual contrast with known common variance.
It does not implement fitted nuisance models, random tail counts, paired rivals,
Holm step-down, or the candidate's block bootstrap.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from statistics import NormalDist

NORMAL = NormalDist()


@dataclass(frozen=True)
class PrecisionDesign:
    event_count: int
    control_count: int
    alpha: float = 0.05
    family_size: int = 4
    target_power: float = 0.8
    design_effect: float = 1.0

    def __post_init__(self):
        for name in ("event_count", "control_count", "family_size"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 10_000_000:
                raise ValueError(name + " must be a bounded positive integer")
        if not all(math.isfinite(x) for x in (self.alpha, self.target_power, self.design_effect)):
            raise ValueError("design values must be finite")
        if not 0 < self.alpha < self.target_power < 1:
            raise ValueError("require 0 < alpha < target_power < 1")
        if not 1 <= self.design_effect <= 100:
            raise ValueError("design effect must be between 1 and 100")

    @property
    def per_test_alpha(self):
        return self.alpha / self.family_size

    @property
    def standard_error_sd(self):
        return math.sqrt(self.design_effect * (1 / self.event_count + 1 / self.control_count))

    def power(self, effect_sd):
        if not math.isfinite(effect_sd):
            raise ValueError("effect must be finite")
        critical = NORMAL.inv_cdf(1 - self.per_test_alpha)
        return NORMAL.cdf(effect_sd / self.standard_error_sd - critical)

    def mde_sd(self):
        return (NORMAL.inv_cdf(1 - self.per_test_alpha) +
                NORMAL.inv_cdf(self.target_power)) * self.standard_error_sd

    def required_counts(self, effect_sd):
        """Hypothetical scale-up at the same event fraction, not a window selector."""
        if not math.isfinite(effect_sd) or effect_sd <= 0:
            raise ValueError("required-count effect must be finite and positive")
        scale = (self.mde_sd() / effect_sd) ** 2
        if not math.isfinite(scale) or max(self.event_count, self.control_count) * scale > 10_000_000:
            raise ValueError("required counts exceed probe bound")
        events = max(1, math.ceil(self.event_count * scale))
        controls = max(1, math.ceil(self.control_count * scale))
        return {"events": events, "controls": controls, "total": events + controls}


def sensitivity_report(*, designs, effects, replicates=20_000, seed=42,
                       subject_digest=None):
    designs, effects = list(designs), list(effects)
    if not designs or not effects or len(designs) * len(effects) > 100:
        raise ValueError("require 1 to 100 sensitivity cells")
    if type(replicates) is not int or not 100 <= replicates <= 100_000:
        raise ValueError("replicates must be between 100 and 100000")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if any(not math.isfinite(x) or x < 0 for x in effects):
        raise ValueError("effects must be finite and nonnegative")
    if subject_digest is not None and (
            len(subject_digest) != 64 or any(c not in "0123456789abcdef" for c in subject_digest)):
        raise ValueError("subject digest must be a lowercase SHA-256")
    cells = []
    for design in designs:
        # Common random numbers make effect comparisons reproducible and monotonic.
        rng = random.Random(seed)
        z = [rng.gauss(0, 1) for _ in range(replicates)]
        critical = NORMAL.inv_cdf(1 - design.per_test_alpha)
        for effect in effects:
            probability = design.power(effect)
            simulated = sum(value + effect / design.standard_error_sd > critical
                            for value in z) / replicates
            cells.append({
                "design": asdict(design), "effect_sd": effect,
                "per_test_alpha": design.per_test_alpha,
                "standard_error_sd": design.standard_error_sd,
                "mde_sd": design.mde_sd(), "analytic_power": probability,
                "simulated_power": simulated,
                "monte_carlo_standard_error": math.sqrt(probability * (1 - probability) / replicates),
                "hypothetical_required_counts": design.required_counts(effect) if effect > 0 else None,
            })
    report = {
        "schema_version": "offline-normal-contrast-sensitivity-v1",
        "subject_digest": subject_digest, "seed": seed, "replicates": replicates,
        "model": "known-variance normal two-group standardized residual contrast",
        "multiplicity": "alpha/family_size Bonferroni threshold; also the first Holm threshold, NOT full Holm power",
        "simulation": "Gaussian contrast draws verify this approximation only, not the exact candidate estimator",
        "design_effect_status": "supplied sensitivity assumptions, not estimated market dependence",
        "effect_status": "hypothetical standardized effects, not evidence of economic relevance",
        "market_data_used": False, "scientific_approval": False,
        "execution_authority": False, "cells": cells,
        "limitations": [
            "Fixed group counts and known variance; no fitted nuisance uncertainty.",
            "No event clustering, eligibility loss, training-threshold transfer, or random support counts.",
            "No exact paired-rival covariance or candidate block-bootstrap calibration.",
            "No listing, point-in-time membership, tradability or profitability evidence.",
            "Joint validation/test and multiple acceptance gates can have lower power.",
            "Precision adequacy requires a separately justified meaningful effect and dependence model.",
        ],
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**report, "report_digest": hashlib.sha256(raw).hexdigest()}
