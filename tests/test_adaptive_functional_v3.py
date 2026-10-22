"""V3 adaptive functional layout search: geometry, graph, bounded repair."""
from itertools import combinations
from backend.design.adaptive_geometry import adaptive_topology
from backend.design.functional_intelligence import inspect, repair_reasons


def test_variable_wing_geometry_has_continuous_internal_corridor():
    shapes=[]
    for ratio,split in ((.38,.36),(.46,.55),(.62,.64)):
        geom=adaptive_topology(17,24,1.6,ratio,split)
        assert geom is not None
        halls,lanes=geom
        assert len(halls)==1 and len(lanes)==4
        central=halls[0]
        assert central["y"]==0 and central["depth"]==24
        assert all(l["width"]>=2.8 and l["depth"]>=5 for l in lanes)
        for lane in lanes:
            assert lane["door_side"] in ("east","west")
            if lane["door_side"]=="east":
                assert abs(lane["x"]+lane["width"]-central["x"])<1e-7
            else:
                assert abs(lane["x"]-(central["x"]+central["width"]))<1e-7
        shapes.append(tuple(round(l["x"],3) for l in lanes))
    assert len(set(shapes))==3


def test_adaptive_shape_handles_undersized_core_without_fake_rooms():
    assert adaptive_topology(5,6,1.6,.5,.5) is None


def test_repair_diagnostics_use_actual_failed_checks():
    model={"checks":[{"check_id":"GF-walkability","status":"FAIL"},
                     {"check_id":"guest-route","status":"FAIL"},
                     {"check_id":"FF-beds","status":"FAIL"},
                     {"check_id":"local-code","status":"PENDING"}]}
    assert set(repair_reasons(model))=={"guest_circulation","family_movement","furnishing"}
    assert repair_reasons({"checks":[{"check_id":"GF-walkability","status":"PASS"}]})==[]


def test_v3_api_opt_in_preserves_legacy_contract():
    import inspect as signature
    from backend.design.general_api import auto_design
    from backend.design.architect_planner import generate_automatic
    assert signature.signature(auto_design).parameters["generation_v3"].default is False
    assert signature.signature(generate_automatic).parameters["generation_v3"].default is False


def test_public_worker_enables_v3_not_a_placeholder():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    content=(root/"lovable_integration"/"build.py").read_text()
    assert "constitution_v2=True,generation_v3=True" in content
    assert "backend/design/adaptive_geometry.py" in str(root/"backend/design/adaptive_geometry.py")


def test_real_v3_designs_are_measured_and_not_preset_l_u_stepped(tmp_path):
    from backend.design.architect_planner import ClientIntent, generate_automatic
    from backend.design.design_selection import difference
    from backend.design.general_models import VillaBrief
    from backend.design.general_engine import validate_general
    from itertools import combinations
    import ezdxf
    intent=ClientIntent(width=24,depth=32,country="YE",region="الحديدة",city="باجل",
                        family=6,street_edges=["bottom"],main_street="bottom")
    result=generate_automatic(intent,tmp_path,constitution_v2=True,generation_v3=True)
    planning=result["planning"]
    assert planning["generation_v3"]["revision"]=="adaptive-functional-search-1"
    assert planning["generation_v3"]["legacy_shapes_in_default_v3_search"] is False
    assert planning["design_selection"]["search_variants_examined"]>=5
    assert all(x["family"] not in {"L","U","stepped"} for x in planning["design_selection"]["diagnostics"])
    assert result["candidates"], "V3 should find at least one geometrically valid candidate"
    for a,b in combinations(result["candidates"],2):
        assert difference(a,b)["distinct"]
    for m in result["candidates"]:
        assert m["release"]["drawing_export_allowed"]
        assert not m["release"]["executive_issue_allowed"]
        assert m["design_evaluation"]["functional_intelligence"]["evaluated_relations"]>0
        assert m["constitution_v2"]["gate_count"]==16
        assert not [c for c in validate_general(m,VillaBrief(**m["brief"])) if c["status"]=="FAIL"]
        doc=ezdxf.readfile(tmp_path/(m["model_revision_id"]+".dxf"))
        assert doc.dxfversion=="AC1024" and not doc.audit().errors
