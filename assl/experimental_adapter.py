"""Read-only bridge from existing VillaBrief/model into ASSL draft diagnostics.

Not imported by production generator. Never mutates brief, geometry or release gates.
"""
from .core import resolve_rules, validate_metrics, score_room

def inspect_candidate(brief, model):
    country = brief.country
    room_results = []
    for floor in model.get("floors", []):
        for room in floor.get("rooms", []):
            if room.get("kind") not in ("bedroom", "master", "majlis", "living", "kitchen"):
                continue
            dims = score_room(room["kind"], room.get("width"), room.get("depth"))
            room_results.append({"floor_id": floor.get("id"), "room_id": room.get("id"),
                                 "kind": room["kind"], **dims})
    # Brief setbacks are customer-entered, NOT municipal approvals.
    # Therefore no legal PASS is inferred from them.
    rules = resolve_rules(country, context={"space_type": "habitable_room"})
    legal = validate_metrics(rules, {})
    return {"revision": "assl-experimental-0.2",
            "mode": "READ_ONLY_NOT_ENFORCING",
            "country": country,
            "legal_checks": legal,
            "design_rooms": room_results,
            "design_warnings": sum(r["status"] == "DESIGN_WARNING" for r in room_results),
            "legal_approval": False,
            "generation_modified": False}
