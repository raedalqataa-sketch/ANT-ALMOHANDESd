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
    if limit<=0:return
    base={k:v for k,v in layout.items() if k!="alternatives"}
    floors=base.get("floors",())
    made=0
    # Moving both shared boundaries translates the middle room without
    # shrinking it. A single-boundary move may fail its area constraint even
    # when the two outer rooms have enough spare depth.
    for floor_index,cells in enumerate(floors):
        for first_index,first in enumerate(cells):
            if not _editable(first) or first.get("door_side") not in ("east","west"):
                continue
            lane=[(index,room) for index,room in enumerate(cells)
                  if _editable(room) and room.get("door_side")==first["door_side"]
                  and abs(room["x"]-first["x"])<=TOL
                  and abs(room["width"]-first["width"])<=TOL]
            lane.sort(key=lambda item:item[1]["y"])
            for triple in zip(lane,lane[1:],lane[2:]):
                (ai,a),(bi,b),(ci,c)=triple
                if ai!=first_index:
                    continue
                if abs(a["y"]+a["depth"]-b["y"])>TOL or abs(b["y"]+b["depth"]-c["y"])>TOL:
                    continue
                for shift in (0.45,-0.45):
                    first_shape={**a,"depth":a["depth"]+shift}
                    last_shape={**c,"y":c["y"]+shift,"depth":c["depth"]-shift}
                    if not _fits(a,first_shape,wall_thickness) or not _fits(c,last_shape,wall_thickness):
                        continue
                    alt=copy.deepcopy(base)
                    left,middle,right=(alt["floors"][floor_index][index] for index in (ai,bi,ci))
                    left["depth"]+=shift
                    middle["y"]+=shift
                    right["y"]+=shift
                    right["depth"]-=shift
                    alt["local_reflow"]={"operation":"redistribute_three_room_boundaries",
                        "floor":floor_index,"room_ids":[a["id"],b["id"],c["id"]],"delta_m":shift}
                    yield alt
                    made+=1
                    if made>=limit:return
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
