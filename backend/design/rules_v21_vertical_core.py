"""Pre-allocation rectangular core reservation; not stair compliance certification."""
import math

def _rect(v):
    return isinstance(v,(list,tuple)) and len(v)==4 and all(type(x) in (int,float) and math.isfinite(x) for x in v) and v[2]>0 and v[3]>0

def reserve_core(envelopes, connected_floors, width, depth, obstacles=None):
    if not isinstance(envelopes,dict) or not isinstance(connected_floors,list) or len(connected_floors)<2 or len(set(connected_floors))!=len(connected_floors):
        return dict(status="needs_data",reason="connected floors required")
    if any(not _rect(envelopes.get(f)) for f in connected_floors) or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (width,depth)):
        return dict(status="needs_data",reason="explicit envelopes and core dimensions required")
    if not isinstance(obstacles,dict) or any(not isinstance(obstacles.get(f),list) or any(not _rect(r) for r in obstacles[f]) for f in connected_floors):
        return dict(status="needs_data",reason="explicit obstacle lists required")
    boxes=[envelopes[f] for f in connected_floors]
    left=max(r[0] for r in boxes); bottom=max(r[1] for r in boxes)
    right=min(r[0]+r[2] for r in boxes); top=min(r[1]+r[3] for r in boxes)
    if right-left<width or top-bottom<depth:
        return dict(status="fail",reason="specified core cannot fit common rectangular envelope")
    blocked=[r for f in connected_floors for r in obstacles[f]]
    xs={left,right-width}; ys={bottom,top-depth}
    for x,y,w,d in blocked:
        xs.update((x-width,x+w));ys.update((y-depth,y+d))
    def overlaps(x,y,r):
        a,b,w,d=r
        return x<a+w and x+width>a and y<b+d and y+depth>b
    for x in sorted(xs):
        for y in sorted(ys):
            if x<left or y<bottom or x+width>right or y+depth>top:continue
            if any(overlaps(x,y,r) for r in blocked):continue
            rect=[x,y,width,depth]
            return dict(status="reservation_ready",reservations={f:rect.copy() for f in connected_floors},reserved_m2=width*depth,stair_geometry_verified=False,slab_opening_verified=False,rule_id="VERTICAL-001")
    return dict(status="fail",reason="no obstacle-free rectangular reservation for specified dimensions")
