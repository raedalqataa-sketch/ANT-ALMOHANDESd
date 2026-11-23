"""Authoritative polygon geometry for opt-in composition strategies (metres)."""
import math
from functools import lru_cache
from shapely.geometry import Polygon,box,LineString

EPS=1e-6

@lru_cache(maxsize=4096)
def _polygon(coords):
    # Shapely 2 geometries are immutable. Coordinate keys invalidate on edits;
    # room identities and cached validation flags never enter this cache.
    return Polygon(coords)

def shape(r):
    return _polygon(tuple(tuple(p) for p in r['polygon'])) if 'polygon' in r else box(r['x'],r['y'],r['x']+r['width'],r['y']+r['depth'])

def net_shape(r,t):
    return shape(r).buffer(-t/2,join_style=2)

def entity(rid,kind,poly,**meta):
    if poly.is_empty or poly.geom_type!='Polygon' or not poly.is_valid or poly.interiors:
        raise ValueError('INVALID_ROOM_POLYGON:'+rid)
    # Canonical nanometre precision removes floating arithmetic slivers,
    # without accepting geometric gaps at architectural tolerance.
    poly=Polygon([(round(x,9),round(y,9)) for x,y in list(poly.exterior.coords)[:-1]])
    x,y,xx,yy=poly.bounds
    return dict(id=rid,kind=kind,x=x,y=y,width=xx-x,depth=yy-y,polygon=[list(p) for p in list(poly.exterior.coords)[:-1]],**meta)

def chamfer(x,y,w,d,corners=(),cut=.65):
    c=min(cut,w/4,d/4);points=[]
    for key,pair,corner in [('sw',[(x,y+c),(x+c,y)],(x,y)),('se',[(x+w-c,y),(x+w,y+c)],(x+w,y)),('ne',[(x+w,y+d-c),(x+w-c,y+d)],(x+w,y+d)),('nw',[(x+c,y+d),(x,y+d-c)],(x,y+d))]:
        points.extend(pair if key in corners else [corner])
    return Polygon(points)

def sized(request,t,*,fixed_depth=None,corners=(),cut=.65):
    """Grow actual clear polygon, never count chamfer waste toward the brief."""
    side=request['min_side']+t
    d=max(side,fixed_depth or side);w=max(side,request['min_area']/(d-t)+t)
    for _ in range(400):
        poly=chamfer(0,0,w,d,corners,cut)
        if poly.buffer(-t/2,join_style=2).area>=request['min_area']-EPS:return w,d
        w+=.025
    raise ValueError('CANNOT_SIZE:'+request['id'])

def axial_edges(poly):
    polys=[poly] if poly.geom_type=='Polygon' else list(getattr(poly,'geoms',[]))
    edges=[]
    for p in polys:
        coords=list(p.exterior.coords)
        for (x,y),(xx,yy) in zip(coords,coords[1:]):
            if abs(y-yy)<EPS:axis,fixed,lo,hi='x',y,min(x,xx),max(x,xx)
            elif abs(x-xx)<EPS:axis,fixed,lo,hi='y',x,min(y,yy),max(y,yy)
            else:continue  # oblique walls are real; orthogonal doors only in v1
            if hi-lo>EPS:edges.append(dict(axis=axis,fixed=fixed,lo=lo,hi=hi,length=hi-lo))
    return edges

def shared_edges(a,b):
    u=shape(a).boundary.intersection(shape(b).boundary)
    lines=[u] if u.geom_type=='LineString' else list(getattr(u,'geoms',[]))
    result=[]
    for line in lines:
        if line.geom_type!='LineString' or line.length<EPS:continue
        points=list(line.coords)
        for p,q in zip(points,points[1:]):
            x,y=p;xx,yy=q
            if abs(y-yy)<EPS:axis,fixed,lo,hi='x',y,min(x,xx),max(x,xx)
            elif abs(x-xx)<EPS:axis,fixed,lo,hi='y',x,min(y,yy),max(y,yy)
            else:continue
            result.append(dict(axis=axis,fixed=fixed,lo=lo,hi=hi,length=hi-lo))
    return result

def exposed_edges(r,objects):
    edges=axial_edges(shape(r));out=[]
    # A pair's contact is independent of the facade edge being examined.
    # Preserve the original neighbor/contact order and exact interval arithmetic.
    contacts=[contact for q in objects if q['id']!=r['id'] for contact in shared_edges(r,q)]
    for edge in edges:
        pieces=[(edge['lo'],edge['hi'])]
        for contact in contacts:
            if contact['axis']!=edge['axis'] or abs(contact['fixed']-edge['fixed'])>EPS:continue
            rest=[]
            for a,b in pieces:
                if contact['hi']<=a or contact['lo']>=b:rest.append((a,b));continue
                if contact['lo']>a:rest.append((a,contact['lo']))
                if contact['hi']<b:rest.append((contact['hi'],b))
            pieces=rest
        out.extend(dict(edge,lo=a,hi=b,length=b-a) for a,b in pieces if b-a>EPS)
    return out
