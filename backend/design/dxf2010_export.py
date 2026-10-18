"""AC1024 export gate. Requires ezdxf; never label an unchecked draft execution-ready."""
from pathlib import Path

def export_dxf2010(candidate: dict, destination: str, *, validated: bool = False):
    if not validated or candidate.get("approval", {}).get("status") not in ("APPROVED", "LOCKED"):
        raise ValueError("Export blocked: engineering validation and approval required")
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for floor in candidate.get("floors", []):
        level = floor.get("id", "F")
        layer = "A-WALL-" + level
        if layer not in doc.layers:
            doc.layers.new(layer)
        for wall in floor.get("walls", []):
            a, b = wall["start"], wall["end"]
            msp.add_line(tuple(a), tuple(b), dxfattribs={"layer": layer})
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output))
    check = ezdxf.readfile(str(output))
    if check.dxfversion != "AC1024":
        output.unlink(missing_ok=True)
        raise ValueError("DXF version mismatch")
    auditor = check.audit()
    if auditor.has_errors:
        output.unlink(missing_ok=True)
        raise ValueError("DXF structural audit failed")
    return str(output)
