"""Measured functional relationships for V3 option ranking.

Door graph topology comes from the geometric model, rather than from proximity
between labels. The resulting heuristics are NOT legal egress/circulation checks.
"""
import math
from .reference_patterns import graph, route
from .general_quality import privacy_evidence

RELATIONSHIPS=(
    ("kitchen", "dining", 1.0, "FOOD_SERVICE"),
    ("living", "dining", .9, "FAMILY_COMMON"),
    ("master", "bathroom", .8, "MASTER_BATH_ACCESS"),
    ("bedroom", "bathroom", .7, "FAMILY_BATH_ACCESS"),
)


def inspect(model):
    routes=[]
    for floor in model.get("floors", ()):
        rooms, doors = graph(floor)
        required=[r for r in rooms.values() if r.get("request_id") and
                  r.get("zone")!="guest"]
        for source_kind, target_kind, weight, relation_id in RELATIONSHIPS:
            source=[r for r in required if r["kind"]==source_kind]
            targets=[r for r in required if r["kind"]==target_kind]
            for a in source:
                if not targets:
                    continue  # A preferred relation is not a requirement to add a room.
                candidates=[]
                for b in targets:
                    if a["id"]==b["id"]:continue
                    distance=route(rooms,doors,a["id"],b["id"])
                    if distance is not None:
                        straight=math.dist(
                            (a["x"]+a["width"]/2,a["y"]+a["depth"]/2),
                            (b["x"]+b["width"]/2,b["y"]+b["depth"]/2))
                        candidates.append((distance,b,straight))
                if not candidates:
                    routes.append(dict(id=relation_id, floor=floor["id"], from_id=a["id"],
                                       target_kind=target_kind,status="UNREACHABLE",
                                       route_m=None,detour_ratio=None,weight=weight))
                    continue
                distance,b,straight=min(candidates,key=lambda q:q[0])
                routes.append(dict(id=relation_id,floor=floor["id"],from_id=a["id"],
                                   to_id=b["id"],target_kind=target_kind,status="MEASURED",
                                   route_m=round(distance,3),
                                   detour_ratio=round(distance/max(straight,.1),3),
                                   weight=weight))
    # Measure kitchen-to-dining detours separately from guest/family circulation.
    # A large detour is a preference warning, not proof of a regulatory failure.
    service_detours=[r for r in routes if r["id"]=="FOOD_SERVICE" and
                     r["status"]=="MEASURED" and r["detour_ratio"]>2.5]
    private = privacy_evidence(model) if model.get("floors") else {
        "family_rooms_exposed":[], "missing_guest_access":[]}
    failures=[item for item in routes if item["status"]=="UNREACHABLE"]
    excessive=[item for item in routes if item["status"]=="MEASURED"
               and item["detour_ratio"]>2.5]
    exposure=private["family_rooms_exposed"]
    # Soft design objective only; hard failures remain with validators.
    weight=sum(item["weight"] for item in routes) or 1
    cost=sum(item["weight"] * (4 if item["status"]=="UNREACHABLE" else
                min(2,max(0,item["detour_ratio"]-1.5))) for item in routes)
    cost+=3*len(exposure)
    return {
        "version":"functional-relations-1",
        "evaluated_relations":len(routes),"routes":routes,
        "unreachable":failures,"long_detours":excessive,
        "guest_family_exposure":list(exposure),
        "guest_access_unreachable":private.get("missing_guest_access",[]),
        "food_service_detours":service_detours,
        "soft_penalty":round(min(cost/(weight*4),1),6),
        "scope":"Hosted door graph only; acoustic, visual sightline and fire egress remain unverified",
    }


def repair_reasons(model):
    """Evidence-driven diagnoses; never silently remove a room to clear a failure."""
    bad={str(row.get("check_id")) for row in model.get("checks",())
         if row.get("status")=="FAIL"}
    suggestions=[]
    for group, codes in (
        ("guest_circulation", {"guest-route","guest-distributor-access","guest-distributor-geometry"}),
        ("openings_and_sweeps", {"GF-door-sweeps","FF-door-sweeps","GF-openings","FF-openings"}),
        ("family_movement", {"GF-walkability","FF-walkability","REF-functional-route"}),
        ("site_and_massing", {"GF-site","FF-site","GF-massing-connected","FF-massing-connected"}),
        ("furnishing", {"GF-fixtures","FF-fixtures","GF-beds","FF-beds"}),
        ("natural_windows", {"GF-windows","FF-windows"}),
        ("vertical_core", {"stair-geometry","vertical-core"}),
    ):
        if bad & codes:suggestions.append(group)
    evidence=inspect(model)
    if evidence["unreachable"] and "family_movement" not in suggestions:
        suggestions.append("family_movement")
    if evidence["food_service_detours"]:
        suggestions.append("food_service_detour")
    if evidence["guest_family_exposure"] and "guest_circulation" not in suggestions:
        suggestions.append("guest_circulation")
    if not suggestions and bad:suggestions.append("other_existing_validation")
    return suggestions
