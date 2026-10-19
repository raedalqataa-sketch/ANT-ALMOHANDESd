"""Orthogonal union geometry and annotation placement in metric coordinates."""
from collections import defaultdict
from .furnishing import overlap,inside

EPS=1e-6


def union_polygons(rectangles,pad=0):
    """Exact orthogonal union on a documented 1 micrometre coordinate grid.

    Snap ALL endpoints once. Occupancy is computed on compressed grid cells,
    never by perturbing rounded edges against unrounded input rectangles.
    Positive exterior loops and negative hole loops conserve occupied area;
    corner-touching components remain separate simple loops.
    """
    import math
    scale=1_000_000
    if not math.isfinite(pad):raise ValueError('قيمة توسيع الحدود غير محدودة')
    boxes=[]
    for r in rectangles:
        values=[r[k] for k in ('x','y','width','depth')]
        if not all(math.isfinite(v) for v in values):raise ValueError('إحداثيات كتلة غير محدودة')
        x,y,w,d=values
        if w<=0 or d<=0:raise ValueError('أبعاد كتلة غير موجبة')
        q=tuple(round(v*scale) for v in (x-pad,y-pad,x+w+pad,y+d+pad))
        if q[0]>=q[2] or q[1]>=q[3]:raise ValueError('أبعاد كتلة أصغر من دقة الميكرومتر أو التوسيع يزيلها')
        boxes.append(q)
    if not boxes:return []
    xs=sorted({v for x,y,xx,yy in boxes for v in (x,xx)});ys=sorted({v for x,y,xx,yy in boxes for v in (y,yy)})
    xi={x:i for i,x in enumerate(xs)};yi={y:i for i,y in enumerate(ys)}
    nx,ny=len(xs)-1,len(ys)-1
    diff=[[0]*(nx+1) for _ in range(ny+1)]
    for x,y,xx,yy in boxes:
        a,b,c,d=xi[x],yi[y],xi[xx],yi[yy]
        diff[b][a]+=1;diff[b][c]-=1;diff[d][a]-=1;diff[d][c]+=1
    occupied=[[False]*nx for _ in range(ny)];area=0
    for j in range(ny):
        for i in range(nx):
            diff[j][i]+=(diff[j-1][i] if j else 0)+(diff[j][i-1] if i else 0)-(diff[j-1][i-1] if i and j else 0)
            occupied[j][i]=diff[j][i]>0
            if occupied[j][i]:area+=(xs[i+1]-xs[i])*(ys[j+1]-ys[j])
    edges=set()
    for j in range(ny):
        for i in range(nx):
            if not occupied[j][i]:continue
            x,xx,y,yy=xs[i],xs[i+1],ys[j],ys[j+1]
            if j==0 or not occupied[j-1][i]:edges.add(((x,y),(xx,y)))
            if i==nx-1 or not occupied[j][i+1]:edges.add(((xx,y),(xx,yy)))
            if j==ny-1 or not occupied[j+1][i]:edges.add(((xx,yy),(x,yy)))
            if i==0 or not occupied[j][i-1]:edges.add(((x,yy),(x,y)))
    successors=defaultdict(list)
    for a,b in sorted(edges):successors[a].append(b)
    def direction(a,b):return 0 if b[0]>a[0] else 2 if b[0]<a[0] else 1 if b[1]>a[1] else 3
    loops=[]
    while edges:
        start,nxt=min(edges);edges.remove((start,nxt));path=[start];previous=start;point=nxt
        while point!=start:
            path.append(point)
            candidates=[q for q in successors[point] if (point,q) in edges]
            if not candidates:raise ValueError('حدود كتلة غير مغلقة في شبكة الاتحاد')
            incoming=direction(previous,point)
            # At diagonal point contacts follow the same occupied component,
            # rather than creating a self-touching figure-eight boundary.
            rank={1:0,0:1,3:2,2:3}
            nxt=min(candidates,key=lambda q:(rank[(direction(point,q)-incoming)%4],q))
            edges.remove((point,nxt));previous,point=point,nxt
        simplified=[]
        for i,point in enumerate(path):
            before,after=path[i-1],path[(i+1)%len(path)]
            if (point[0]-before[0])*(after[1]-point[1])!=(point[1]-before[1])*(after[0]-point[0]):simplified.append(point)
        if len(simplified)<4:raise ValueError('حدود كتلة متدهورة بعد الاتحاد')
        loops.append(simplified)
    twice_area=sum(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1])) for p in loops)
    if twice_area!=2*area:raise ValueError('مساحة حدود الاتحاد لا تطابق الخلايا المشغولة')
    return [[(x/scale,y/scale) for x,y in loop] for loop in loops]


def signed_area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def annotate(floor,stairs):
    """Place name and dimensions in empty floor space, avoiding furniture and door sweeps."""
    from reportlab.pdfbase import pdfmetrics
    from bidi.algorithm import get_display
    import arabic_reshaper
    from . import presentation  # font registration shared with PDF
    labels=[]
    for room in floor['rooms']:
        if room['kind']=='corridor' and not room.get('guest_distributor'):continue
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
