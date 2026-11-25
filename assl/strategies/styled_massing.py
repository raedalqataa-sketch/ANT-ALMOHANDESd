"""Four architectural treatments for one immutable, validated plan revision."""
import hashlib
import json
import math

import shapely
from shapely.geometry import Point, Polygon, box
from shapely.ops import triangulate, unary_union

from assl.openings_009 import cut, opening_fits, wall_cut, window_clear
from .geometry import exposed_edges, net_shape, shape

STYLES = (
    ("modern", "مودرن", "إطار غرافيتي ومظلة أفقية وشرائح خشبية", "#e6ddcc", "#353a3f"),
    ("najdi", "نجدي معاصر", "بوابة حجرية وحواجز سقف مسنّنة", "#c8a77e", "#967252"),
    ("contemporary", "حديث معاصر", "بوابة حجرية عميقة ونوافذ مؤطرة ودرجات الكتلة", "#d8c4a5", "#f0e2c8"),
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


def facade_schedule(proposal, thickness, height):
    """Derive a measurable facade opening schedule while retaining the approved plan."""
    schedules, review = [], []
    for index, (rooms, halls, level) in enumerate(zip(
            proposal["rooms_by_floor"], proposal["halls_by_floor"],
            proposal["opening_model_009"], strict=True)):
        enclosed = [r for r in rooms+halls if r["kind"] != "terrace"]
        windows = level["windows"]
        doors = level["doors"]
        scheduled = []
        for number, window in enumerate(windows, 1):
            candidates = [(r,e) for r in enclosed for e in exposed_edges(r,enclosed)
                          if (not window.get("room_id") or r["id"]==window["room_id"])
                          and opening_fits(window,e)]
            if not candidates:
                raise ValueError("FACADE_WINDOW_HAS_NO_EXTERIOR_HOST")
            room, edge = max(candidates,key=lambda item:item[1]["length"])
            kind = room["kind"]
            axis = 0 if window["axis"]=="x" else 1
            center = window["center"][axis]
            available = 2*min(center-edge["lo"]-.38,edge["hi"]-.38-center)
            maximum = 5.65 if kind in ("majlis","living","dining") else 1.35 if kind=="bathroom" else 3.75
            trial_width = round(max(window["width"], min(available,maximum,edge["length"]*.76)),5)
            sill = 1.55 if kind=="bathroom" else .95 if kind in ("kitchen","storage") else .30 if kind in ("majlis","living","dining") else .65
            head = min(height-.28, 2.89)
            sill = min(sill,head-.65)
            trial = {**window, "id":window.get("id",f"window-{number}"),"room_id":room["id"],
                     "width":trial_width,"height":head-sill,"operable_fraction":window.get("operable_fraction",.5)}
            obstacles = [*doors, *scheduled, *windows[number:]]
            # Widening must not consume a door, another opening, or an exterior return.
            if not opening_fits(trial,edge) or not window_clear(trial,room,enclosed,thickness) or any(
                    cut(trial,thickness).intersects(cut(o,thickness)) for o in obstacles):
                trial["width"] = window["width"]
            for other in scheduled:
                if cut(trial,thickness).intersection(cut(other,thickness)).area>1e-6:
                    raise ValueError("FACADE_WINDOW_OVERLAP")
            scheduled.append({**trial,"source_width":window["width"],"sill":sill,"head":head,
                              "floor":index,"privacy":kind=="bathroom"})
        covered = {w["room_id"] for w in scheduled}
        for room in rooms:
            if (room.get("request_id") and room["kind"]!="storage" or index and room["kind"] in {"living","master","bedroom","bathroom"}) and room["id"] not in covered:
                review.append({"floor":index,"room_id":room["id"],"reason":"WINDOW_REVIEW_REQUIRED"})
        schedules.append(scheduled)
    return schedules,review


def base_geometry(proposal, schedule):
    brief = proposal["brief_snapshot"]
    thickness, height = brief["wall_thickness"], brief["floor_height"]
    floors = []
    for rooms, halls, original, windows in zip(proposal["rooms_by_floor"], proposal["halls_by_floor"],
                                       proposal["opening_model_009"], schedule, strict=True):
        openings={**original,"windows":windows}
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
        for sign in (-1,1):
            a,b=sorted((sign*(width+.14),sign*(width+.43)))
            block(a,b,near,1.18,0,2.83,accent)
        block(-width-.43,width+.43,near,1.18,2.63,2.83,accent)
        block(-width-.43,width+.43,near,1.30,2.83,3.01,accent)


def frame_windows(mesh, floors, thickness, height, accent, style):
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
            projection={"contemporary":.50,"modern":.26,"classical":.24,"najdi":.21}[style]
            a,b = sorted((direction*(thickness/2-.01), direction*(thickness/2+projection)))
            w = window["width"]/2
            sill,head=window["sill"],window["head"]
            rim=.15 if style=="contemporary" else .09
            for lo,hi,bottom,top in ((-w-rim,-w,sill-rim,head+rim),(w,w+rim,sill-rim,head+rim),
                                     (-w,w,sill-rim,sill),(-w,w,head,head+rim)):
                trim = box(x+lo,y+a,x+hi,y+b) if along_x else box(x+a,y+lo,x+b,y+hi)
                mesh.extrude(trim,z+bottom,z+top,accent)
            for i in range(1,max(1,math.ceil(2*w/1.45))):
                u=-w+2*w*i/math.ceil(2*w/1.45)
                n0,n1=sorted((direction*(thickness/2-.025),direction*(thickness/2+.035)))
                strip=box(x+u-.027,y+n0,x+u+.027,y+n1) if along_x else box(x+n0,y+u-.027,x+n1,y+u+.027)
                mesh.extrude(strip,z+sill,z+head,"#353a3f")


def build_styles(proposal, progress=None):
    brief=proposal["brief_snapshot"]
    schedule,review=facade_schedule(proposal,brief["wall_thickness"],brief["floor_height"])
    floors, thickness, height = base_geometry(proposal,schedule)
    opening_model = floors[0][4]
    outside = [d for d in opening_model["doors"] if "OUTSIDE" in d["connects"]]
    entry = next((d for d in outside if d["receiving_room"] == "main-foyer"), None)
    entry = entry or (outside[0] if outside else None)
    if entry is None:
        raise ValueError("MASSING_ENTRY_REQUIRED")
    receiving = next(r for r in proposal["rooms_by_floor"][0]+proposal["halls_by_floor"][0]
                     if r["id"] == entry["receiving_room"])
    variants = []
    for index, (key, title, caption, wall, accent) in enumerate(STYLES):
        if progress:
            progress(30+index*16, "رفع الكتلة بطراز "+title)
        mesh = Mesh()
        for i,(footprint,shell,doors,windows,_) in enumerate(floors):
            z = i*height
            rooms = proposal["rooms_by_floor"][i]
            landing_void = unary_union([net_shape(room,thickness) for room in rooms
                                        if i and room["kind"] == "stair"])
            mesh.extrude(footprint.difference(landing_void),z-.18,z,"#a09a8e")
            terraces = unary_union([shape(room) for room in rooms if room["kind"] == "terrace"])
            mesh.extrude(terraces.difference(footprint),z-.18,z,"#a09a8e")
            portals=schedule[i]
            door_head=min(2.15,height-.18)
            breaks=sorted({0.,door_head,height-.18,*(w[k] for w in portals for k in ("sill","head"))})
            for low,high in zip(breaks,breaks[1:]):
                active=unary_union([wall_cut(w,thickness) for w in portals if w["sill"]<=low and w["head"]>=high])
                cuts=active.union(doors) if high<=door_head else active
                mesh.extrude(shell.difference(cuts),z+low,z+high,wall)
            for w in portals:
                glass=shell.intersection(wall_cut(w,thickness))
                mesh.extrude(glass,z+w["sill"],z+w["head"],"#939d98" if w["privacy"] else "#618a9b")
            roof = footprint.difference(floors[i+1][0]) if i+1<len(floors) else footprint
            if i+1 < len(floors):
                roof = roof.difference(unary_union([
                    shape(room) for room in proposal["rooms_by_floor"][i+1]
                    if room["kind"] == "terrace"]))
            mesh.extrude(roof,z+height-.18,z+height,"#aaa59a")
        for platform in proposal.get("entrance_platforms", ()):
            level = platform["level_m"]
            mesh.extrude(Polygon(platform["landing_polygon"]),level-.14,level,"#a09a8e")
            for step in platform["treads"]:
                level = step["level_m"]
                mesh.extrude(Polygon(step["polygon"]),level-.14,level,"#a09a8e")
        base_faces = len(mesh.faces)
        frame_windows(mesh,floors,thickness,height,accent,key)
        decorate(mesh,key,floors[-1][0],height*len(floors),entry,receiving,accent,thickness)
        variants.append(dict(id=key,title=title,caption=caption,faces=mesh.faces,base_faces=base_faces))
    geometry = {k:proposal[k] for k in ("rooms_by_floor","halls_by_floor","opening_model_009","brief_snapshot")}
    geometry["entrance_platforms"] = proposal.get("entrance_platforms", [])
    digest = hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    for variant in variants:
        variant["facade_sha256"]=hashlib.sha256(json.dumps(variant["faces"],separators=(",",":")).encode()).hexdigest()
    return dict(proposal_id=proposal["id"],revision=digest, floors=len(floors),units="m",
                styles=variants,facade_openings=schedule,facade_review=review)


def export_style_dxf(model, style_id):
    """A single compressed CAD file made of the same faces as the viewer."""
    import ezdxf
    from io import BytesIO, StringIO
    from zipfile import ZIP_DEFLATED, ZipFile

    style = next((s for s in model["styles"] if s["id"] == style_id), None)
    if style is None:
        raise ValueError("MASSING_STYLE_NOT_AVAILABLE")
    doc = ezdxf.new("R2010")
    doc.units = 6
    doc.header["$MEASUREMENT"] = 1
    space = doc.modelspace()
    meta = doc.ezdxf_metadata()
    meta["ANT_PLAN_REVISION"] = model["revision"]
    meta["ANT_FACADE_SHA256"] = style["facade_sha256"]
    meta["ANT_STYLE"] = style_id
    for vertices,color in style["faces"]:
        layer = "FACADE-"+color[1:].upper()
        if layer not in doc.layers:
            doc.layers.new(layer,dxfattribs={"color":7})
        entity = space.add_3dface(vertices,dxfattribs={"layer":layer})
        entity.rgb = tuple(int(color[i:i+2],16) for i in (1,3,5))
    stream = StringIO()
    doc.write(stream)
    stream.seek(0)
    reopened = ezdxf.read(stream)
    audit = reopened.audit()
    if audit.errors or audit.fixes or reopened.units != 6 or reopened.dxfversion != "AC1024":
        raise ValueError("MASSING_DXF_AUDIT_FAILED")
    if len(reopened.modelspace().query("3DFACE")) != len(style["faces"]):
        raise ValueError("MASSING_DXF_FACE_COUNT_MISMATCH")
    result=BytesIO()
    with ZipFile(result,"w",ZIP_DEFLATED) as archive:
        archive.writestr(f"ANT-{model['revision'][:12]}-{style_id}.dxf",stream.getvalue().encode("utf-8"))
    return result.getvalue()
