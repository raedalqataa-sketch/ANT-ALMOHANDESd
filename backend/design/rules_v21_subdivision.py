"""Experimental rectangular subdivision in millimetres; areas in square metres.
Unallocated area remains explicit. No claim of circulation or furniture compliance.
"""
import math

def subdivide_wing(rect_mm, rooms):
    if not isinstance(rect_mm,(list,tuple)) or len(rect_mm)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in rect_mm) or min(rect_mm[2:])<=0:
        return dict(status="needs_data",reason="valid rectangular wing required")
    if not isinstance(rooms,list) or not rooms:
        return dict(status="needs_data",reason="room instances required")
    seen=set()
    for r in rooms:
        if not isinstance(r,dict) or not isinstance(r.get("id"),str) or not r["id"] or r["id"] in seen:
            return dict(status="needs_data",reason="unique instance identifiers required")
        seen.add(r["id"])
        a=[r.get(k) for k in ("area_min_m2","area_target_m2","area_max_m2","min_side_mm")]
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in a) or not a[0]<=a[1]<=a[2]:
            return dict(status="needs_data",reason="explicit consistent area and side bounds required")
    x,y,w,h=rect_mm
    proposals=[]
    for axis in (0,1):
        span,cross=(w,h) if axis==0 else (h,w)
        for field in ("area_target_m2","area_min_m2"):
            cursor=0.; cells=[]
            for r in rooms:
                length=max(r[field]*1e6/cross,r["min_side_mm"])
                area=length*cross/1e6
                if cross<r["min_side_mm"] or area>r["area_max_m2"]+1e-9 or cursor+length>span+1e-7:
                    break
                box=[x+cursor,y,length,h] if axis==0 else [x,y+cursor,w,length]
                cells.append(dict(id=r["id"],rect_mm=box,area_m2=area))
                cursor+=length
            if len(cells)!=len(rooms):continue
            remaining=span-cursor
            residual=([x+cursor,y,remaining,h] if axis==0 else [x,y+cursor,w,remaining]) if remaining>1e-7 else None
            proposals.append(dict(rooms=cells,unclassified_rect_mm=residual,unclassified_m2=max(0,remaining)*cross/1e6,geometry_only=True,adjacency_verified=False,furniture_verified=False,walls_verified=False))
    return dict(status="proposals_ready" if proposals else "search_exhausted",candidates=proposals)
