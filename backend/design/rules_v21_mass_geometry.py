"""Exact rectangular mass union via coordinate compression.
Geometric connectivity is not evidence of functional connectivity.
"""
import math

def mass_union(rectangles):
    if not isinstance(rectangles,list) or not rectangles:
        return {"status":"needs_data"}
    for r in rectangles:
        if not isinstance(r,(list,tuple)) or len(r)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in r) or min(r[2:])<=0:
            return {"status":"fail","reason":"invalid rectangle"}
    xs=sorted({v for x,y,w,h in rectangles for v in (x,x+w)})
    ys=sorted({v for x,y,w,h in rectangles for v in (y,y+h)})
    cells=set()
    for i,(a,b) in enumerate(zip(xs,xs[1:])):
        for j,(c,d) in enumerate(zip(ys,ys[1:])):
            if any(x<=a and b<=x+w and y<=c and d<=y+h for x,y,w,h in rectangles):
                cells.add((i,j))
    area=sum((xs[i+1]-xs[i])*(ys[j+1]-ys[j]) for i,j in cells)
    unseen=set(cells); components=0
    while unseen:
        components+=1
        stack=[unseen.pop()]
        while stack:
            i,j=stack.pop()
            for n in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)):
                if n in unseen:
                    unseen.remove(n);stack.append(n)
    boundary=[]
    for i,j in sorted(cells):
        a,b,c,d=xs[i],xs[i+1],ys[j],ys[j+1]
        for n,edge in [((i-1,j),[a,c,a,d]),((i+1,j),[b,c,b,d]),((i,j-1),[a,c,b,c]),((i,j+1),[a,d,b,d])]:
            if n not in cells:boundary.append(edge)
    return dict(status="geometry_ready",union_area_m2=area,
                duplicate_area_m2=max(0,sum(w*h for x,y,w,h in rectangles)-area),
                components=components,boundary_segments=boundary,
                union_cells=[[xs[i],ys[j],xs[i+1]-xs[i],ys[j+1]-ys[j]] for i,j in sorted(cells)],
                functional_connectivity_verified=False,envelope_match_verified=False)
