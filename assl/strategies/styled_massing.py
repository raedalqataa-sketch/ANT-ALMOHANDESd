"""Four architectural treatments for one immutable, validated plan revision."""
import hashlib
import json
import math

import shapely
from shapely.geometry import Point, Polygon, box
from shapely.ops import triangulate, unary_union

from assl.openings_009 import wall_cut
from .geometry import net_shape, shape

STYLES = (
    ("modern", "مودرن", "إطار غرافيتي ومظلة أفقية وشرائح خشبية", "#e6ddcc", "#353a3f"),
    ("najdi", "نجدي معاصر", "بوابة حجرية وحواجز سقف مسنّنة", "#c8a77e", "#967252"),
    ("mediterranean", "متوسطي", "مدخل مقوّس وسقف مائل بلون القرميد", "#f1dfc4", "#ab543c"),
    ("classical", "كلاسيكي مبسّط", "أعمدة مدخل وكورنيش متدرّج", "#e5dfd4", "#b0a08a"),
)


class Mesh:
    def __init__(self):
        self.faces = []

    def face(self, points, color):
        self.faces.append([[[round(v, 5) for v in p] for p in points], color])

    def extrude(self, geometry, z0, z1, color):
        triangulator = getattr(shapely, "constrained_delaunay_triangles", None)
        for part in shapely.get_parts(geometry):
            if part.geom_type != "Polygon" or part.area < 1e-8:
                continue
            part = shapely.geometry.polygon.orient(part, 1)
            triangles = (list(triangulator(part).geoms) if triangulator
                         else [item for item in triangulate(part) if part.covers(item)])
            if abs(sum(t.area for t in triangles)-part.area) > 1e-6:
                raise ValueError("MASSING_TRIANGULATION_INCOMPLETE")
            for triangle in triangles:
                points = list(triangle.exterior.coords)[:3]
                self.face([(x, y, z1) for x, y in points], color)
                self.face([(x, y, z0) for x, y in reversed(points)], color)
            for ring in (part.exterior, *part.interiors):
                points = list(ring.coords)
                for a, b in zip(points, points[1:]):
                    self.face([(*a,z0), (*b,z0), (*b,z1), (*a,z1)], color)


def base_geometry(proposal):
    brief = proposal["brief_snapshot"]
    thickness, height = brief["wall_thickness"], brief["floor_height"]
    floors = []
    for rooms, halls, openings in zip(proposal["rooms_by_floor"], proposal["halls_by_floor"],
                                       proposal["opening_model_009"], strict=True):
        enclosed = [room for room in rooms+halls if room["kind"] != "terrace"]
        footprint = unary_union([shape(room) for room in enclosed]).buffer(thickness/2, join_style=2)
        shell = unary_union([shape(room).buffer(thickness/2, join_style=2).difference(
            net_shape(room, thickness)) for room in enclosed])
        doors = unary_union([wall_cut(o, thickness/2+1e-6 if o.get("open_passage") else thickness)
                             for o in openings["doors"]])
        windows = unary_union([wall_cut(o, thickness) for o in openings["windows"]])
        floors.append((footprint, shell, doors, windows, openings))
    if not floors or not 2.3 <= height <= 6:
        raise ValueError("MASSING_FLOOR_GEOMETRY_UNSUPPORTED")
    return floors, thickness, height


def decorate(mesh, style, roof, levels, entry, receiving, accent, thickness):
    top = levels
    def band(projection, z, height, color):
        mesh.extrude(roof.buffer(projection, join_style=2).difference(
            roof.buffer(-.12, join_style=2)), z, z+height, color)
    if style == "modern":
        band(.24, top-.14, .28, accent)
    elif style == "najdi":
        band(.05, top, .34, accent)
        for ring in shapely.get_parts(roof):
            for a, b in zip(ring.exterior.coords, list(ring.exterior.coords)[1:]):
                length = math.dist(a,b)
                for i in range(1, int(length/.74)):
                    x,y = (a[k]+(b[k]-a[k])*i*.74/length for k in range(2))
                    mesh.extrude(box(x-.14,y-.14,x+.14,y+.14),top+.31,top+.63,accent)
    elif style == "classical":
        for projection, z, height in ((.14,top-.16,.12),(.28,top-.04,.14),(.18,top+.10,.13)):
            band(projection, z, height, accent)
    else:
        band(.17, top-.1, .21, accent)

    x, y = entry["center"]
    along_x = entry["axis"] == "x"
    interior = shape(receiving).representative_point()
    normal = (1 if y>interior.y else -1) if along_x else (1 if x>interior.x else -1)
    width = entry["width"]/2
    def world(u, v, z):
        return (x+u,y+normal*v,z) if along_x else (x+normal*v,y+u,z)
    def block(left, right, near, far, low, high, color):
        polygon = Polygon([world(u,v,0)[:2] for u,v in
                           ((left,near),(right,near),(right,far),(left,far))])
        mesh.extrude(polygon,low,high,color)
    near = thickness/2
    # Keep supports outside the width of the selected opening.
    if style == "modern":
        block(-width-.6,width+.6,near,1.5,2.32,2.57,accent)
        for i in range(4):
            pos=width+.18+i*.1
            block(pos,pos+.035,near,.45,.25,2.32,"#845737")
    elif style == "najdi":
        for sign in (-1,1):
            a,b=sorted((sign*(width+.10),sign*(width+.42)))
            block(a,b,near,.58,.12,2.6,accent)
        block(-width-.42,width+.42,near,.58,2.31,2.66,accent)
    elif style == "classical":
        for sign in (-1,1):
            a,b=sorted((sign*(width+.18),sign*(width+.37)))
            block(a,b,1,1.2,0,2.33,accent)
            block(a-.08,b+.08,.95,1.25,0,.18,accent)
            block(a-.07,b+.07,.95,1.25,2.2,2.36,accent)
        block(-width-.5,width+.5,near,1.27,2.36,2.63,accent)
    else:
        radius=width+.1
        for i in range(16):
            a,b=(math.pi*k/16 for k in (i,i+1))
            for depth in (.95,1.19):
                points=[world(r*math.cos(theta),depth,1.62+r*math.sin(theta))
                        for r,theta in ((radius,a),(radius,b),(radius+.16,b),(radius+.16,a))]
                mesh.face(points,accent)
        for sign in (-1,1):
            a,b=sorted((sign*radius,sign*(radius+.16)))
            block(a,b,.95,1.19,0,1.62,accent)
        span=radius+.34
        ridge=min(3.45,max(3.02,1.62+radius+.45))
        eave=ridge-.25
        for sign in (-1,1):
            mesh.face([world(0,near,ridge),world(0,1.4,ridge),
                       world(sign*span,1.4,eave),world(sign*span,near,eave)],accent)


def frame_windows(mesh, floors, thickness, height, accent):
    for index, (footprint, _, _, _, openings) in enumerate(floors):
        z = index*height
        for window in openings["windows"]:
            x,y = window["center"]
            along_x = window["axis"] == "x"
            test = thickness/2+.08
            probes = ((x,y+test),(x,y-test)) if along_x else ((x+test,y),(x-test,y))
            inside = [footprint.covers(Point(q)) for q in probes]
            if inside[0] == inside[1]:
                continue
            direction = 1 if not inside[0] else -1
            a,b = sorted((direction*(thickness/2-.01), direction*(thickness/2+.16)))
            w = window["width"]/2
            for lo,hi,bottom,top in ((-w-.09,-w,.81,2.24),(w,w+.09,.81,2.24),
                                     (-w,w,.81,.9),(-w,w,2.15,2.24)):
                trim = box(x+lo,y+a,x+hi,y+b) if along_x else box(x+a,y+lo,x+b,y+hi)
                mesh.extrude(trim,z+bottom,z+top,accent)


def build_styles(proposal):
    floors, thickness, height = base_geometry(proposal)
    opening_model = floors[0][4]
    outside = [d for d in opening_model["doors"] if "OUTSIDE" in d["connects"]]
    entry = next((d for d in outside if d["receiving_room"] == "main-foyer"), None)
    entry = entry or (outside[0] if outside else None)
    if entry is None:
        raise ValueError("MASSING_ENTRY_REQUIRED")
    receiving = next(r for r in proposal["rooms_by_floor"][0]+proposal["halls_by_floor"][0]
                     if r["id"] == entry["receiving_room"])
    variants = []
    for key, title, caption, wall, accent in STYLES:
        mesh = Mesh()
        for i,(footprint,shell,doors,windows,_) in enumerate(floors):
            z = i*height
            mesh.extrude(footprint,z-.18,z,"#a09a8e")
            mesh.extrude(shell.difference(doors),z,z+.9,wall)
            mesh.extrude(shell.difference(doors.union(windows)),z+.9,z+2.15,wall)
            mesh.extrude(shell,z+2.15,z+height,wall)
            glass = shell.intersection(windows)
            mesh.extrude(glass,z+.9,z+2.15,"#618a9b")
            roof = footprint.difference(floors[i+1][0]) if i+1<len(floors) else footprint
            mesh.extrude(roof,z+height-.18,z+height,"#aaa59a")
        for platform in proposal.get("entrance_platforms", ()):
            level = platform["level_m"]
            mesh.extrude(Polygon(platform["landing_polygon"]),level-.14,level,"#a09a8e")
            for step in platform["treads"]:
                level = step["level_m"]
                mesh.extrude(Polygon(step["polygon"]),level-.14,level,"#a09a8e")
        base_faces = len(mesh.faces)
        if key == "modern":
            frame_windows(mesh,floors,thickness,height,accent)
        decorate(mesh,key,floors[-1][0],height*len(floors),entry,receiving,accent,thickness)
        variants.append(dict(id=key,title=title,caption=caption,faces=mesh.faces,base_faces=base_faces))
    geometry = {k:proposal[k] for k in ("rooms_by_floor","halls_by_floor","opening_model_009","brief_snapshot")}
    geometry["entrance_platforms"] = proposal.get("entrance_platforms", [])
    digest = hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return dict(proposal_id=proposal["id"],revision=digest, floors=len(floors),units="m",styles=variants)
