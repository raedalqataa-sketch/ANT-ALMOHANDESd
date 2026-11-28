"""Experimental rectangular wing mass proposals, not finished floor plans."""
import math
from .rules_v21_mass_geometry import mass_union

def propose_masses(wings, envelope, max_candidates=12):
    if not isinstance(envelope,(list,tuple)) or len(envelope)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in envelope) or min(envelope[2:])<=0:
        return dict(status="needs_data",candidates=[])
    if not isinstance(wings,list) or len(wings)<2 or any(not isinstance(w,dict) or type(w.get("target_m2")) not in (int,float) or not math.isfinite(w["target_m2"]) or w["target_m2"]<=0 for w in wings):
        return dict(status="needs_data",candidates=[])
    x,y,W,H=envelope
    total=sum(w["target_m2"] for w in wings)
    candidates=[]
    # Two bands, variable depth and stagger. Shared overlap is extra area,
    # not deducted from the exclusive target area of each wing.
    for split in range(1,len(wings)):
        bands=(wings[:split],wings[split:])
        for fraction in (.4,.5,.6):
            depths=(H*fraction,H*(1-fraction))
            for overlap in (.3,.6,1.0):
                if overlap>=min(depths):continue
                rects=[]; labels=[]
                for j,band in enumerate(bands):
                    widths=[w["target_m2"]/depths[j] for w in band]
                    span=sum(widths)
                    if span>W:break
                    cursor=x+(W-span)*(0 if j==0 else .5)
                    for w,width in zip(band,widths):
                        rect=[cursor,y if j==0 else y+depths[0]-overlap,width,depths[j]+(overlap if j==0 else 0)]
                        rects.append(rect);labels.append(w.get("zone"));cursor+=width
                if len(rects)!=len(wings):continue
                g=mass_union(rects)
                if g["components"]!=1 or g["duplicate_area_m2"]<=1e-8 or g["union_area_m2"]+1e-8<total:continue
                # Exclusive wing areas must remain sufficient after all overlaps.
                exclusive=[]
                for i,r in enumerate(rects):
                    a,b,c,d=r
                    area=0.
                    for p,q,s,t in g["union_cells"]:
                        if a<=p and q>=b and p+s<=a+c and q+t<=b+d and not any(k!=i and u<=p and v<=q and p+s<=u+ww and q+t<=v+hh for k,(u,v,ww,hh) in enumerate(rects)):
                            area+=s*t
                    exclusive.append(area)
                if any(a+1e-8<w["target_m2"] for a,w in zip(exclusive,wings)):continue
                candidates.append(dict(rectangles=rects,zones=labels,exclusive_m2=exclusive,geometry=g,functional_verified=False,core_verified=False))
    candidates.sort(key=lambda c:c["geometry"]["union_area_m2"])
    return dict(status="proposals_ready" if candidates else "search_exhausted",candidates=candidates[:max_candidates])
