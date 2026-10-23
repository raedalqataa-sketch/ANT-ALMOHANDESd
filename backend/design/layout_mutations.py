"""Bounded room moves and boundary resizing BEFORE materialization.

Source is unapproved search-space cells, never walls/doors from an approved
drawing. All derived walls, openings, stairs, windows and furniture must be
rebuilt from each mutation and validated before a candidate can be returned.
"""
import copy
import math

TOL=1e-6


def _editable(r):
    return bool(r.get("request_id")) and r.get("zone")!="guest" and not (
        r.get("guest_parent") or r.get("guest_distributor")) and r.get("kind")!="stair"


def _fits(room, footprint, wall_thickness):
    cross=footprint["width"]-wall_thickness
    length=footprint["depth"]-wall_thickness
    if min(cross,length) < room["min_side"]-TOL:return False
    if cross*length < room["min_area"]-TOL:return False
    if room.get("kind")=="dining" and cross < 3.45-TOL and room.get("door_side") in ("east","west"):
        return False
    if max(cross,length)/max(min(cross,length),TOL)>2.8+TOL:return False
    return True


def mutation_variants(layout, wall_thickness, *, limit=6):
    """Yield a few deterministic transactional alternatives of the same program.

    A swap moves whole room programs between two existing physical cells in
    the *same lane*. A resize moves a shared boundary up to 0.6 m; the second
    room moves as its usable depth changes. Corridor/receptive rooms untouched.
    """
    if layout.get("release", {}).get("status") in ("APPROVED", "LOCKED"):
        raise ValueError("cannot mutate an approved or locked design")
    if limit<=0:return
    base={k:v for k,v in layout.items() if k!="alternatives"}
    floors=base.get("floors",())
    made=0
    for floor_index, cells in enumerate(floors):
        for i,first in enumerate(cells):
            if not _editable(first) or first.get("door_side") not in ("east","west"):
                continue
            for j in range(i+1,len(cells)):
                second=cells[j]
                if not _editable(second) or second.get("door_side")!=first["door_side"]:
                    continue
                if abs(first["x"]-second["x"])>TOL or abs(first["width"]-second["width"])>TOL:
                    continue
                # Only reflow in the same room strip, not across courtyard/
                # guest corridor or stair cells.
                geometry_fields=("x","y","width","depth")
                if _fits(first,second,wall_thickness) and _fits(second,first,wall_thickness):
                    alt=copy.deepcopy(base)
                    a,b=alt["floors"][floor_index][i],alt["floors"][floor_index][j]
                    first_shape={k:a[k] for k in geometry_fields}
                    for k in geometry_fields:a[k]=b[k]
                    for k in geometry_fields:b[k]=first_shape[k]
                    alt["local_reflow"]={"operation":"swap_room_locations",
                        "floor":floor_index,"room_ids":[first["id"],second["id"]]}
                    yield alt
                    made+=1
                    if made>=limit:return
                if abs(first["y"]+first["depth"]-second["y"])>TOL:
                    continue
                for shift in (0.45,-0.45):
                    a1={**first,"depth":first["depth"]+shift}
                    b1={**second,"y":second["y"]+shift,"depth":second["depth"]-shift}
                    if min(a1["depth"],b1["depth"])<=wall_thickness:continue
                    if not _fits(first,a1,wall_thickness) or not _fits(second,b1,wall_thickness):
                        continue
                    alt=copy.deepcopy(base)
                    a,b=alt["floors"][floor_index][i],alt["floors"][floor_index][j]
                    a["depth"]+=shift
                    b["y"]+=shift
                    b["depth"]-=shift
                    alt["local_reflow"]={"operation":"shift_shared_room_boundary",
                        "floor":floor_index,"room_ids":[first["id"],second["id"]],
                        "delta_m":shift}
                    yield alt
                    made+=1
                    if made>=limit:return
