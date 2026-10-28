"""Second-stage furniture-free architectural concept quality.

No visual objects, room program changes, or legal certification. Measures
hall shape/connectivity, functional proximity, reserved stair adjacency and
guest distributor. Scores are comparative heuristic, not a building code.
"""
from __future__ import annotations


EPS=1e-6


def bounds(r):
    return r["x"],r["y"],r["x"]+r["width"],r["y"]+r["depth"]


def edge_contact(a,b):
    ax0,ay0,ax1,ay1=bounds(a);bx0,by0,bx1,by1=bounds(b)
    if abs(ax1-bx0)<=EPS or abs(ax0-bx1)<=EPS:
        return max(0.,min(ay1,by1)-max(ay0,by0))
    if abs(ay1-by0)<=EPS or abs(ay0-by1)<=EPS:
        return max(0.,min(ax1,bx1)-max(ax0,bx0))
    return 0.


def _touch(a,b):
    if edge_contact(a,b)>EPS:return True
    ax0,ay0,ax1,ay1=bounds(a);bx0,by0,bx1,by1=bounds(b)
    return min(ax1,bx1)-max(ax0,bx0)>EPS and min(ay1,by1)-max(ay0,by0)>EPS


def union_area(rects):
    """Exact (within floating-point precision) orthogonal rectangle union."""
    if not rects:return 0.
    xs=sorted({value for r in rects for value in (r["x"],r["x"]+r["width"])})
    total=0.
    for lo,hi in zip(xs,xs[1:]):
        if hi-lo<=EPS:continue
        spans=sorted((r["y"],r["y"]+r["depth"]) for r in rects
                     if r["x"]<hi-EPS and r["x"]+r["width"]>lo+EPS)
        end=None
        for a,b in spans:
            if end is None or a>end:
                total+=(hi-lo)*(b-a);end=b
            elif b>end:
                total+=(hi-lo)*(b-end);end=b
    return total


def hall_shape(halls):
    if not halls:
        return {"components":0,"segments":0,"union_area_m2":0.,
                "max_straight_run_m":0.,"long_run_excess_sq_m2":0.,
                "pattern":"NONE"}
    unseen=set(range(len(halls)));components=0
    while unseen:
        components+=1;stack=[unseen.pop()]
        while stack:
            i=stack.pop()
            linked={j for j in unseen if _touch(halls[i],halls[j])}
            unseen-=linked;stack.extend(linked)
    lengths=[max(h["width"],h["depth"]) for h in halls]
    axes={"horizontal" if h["width"]>=h["depth"] else "vertical" for h in halls}
    pattern=("LINEAR" if len(halls)==1 else
             "CONNECTED_BENDS_OR_JUNCTIONS" if len(axes)>1 else
             "PARALLEL_SEGMENTS")
    return {"components":components,"segments":len(halls),
            "union_area_m2":round(union_area(halls),4),
            "max_straight_run_m":round(max(lengths),4),
            "long_run_excess_sq_m2":round(sum(max(0.,length-10.)**2
                                               for length in lengths),4),
            "pattern":pattern}


def gap(a,b):
    ax0,ay0,ax1,ay1=bounds(a);bx0,by0,bx1,by1=bounds(b)
    return max(0.,bx0-ax1,ax0-bx1)+max(0.,by0-ay1,ay0-by1)


def relation_penalties(cells):
    requested=[r for r in cells if r.get("request_id") and r.get("zone")!="guest"]
    pairs=(("kitchen","dining",8.,1.8),("living","dining",4.,2.5),
           ("master","bathroom",2.,4.0),("bedroom","bathroom",1.,4.0))
    measurements=[];total=0.
    for a_kind,b_kind,weight,allowed in pairs:
        group_a=[r for r in requested if r.get("kind")==a_kind]
        group_b=[r for r in requested if r.get("kind")==b_kind]
        if not group_a or not group_b:continue
        distance=min(gap(a,b) for a in group_a for b in group_b)
        penalty=weight*max(0.,distance-allowed)
        measurements.append({"relation":f"{a_kind}:{b_kind}",
                             "nearest_boundary_gap_m":round(distance,4),
                             "penalty":round(penalty,4)})
        total+=penalty
    return total,measurements


def enrich_composition_quality(layout,wall_thickness,report):
    """Preserve hard room-size/facade tests; add measured quality + core checks."""
    floors=layout.get("floors",[])
    halls_by_floor=layout.get("halls_by_floor",[])
    summaries=[];relations=[];stair_centers=[];new_issues=[]
    functional_cost=0.;run_cost=0.;union_total=0.
    for floor_num,cells in enumerate(floors):
        halls=halls_by_floor[floor_num] if floor_num<len(halls_by_floor) else []
        hall=hall_shape(halls)
        union_total+=hall["union_area_m2"]
        run_cost+=hall["long_run_excess_sq_m2"]*2.2
        if hall["components"]>1:
            new_issues.append({"floor":floor_num,"reason":"DISCONNECTED_HALLWAY_SEGMENTS"})
        cost,relation=relation_penalties(cells)
        functional_cost+=cost
        relations.append({"floor":floor_num,"relations":relation})
        stairs=[r for r in cells if r.get("kind")=="stair"]
        stair_centers.append(stairs)
        if stairs and not any(edge_contact(stair,h)>=.90
                              for stair in stairs for h in halls):
            new_issues.append({"floor":floor_num,
                               "reason":"STAIR_CORE_WITHOUT_HALL_CONTACT_POTENTIAL"})
        guests=[r for r in cells if r.get("guest_distributor")]
        for guest in guests:
            connections=[r for r in cells if r.get("guest_vestibule")==guest.get("id")]
            if connections and any(edge_contact(guest,r)<.90 for r in connections):
                new_issues.append({"floor":floor_num,
                                   "reason":"GUEST_VESTIBULE_NOT_ADJACENT_TO_ASSOCIATED_ROOMS",
                                   "vestibule_id":guest.get("id")})
        summaries.append({"floor":floor_num,**hall,"reserved_stair_count":len(stairs),
                          "guest_distributor_count":len(guests)})
    if len(floors)>1:
        if any(len(stairs)!=1 for stairs in stair_centers):
            new_issues.append({"reason":"STAIR_CORE_MISSING_ON_SOME_FLOORS"})
        elif any(any(abs(stair_centers[0][0][key]-stairs[0][key])>EPS
                         for key in ("x","y","width","depth"))
                 for stairs in stair_centers[1:]):
            new_issues.append({"reason":"VERTICAL_STAIR_CORE_MISALIGNED"})
    output=dict(report)
    output["hard_issues"]=[*report.get("hard_issues",[]),*new_issues]
    output["status"]=("ARCHITECTURAL_REVIEW" if output["hard_issues"]
                      else "PRELIMINARY_GEOMETRY_ELIGIBLE")
    output["corridor_topology"]=summaries
    output["hall_union_area_m2"]=round(union_total,4)
    output["long_straight_run_penalty"]=round(run_cost,4)
    output["functional_closeness_penalty"]=round(functional_cost,4)
    output["functional_relations"]=relations
    output["architectural_bubble_graph_validated"]=False
    output["circulation_walk_paths_validated"]=False
    output["doors_generated"]=False
    output["stair_cores_reserved_by_floor"]=[len(q) for q in stair_centers]
    output["architecture_score"]=round(report["architecture_score"]+
                                      run_cost+functional_cost+
                                      1000*len(new_issues),5)
    return output
