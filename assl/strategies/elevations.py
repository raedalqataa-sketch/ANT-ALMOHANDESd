"""Metric orthographic elevations of the same mesh used by the massing viewer."""
from collections import defaultdict
from itertools import pairwise

from shapely import get_parts
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from assl.openings_009 import opening_fits
from .geometry import exposed_edges, shape
from .styled_massing import DOOR_HEAD_M, WINDOW_HEAD_M, WINDOW_SILL_M, mesh_fingerprint

FACADE_STYLES = ("modern", "classical")
# (horizontal axis/sign, depth axis/sign). Larger depth faces the viewer.
VIEWS = {
    "south": (0, 1, 1, -1),
    "north": (0, -1, 1, 1),
    "east": (1, 1, 0, 1),
    "west": (1, -1, 0, -1),
}
DEPTH_TOLERANCE_M = 1e-5
AREA_TOLERANCE_M2 = 1e-8


def project_faces(faces, side):
    axis, sign, depth_axis, depth_sign = VIEWS[side]
    projected = []
    for face, color in faces:
        points = [(sign*p[axis], p[2]) for p in face]
        polygon = Polygon(points)
        if polygon.area <= AREA_TOLERANCE_M2 or not polygon.is_valid:
            continue
        depth = [depth_sign*p[depth_axis] for p in face]
        u0, z0 = points[0]
        for i in range(1, len(points)-1):
            u1, z1 = points[i][0]-u0, points[i][1]-z0
            u2, z2 = points[i+1][0]-u0, points[i+1][1]-z0
            det = u1*z2-u2*z1
            if abs(det) > AREA_TOLERANCE_M2:
                d1, d2 = depth[i]-depth[0], depth[i+1]-depth[0]
                a, b = (d1*z2-d2*z1)/det, (u1*d2-u2*d1)/det
                plane = tuple(round(v, 7) for v in (a, b, depth[0]-a*u0-b*z0))
                projected.append((polygon, plane, min(depth), max(depth), color))
                break
    return projected


def nearer_part(polygon, plane, other_plane):
    """Clip a projected face to the region where it sits in front of another."""
    a, b, c = (p-q for p, q in zip(plane, other_plane, strict=True))
    points = list(polygon.exterior.coords)
    distances = [a*u+b*z+c-DEPTH_TOLERANCE_M for u, z in points]
    if min(distances) >= 0:
        return polygon
    if max(distances) <= 0:
        return None
    visible = []
    for ((u, z), d), ((v, w), e) in pairwise(zip(points, distances, strict=True)):
        if d >= 0:
            visible.append((u, z))
        if (d >= 0) != (e >= 0):
            fraction = d/(d-e)
            visible.append((u+fraction*(v-u), z+fraction*(w-z)))
    return Polygon(visible) if len(visible) >= 3 else None


def elevation_surfaces(faces, side):
    planes = project_faces(faces, side)
    tree = STRtree([item[0] for item in planes])
    patches = defaultdict(list)
    for poly, plane, low, high, color in planes:
        occluders = []
        covered = False
        for index in tree.query(poly):
            other, other_plane, other_low, other_high, _ = planes[index]
            if plane == other_plane or other_high <= low+DEPTH_TOLERANCE_M:
                continue
            front = other if other_low > high+DEPTH_TOLERANCE_M else nearer_part(other, other_plane, plane)
            if front is None or front.area <= AREA_TOLERANCE_M2:
                continue
            if front.covers(poly):
                covered = True
                break
            occluders.append(front)
        if not covered:
            visible = poly.difference(unary_union(occluders)) if occluders else poly
            if visible.area > AREA_TOLERANCE_M2:
                patches[(plane, color)].append(visible)
    surfaces = []
    for (_, color), polygons in patches.items():
        for part in get_parts(unary_union(polygons)):
            if part.geom_type == "Polygon" and part.area > AREA_TOLERANCE_M2:
                rings = [[list(point) for point in ring.coords] for ring in (part.exterior, *part.interiors)]
                surfaces.append({"color": color, "rings": rings})
    return surfaces


def opening_references(proposal):
    """Locate exterior openings on their hosted face, including recessed hosts."""
    references = {side: [] for side in VIEWS}
    height = proposal["brief_snapshot"]["floor_height"]
    for floor, (rooms, halls, openings) in enumerate(zip(
        proposal["rooms_by_floor"], proposal["halls_by_floor"], proposal["opening_model_009"], strict=True
    )):
        objects = [r for r in rooms+halls if r["kind"] != "terrace"]
        hosts = [(shape(r), exposed_edges(r, objects)) for r in objects]
        for kind, low, high in (("doors", 0, DOOR_HEAD_M), ("windows", WINDOW_SILL_M, WINDOW_HEAD_M)):
            for opening in openings[kind]:
                x, y = opening["center"]
                for polygon, edges in hosts:
                    if not any(opening_fits(opening, edge) for edge in edges):
                        continue
                    if opening["axis"] == "x":
                        side = "south" if polygon.covers(Point(x, y+.001)) else "north"
                    else:
                        side = "west" if polygon.covers(Point(x+.001, y)) else "east"
                    axis, sign, _, _ = VIEWS[side]
                    references[side].append({
                        "kind": kind, "floor": floor, "center_m": sign*opening["center"][axis],
                        "width_m": opening["width"], "bottom_m": floor*height+low, "top_m": floor*height+high,
                    })
                    break
    return references


def build_elevations(proposal, model):
    references = opening_references(proposal)
    height = proposal["brief_snapshot"]["floor_height"]
    return {
        "proposal_id": model["proposal_id"], "revision": model["revision"], "units": model["units"],
        "entrance_face": proposal["brief_snapshot"]["entrance_face"],
        "levels_m": [floor*height for floor in range(model["floors"]+1)],
        "options": [
            {key: style[key] for key in ("id", "title", "caption")} | {
                "mesh_revision": mesh_fingerprint(style),
                "views": {
                    side: {"surfaces": elevation_surfaces(style["faces"], side), "openings": references[side]}
                    for side in VIEWS
                }
            }
            for style in model["styles"]
        ],
    }
