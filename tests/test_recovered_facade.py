"""Regression checks for the recovered approved-plan-to-CAD path."""
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
import json

import ezdxf
from fastapi import HTTPException
import pytest

from backend.design.general_api import _checked_massing, download_massing, StyleExportRequest
from assl.strategies.styled_massing import export_style_dxf


@pytest.fixture(scope="module")
def proposal():
    path = Path(__file__).parents[1]/"frontend/composition/clustered-sample.json"
    return json.loads(path.read_text())["proposals"][0]


@pytest.fixture(scope="module")
def model(proposal):
    return _checked_massing(proposal)


def test_style_geometry_and_window_schedule(model, proposal):
    assert {s["id"] for s in model["styles"]} == {"modern","contemporary","classical","najdi"}
    assert len({s["facade_sha256"] for s in model["styles"]}) == 4
    assert not model["facade_review"]
    original = {w["id"]:w for w in proposal["opening_model_009"][0]["windows"]}
    for adjusted in model["facade_openings"][0]:
        source = original[adjusted["id"]]
        assert adjusted["center"] == source["center"]
        assert adjusted["width"] >= source["width"]
    assert any(w["width"]>w["source_width"] for w in model["facade_openings"][0])


def test_dxf_reopens_and_matches_every_surface(model):
    style = next(s for s in model["styles"] if s["id"]=="contemporary")
    with ZipFile(BytesIO(export_style_dxf(model,style["id"]))) as bundle:
        assert len(bundle.namelist()) == 1 and bundle.testzip() is None
        doc = ezdxf.read(StringIO(bundle.read(bundle.namelist()[0]).decode()))
    audit=doc.audit()
    assert not audit.errors and not audit.fixes and doc.units==6 and doc.dxfversion=="AC1024"
    assert doc.ezdxf_metadata()["ANT_PLAN_REVISION"] == model["revision"]
    assert doc.ezdxf_metadata()["ANT_FACADE_SHA256"] == style["facade_sha256"]
    entities=list(doc.modelspace().query("3DFACE"))
    assert len(entities)==len(style["faces"])
    for entity,(vertices,color) in zip(entities,style["faces"],strict=True):
        assert [list(entity.dxf.get(f"vtx{i}")) for i in range(len(vertices))]==vertices
        assert entity.rgb==tuple(int(color[i:i+2],16) for i in (1,3,5))


def test_stale_plan_export_is_blocked(proposal):
    with pytest.raises(HTTPException) as error:
        download_massing(StyleExportRequest(proposal=proposal,style="modern",revision="0"*64))
    assert error.value.status_code == 409
