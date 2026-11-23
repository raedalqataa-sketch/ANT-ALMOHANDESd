"""Manual operations on real polygons. No generation, minima or role changes."""
import copy,math
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter
from shapely.geometry import Polygon,LineString,Point
from shapely.affinity import translate,scale
from assl.strategies.geometry import shape,entity,net_shape

class Operation(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    room_id:str=Field(min_length=1,max_length=100)
class Move(Operation):
    type:Literal['move'];dx:float=Field(ge=-60,le=60);dy:float=Field(ge=-80,le=80)
class Resize(Operation):
    type:Literal['resize'];width:float=Field(ge=.5,le=60);depth:float=Field(ge=.5,le=80)
class Wall(Operation):
    type:Literal['wall'];edge:int=Field(ge=0,le=255);offset:float=Field(ge=-10,le=10)
OPS=TypeAdapter(list[Annotated[Move|Resize|Wall,Field(discriminator='type')]])


def _replace(r,g):
    if not g.is_valid or g.is_empty or g.geom_type!='Polygon' or g.area<.1:raise ValueError('INVALID_EDITED_POLYGON:'+r['id'])
    meta={k:v for k,v in r.items() if k not in ('id','kind','polygon','x','y','width','depth')}
    r.update(entity(r['id'],r['kind'],g,**meta))


def _wall(objects,target,edge,offset):
    coords=list(shape(target).exterior.coords)[:-1]
    if edge>=len(coords):raise ValueError('UNKNOWN_WALL_EDGE')
    a,b=coords[edge],coords[(edge+1)%len(coords)];line=LineString([a,b]);length=line.length
    if length<1e-6:raise ValueError('ZERO_LENGTH_WALL')
    sign=1 if shape(target).exterior.is_ccw else -1
    dx=(b[1]-a[1])/length*offset*sign;dy=-(b[0]-a[0])/length*offset*sign
    def on(p):return line.distance(Point(p))<1e-7
    def collinear(p,q):
        return abs((q[0]-p[0])*(b[1]-a[1])-(q[1]-p[1])*(b[0]-a[0]))<1e-7
    for r in objects:
        original=shape(r)
        if original.boundary.intersection(line).length<1e-7:continue
        vs=list(original.exterior.coords)[:-1];expanded=[]
        # Split a neighbour's longer wall at the edited segment endpoints.
        for p,q in zip(vs,vs[1:]+vs[:1]):
            edge_line=LineString([p,q]);splits=[(0,p)]
            if edge_line.length>1e-7:
                for end in (a,b):
                    f=edge_line.project(Point(end),normalized=True)
                    if 1e-7<f<1-1e-7 and edge_line.distance(Point(end))<1e-7:splits.append((f,end))
            expanded.extend(v for _,v in sorted(splits,key=lambda x:x[0]))
        output=[]
        for p,q in zip(expanded,expanded[1:]+expanded[:1]):
            middle=((p[0]+q[0])/2,(p[1]+q[1])/2)
            continuation=collinear(p,q) and not on(middle)
            for v in (p,q):
                moved=(v[0]+dx,v[1]+dy) if on(v) and not continuation else v
                if not output or math.dist(output[-1],moved)>1e-8:output.append(moved)
        if len(output)>1 and math.dist(output[0],output[-1])<1e-8:output.pop()
        g=Polygon(output)
        if not g.equals(original):
            if r['kind']=='stair':raise ValueError('LOCKED_STAIR:shared-wall')
            _replace(r,g)


def apply_operations(baseline,operations):
    if baseline.get('schema') not in ('assl-clustered-1','assl-clustered-2','assl-relational-1'):raise ValueError('UNSUPPORTED_EDITOR_SCHEMA')
    if len(operations)>120:raise ValueError('TOO_MANY_OPERATIONS')
    parsed=OPS.validate_python(operations);out=copy.deepcopy(baseline)
    objects=out['rooms_by_floor'][0]+out['halls_by_floor'][0];ids={r['id']:r for r in objects}
    for op in parsed:
        r=ids.get(op.room_id)
        if r is None:raise ValueError('UNKNOWN_ROOM:'+op.room_id)
        if r['kind']=='stair':raise ValueError('LOCKED_STAIR')
        if op.type=='move':_replace(r,translate(shape(r),op.dx,op.dy))
        elif op.type=='resize':_replace(r,scale(shape(r),op.width/r['width'],op.depth/r['depth'],origin=(r['x'],r['y'])))
        else:_wall(objects,r,op.edge,op.offset)
    for key in ('validation_009','quality_010','opening_model_009','furniture_by_floor','furnishing_diagnostics'):out.pop(key,None)
    return out


def refresh_and_validate(baseline,operations):
    from .general_models import VillaBrief
    from assl.strategies.openings import construct_clustered
    from assl.strategies.furnishing import furnish_clustered
    from assl.openings_009 import validate
    from assl.layout_critic_010 import critique
    b=VillaBrief.model_validate(baseline['brief_snapshot']);p=apply_operations(baseline,operations)
    p=furnish_clustered(b,construct_clustered(b,p));qa=validate(b,p);qc=critique(b,p)
    p.update(validation_009=qa,quality_010=qc)
    accepted=qa['status']=='PASS' and qc['status']=='ACCEPTABLE_DESIGN_INDICATORS'
    return dict(proposal=p,areas={r['id']:round(net_shape(r,b.wall_thickness).area,4) for r in p['rooms_by_floor'][0]+p['halls_by_floor'][0]},status='CHECKED_CONCEPT' if accepted else 'DRAFT_WITH_ISSUES',exportable=accepted,
                issues=qa['issues']+[d['type'] for d in qc['defects'] if d['type']!='HARD_VALIDATION'])
