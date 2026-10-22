"""Measurable massing quality, independent of regulatory setback compliance."""
import math

def measures(rectangles):
    area=sum(r['width']*r['depth'] for r in rectangles)
    perimeter=sum(2*(r['width']+r['depth']) for r in rectangles)
    contacts=[set() for _ in rectangles]
    for i,a in enumerate(rectangles):
        for j in range(i+1,len(rectangles)):
            b=rectangles[j];shared=0
            if abs(a['x']+a['width']-b['x'])<1e-6 or abs(b['x']+b['width']-a['x'])<1e-6:
                shared=max(0,min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y']))
            elif abs(a['y']+a['depth']-b['y'])<1e-6 or abs(b['y']+b['depth']-a['y'])<1e-6:
                shared=max(0,min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x']))
            if shared>1e-6:contacts[i].add(j);contacts[j].add(i);perimeter-=2*shared
    remaining=set(range(len(rectangles)));components=0
    while remaining:
        components+=1;queue=[remaining.pop()]
        while queue:
            connected=contacts[queue.pop()]&remaining;remaining-=connected;queue.extend(connected)
    w=max(r['x']+r['width'] for r in rectangles)-min(r['x'] for r in rectangles)
    d=max(r['y']+r['depth'] for r in rectangles)-min(r['y'] for r in rectangles)
    return {'area':area,'perimeter':perimeter,'envelope_fill':area/(w*d),'envelope_aspect':max(w,d)/min(w,d),
            'normalized_perimeter':perimeter/(4*math.sqrt(area)),'components':components,
            'circulation_ratio':sum(r['width']*r['depth'] for r in rectangles if r.get('kind','corridor')=='corridor')/area}

def penalty(floors,halls):
    metrics=[measures(cells+halls) for cells in floors]
    value=sum(1.8*max(0,m['normalized_perimeter']-1)+1.5*m['circulation_ratio']+
              1.0*max(0,m['envelope_aspect']-1.35)+.65*(1-m['envelope_fill']) for m in metrics)/len(metrics)
    rooms=[r for cells in floors for r in cells if r.get('request_id')]
    if rooms:value+=.5*sum(max(0,max(r['width'],r['depth'])/min(r['width'],r['depth'])-1.65) for r in rooms)/len(rooms)
    return value,metrics

def trim_corridor_tails(halls,cells):
    """Remove exposed corridor tails that serve neither rooms nor another corridor.

    Keep junctions and all room-facing wall intervals; a shortened entry hall
    receives its external door during materialization, after the trim.
    """
    result=[dict(h) for h in halls]
    for _ in range(2):
        for index,h in enumerate(result):
            vertical=h['depth']>=h['width'];axis='y' if vertical else 'x';length='depth' if vertical else 'width'
            cross='x' if vertical else 'y';breadth='width' if vertical else 'depth'
            intervals=[]
            for item_index,q in enumerate(cells+[v for i,v in enumerate(result) if i!=index]):
                touch=abs(q[cross]+q[breadth]-h[cross])<1e-6 or abs(h[cross]+h[breadth]-q[cross])<1e-6
                lo=max(h[axis],q[axis]);hi=min(h[axis]+h[length],q[axis]+q[length])
                if touch and hi>lo+1e-6:intervals.append((lo,hi))
                if item_index>=len(cells):
                    cross_overlap=min(h[cross]+h[breadth],q[cross]+q[breadth])-max(h[cross],q[cross])
                    if cross_overlap>1e-6:
                        if abs(q[axis]+q[length]-h[axis])<1e-6:intervals.append((h[axis],h[axis]+h[breadth]))
                        if abs(h[axis]+h[length]-q[axis])<1e-6:intervals.append((h[axis]+h[length]-h[breadth],h[axis]+h[length]))
            if intervals:
                lo=min(a for a,b in intervals);hi=max(b for a,b in intervals)
                if hi-lo>=h[breadth]-1e-6:h[axis]=lo;h[length]=hi-lo
    return result
