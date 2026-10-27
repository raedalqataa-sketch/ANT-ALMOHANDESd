"""Opt-in ranking overlay for V4 draft candidates, preserving baseline scoring.

This is a diagnostic experiment: the main generator and release checks are untouched.
"""
from __future__ import annotations

from .space_efficiency_audit import audit_floor


def assess_candidate(model, *, pocket_threshold_m2=0.5):
    """Return a comparable space-efficiency report for a materialized candidate.

    Requires explicit floor measurement envelopes from caller; does not silently
    equate land parcel area, building footprint, and interior usable area.
    """
    reports = []
    envelopes = model.get("space_audit_envelopes", {})
    for floor in model.get("floors", []):
        fid = floor.get("id")
        if fid not in envelopes:
            return {"status": "PENDING", "reason": "MISSING_MEASUREMENT_ENVELOPE",
                    "floor": fid, "eligible_for_ranking": False}
        reports.append(audit_floor(floor, envelopes[fid],
                                   pocket_threshold_m2=pocket_threshold_m2))
    if not reports:
        return {"status": "PENDING", "reason": "NO_FLOORS", "eligible_for_ranking": False}
    if any(r["status"] == "INVALID_GEOMETRY" for r in reports):
        return {"status": "INVALID_GEOMETRY", "floors": reports,
                "eligible_for_ranking": False}
    corridor = sum(r["corridor_union_m2"] for r in reports)
    envelope = sum(r["measurement_envelope_m2"] for r in reports)
    leftover = sum(r["leftover_m2"] for r in reports)
    ratio_reviews = sum(len(r["elongated_room_reviews"]) for r in reports)
    pocket_area = sum(sum(p["area_m2"] for p in r["leftover_review_regions"])
                      for r in reports)
    return {"status": "REVIEW" if ratio_reviews or pocket_area else "MEASURED",
            "eligible_for_ranking": True, "floors": reports,
            "corridor_union_m2": round(corridor, 4),
            "corridor_envelope_ratio": round(corridor / envelope, 6),
            "leftover_review_m2": round(pocket_area, 4),
            "leftover_total_m2": round(leftover, 4),
            "elongated_room_review_count": ratio_reviews,
            "score_terms": {
                "circulation": round(corridor / envelope, 6),
                "unallocated_review": round(pocket_area / envelope, 6),
                "elongation_review": round(ratio_reviews / max(1, sum(len(f.get("rooms", []))
                                        for f in model["floors"])), 6),
            },
            "limitations": "Measured review indicators, not a legal pass or a proof of waste."}


def compare_candidates(candidates, *, weights=None):
    """Rank candidates with independent measurements; no mutation or approval.

    Caller passes an iterable of {'candidate_id', 'model', 'baseline_score'}.
    Baseline scores are comparable only for the same brief and design priority.
    Lower is better. Invalid/incomplete candidates are excluded, not repaired.
    """
    w = weights or {"circulation": 0.25, "unallocated_review": 0.25,
                    "elongation_review": 0.15}
    if set(w) != {"circulation", "unallocated_review", "elongation_review"} or any(
            not isinstance(v, (int, float)) or not 0 <= v <= 10 for v in w.values()):
        raise ValueError("invalid weights")
    rows = []
    for item in candidates:
        audit = assess_candidate(item["model"])
        baseline = float(item["baseline_score"])
        if not __import__("math").isfinite(baseline):
            raise ValueError("baseline score must be finite")
        eligible = audit["eligible_for_ranking"]
        penalty = (sum(w[k] * audit["score_terms"][k] for k in w)
                   if eligible else None)
        rows.append({"candidate_id": item["candidate_id"],
                     "baseline_score": baseline, "space_audit": audit,
                     "experimental_penalty": round(penalty, 6) if eligible else None,
                     "experimental_score": round(baseline + penalty, 6)
                     if eligible else None})
    rows.sort(key=lambda r: (not r["space_audit"]["eligible_for_ranking"],
                            r["experimental_score"] if r["experimental_score"] is not None
                            else float("inf"), str(r["candidate_id"])))
    return {"mode": "OPT_IN_DIAGNOSTIC_ONLY", "ranked": rows,
            "baseline_unchanged": True, "approved_for_export": False}
