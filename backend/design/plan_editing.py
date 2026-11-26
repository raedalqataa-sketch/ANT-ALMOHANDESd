"""Replay manual geometry and program edits on a saved proposal."""
import copy,math
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter
from shapely.geometry import Polygon,LineString,Point,box
from shapely.affinity import translate,scale
from assl.strategies.geometry import shape,entity,net_shape,shared_edges

class Operation(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    room_id:str=Field(min_length=1,max_length=100)
    floor:int=Field(default=0,ge=0,le=1)
class Move(Operation):
    type:Literal['move'];dx:float=Field(ge=-60,le=60);dy:float=Field(ge=-80,le=80)
class Resize(Operation):
    type:Literal['resize'];width:float=Field(ge=.5,le=60);depth:float=Field(ge=.5,le=80)
class Wall(Operation):
    type:Literal['wall'];edge:int=Field(ge=0,le=255);offset:float=Field(ge=-10,le=10)
class AddSpace(Operation):
    type:Literal['add_space']
    name:str=Field(min_length=1,max_length=65)
    kind:Literal['storage','office','laundry','bathroom','living','bedroom']
    x:float=Field(ge=-100,le=100)
    y:float=Field(ge=-100,le=100)
    width:float=Field(ge=.5,le=60)
    depth:float=Field(ge=.5,le=80)
class DeleteSpace(Operation):
    type:Literal['delete_space']
class Partition(Operation):
    type:Literal['partition']
    edge:int=Field(ge=0,le=255)
    open:bool
OPS=TypeAdapter(list[Annotated[Move|Resize|Wall|AddSpace|DeleteSpace|Partition,Field(discriminator='type')]])


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


def change_activity(proposal, room, operation, index):
    if operation.floor != 0:
        raise ValueError("EDITOR_ACTIVITY_GROUND_ONLY")
    snapshot = proposal["brief_snapshot"]
    if operation.type == "delete_space":
        req_id = room.get("request_id")
        if (not req_id or sum(r.get("request_id") == req_id for r in proposal["rooms_by_floor"][0]) != 1
                or any(req_id in group["rooms"] for group in snapshot.get("guest_groups", []))
                or any(req_id in (rel["source"], rel["target"]) for rel in snapshot.get("spatial_requirements", []))
                or any(r.get("ensuite_for") == req_id or (r["id"] == req_id and r.get("ensuite_for"))
                       for r in snapshot["rooms"])):
            raise ValueError("EDITOR_ACTIVITY_LINKED")
        snapshot["rooms"] = [req for req in snapshot["rooms"] if req["id"] != req_id]
        proposal["rooms_by_floor"][0].remove(room)
        proposal["connection_requirements"] = [
            link for link in proposal["connection_requirements"] if room["id"] not in (link["a"], link["b"])
        ]
        return

    if (room.get("guest_entries") or room.get("guest_entry") or
            room["kind"] not in ("living","kitchen","corridor","dining")):
        raise ValueError("EDITOR_SELECT_FAMILY_HOST")
    from .general_models import SpaceRequest
    from .general_engine import expanded_program
    from .general_models import PROPOSAL_BRIEF
    thickness = snapshot["wall_thickness"]
    width, depth = operation.width-thickness, operation.depth-thickness
    request = SpaceRequest(id=f"editor-activity-{index}", name=operation.name, kind=operation.kind,
                           floor=0, min_area=min(100,width*depth), min_side=min(10,width,depth))
    if any(r["id"] == request.id for r in snapshot["rooms"]):
        raise ValueError("EDITOR_ACTIVITY_ID_EXISTS")
    snapshot["rooms"].append(request.model_dump())
    brief = PROPOSAL_BRIEF.validate_python(snapshot)
    row = next(r for r in expanded_program(brief, 0) if r["request_id"] == request.id)
    polygon = box(operation.x, operation.y, operation.x+operation.width, operation.y+operation.depth)
    activity = entity(row["id"], operation.kind, polygon, **{
        key:value for key,value in row.items() if key not in ("id","kind")
    }, guest_entries=[], ensuite_for=None)
    proposal["rooms_by_floor"][0].append(activity)
    proposal["connection_requirements"].append({"a":room["id"],"b":activity["id"],"roles":["family"]})


def change_partition(proposal, objects, room, operation):
    if operation.floor != 0:
        raise ValueError("EDITOR_PARTITION_GROUND_ONLY")
    coords = list(shape(room).exterior.coords)[:-1]
    if operation.edge >= len(coords):
        raise ValueError("UNKNOWN_WALL_EDGE")
    edge = LineString([coords[operation.edge], coords[(operation.edge+1) % len(coords)]])
    compatible = []
    for other in objects:
        if (other["id"] == room["id"] or other.get("guest_entries") or other.get("guest_entry")
                or other["kind"] not in ("living","dining","corridor")
                or room.get("guest_entries") or room.get("guest_entry")
                or room["kind"] not in ("living","dining","corridor")):
            continue
        for shared in shared_edges(room, other):
            axis = 0 if shared["axis"] == "x" else 1
            points = [(q,shared["fixed"]) if axis == 0 else (shared["fixed"],q) for q in (shared["lo"],shared["hi"])]
            if edge.intersection(LineString(points)).length < 1.2-1e-6:
                continue
            compatible.extend(
                link for link in proposal["connection_requirements"]
                if {link["a"],link["b"]} == {room["id"],other["id"]}
                and not link.get("controlled") and link.get("roles",["family"]) == ["family"]
            )
    if len(compatible) != 1:
        raise ValueError("EDITOR_PARTITION_REQUIRES_FAMILY_CONNECTION")
    compatible[0]["open_passage"] = operation.open


def apply_operations(baseline,operations):
    if baseline.get('schema') not in ('assl-clustered-1','assl-clustered-2','assl-relational-1'):raise ValueError('UNSUPPORTED_EDITOR_SCHEMA')
    if len(operations)>120:raise ValueError('TOO_MANY_OPERATIONS')
    parsed=OPS.validate_python(operations);out=copy.deepcopy(baseline)
    for index, op in enumerate(parsed, 1):
        if op.floor >= len(out["rooms_by_floor"]):
            raise ValueError("EDITOR_FLOOR_NOT_FOUND")
        objects=out['rooms_by_floor'][op.floor]+out['halls_by_floor'][op.floor]
        r=next((room for room in objects if room["id"] == op.room_id), None)
        if r is None:raise ValueError('UNKNOWN_ROOM:'+op.room_id)
        if r['kind']=='stair':raise ValueError('LOCKED_STAIR')
        if op.type=='move':_replace(r,translate(shape(r),op.dx,op.dy))
        elif op.type=='resize':_replace(r,scale(shape(r),op.width/r['width'],op.depth/r['depth'],origin=(r['x'],r['y'])))
        elif op.type=='wall':_wall(objects,r,op.edge,op.offset)
        elif op.type=='partition':change_partition(out,objects,r,op)
        else:change_activity(out,r,op,index)
    for key in ('validation_009','quality_010','opening_model_009','furniture_by_floor','furnishing_diagnostics'):out.pop(key,None)
    return out


def room_areas(proposal):
    return {
        room["id"]:round(net_shape(room, proposal["brief_snapshot"]["wall_thickness"]).area,4)
        for rooms,halls in zip(proposal["rooms_by_floor"], proposal["halls_by_floor"], strict=True)
        for room in rooms+halls
    }


def refresh_and_validate(baseline,operations):
    from .general_models import PROPOSAL_BRIEF, UpperFloorProgram
    from assl.strategies.openings import construct_clustered
    from assl.strategies.furnishing import furnish_clustered
    from assl.openings_009 import validate
    from assl.layout_critic_010 import critique

    p=apply_operations(baseline,operations)
    b=PROPOSAL_BRIEF.validate_python(p['brief_snapshot'])
    ground={**p, "rooms_by_floor":p["rooms_by_floor"][:1], "halls_by_floor":p["halls_by_floor"][:1]}
    ground=furnish_clustered(b,construct_clustered(b,ground))
    issues = []
    try:
        qa=validate(b,ground)
        qc=critique(b,{**ground,"validation_009":qa})
        issues=qa['issues']+[d['type'] for d in qc['defects'] if d['type']!='HARD_VALIDATION']
        accepted=qa['status']=='PASS' and qc['status']=='ACCEPTABLE_DESIGN_INDICATORS'
    except (ValueError, KeyError) as error:
        qa, qc, accepted = {"status":"FAIL"}, {"status":"REJECT_AND_REPLAN"}, False
        issues = [str(error)]
    p.update(validation_009=qa,quality_010=qc,opening_model_009=ground["opening_model_009"],
             furniture_by_floor=ground["furniture_by_floor"],entrance_platforms=ground["entrance_platforms"])
    if len(p["rooms_by_floor"]) == 2:
        from assl.strategies.clustered_multilevel import (
            check_family_proposal, inspect_upper, level_windows, upper_connections,
        )

        upper = p["rooms_by_floor"][1]
        enclosed = [room for room in upper if room["kind"] != "terrace"]
        p["opening_model_009"].append({"doors":[],"windows":[]})
        p["furniture_by_floor"].append([])
        try:
            program = UpperFloorProgram.model_validate(p.get("upper_program", {}))
            doors,_ = inspect_upper(b,upper,upper_connections(program.children))
            windows = [w for w,_ in level_windows(enclosed,doors,b.wall_thickness)]
            p["opening_model_009"][1] = {"doors":doors,"windows":windows}
            p = check_family_proposal(b,p)
        except (ValueError,KeyError) as error:
            issues.append(str(error))
            accepted = False
    return dict(proposal=p,areas=room_areas(p),status='CHECKED_CONCEPT' if accepted else 'DRAFT_WITH_ISSUES',
                exportable=accepted,issues=issues)
