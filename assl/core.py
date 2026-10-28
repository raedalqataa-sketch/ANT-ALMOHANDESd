"""ASSL v0.2: pure, opt-in resolution and evaluation; never certifies legal compliance."""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALID_COUNTRIES = {"SA", "YE"}
SUPPORTED_OPERATORS = {">=", "<=", "=="}
CONFIRMED = {"VERIFIED_PRIMARY_CURRENT", "VERIFIED_PRIMARY_CURRENT_TEXT"}

def load_rules(path=None):
    data = json.loads(Path(path or ROOT / "rules.draft.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != "0.2.0" or not isinstance(data.get("rules"), list):
        raise ValueError("Unsupported ASSL rule schema")
    ids = [r["id"] for r in data["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ASSL rule IDs")
    return data

def resolve_rules(country, *, context=None, ruleset=None, local_values=None):
    """Select matching rules; do not infer local limits from site descriptions.

    Local values are caller-supplied evidence only, NOT automatically authenticated.
    """
    if country not in VALID_COUNTRIES:
        raise ValueError("Country must be SA or YE")
    data = ruleset if ruleset is not None else load_rules()
    context = context or {}
    local_values = local_values or {}
    output = []
    for original in data["rules"]:
        if original.get("country") not in (country, "*"):
            continue
        applies = original.get("applies_when", {})
        if any(context.get(k) != v for k, v in applies.items()):
            continue
        rule = dict(original)
        if rule.get("verification_status") == "LOCAL_DYNAMIC":
            provided = local_values.get(rule["id"])
            if isinstance(provided, dict) and provided.get("approved") is True and provided.get("source_url") and _finite(provided.get("value")):
                rule["value"] = provided["value"]
                rule["local_evidence"] = {"source_url": provided["source_url"], "approved": True}
                rule["resolution_status"] = "RESOLVED_LOCAL_EVIDENCE"
            else:
                rule["resolution_status"] = "UNRESOLVED"
        else:
            rule["resolution_status"] = "RESOLVED_DRAFT" if _finite(rule.get("value")) else "UNRESOLVED"
        output.append(rule)
    return output

def _finite(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0

def validate_metrics(rules, metrics, *, enforcement_enabled=False):
    """Never label an unverified rule PASS/FAIL as legal compliance.

    DRAFT_COMPARISON is informative only. UNRESOLVED never means PASS.
    """
    results = []
    for rule in rules:
        metric = rule["metric"]
        actual = metrics.get(metric)
        limit = rule.get("value")
        status = rule.get("verification_status")
        approved = status in CONFIRMED or rule.get("resolution_status") == "RESOLVED_LOCAL_EVIDENCE"
        if rule.get("resolution_status") == "UNRESOLVED" or not _finite(limit):
            outcome = "UNRESOLVED"
        elif not _finite(actual):
            outcome = "UNRESOLVED"
        elif rule.get("operator") not in SUPPORTED_OPERATORS:
            outcome = "UNRESOLVED"
        else:
            passed = {">=": lambda: actual + 1e-9 >= limit,
                      "<=": lambda: actual <= limit + 1e-9,
                      "==": lambda: abs(actual - limit) <= 1e-9}[rule["operator"]]()
            outcome = ("PASS" if passed else "FAIL") if (approved and enforcement_enabled and rule.get("enforcement") != "disabled") else ("DRAFT_MATCH" if passed else "DRAFT_MISMATCH")
        results.append({"rule_id": rule["id"], "metric": metric, "actual": actual,
                        "required": limit, "status": outcome,
                        "source_id": rule.get("source_id"), "verification_status": status,
                        "legal_compliance_certified": False})
    return results

def score_room(kind, width, depth, *, guidelines=None):
    """Non-legal geometric design signals, not code checks."""
    if not _finite(width) or not _finite(depth) or min(width, depth) <= 0:
        return {"status": "UNRESOLVED", "reasons": ["invalid_dimensions"]}
    data = guidelines or json.loads((ROOT / "design_guidelines.draft.json").read_text(encoding="utf-8"))
    profile = {"bedroom": "ordinary_bedroom", "master": "master_bedroom",
               "majlis": "men_guest_council", "living": "family_living",
               "kitchen": "kitchen"}.get(kind)
    if profile is None:
        return {"status": "NOT_APPLICABLE", "reasons": []}
    p = data["profiles"][profile]
    area, ratio = width * depth, max(width, depth) / min(width, depth)
    reasons = []
    if area < p["design_min_m2"]: reasons.append("below_design_min")
    if area > p["advisory_max_m2"]: reasons.append("above_advisory_max")
    if ratio > p.get("warning_aspect_ratio_above", 2.0): reasons.append("elongated_room")
    return {"status": "DESIGN_WARNING" if reasons else "DESIGN_ACCEPTABLE",
            "area_m2": round(area, 4), "aspect_ratio": round(ratio, 4),
            "reasons": reasons, "is_legal_assessment": False}
