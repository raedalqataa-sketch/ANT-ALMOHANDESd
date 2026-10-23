"""Tests for evidence-aware building coordination and transactional relayout."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.design.execution_coordination import assess, checks
from backend.design.layout_rebuild import replacement_evidence


def brief():
    return SimpleNamespace(
        plot_width=20, plot_depth=25,
        setbacks=SimpleNamespace(north=2,south=3,east=2,west=2),
        parcel_number='', plan_number='', boundary_widths={},
        country='YE',region='صنعاء',city='صنعاء',
    )


def cell(code,x,y,w,d,kind="living",request="room"):
    return {"id":code,"x":x,"y":y,"width":w,"depth":d,
            "kind":kind, "floor_id":"GF", "request_id":request}


def model():
    a=cell("GF-ROOM",2.5,3,5,6)
    hall=cell("GF-HALL",7.5,3,1.5,6,kind="corridor",request=None)
    return dict(model_revision_id="first",status="DRAFT_REVIEW",brief={"project":"same"},
                floors=[dict(id="GF",rooms=[a,hall],cells=[a,hall])],
                release={"drawing_export_allowed":False},checks=[dict(status="FAIL",check_id="test")])


def test_site_gross_cells_outside_setback_block_draft_export():
    m=model();result=assess(m,brief())
    assert result["site"]["geometric_status"]=="PASS"
    m["floors"][0]["cells"][0]["x"]=1.0
    result=assess(m,brief())
    assert result["site"]["geometric_status"]=="FAIL"
    assert result["site"]["gross_cell_setback_excess"][0]["outside_buildable_m2"]>0
    assert {row["check_id"]:row["status"] for row in checks(result)}["V4-site-gross-envelope"]=="FAIL"


def test_code_structure_mep_are_pending_without_source_documents():
    result=assess(model(),brief())
    assert result["code"]["status"]=="PENDING"
    assert result["structure"]["status"]=="PENDING"
    assert result["mep"]["status"]=="PENDING"
    assert not result["executive_approval"]
    rows={r["check_id"]:r for r in checks(result)}
    assert {rows[k]["status"] for k in
            ("V4-local-code-verified","V4-structural-coordination","V4-mep-coordination")}=={"PENDING"}
    assert result["site"]["survey_status"]=="PENDING"


def test_relayout_evidence_measures_room_move_resize_and_corridor_change():
    old=model()
    new=deepcopy(old);new["model_revision_id"]="second"
    new["floors"][0]["rooms"][0]["x"]+=1
    new["floors"][0]["rooms"][0]["width"]+=1
    new["floors"][0]["cells"][0]["x"]+=1
    new["floors"][0]["cells"][0]["width"]+=1
    new["floors"][0]["cells"][1]["width"]+=.4
    new["release"]={"drawing_export_allowed":True}
    new["checks"]=[{"status":"PASS","check_id":"geometry"}]
    delta=replacement_evidence(old,new)
    assert delta["status"]=="REBUILT_DRAFT_AFTER_VALIDATION"
    assert len(delta["relocated_rooms"])==1
    assert len(delta["resized_rooms"])==1
    assert delta["corridor_rebuild"]["before_count"]==1
    assert delta["new_revision"]=="second"


def test_rebuild_never_changes_brief_or_approved_plan():
    original=model();candidate=deepcopy(original)
    candidate["release"]={"drawing_export_allowed":True}
    candidate["checks"]=[{"status":"PASS"}]
    candidate["brief"]={"project":"different"}
    with pytest.raises(ValueError,match="brief"):
        replacement_evidence(original,candidate)
    original["status"]="LOCKED"
    candidate["brief"]=original["brief"]
    with pytest.raises(ValueError,match="locked"):
        replacement_evidence(original,candidate)


def test_rebuild_rejects_program_change_or_failed_replacement():
    original=model();candidate=deepcopy(original)
    candidate["floors"][0]["rooms"][0]["request_id"]="new-room"
    candidate["floors"][0]["rooms"][0]["id"]="GF-OTHER"
    candidate["release"]={"drawing_export_allowed":True}
    candidate["checks"]=[{"status":"PASS"}]
    with pytest.raises(ValueError,match="program"):
        replacement_evidence(original,candidate)
    candidate=deepcopy(original)
    with pytest.raises(ValueError,match="not passed"):
        replacement_evidence(original,candidate)
