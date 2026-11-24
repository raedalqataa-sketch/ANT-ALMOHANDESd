"""Parametric classical details hosted on the existing entrance and terraces."""
import math

import shapely
from shapely.geometry import LineString, Point, Polygon, box


def add_portal(mesh, entry, receiving, footprint, thickness, height, wall, accent):
    x, y = entry["center"]
    along_x = entry["axis"] == "x"
    interior = receiving.representative_point()
    normal = (1 if y > interior.y else -1) if along_x else (1 if x > interior.x else -1)

    def plan(u, v):
        return (x + u, y + normal*v) if along_x else (x + normal*v, y + u)

    def block(left, right, near, far, bottom, top, color):
        polygon = Polygon([plan(u,v) for u,v in
                           ((left,near),(right,near),(right,far),(left,far))])
        mesh.extrude(polygon,bottom,top,color)

    half = entry["width"]/2
    near = thickness/2 + .002
    max_span = half + .28
    # Reserve the clear door width and find a recess that does not intersect
    # a neighboring room. Small entries can use the original simple surround.
    clearance = max_span + .03
    depth = next((depth for depth in (.90,.65,.42)
                  if footprint.intersection(Polygon([
                      plan(-clearance,near),plan(clearance,near),
                      plan(clearance,depth),plan(-clearance,depth)
                  ])).area < 1e-6), None)
    spring = 2.15
    if depth is None or spring + max_span > height + .12:
        return False

    for inner, outer, outer_depth, color in (
        (half+.012,half+.090,depth,wall),
        (half+.091,half+.171,depth-.055,accent),
        (half+.172,max_span,depth-.10,wall),
    ):
        for sign in (-1,1):
            lo,hi = sorted((sign*inner,sign*outer))
            block(lo,hi,near,outer_depth,0,spring,color)
        for index in range(24):
            a,b = (math.pi*k/24 for k in (index,index+1))
            arc = [(radius*math.cos(angle),spring+radius*math.sin(angle))
                   for radius,angle in ((inner,a),(inner,b),(outer,b),(outer,a))]
            front = [(*plan(u,outer_depth),z) for u,z in arc]
            back = [(*plan(u,near),z) for u,z in arc]
            mesh.face(front,color)
            mesh.face(back[::-1],color)
            for side in (1,3):
                end = (side+1)%4
                mesh.face([front[side],front[end],back[end],back[side]],color)

    for sign in (-1,1):
        lo,hi = sorted((sign*(half+.01),sign*max_span))
        block(lo,hi,near,depth+.035,0,.16,accent)
        block(lo,hi,near,depth+.035,spring-.09,spring,accent)
    crown = spring+max_span
    block(-.09,.09,near,depth-.045,crown-.13,crown+.04,accent)
    return True


def terrace_railings(mesh, terrace, facade, z, color):
    """Use terrace edges which are open to the outside, with detached balusters."""
    perimeter = terrace.boundary.difference(facade.buffer(.23))
    for edge in shapely.get_parts(perimeter):
        if edge.geom_type != "LineString" or edge.length < .60:
            continue
        points = list(edge.coords)
        for a,b in zip(points,points[1:]):
            length = math.dist(a,b)
            if length < .6:
                continue
            run = LineString([a,b])
            mesh.extrude(run.buffer(.055,cap_style=2),z+.89,z+1.0,color)
            mesh.extrude(run.buffer(.035,cap_style=2),z+.09,z+.16,color)
            count = max(2,math.ceil(length/.18))
            for i in range(1,count):
                center=run.interpolate(i/count,normalized=True)
                for low,high,width in ((.16,.29,.052),(.29,.73,.037),(.73,.89,.052)):
                    mesh.extrude(box(center.x-width,center.y-width,center.x+width,center.y+width),
                                 z+low,z+high,color)


def stair_pilasters(mesh, proposal, floors, entry, receiving, thickness, height, accent):
    """Emphasize an exterior stair wall continuous from ground to first floor."""
    from .geometry import exposed_edges

    objects = [rooms+halls for rooms,halls in
               zip(proposal["rooms_by_floor"],proposal["halls_by_floor"],strict=True)]
    stairs = [next((r for r in floor if r["kind"] == "stair"), None) for floor in objects]
    if len(stairs) != 2 or any(stair is None for stair in stairs):
        return False
    axis = entry["axis"]
    across = 1 if axis == "x" else 0
    normal = 1 if entry["center"][across] > receiving.representative_point().coords[0][across] else -1
    edges = [[e for e in exposed_edges(stair,floor) if e["axis"] == axis]
             for stair,floor in zip(stairs,objects,strict=True)]
    exterior = [floor[0] for floor in floors]
    options = []
    for low in edges[0]:
        for high in edges[1]:
            if abs(low["fixed"]-high["fixed"]) > 1e-6:
                continue
            start, end = max(low["lo"],high["lo"]), min(low["hi"],high["hi"])
            if end-start < 1.5:
                continue
            mid = (start+end)/2
            depth = low["fixed"]+normal*(thickness/2+.15)
            point = Point(mid,depth) if axis=="x" else Point(depth,mid)
            if any(outline.covers(point) for outline in exterior):
                continue
            options.append((end-start,start,end,low["fixed"]))
    if not options:
        return False
    _,start,end,fixed = max(options)
    a,b = sorted((fixed+normal*(thickness/2+.007),fixed+normal*(thickness/2+.21)))
    for mid in (start+.16,end-.16):
        pier = box(mid-.11,a,mid+.11,b) if axis=="x" else box(a,mid-.11,b,mid+.11)
        # Check the full strip against neighboring wings on both levels.
        if not any(pier.intersection(outline).area > 1e-7 for outline in exterior):
            mesh.extrude(pier,0,2*height-.16,accent)
    return True
