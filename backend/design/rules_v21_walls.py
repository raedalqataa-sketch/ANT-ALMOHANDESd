"""Extract atomic room boundary segments in millimetres.
Single-sided boundaries are not automatically exterior walls.
"""
import math

def extract_wall_network(rooms):
    if not isinstance(rooms,list) or not rooms:
        return dict(status="needs_data")
    boxes=[]; ids=set()
    for room in rooms:
        if not isinstance(room,dict):return dict(status="needs_data")
        key=room.get("id"); r=room.get("rect_mm")
        if not isinstance(key,str) or not key or key in ids or not isinstance(r,(list,tuple)) or len(r)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in r) or min(r[2:])<=0:
            return dict(status="needs_data",reason="invalid room geometry")
        ids.add(key);boxes.append((key,*r))
    for i,(key,x,y,w,h) in enumerate(boxes):
        for other,a,b,c,d in boxes[i+1:]:
            if min(x+w,a+c)>max(x,a) and min(y+h,b+d)>max(y,b):
                return dict(status="fail",reason="overlapping rooms",rooms=[key,other])
    lines={}
    for key,x,y,w,h in boxes:
        for axis,fixed,start,end in (("v",x,y,y+h),("v",x+w,y,y+h),("h",y,x,x+w),("h",y+h,x,x+w)):
            lines.setdefault((axis,fixed),[]).append((start,end,key))
    walls=[]
    for (axis,fixed),edges in sorted(lines.items()):
        cuts=sorted({p for a,b,k in edges for p in (a,b)})
        for a,b in zip(cuts,cuts[1:]):
            owners=sorted({k for lo,hi,k in edges if lo<=a and b<=hi})
            if not owners:continue
            walls.append(dict(id="W%04d"%(len(walls)+1),start_mm=[fixed,a] if axis=="v" else [a,fixed],end_mm=[fixed,b] if axis=="v" else [b,fixed],length_mm=b-a,rooms=owners,kind="shared_internal" if len(owners)==2 else "unclassified_boundary",thickness_mm=None))
    return dict(status="network_ready",walls=walls,exterior_verified=False,thickness_verified=False,openings_verified=False)
