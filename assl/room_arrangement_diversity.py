"""Architecture-only multi-objective selection of genuinely distinct spatial plans.

Do not accept a plan as radically different only because a 2m corridor branch
was added or a topology/style label changed. Measure displacement of the same
client-requested rooms relative to the buildable envelope, shared-wall neighbor
changes, and actual used-hall topology. These are *concept* diagnostics.
"""
from __future__ import annotations
from itertools import product
from math import hypot
from .concept_quality_v2 import edge_contact

EPS=1e-8


def _rooms(option):
    # Intentionally excludes artificial guest-distributor nodes and stair
    # markers. Room identity is the actual requested program ID.
    rows={}
    for fi,floor in enumerate(option["rooms_by_floor"]):
        for r in floor:
            if r.get("request_id"):
                rows[r["id"]]=(fi,r)
    return rows


def _neighbor_edges(option):
    edges=set()
    for fi,floor in enumerate(option["rooms_by_floor"]):
        rs=[r for r in floor if r.get("request_id")]
        for i,a in enumerate(rs):
            for b in rs[i+1:]:
                if edge_contact(a,b)>=.9-EPS:
                    edges.add((fi,*sorted((a["id"],b["id"]))))
    return edges


def compare_room_arrangements(first,second,*,motion_threshold=.05):
    """Compare real room placements, not arbitrary geometric graph labels."""
    a,b=_rooms(first),_rooms(second)
    if set(a)!=set(b):
        return {"program_compatible":False,"different":False,
                "missing_in_first":sorted(set(b)-set(a)),
                "missing_in_second":sorted(set(a)-set(b))}
    W,D=first["building_envelope_m"]
    if not W or not D:return {"program_compatible":False,"different":False}
    displacements=[]
    for rid,(fi,r) in a.items():
        fi2,s=b[rid]
        if fi!=fi2:
            return {"program_compatible":False,"different":False,
                    "room_floor_mismatch":rid}
        dx=(r["x"]+r["width"]/2-s["x"]-s["width"]/2)/W
        dy=(r["y"]+r["depth"]/2-s["y"]-s["depth"]/2)/D
        displacements.append({"room_id":rid,"relative_displacement":round(hypot(dx,dy),5)})
    count=len(displacements)
    mean=sum(x["relative_displacement"] for x in displacements)/max(count,1)
    fraction=sum(x["relative_displacement"]>=motion_threshold
                 for x in displacements)/max(count,1)
    adjacent_a,adjacent_b=_neighbor_edges(first),_neighbor_edges(second)
    union=adjacent_a|adjacent_b
    neighbor_change=len(adjacent_a^adjacent_b)/max(1,len(union))
    graph_changed=(first["topology_evidence"]["geometric_graph_signature"]!=
                   second["topology_evidence"]["geometric_graph_signature"])
    return {
        "program_compatible":True,
        "mean_normalized_room_displacement":round(mean,5),
        "fraction_rooms_moved_at_least_5pct":round(fraction,5),
        "room_count":count,
        "shared_room_wall_difference_fraction":round(neighbor_change,5),
        "corridor_graph_changed":graph_changed,
        "room_displacements":sorted(displacements,key=lambda v:v["room_id"]),
    }


def difference_passes(stats,*,min_mean=.08,min_fraction=.35):
    """Concept design threshold, not a regulation or approval."""
    return (stats.get("program_compatible",False)
            and stats.get("corridor_graph_changed",False)
            and stats.get("mean_normalized_room_displacement",0)>=min_mean
            and stats.get("fraction_rooms_moved_at_least_5pct",0)>=min_fraction)


def select_distinct_proposals(per_style,styles,max_results=3,
                              *,max_quality_regression=1.30):
    """Find the best *group* of feasible, physically different candidates.

    Enumerates small top-N pools per style and maximizes the weakest pair,
    preserving broad quality limits. Explicitly reports a shortfall rather
    than claiming three when the available geometries are too similar.
    """
    pools=[]
    for style in styles:
        rows=sorted((r for r in per_style.get(style,[])
                     if r["topology_evidence"]["distinctive_nodes_actually_serve_rooms"]),
                    key=lambda r:r["quality"]["architecture_score"])
        if not rows:return {"selected":[],"reason":"TOPOLOGY_UNAVAILABLE:"+style,
                            "available_styles":{s:len(per_style.get(s,[])) for s in styles}}
        best=rows[0]["quality"]["architecture_score"]
        upper=max(best,1)*max_quality_regression
        pools.append([x for x in rows[:12]
                      if x["quality"]["architecture_score"]<=upper])
    possibilities=[]
    diagnostics={"triplets_checked":0,"below_threshold":0,
                 "quality_rejected_before_search":sum(len(per_style.get(style,[]))-len(pool)
                                                       for style,pool in zip(styles,pools))}
    for options in product(*pools):
        diagnostics["triplets_checked"]+=1
        comparisons=[compare_room_arrangements(options[i],options[j])
                     for i,j in ((0,1),(0,2),(1,2))]
        if not all(difference_passes(x) for x in comparisons):
            diagnostics["below_threshold"]+=1
            continue
        weak=min(x["mean_normalized_room_displacement"] for x in comparisons)
        min_fraction=min(x["fraction_rooms_moved_at_least_5pct"] for x in comparisons)
        cost=sum(x["quality"]["architecture_score"] for x in options)
        # Strongly prioritize *minimum* true displacement between any pair
        # subject to bounded architectural cost. More m² isn't free.
        score=weak+.12*min_fraction-.0003*cost
        possibilities.append((score,cost,options,comparisons))
    if not possibilities:
        return {"selected":[],"reason":"REAL_ROOM_CONFIGURATION_DIVERSITY_SHORTFALL",
                "diagnostics":diagnostics}
    winner=max(possibilities,key=lambda p:(p[0],-p[1]))
    return {"selected":list(winner[2]),"reason":"MEASURED_GROUP_DIVERSITY",
            "comparisons":winner[3],
            "selection_score":round(winner[0],6),
            "diagnostics":diagnostics,
            "distinctness_is_not_legal_or_construction_approval":True}
