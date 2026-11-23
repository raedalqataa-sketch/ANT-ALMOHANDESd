"""Deliver three coordinated family-stack alternatives on the same client brief."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import Matrix44

from backend.design.general_models import VillaBrief
from .clustered_multilevel import build_family_stack, draw_level
from .export import export_dxf
from .geometry import shape
from .structural_grid import draw_grid

PROFILES = (
    ((1, 1, 1), "east", "BEDROOMS ON THREE SIDES"),
    ((2, 1, 0), "east", "TWO BEDROOMS IN WEST WING"),
    ((1, 1, 1), "south", "SOUTH MASTER TERRACE"),
)


def export_alternatives(brief, archive_path):
    candidates = [
        build_family_stack(brief, wing_group=group, terrace_side=terrace)
        for group, terrace, _ in PROFILES
    ]
    signatures = {
        tuple((room["id"], shape(room).normalize().wkb) for room in candidate["first"])
        for candidate in candidates
    }
    if len(signatures) != len(PROFILES):
        raise ValueError("The selected first-floor layouts are not distinct")

    target = ezdxf.new("R2010")
    target.units = 6
    with TemporaryDirectory() as temp:
        path = Path(temp) / "ground.dxf"
        next_x = 0
        for letter, candidate, (_, _, caption) in zip("ABC", candidates, PROFILES, strict=True):
            export_dxf(candidate["brief"], candidate["ground"], path)
            source = ezdxf.readfile(path)
            source.layers.new("TERRACES", dxfattribs={"color": 7})
            source.linetypes.new("ANT_AXIS", dxfattribs={"description":"Structural axes","pattern":[.6,.35,-.15,.02,-.08]})
            for name in ("STRUCTURAL_GRID", "STRUCTURAL_GRID_LABELS", "SUPPORT_CANDIDATES"):
                attrs = {"color": 7, **({"linetype": "ANT_AXIS"} if name == "STRUCTURAL_GRID" else {})}
                source.layers.new(name, dxfattribs=attrs)
            space = source.modelspace()
            ground_box = bbox.extents(space)
            first_bounds = [shape(r).bounds for r in candidate["first"]]
            first_left = min(b[0] for b in first_bounds)
            offset = ground_box.extmax.x + 7 - first_left
            draw_level(space, candidate["first"], candidate["doors"], brief.wall_thickness, offset)
            bounds = (min(ground_box.extmin.x, first_left), min(ground_box.extmin.y, min(b[1] for b in first_bounds)),
                      max(ground_box.extmax.x, max(b[2] for b in first_bounds)),
                      max(ground_box.extmax.y, max(b[3] for b in first_bounds)))
            for dx in (0, offset):
                draw_grid(space, candidate["structural_grid"], bounds, dx)
            label_y = bounds[3] + 4
            for label, dx in ((f"{letter} | GROUND +0.00 m", bounds[0]),
                              (f"{letter} | FIRST +{brief.floor_height:.2f} m | {caption}", first_left+offset)):
                space.add_text(label, dxfattribs={"insert":(dx,label_y),"height":.38,"layer":"ROOM_LABELS"})
            extents = bbox.extents(space)
            transform = Matrix44.translate(next_x-extents.extmin.x, -extents.extmin.y, 0)
            for drawing in space:
                drawing.transform(transform)
            importer = Importer(source, target)
            importer.import_modelspace()
            importer.finalize()
            next_x += extents.size.x + 10
        final = Path(temp) / "ANT-Central-Three-Alternatives-R2010.dxf"
        target.saveas(final)
        reopened = ezdxf.readfile(final)
        audit = reopened.audit()
        labels = [e.dxf.text for e in reopened.modelspace().query("TEXT")]
        if (reopened.dxfversion != "AC1024" or reopened.units != 6 or audit.errors or audit.fixes
                or not all(any(label.startswith(f"{key} | {level}") for label in labels)
                           for key in "ABC" for level in ("GROUND", "FIRST"))):
            raise ValueError("Combined DXF failed reopen checks")
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            archive.write(final, final.name)
    return candidates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    for name, candidate in zip("ABC", export_alternatives(
            VillaBrief.model_validate_json(args.brief.read_bytes()), args.archive), strict=True):
        print(name, candidate["footprint_metrics"])
