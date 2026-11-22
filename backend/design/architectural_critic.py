"""Non-mutating architectural critique from measured space-efficiency evidence.

This module proposes repairs but NEVER edits a plan or claims buildability.
"""
from __future__ import annotations

from .space_efficiency_ranking import assess_candidate


def critique(model):
    report = assess_candidate(model)
    if not report.get("eligible_for_ranking"):
        return {"status": report["status"], "issues": [],
                "blocked": True, "reason": report.get("reason", "INVALID_GEOMETRY"),
                "repairs_applied": 0}
    issues = []
    for floor in report["floors"]:
        fid = floor["floor"]
        for room in floor["elongated_room_reviews"]:
            issues.append({"floor": fid, "type": "ELONGATED_ROOM",
                           "room_id": room["room_id"], "severity": "REVIEW",
                           "evidence": {"aspect_ratio": room["ratio"]},
                           "suggestion": "Rebalance room width and depth; verify actual furniture and door clearance."})
        for pocket in floor["leftover_review_regions"]:
            issues.append({"floor": fid, "type": "UNASSIGNED_REGION",
                           "severity": "REVIEW", "evidence": pocket,
                           "suggestion": "Classify as wall, intentional void, service, or unused area before optimizing."})
    return {"status": "REVIEW" if issues else "MEASURED",
            "issues": issues, "blocked": False, "repairs_applied": 0,
            "audit": report,
            "limitations": "No furniture, privacy, ventilation, daylight or actual walk-path proof. No automatic repair."}


def compare_revisions(before, after):
    """Report measurable differences; do not declare improvement without all checks."""
    a, b = critique(before), critique(after)
    if a["blocked"] or b["blocked"]:
        return {"status": "BLOCKED", "before": a, "after": b}
    am, bm = a["audit"], b["audit"]
    return {"status": "MEASURED_NOT_APPROVED",
            "delta_corridor_union_m2": round(bm["corridor_union_m2"]-am["corridor_union_m2"], 4),
            "delta_leftover_review_m2": round(bm["leftover_review_m2"]-am["leftover_review_m2"], 4),
            "delta_elongated_room_count": bm["elongated_room_review_count"]-am["elongated_room_review_count"],
            "before_issues": a["issues"], "after_issues": b["issues"],
            "requires": ["identical site and program", "unchanged locked elements",
                         "furniture clearance", "privacy", "natural light and ventilation",
                         "door and walk-path verification", "PDF/DXF visual review"]}
