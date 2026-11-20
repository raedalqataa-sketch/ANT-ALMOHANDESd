"""Regression coverage for the central release boundary."""
import copy
import hashlib
import json

from backend.design.auto_repair import fingerprint
from backend.design.central_engine import REQUIRED_CHECKS, find_file, verified_files


def drawing_set(folder):
    revision = "test_revision"
    model = {
        "model_revision_id": revision,
        "floors": [{"id": "GF", "rooms": [{"id": "r1", "x": 1}]}],
        "release": {"drawing_export_allowed": True, "executive_issue_allowed": False},
        "checks": [{"check_id": row, "status": "PASS"} for row in sorted(REQUIRED_CHECKS)],
        "downloads": {ext: f"/api/files/{revision}.{ext}" for ext in ("pdf", "dxf", "json")},
        "previews": {floor: f"/api/files/{revision}-{floor}.svg" for floor in ("GF", "SITE")},
        "export_audit": {"audit_errors": 0, "dxf_version": "AC1024", "model_revision_id": revision},
    }
    model["geometry_sha256"] = fingerprint(model)
    for path in [*model["downloads"].values(), *model["previews"].values()]:
        (folder / path.rsplit("/", 1)[1]).write_text(json.dumps(model))
    return model


def test_release_requires_geometry_match_and_all_hard_checks(tmp_path):
    model = drawing_set(tmp_path)
    assert verified_files(model, tmp_path)
    broken = copy.deepcopy(model)
    broken["floors"][0]["rooms"][0]["x"] = 2
    assert verified_files(broken, tmp_path) is None
    broken = copy.deepcopy(model)
    broken["checks"][0]["status"] = "FAIL"
    assert verified_files(broken, tmp_path) is None
    (tmp_path / "test_revision-SITE.svg").unlink()
    assert verified_files(model, tmp_path) is None


def test_only_intact_manifest_files_are_visible(tmp_path):
    run = "a" * 32
    target = tmp_path / run
    target.mkdir()
    pdf = target / "plan.pdf"
    pdf.write_bytes(b"abc")
    (target / "result.json").write_text(json.dumps({
        "files": {"plan.pdf": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}}
    }))
    assert find_file(tmp_path, run, "plan.pdf") == pdf
    assert find_file(tmp_path, run, "result.json") is None
    assert find_file(tmp_path, "../" + run, "plan.pdf") is None
    pdf.write_bytes(b"xyz")
    assert find_file(tmp_path, run, "plan.pdf") is None


def test_diagnostic_flags_a_window_facing_a_narrow_external_gap():
    from backend.design.window_clearance import inspect_window_clearance

    floor = {
        "id": "GF",
        "rooms": [{"id": "bath", "x": 0, "y": 0, "width": 2, "depth": 2},
                  {"id": "other", "x": 2.35, "y": 0, "width": 2, "depth": 2}],
        "walls": [{"id": "e", "axis": "vertical", "thickness": .2, "exterior": True}],
        "openings": [{"id": "window", "kind": "window", "wall_id": "e",
                      "center": [2.1, 1], "width": 1.2, "clear_width": 1.08,
                      "connects": ["bath", "OUTSIDE"]}],
    }
    assert inspect_window_clearance({"floors": [floor]})["windows"][0]["status"] == "review_obstruction"
    floor["rooms"][1]["x"] = 5
    assert inspect_window_clearance({"floors": [floor]})["windows"][0]["status"] == "no_modelled_obstruction"
