"""Distinct compact circulation nuclei for room-first architectural packing.

Topologies vary the actual reserved corridor graph (not just scoring or label).
Rotation maps the entrance spur onto the explicitly requested plot frontage.
Every proposal remains concept-only until placed doors, windows and paths pass
the downstream validators.
"""
from __future__ import annotations
from .concept_quality_v2 import edge_contact, hall_shape

EPS=1e-6

def local_envelope(width,depth,entrance_face):
    if entrance_face in ("east","west"):
        return depth,width
    return width,depth

def transform_rectangle(item,width,depth,entrance_face):
    """From south-entry local rectangle to selected street-side coordinates."""
    r=dict(item)
    x,y,w,d=(item[k] for k in ("x","y","width","depth"))
    if entrance_face=="north":
        r.update(x=width-x-w,y=depth-y-d)
    elif entrance_face=="east":
        # Local width == physical depth; local depth == physical width.
        r.update(x=depth-y-d,y=x,width=d,depth=w)
    elif entrance_face=="west":
        r.update(x=y,y=width-x-w,width=d,depth=w)
    elif entrance_face!="south":
        raise ValueError("INVALID_ENTRANCE_FACE")
    return {k:round(v,4) if k in ("x","y","width","depth") else v
            for k,v in r.items()}

def transform_candidate(layout,local_w,local_d,entrance_face):
    if entrance_face=="south":
        return {"floors":layout["floors"],
                "halls_by_floor":layout["halls_by_floor"]}
    return {
        "floors":[[transform_rectangle(r,local_w,local_d,entrance_face)
                   for r in floor] for floor in layout["floors"]],
        "halls_by_floor":[[transform_rectangle(r,local_w,local_d,entrance_face)
                           for r in floor] for floor in layout["halls_by_floor"]],
    }

def attach_core_nodes(rect_factory,core_halls,stair,width,depth,style):
    """Construct genuinely different *connected* compact movement graphs."""
    if style=="axial":
        return [dict(h) for h in core_halls]
    if style not in ("elbow","split_hub"):
        raise ValueError("UNKNOWN_CORE_TOPOLOGY")
    hub=core_halls[0]
    hx,hy=hub["x"],hub["y"]
    # Exit via the rear stem well beyond the staircase's 4.6m depth,
    # not through the guest suite and not through the shared stair.
    # Shorter offset gallery on compact lots. It must share at least 1.2m
    # with the rear stem and lie below the staircase's actual south edge.
    arm_width=2.25 if width<20. else 3.
    arm=rect_factory(hx+2.,hy+3.75,arm_width,1.5,
                     kind="corridor",id="side-gallery",core_role="cross-link")
    # arm touches rear corridor along its west wall, independently of
    # room positions. Separate family routing, not a guest access door.
    new=[dict(h) for h in core_halls]+[arm]
    if style=="split_hub":
        satellite_width=2. if width<20. else 2.5
        satellite_depth=2.25 if width<20. else 2.5
        satellite=rect_factory(hx+2.+arm_width,hy+3.75,
                               satellite_width,satellite_depth,
                               kind="corridor",id="secondary-family-hub",
                               core_role="satellite")
        new.append(satellite)
    if any(r["x"]<-EPS or r["y"]<-EPS or
           r["x"]+r["width"]>width+EPS or
           r["y"]+r["depth"]>depth+EPS for r in new):
        return None
    if any(overlap_area_rect(r,stair)>EPS for r in new):
        return None
    if not all(any(edge_contact(r,other)>=1.2-EPS
                   for j,other in enumerate(new) if i!=j)
               for i,r in enumerate(new)):
        return None
    if hall_shape(new)["components"]!=1:
        return None
    return new

def overlap_area_rect(a,b):
    return max(0,min(a["x"]+a["width"],b["x"]+b["width"])-max(a["x"],b["x"])) * max(
        0,min(a["y"]+a["depth"],b["y"]+b["depth"])-max(a["y"],b["y"]))

def structural_evidence(rooms_by_floor,halls_by_floor,style,face):
    """Only observable geometric attributes count as diversity evidence."""
    profiles=[];neighbor_patterns=[];active_nodes=[]
    for rooms,halls in zip(rooms_by_floor,halls_by_floor):
        info=hall_shape(halls)
        profiles.append({"corridor_segments":info["segments"],
                         "pattern":info["pattern"],
                         "max_straight_run_m":info["max_straight_run_m"],
                         "hall_union_area_m2":info["union_area_m2"],
                         "connected_components":info["components"]})
        # Geometry-based room to hall incidence. Ignore room names in the
        # fingerprint so cosmetic naming cannot inflate structural novelty.
        counts=sorted(sum(edge_contact(room,h)>=.9-EPS for room in rooms
                          if room.get("request_id") and room.get("zone")!="guest")
                      for h in halls)
        neighbor_patterns.append(tuple(counts))
        roles=[]
        for hall in halls:
            role=hall.get("core_role")
            if not role:continue
            attached=[r.get("id") for r in rooms
                      if r.get("request_id") and r.get("zone")!="guest"
                      and edge_contact(r,hall)>=.9-EPS]
            roles.append({"core_role":role,"family_rooms_served":attached,
                          "serves_requested_room":bool(attached)})
        active_nodes.append(roles)
    # A reported core style alone is never evidence of genuine novelty.
    geometric_signature=tuple((p["corridor_segments"],p["pattern"],j)
                              for p,j in zip(profiles,neighbor_patterns))
    return {"topology_style":style,"entrance_face":face,
            "by_floor":profiles,
            "room_hall_incidence":neighbor_patterns,
            "special_core_access_by_floor":active_nodes,
            "distinctive_nodes_actually_serve_rooms":all(
                any(node["serves_requested_room"] for roles in active_nodes
                    for node in roles if node["core_role"]==target)
                for target in (("cross-link",) if style=="elbow" else
                               ("cross-link","satellite") if style=="split_hub" else ())),
            "geometric_graph_signature":str(geometric_signature),
            "actual_doors_checked":False,
            "architectural_distinctness_certified":False}

def compare_structural_evidence(first,second):
    """Reports actual differences; no unsupported categorical 'radical' PASS."""
    a,b=first["by_floor"],second["by_floor"]
    count=max(len(a),len(b))
    segment_distance=sum(abs(x["corridor_segments"]-y["corridor_segments"])
                         for x,y in zip(a,b))
    maxrun_distance=sum(abs(x["max_straight_run_m"]-y["max_straight_run_m"])
                        for x,y in zip(a,b))
    incidence_changed=(first["room_hall_incidence"]!=second["room_hall_incidence"])
    different_signature=(first["geometric_graph_signature"]!=
                         second["geometric_graph_signature"])
    return {"different_measured_geometry":different_signature,
            "segment_count_delta":segment_distance,
            "max_straight_run_delta_m":round(maxrun_distance,4),
            "different_room_access_distribution":incidence_changed,
            "different_reported_styles":first["topology_style"]!=second["topology_style"],
            "unproven_radical_difference":True}
