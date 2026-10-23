"""Evidence of transactional whole-plan rebuilding instead of unsafe room edits.

A repair replaces a *rejected draft candidate* with a newly materialized plan.
All walls, doors, furniture, stairs and corridor cells are re-derived and
revalidated. Accepted/signed or locked plans must never be changed in place.
"""
import math
from collections import Counter

from .general_geometry import union_polygons, signed_area

LOCKED_STATUSES=frozenset(("APPROVED","LOCKED","EXECUTIVE_ISSUED"))


def _rooms(model):
    return {r["id"]:r for floor in model.get("floors",())
            for r in floor.get("rooms",()) if r.get("request_id")}


def _corridors(model):
    return [r for f in model.get("floors",()) for r in f.get("cells",())
            if r.get("kind")=="corridor" and not r.get("guest_distributor")]


def replacement_evidence(rejected, rebuilt, *, min_delta_m=.05):
    """Describe a complete re-layout and refuse a program or approval downgrade."""
    if rejected.get("status") in LOCKED_STATUSES:
        raise ValueError("cannot rebuild an approved or locked design")
    if rejected.get("brief") != rebuilt.get("brief"):
        raise ValueError("cannot silently change the approved client brief")
    a,b=_rooms(rejected),_rooms(rebuilt)
    if set(a)!=set(b):
        raise ValueError("room count and program IDs cannot change in a re-layout")
    if any(a[k].get("kind")!=b[k].get("kind") or
           a[k].get("request_id")!=b[k].get("request_id") or
           a[k].get("floor_id")!=b[k].get("floor_id") or
           a[k].get("capacity")!=b[k].get("capacity") for k in a):
        raise ValueError("room type, floor and capacity cannot change")
    if not rebuilt.get("release",{}).get("drawing_export_allowed"):
        raise ValueError("replacement candidate has not passed geometric checks")
    if any(c.get("status")=="FAIL" for c in rebuilt.get("checks",())):
        raise ValueError("replacement contains a failed check")
    relocated=[];resized=[]
    for key in sorted(a):
        before,after=a[key],b[key]
        displacement=math.dist(
            (before["x"]+before["width"]/2,before["y"]+before["depth"]/2),
            (after["x"]+after["width"]/2,after["y"]+after["depth"]/2))
        area_change=after["width"]*after["depth"]-before["width"]*before["depth"]
        if displacement>min_delta_m:
            relocated.append({"id":key,"center_move_m":round(displacement,3)})
        if abs(area_change)>.05 or any(abs(after[k]-before[k])>min_delta_m for k in ("width","depth")):
            resized.append({"id":key,"net_area_change_m2":round(area_change,3),
                            "width_from_to_m":[round(before["width"],3),round(after["width"],3)],
                            "depth_from_to_m":[round(before["depth"],3),round(after["depth"],3)]})
    corridors_before=_corridors(rejected);corridors_after=_corridors(rebuilt)
    def area(rows):
        polygons=union_polygons(rows) if rows else []
        return round(sum(signed_area(p) for p in polygons),3)
    return {
        "status":"REBUILT_DRAFT_AFTER_VALIDATION",
        "method":"re-search + re-materialize all walls/openings/furniture + full checks",
        "previous_revision":rejected.get("model_revision_id"),
        "new_revision":rebuilt.get("model_revision_id"),
        "relocated_rooms":relocated,
        "resized_rooms":resized,
        "corridor_rebuild":{
            "before_count":len(corridors_before),"after_count":len(corridors_after),
            "before_area_m2":area(corridors_before),
            "after_area_m2":area(corridors_after),
        },
        "unchanged_client_brief":True,
        "code_and_execution_approval":False,
    }
