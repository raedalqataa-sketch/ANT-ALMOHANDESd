"""Export verified site benchmarks as one metric AutoCAD 2010 drawing."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import ezdxf
from ezdxf import bbox, zoom
from ezdxf.addons import Importer
from ezdxf.math import Matrix44

from assl.strategies.clustered_multilevel import draw_level
from assl.strategies.export import export_dxf
from assl.strategies.styled_massing import geometry_fingerprint
from backend.design.general_models import VillaBrief

ACCEPTED_SITES = ("narrow-28x38", "wide-36x40")


def add_plans(doc, brief, plan, row_y, label):
    ground = {
        **plan, "rooms_by_floor": plan["rooms_by_floor"][:1],
        "halls_by_floor": plan["halls_by_floor"][:1],
        "opening_model_009": plan["opening_model_009"][:1],
    }
    with TemporaryDirectory() as temp:
        path = Path(temp) / "ground.dxf"
        export_dxf(brief, ground, path)
        source = ezdxf.readfile(path)
    plans = source.modelspace()
    for layer in ("TERRACES", "STAIR_VOID"):
        source.layers.new(layer, dxfattribs={"color": 7})
    ground_bounds = bbox.extents(plans)
    upper = plan["rooms_by_floor"][1]
    offset = ground_bounds.extmax.x + 5 - min(room["x"] for room in upper)
    draw_level(plans, upper, plan["opening_model_009"][1]["doors"], brief.wall_thickness, offset)
    for opening in plan["slab_openings_by_floor"][1]:
        plans.add_lwpolyline(
            [(x + offset, y) for x, y in opening], close=True,
            dxfattribs={"layer": "STAIR_VOID"},
        )
    bounds = bbox.extents(plans)
    heading_y = bounds.extmax.y + 1.5
    for title, start in (
        (f"{label} | GROUND +0.00 m", ground_bounds.extmin.x),
        (f"{label} | FIRST +{brief.floor_height:.2f} m", ground_bounds.extmax.x + 5),
    ):
        plans.add_text(title, dxfattribs={"insert": (start, heading_y), "height": .36, "layer": "REVIEW_NOTES"})
    shift = Matrix44.translate(-bounds.extmin.x, row_y-bounds.extmin.y, 0)
    for entity in plans:
        entity.transform(shift)
    importer = Importer(source, doc)
    importer.import_modelspace()
    importer.finalize()
    return bounds.size.x, bounds.size.y + 3


def add_massing(space, style, x, y, layer):
    vertices = [point for face, _ in style["faces"] for point in face]
    min_x, min_y = (min(point[axis] for point in vertices) for axis in (0, 1))
    max_x, max_y = (max(point[axis] for point in vertices) for axis in (0, 1))
    for points, color in style["faces"]:
        face = space.add_3dface(
            [(x + u - min_x, y + v - min_y, z) for u, v, z in points],
            dxfattribs={"layer": layer},
        )
        face.rgb = tuple(bytes.fromhex(color[1:]))
    return max_x - min_x, max_y - min_y


def export(evidence, path):
    doc = ezdxf.new("R2010")
    doc.units = 6
    doc.header["$MEASUREMENT"] = 1
    space = doc.modelspace()
    expected_faces = {}
    expected_labels = []
    row_y = 0.0
    for site in ACCEPTED_SITES:
        group = evidence / site
        plans = json.loads((group / "floor-plans.json").read_text())
        models = json.loads((group / "massing.json").read_text())
        verification = json.loads((group / "verification.json").read_text())
        if len(plans) != 2 or len(models) != 2:
            raise ValueError(f"Incomplete alternative evidence for {site}")
        for index, (plan, model, check) in enumerate(zip(plans, models, verification["alternatives"], strict=True), 1):
            if not (
                plan["id"] == model["proposal_id"] == check["proposal_id"]
                and model["revision"] == check["revision"] == geometry_fingerprint(plan)
                and model["units"] == "m" and model["floors"] == 2 and len(model["styles"]) == 4
            ):
                raise ValueError(f"Plan and massing evidence disagree for {site} alternative {index}")
            brief = VillaBrief.model_validate(plan["brief_snapshot"])
            label = f"{site.upper()} | ALT {index}"
            width, height = add_plans(doc, brief, plan, row_y, label)
            expected_labels.extend((f"{label} | GROUND +0.00 m", f"{label} | FIRST +{brief.floor_height:.2f} m"))
            x = width + 6
            for style in model["styles"]:
                layer = f"3D_{site.upper()}_{index}_{style['id'].upper()}"
                doc.layers.new(layer, dxfattribs={"color": 7})
                dx, dy = add_massing(space, style, x, row_y, layer)
                space.add_text(
                    f"{label} | {style['id'].upper()} 3D",
                    dxfattribs={"insert": (x, row_y + dy + 1.5), "height": .36, "layer": "REVIEW_NOTES"},
                )
                expected_faces[layer] = len(style["faces"])
                x += dx + 5
                height = max(height, dy + 3)
            row_y += height + 6
    restricted = json.loads((evidence / "restricted-17x24.json").read_text())
    failures = {failure["reason"] for failure in restricted["failures"]}
    if restricted["proposals"] or not failures:
        raise ValueError("Restricted site did not report its rejection")
    space.add_mtext(
        "RESTRICTED 17 x 24 m | No accepted alternative\n" + "\n".join(sorted(failures)),
        dxfattribs={"insert": (0, row_y + 2), "char_height": .35, "width": 50, "layer": "REVIEW_NOTES"},
    )
    zoom.extents(space, factor=1.1)
    doc.saveas(path)

    reopened = ezdxf.readfile(path)
    audit = reopened.audit()
    msp = reopened.modelspace()
    labels = {item.dxf.text for item in msp.query("TEXT")}
    voids = msp.query('LWPOLYLINE[layer=="STAIR_VOID"]')
    if (reopened.dxfversion != "AC1024" or reopened.units != 6 or reopened.header["$MEASUREMENT"] != 1
            or audit.errors or audit.fixes or not set(expected_labels) <= labels
            or len(voids) != 4 or not all(poly.closed for poly in voids)
            or Counter(face.dxf.layer for face in msp.query("3DFACE")) != expected_faces):
        raise ValueError("The exported DXF failed its reopen checks")
    print(f"Verified {path.name}: {len(expected_labels)} plans, {len(expected_faces)} styled 3D models")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("dxf", type=Path)
    args = parser.parse_args()
    export(args.evidence, args.dxf)
