"""Parametric orthogonal massing for the experimental V3 geometric search.

No prescribed L, U or stepped silhouette: independent front/rear setbacks on
both wings generate an envelope from its actually occupied rooms and hall cells.
This is a bounded, orthogonal search, not unrestricted polygon optimization.
"""
import math


def adaptive_topology(width, depth, corridor, center_fraction, split_fraction):
    if min(width, depth, corridor) <= 0:
        return None
    center = width * center_fraction
    left_edge = center - corridor / 2
    right_edge = center + corridor / 2
    if left_edge <= 0 or right_edge >= width:
        return None
    split = depth * split_fraction
    if min(split, depth - split) < 5.0:
        return None

    def inlet(maximum, band, side):
        # Continuous variations in setbacks, not templates keyed to a facade type.
        phase = (center_fraction * 5.7 + split_fraction * 3.9 + side * 1.4
                 + band * 1.9) * math.pi
        amount = .08 + .92 * (1 + math.sin(phase)) / 2
        return min(maximum * .16, 1.35) * amount

    hall = [{"x": left_edge, "y": 0, "width": corridor, "depth": depth}]
    lanes = []
    for band, (y, size) in enumerate(((0, split), (split, depth - split))):
        left_inlet = inlet(left_edge, band, 0)
        right_inlet = inlet(width - right_edge, band, 1)
        left_width = left_edge - left_inlet
        right_width = width - right_edge - right_inlet
        if min(left_width, right_width) < 2.8:
            return None
        lanes.extend([
            dict(x=left_inlet, y=y, width=left_width, depth=size,
                 axis="y", door_side="east"),
            dict(x=right_edge, y=y, width=right_width, depth=size,
                 axis="y", door_side="west"),
        ])
    return hall, lanes


def freeform_topology(width, depth, corridor, center_fraction, split_fraction):
    """Three independently recessed room bands around a continuous central hall.

    The section depths and setbacks vary parametrically. This is an orthogonal,
    bounded massing candidate, not a claim to unconstrained arbitrary geometry.
    All cells have positive dimensions, do not overlap and meet the shared hall.
    """
    if min(width, depth, corridor) <= 0:
        return None
    spine_x = width * center_fraction - corridor / 2
    spine_right = spine_x + corridor
    if spine_x < 3.2 or width - spine_right < 3.2:
        return None
    first = depth * split_fraction
    second = first + (depth-first) * (.43 + .12*center_fraction)
    stops = (0.0, first, second, depth)
    if min(b-a for a,b in zip(stops,stops[1:])) < 5.0:
        return None
    hall = [dict(x=spine_x,y=0.0,width=corridor,depth=depth)]
    lanes=[]
    for band,(a,b) in enumerate(zip(stops,stops[1:])):
        for side in (0,1):
            available = spine_x if side==0 else width-spine_right
            # Deterministic continuous offsets: each wing can recess independently.
            phase = (center_fraction*7.13 + split_fraction*4.77 +
                     band*1.63 + side*2.41)*math.pi
            recess = min(1.8,.22*available)*(.18+.82*(1+math.sin(phase))/2)
            cross = available-recess
            if cross < 2.8:
                return None
            x = recess if side==0 else spine_right
            lanes.append(dict(x=x,y=a,width=cross,depth=b-a,
                              axis="y",door_side="east" if side==0 else "west"))
    return hall,lanes


# These multipliers are disclosed design heuristics for proportional room planning.
# They are NOT statutory maximum floor areas.
EXPANSION_MULTIPLIERS={
    "bathroom":1.7,"bedroom":1.8,"master":1.9,
    "dining":1.85,"kitchen":1.85,"living":1.9,
    "majlis":1.9,"office":1.85,"laundry":1.8,"storage":1.8,
}


def moderate_room_expansion(cells, wall_thickness):
    """Trim oversized occupied wings *toward* the central corridor.

    Only regular room cells with actual program requirements are reduced.
    The corridor-facing boundary and requested min net area/side remain fixed.
    Unoccupied strips become exterior setbacks, yielding a finer freeform mass.
    Full geometric, furniture, door and daylight validation still decides acceptance.
    """
    result=[]
    for original in cells:
        cell=dict(original)
        kind=cell.get("kind")
        ratio=EXPANSION_MULTIPLIERS.get(kind)
        if ratio is None or not cell.get("request_id") or cell.get("door_side") not in ("east","west"):
            result.append(cell)
            continue
        t=wall_thickness
        net_depth=cell["depth"]-t
        if net_depth<=0:
            result.append(cell)
            continue
        target=max(t+cell["min_side"],
                   t+ratio*cell["min_area"]/net_depth,
                   t+net_depth/2.8)
        target=min(cell["width"],target)
        if target<cell["width"]-1e-6:
            if cell["door_side"]=="east":
                cell["x"]+=cell["width"]-target
            cell["width"]=target
        result.append(cell)
    return result


def clustered_topology(width, depth, corridor, front_fraction, split_fraction):
    """Two room clusters linked by a lateral node, without a full axial hall.

    Orthogonal bounded topology: independent front/back stems yield circulation
    bends and exterior recesses. Occupied cells determine the final silhouette.
    Parameters are searched against the actual program, never a fixed facade.
    """
    if min(width,depth,corridor)<=0:return None
    junction=depth*split_fraction
    front=width*front_fraction-corridor/2
    rear=width*(1-front_fraction)-corridor/2
    if min(front,rear,width-front-corridor,width-rear-corridor)<2.8:return None
    if min(junction,depth-junction-corridor)<5:return None
    left=min(front,rear);right=max(front,rear)+corridor
    halls=[dict(x=front,y=0.,width=corridor,depth=junction),
           dict(x=left,y=junction,width=right-left,depth=corridor),
           dict(x=rear,y=junction+corridor,width=corridor,depth=depth-junction-corridor)]
    lanes=[]
    for x,y,size in ((front,0.,junction),(rear,junction+corridor,depth-junction-corridor)):
        lanes.extend([dict(x=0.,y=y,width=x,depth=size,axis='y',door_side='east'),
                      dict(x=x+corridor,y=y,width=width-x-corridor,depth=size,axis='y',door_side='west')])
    return halls,lanes
