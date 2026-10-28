"""ASSL opt-in space optimization: ranking existing geometries, not geometric repair.

Pre-materialization ranks search layouts; post-generation ranks validated variants.
Never weakens the generator's hard checks, changes legal rules, or replaces user program.
"""
from __future__ import annotations
import json
import math
from .core import ROOT

SUPPORTED = {"bedroom": "ordinary_bedroom", "master": "master_bedroom",
             "majlis": "men_guest_council", "living": "family_living",
             "kitchen": "kitchen"}

def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

def _guidelines():
    return json.loads((ROOT / "design_guidelines.draft.json").read_text(encoding="utf-8"))["profiles"]

def room_quality(room, *, gross_dimensions=False, wall_thickness=0.0, profiles=None):
    """Request-aware, non-legal penalty for disproportion and excess area."""
    kind = room.get("kind")
    if not room.get("request_id") or kind not in SUPPORTED:
        return {"applicable": False, "penalty": 0.0}
    w, d = room.get("width"), room.get("depth")
    if not (_number(w) and _number(d)):
        return {"applicable": True, "penalty": 0.0, "measurement_status": "UNRESOLVED"}
    if gross_dimensions:
        w -= wall_thickness
        d -= wall_thickness
    if w <= 0 or d <= 0:
        return {"applicable": True, "penalty": 0.0, "measurement_status": "UNRESOLVED"}
    p = (profiles or _guidelines())[SUPPORTED[kind]]
    requested = room.get("min_area")
    if not _number(requested):
        return {"applicable": True, "penalty": 0.0, "measurement_status": "UNRESOLVED"}
    area, aspect = w*d, max(w,d)/min(w,d)
    preferred = p.get("preferred_aspect_ratio_max", 1.85)
    # A client's larger minimum takes precedence over the internal advisory maximum.
    upper = max(float(p["advisory_max_m2"]), requested*1.08)
    excess = max(0.0, area-upper)
    slender = max(0.0, aspect-preferred)
    penalty = 1.8*excess + 18.0*slender*slender
    return {"applicable": True, "penalty": round(penalty,6),
            "measurement_status": "MEASURED", "net_area_m2": round(area,5),
            "aspect_ratio": round(aspect,5), "requested_min_m2": requested,
            "violates_requested_min_area": area+1e-6 < requested,
            "advisory_max_m2": p["advisory_max_m2"],
            "excess_above_request_aware_target_m2": round(excess,5),
            "proportion_penalty": round(18.0*slender*slender,5)}

def score_layout(layout, *, wall_thickness):
    """Score a pre-wall search layout. Hall area is NOT pedestrian-path union."""
    base = layout.get("score")
    if not _number(base):
        raise ValueError("Missing original search score")
    profiles = _guidelines()
    measures = [room_quality(r,gross_dimensions=True,
                             wall_thickness=wall_thickness,profiles=profiles)
                for floor in layout.get("floors",()) for r in floor]
    incomplete = sum(x.get("measurement_status")=="UNRESOLVED" for x in measures)
    warning = sum(x.get("penalty",0.0) for x in measures)
    halls = sum(max(0,h["width"])*max(0,h["depth"])
                for floor in layout.get("halls_by_floor",()) for h in floor)
    return {"base_score":round(base,6),"room_penalty":round(warning,6),
            "hall_rectangle_proxy_m2":round(halls,5),
            "unresolved_rooms":incomplete,
            "assl_rank_score":round(base+warning+.25*halls,6),
            "geometry_modified":False,"legal_compliance_certified":False}

def _protected_statuses(model):
    checks = model.get("checks",[])
    protected = {"guest-route","guest-distributor-access","V4-furniture-clearance"}
    return {item["check_id"]:item.get("status") for item in checks
            if item.get("check_id") in protected or
            any(word in item.get("check_id","").lower()
                for word in ("daylight","ventilation"))}

def rank_existing_candidates(candidates, *, max_circulation_increase_m2=0.0):
    """Conservative read-only choice among validated alternatives of same program.

    The original first candidate is baseline. Do not recommend a geometry that
    regresses built area, circulation, or protected check statuses.
    """
    if not _number(max_circulation_increase_m2):
        raise ValueError("Invalid circulation tolerance")
    profiles = _guidelines()
    rows = []
    for index,c in enumerate(candidates):
        failed = [check.get("check_id") for check in c.get("checks",[])
                  if check.get("status")=="FAIL"]
        eligible = c.get("release",{}).get("drawing_export_allowed") is True and not failed
        metrics=c.get("metrics",{})
        built=metrics.get("floor_built_by_id",{})
        gross=sum(built.values()) if isinstance(built,dict) and built and all(_number(v) for v in built.values()) else None
        circulation=metrics.get("circulation_m2")
        measures=[room_quality(r,profiles=profiles)
                  for f in c.get("floors",[]) for r in f.get("rooms",[])]
        unresolved=any(m.get("measurement_status")=="UNRESOLVED" for m in measures)
        minimum_area_breached=any(m.get("violates_requested_min_area") for m in measures)
        if not (_number(gross) and _number(circulation)) or unresolved or minimum_area_breached:
            eligible=False
        penalty=sum(m["penalty"] for m in measures)
        score=round(gross+.35*circulation+penalty,5) if _number(gross) and _number(circulation) else None
        rows.append({"original_index":index,"candidate_id":c.get("candidate_id"),
                     "revision_id":c.get("model_revision_id"),"eligible":eligible,
                     "failed_checks":failed,"score":score,
                     "gross_built_m2":gross,"circulation_m2":circulation,
                     "room_penalty":round(penalty,5),
                     "unresolved_rooms":unresolved,
                     "min_area_breached":minimum_area_breached,
                     "protected_checks":_protected_statuses(c),
                     "safe_vs_baseline":False})
    baseline=rows[0] if rows else None
    if baseline and baseline["eligible"]:
        for row in rows:
            if not row["eligible"]:continue
            same_program=candidates[row["original_index"]].get("brief")==candidates[0].get("brief")
            no_gross=row["gross_built_m2"]<=baseline["gross_built_m2"]+1e-6
            no_circulation=row["circulation_m2"]<=baseline["circulation_m2"]+max_circulation_increase_m2+1e-6
            protected=all(row["protected_checks"].get(name)==status
                          for name,status in baseline["protected_checks"].items())
            row["safe_vs_baseline"]=same_program and no_gross and no_circulation and protected
    safe=sorted((r for r in rows if r["safe_vs_baseline"]),
                key=lambda r:(r["score"],r["original_index"]))
    for rank,row in enumerate(safe,1):row["safe_rank"]=rank
    return {"ranking":rows,
            "recommended_revision_id":safe[0]["revision_id"] if safe else None,
            "recommended_original_index":safe[0]["original_index"] if safe else None,
            "baseline_revision_id":baseline["revision_id"] if baseline else None,
            "mode":"SAFE_EXISTING_ALTERNATIVE_RECOMMENDATION",
            "geometry_modified":False,"legal_compliance_certified":False,
            "does_not_verify_unresolved_checks":True}
