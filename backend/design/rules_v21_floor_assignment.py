"""Bounded floor assignment of mandatory program instances before geometry."""
import math

def assign_floors(document, capacities_m2, max_states=100000):
    if not isinstance(capacities_m2,dict) or not capacities_m2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in capacities_m2.values()):
        return dict(status="needs_data",reason="explicit net floor capacities required")
    rows=document.get("program")
    if not isinstance(rows,list) or not rows:
        return dict(status="needs_data",reason="program missing")
    items=[]; optional=[]; seen=set()
    for row in rows:
        key=row.get("id"); count=row.get("count"); allowed=row.get("allowed_floors"); area=row.get("area_min_m2")
        if not isinstance(key,str) or not key or key in seen or type(count) is not int or count<1 or not isinstance(allowed,list) or not allowed or any(type(f) not in (str,int) for f in allowed) or type(area) not in (int,float) or not math.isfinite(area) or area<=0 or type(row.get("required")) is not bool:
            return dict(status="needs_data",reason="invalid or incomplete program evidence")
        seen.add(key)
        if not row["required"]:
            optional.append(key);continue
        choices=tuple(dict.fromkeys(f for f in allowed if f in capacities_m2))
        if not choices:
            return dict(status="fail",reason="no allowed floor available",program_id=key)
        items.extend((key,i,area,choices) for i in range(count))
    if len(items)>500:
        return dict(status="needs_data",reason="instance search limit")
    items.sort(key=lambda x:(len(x[3]),-x[2],x[0],x[1]))
    remaining=dict(capacities_m2); placed=[]; states=0; exhausted=False
    def search(i):
        nonlocal states,exhausted
        if i==len(items):return True
        if states>=max_states:
            exhausted=True;return False
        states+=1
        key,index,area,choices=items[i]
        for floor in sorted(choices,key=lambda f:(remaining[f]-area,str(f))):
            if remaining[floor]+1e-9<area:continue
            remaining[floor]-=area
            placed.append(dict(program_id=key,instance=index,floor=floor,min_m2=area))
            if search(i+1):return True
            placed.pop();remaining[floor]+=area
            if exhausted:return False
        return False
    if not search(0):
        return dict(status="needs_data" if exhausted else "fail",reason="search limit" if exhausted else "minimum area assignment infeasible under supplied capacities",states=states)
    return dict(status="assignment_ready",assignments=placed,remaining_m2=remaining,optional_pending=optional,states=states,geometry_verified=False,vertical_core_verified=False)
