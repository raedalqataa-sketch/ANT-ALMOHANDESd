"""Orthogonal union geometry and annotation placement in metric coordinates."""
from collections import defaultdict
from .furnishing import overlap,inside

EPS=1e-6


def union_polygons(rectangles,pad=0):
    edges=defaultdict(list)
    for i,r in enumerate(rectangles):
        x,y=r['x']-pad,r['y']-pad;w,d=r['width']+2*pad,r['depth']+2*pad
        for axis,fixed,a,b,direction in [('h',y,x,x+w,1),('v',x+w,y,y+d,1),('h',y+d,x,x+w,-1),('v',x,y,y+d,-1)]:
            edges[(axis,round(fixed,6))].append((round(a,6),round(b,6),direction))
    xs=sorted({round(r['x']+v,6) for r in rectangles for v in (-pad,r['width']+pad)})
    ys=sorted({round(r['y']+v,6) for r in rectangles for v in (-pad,r['depth']+pad)})
    # Remove any edge intervals inside the union, including overlapping padded strips.
    oriented=[]
    for (axis,fixed),spans in edges.items():
        lo=min(a for a,b,_ in spans);hi=max(b for a,b,_ in spans)
        cuts=[v for v in (xs if axis=='h' else ys) if lo<=v<=hi]
        for a,b in zip(cuts,cuts[1:]):
            mid=(a+b)/2
            if not any(lo-EPS<mid<hi+EPS for lo,hi,_ in spans):continue
            # Sample just to either side to determine occupancy; boundary direction follows interior on right.
            def occupied(delta):
                x,y=(mid,fixed+delta) if axis=='h' else (fixed+delta,mid)
                return any(r['x']-pad-EPS/10<x<r['x']+r['width']+pad+EPS/10 and r['y']-pad-EPS/10<y<r['y']+r['depth']+pad+EPS/10 for r in rectangles)
            neg,pos=occupied(-1e-5),occupied(1e-5)
            if neg==pos:continue
            start,end=((a,fixed),(b,fixed)) if axis=='h' else ((fixed,a),(fixed,b))
            forward=pos if axis=='h' else neg
            oriented.append((start,end) if forward else (end,start))
    by_start=defaultdict(list)
    for a,b in oriented:by_start[a].append(b)
    loops=[]
    while by_start:
        start=next(iter(by_start));path=[start];p=start
        for _ in range(len(oriented)+1):
            if p not in by_start:raise ValueError('حدود كتلة غير مغلقة')
            q=by_start[p].pop()
            if not by_start[p]:del by_start[p]
            if q==start:break
            path.append(q);p=q
        else:raise ValueError('تعذر إغلاق مضلع الكتلة')
        # Suppress collinear splits left by room partitions.
        changed=True
        while changed and len(path)>3:
            changed=False
            for i,p in enumerate(path):
                a,b=path[i-1],path[(i+1)%len(path)]
                if abs((p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0]))<EPS:
                    path.pop(i);changed=True;break
        loops.append(path)
    return loops


def signed_area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def annotate(floor,stairs):
    """Place name and dimensions in empty floor space, avoiding furniture and door sweeps."""
    from reportlab.pdfbase import pdfmetrics
    from bidi.algorithm import get_display
    import arabic_reshaper
    from . import presentation  # font registration shared with PDF
    labels=[]
    for room in floor['rooms']:
        if room['kind']=='corridor':continue
        label='درج' if room['kind']=='stair' else room['name']
        dimension=f"{room['width']:.2f} × {room['depth']:.2f} m"
        obstacles=[q for q in floor['furniture'] if q['room_id']==room['id'] and q.get('physical',True)]
        obstacles += [o['swing_rect'] for o in floor['openings'] if room['id'] in o['connects'] and o.get('swing_rect')]
        obstacles += [q for s in stairs if s['room_id']==room['id'] for q in s['flights']+[s['landing']]]
        chosen=None
        for size in (.25,.22,.19,.16):
            width=max(pdfmetrics.stringWidth(get_display(arabic_reshaper.reshape(label)),'PlanV04',size),pdfmetrics.stringWidth(dimension,'PlanV04',size*.78))+.12
            height=size*2.7
            x0=room['x']+.12;y0=room['y']+.12
            nx=max(1,int((room['width']-width-.24)/.18)+1);ny=max(1,int((room['depth']-height-.24)/.18)+1)
            candidates=[]
            for j in range(ny):
                for i in range(nx):
                    q=dict(x=x0+i*.18,y=y0+j*.18,width=width,depth=height)
                    if not inside(room,q) or any(overlap(q,o) for o in obstacles+labels):continue
                    cost=(q['x']+width/2-room['x']-room['width']/2)**2+(q['y']+height/2-room['y']-room['depth']/2)**2
                    candidates.append((cost,q))
            if candidates:chosen=min(candidates,key=lambda v:v[0])[1];chosen.update(size=size,label=label,dimension=dimension,room_id=room['id']);break
        if chosen is None:
            # No masking fill: put a numbered room marker and use a clear external legend.
            chosen=dict(x=room['x']+.15,y=room['y']+.15,width=.3,depth=.3,size=.18,label=str(len(labels)+1),dimension='',room_id=room['id'],legend=label+' · '+dimension)
        labels.append(chosen)
    return labels
