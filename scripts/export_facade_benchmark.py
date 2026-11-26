"""Export the tested facade options for the narrow site as one metric DXF."""
import argparse
import json
from pathlib import Path

import ezdxf
from ezdxf import zoom
from shapely.geometry import Polygon
from shapely.ops import unary_union

from assl.strategies.elevations import VIEWS
from assl.strategies.styled_massing import geometry_fingerprint
from backend.design.general_api import MassingRequest, PlanSource, concept_facades, concept_massing


def verify_projection(view, side, style, plan, levels):
    axis, sign, _, _ = VIEWS[side]
    projected = [Polygon([(sign*p[axis], p[2]) for p in face]) for face, _ in style["faces"]]
    silhouette = unary_union([p for p in projected if p.is_valid and p.area > 1e-8])
    visible = unary_union([Polygon(s["rings"][0], s["rings"][1:]) for s in view["surfaces"]])
    if visible.symmetric_difference(silhouette).area > 1e-4:
        raise ValueError(f"Facade silhouette differs from massing: {style['id']} {side}")
    for mark in view["openings"]:
        openings = plan["opening_model_009"][mark["floor"]][mark["kind"]]
        datum = levels[mark["floor"]]
        bottom = datum if mark["kind"] == "doors" else datum + .90
        if (mark["bottom_m"] != bottom or mark["top_m"] != datum+2.15
                or not any(o["width"] == mark["width_m"] and sign*o["center"][axis] == mark["center_m"]
                           for o in openings)):
            raise ValueError(f"Facade opening differs from hosted opening: {style['id']} {side}")
    return visible.bounds


def draw_view(space, view, bounds, levels, x, y, label):
    left, bottom, right, top = bounds
    dx, dy = x-left, y-bottom
    attrs = {"layer": "ELEVATION"}
    for surface in view["surfaces"]:
        for ring in surface["rings"]:
            space.add_lwpolyline([(u+dx,z+dy) for u,z in ring[:-1]], close=True, dxfattribs=attrs)
    for level in levels:
        lvl = level+dy
        space.add_line((x-.70,lvl),(x-.10,lvl),dxfattribs={"layer":"LEVELS"})
        space.add_text(f"+{level:.2f} m",dxfattribs={"insert":(x-2.30,lvl), "height":.25, "layer":"LEVELS"})
    for opening in view["openings"]:
        c, half = opening["center_m"]+dx, opening["width_m"]/2
        lo, hi = opening["bottom_m"]+dy, opening["top_m"]+dy
        space.add_lwpolyline([(c-half,lo),(c+half,lo),(c+half,hi),(c-half,hi)], close=True,
                             dxfattribs={"layer":"OPENING_REFERENCE"})
    space.add_text(label,dxfattribs={"insert":(x,y+top-bottom+1.50), "height":.38, "layer":"NOTES"})
    space.add_text(f"Envelope: {right-left:.2f} m W x {top-bottom:.2f} m H",
                   dxfattribs={"insert":(x,y-.8), "height":.28, "layer":"NOTES"})
    return right-left, top-bottom


def export(evidence, path):
    folder = evidence / "narrow-28x38"
    plans = json.loads((folder / "floor-plans.json").read_text())
    if len(plans) != 2:
        raise ValueError("Expected two verified plans for the narrow site")
    doc = ezdxf.new("R2010")
    doc.units = 6
    doc.header["$MEASUREMENT"] = 1
    for name, color in (("ELEVATION",7), ("LEVELS",8), ("NOTES",7), ("OPENING_REFERENCE",4)):
        doc.layers.new(name, dxfattribs={"color":color})
    doc.layers.get("OPENING_REFERENCE").off()
    space = doc.modelspace()
    labels, results = [], []
    y = 0
    for index, plan in enumerate(plans, 1):
        facades = concept_facades(PlanSource(proposal=plan))
        if facades["revision"] != geometry_fingerprint(plan) or facades["proposal_id"] != plan["id"]:
            raise ValueError("Facade plan fingerprint mismatch")
        levels = facades["levels_m"]
        height = plan["brief_snapshot"]["floor_height"]
        if levels != [0, height, 2*height] or [o["id"] for o in facades["options"]] != ["modern","classical"]:
            raise ValueError("Unexpected facade options or floor levels")
        for option in facades["options"]:
            choice = {
                "proposal_id":facades["proposal_id"], "revision":facades["revision"],
                "style":option["id"], "mesh_revision":option["mesh_revision"],
            }
            model = concept_massing(MassingRequest(proposal=plan, facade_choice=choice))
            style, = model["styles"]
            if style["mesh_revision"] != option["mesh_revision"] or style["id"] != option["id"]:
                raise ValueError("Selected facade does not match the massing")
            x, row_height = 0, 0
            for side, view in option["views"].items():
                bounds = verify_projection(view, side, style, plan, levels)
                label = f"ALT {index} | {option['id'].upper()} | {side.upper()} | {facades['revision'][:10]}"
                width, view_height = draw_view(space, view, bounds, levels, x, y, label)
                labels.append(label)
                x += width + 8
                row_height = max(row_height, view_height)
            y += row_height + 6
        results.append(facades)
    notes = ("28 x 38 m | CONCEPT DESIGN | METRES\n"
             "ASSUMED DOOR HEAD +2.15 m; WINDOW SILL +0.90 m; HEAD +2.15 m FROM FLOOR.\n"
             "OPENING_REFERENCE (OFF) INCLUDES RECESSED AND OCCLUDED HOSTS.")
    space.add_mtext(notes, dxfattribs={"insert":(0,y), "char_height":.35, "width":55, "layer":"NOTES"})
    zoom.extents(space)
    doc.saveas(path)
    loaded = ezdxf.readfile(path)
    audit = loaded.audit()
    written = {entity.dxf.text for entity in loaded.modelspace().query("TEXT")}
    if loaded.dxfversion != "AC1024" or loaded.units != 6 or audit.errors or audit.fixes or not set(labels) <= written:
        raise ValueError("Facade DXF failed its reopen checks")
    (folder / "facades.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Verified {len(labels)} metric elevations in {path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("dxf", type=Path)
    args = parser.parse_args()
    export(args.evidence, args.dxf)
