"""Preliminary coordination of continuous wall axes across clustered levels."""
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from assl.openings_009 import wall_cut
from .geometry import shape


def wall_axis_segments(rooms, doors, thickness):
    """Extract orthogonal wall runs with door openings removed."""
    cuts = unary_union([wall_cut(door, thickness*0.55) for door in doors])
    directions = {"x": [], "y": []}
    for room in rooms:
        if room["kind"] == "terrace":
            continue
        ring = list(shape(room).exterior.coords)
        for a, b in zip(ring, ring[1:]):
            if abs(a[0]-b[0]) < 1e-7:
                direction = "y"
            elif abs(a[1]-b[1]) < 1e-7:
                direction = "x"
            else:
                continue
            directions[direction].append(LineString([a,b]))
    return {axis: unary_union(lines).difference(cuts) for axis,lines in directions.items()}


def family_grid_profile(brief):
    """Reserve preliminary bays before generating a south-facing family stack."""
    if brief.entrance_face != "south":
        raise ValueError("The initial grid-first profile supports a south entrance")
    width=brief.plot_width-brief.setbacks.west-brief.setbacks.east-brief.wall_thickness
    depth=brief.plot_depth-brief.setbacks.south-brief.setbacks.north-brief.wall_thickness
    ox,oy=round(width*.436,6),round(depth*.62,6)
    # Tie the two stair side walls to the family and east-wing wall runs.
    supports=((0,-4.2,False,"y"),(0,1.4,True,"y"),(0,4.64,True,"x"),
              (3.8,0,True,"x"),(3.8,4.64,True,"x"),(5.6,0,False,"x"),(8.6,0,False,"x"))
    return {
        "status":"GRID_FIRST_CONCEPT",
        "stair_origin":(ox,oy),
        "stair_width_m":3.8,
        "living_depth_m":6.7,
        "east_wall_offset_m":8.6,
        "east_bedroom_south_offset_m":-4.2,
        "points":[(round(ox+x,6),round(oy+y,6),roof) for x,y,roof,_ in supports],
        "support_directions":[axis for *_,axis in supports],
        "wall_alignment_tolerance_m":1e-6,
    }


def unsupported_grid_points(grid, axes, *, roof_only=False):
    tolerance=grid["wall_alignment_tolerance_m"]
    return [(x,y) for (x,y,roof),direction in zip(grid["points"],grid["support_directions"])
            if (not roof_only or roof) and axes[direction].distance(Point(x,y))>tolerance]


def draw_grid(space, grid, bounds, offset, roof_only=False):
    """Show the full reference grid on every level, independently of the walls."""
    xmin,ymin,xmax,ymax=bounds
    xs=sorted({x for x,_,_ in grid["points"]})
    ys=sorted({y for _,y,_ in grid["points"]})
    for index,x in enumerate(xs,1):
        space.add_line((x+offset,ymin-1),(x+offset,ymax+1),dxfattribs={"layer":"STRUCTURAL_GRID"})
        space.add_text(f"X{index}",dxfattribs={"layer":"STRUCTURAL_GRID_LABELS",
                       "insert":(x+offset,ymax+1.15),"height":.22})
    for index,y in enumerate(ys,1):
        space.add_line((xmin+offset-1,y),(xmax+offset+1,y),dxfattribs={"layer":"STRUCTURAL_GRID"})
        space.add_text(f"Y{index}",dxfattribs={"layer":"STRUCTURAL_GRID_LABELS",
                       "insert":(xmin+offset-1.7,y),"height":.22})
    for x,y,roof in grid["points"]:
        if roof_only and not roof:
            continue
        space.add_point((x+offset,y),dxfattribs={"layer":"SUPPORT_CANDIDATES"})
        space.add_text("+",dxfattribs={"layer":"SUPPORT_CANDIDATES","insert":(x+offset-.07,y-.08),
                                      "height":.18})
