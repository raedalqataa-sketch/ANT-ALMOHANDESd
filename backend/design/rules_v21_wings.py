"""Pre-geometric wing demand planning; no inferred floor assignments."""
import math
from .rules_v21_program_graph import build_program_graph

def plan_wings(document):
    graph=build_program_graph(document)
    issues=list(graph["unresolved"])
    groups={}
    floors=document.get("floors")
    for key,node in graph["nodes"].items():
        zone=node["privacy_zone"]
        allowed=node["allowed_floors"]
        count=node["count"]
        areas=[node[k] for k in ("area_min_m2","area_target_m2","area_max_m2")]
        if not isinstance(zone,str) or not zone or not isinstance(allowed,list) or not allowed or any(type(f) not in (str,int) for f in allowed) or type(count) is not int or count<1 or any(type(a) not in (int,float) or not math.isfinite(a) or a<=0 for a in areas):
            issues.append(dict(source=key,reason="wing demand evidence incomplete"))
            continue
        if not areas[0]<=areas[1]<=areas[2]:
            graph["conflicts"].append(dict(source=key,reason="area bounds inconsistent"))
            continue
        group=groups.setdefault(zone,dict(zone=zone,items=[],min_m2=0.,target_m2=0.,max_m2=0.))
        group["items"].append(dict(id=key,count=count,allowed_floors=allowed,required=node["required"]))
        for field,a in zip(("min_m2","target_m2","max_m2"),areas):
            group[field]+=count*a
    return dict(wings=list(groups.values()),relationships=graph["edges"],unresolved=issues,conflicts=graph["conflicts"],status="fail" if graph["conflicts"] else "needs_data" if issues else "demand_ready",geometry_generated=False,floor_assignment_completed=False)
