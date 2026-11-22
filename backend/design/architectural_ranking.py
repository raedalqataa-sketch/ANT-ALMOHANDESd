"""Transparent, non-regulatory ranking of generated architectural candidates.

Hard-failed designs must be filtered by the caller before ranking.
This module does not certify building-code compliance.
"""
from __future__ import annotations

from math import isfinite


WEIGHTS = {
    "functional_adjacency": 25,
    "privacy": 25,
    "circulation": 15,
    "daylight_ventilation": 15,
    "area_efficiency": 10,
    "facade_coherence": 10,
}


def score_candidate(metrics: dict, *, hard_failures=()):
    """Score normalized evidence [0, 1]; unknown evidence remains pending.

    A missing metric is never interpreted as success. A hard failure disqualifies
    the candidate regardless of score. This is a design-ranking aid only.
    """
    failures = list(hard_failures)
    if failures:
        return {"eligible": False, "score": None, "hard_failures": failures,
                "pending": [], "breakdown": {}}
    unknown = [key for key in WEIGHTS if key not in metrics or metrics[key] is None]
    breakdown = {}
    for key, weight in WEIGHTS.items():
        value = metrics.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid normalized evidence: {key}")
        breakdown[key] = round(value * weight, 3)
    return {
        "eligible": not unknown,
        "score": round(sum(breakdown.values()), 3) if not unknown else None,
        "hard_failures": [],
        "pending": unknown,
        "breakdown": breakdown,
    }


def rank_candidates(candidates):
    """Return fully-evidenced feasible candidates in descending score order."""
    ranked = []
    for candidate in candidates:
        assessment = score_candidate(
            candidate.get("metrics", {}),
            hard_failures=candidate.get("hard_failures", ()),
        )
        ranked.append({**candidate, "assessment": assessment})
    return sorted(ranked, key=lambda c: (
        not c["assessment"]["eligible"],
        -(c["assessment"]["score"] or 0),
        str(c.get("id", "")),
    ))
