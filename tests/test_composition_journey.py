import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from assl.strategies.geometry import net_shape
from backend.design import plan_editor_api as editor
from backend.design.general_api import (
    PlanSource, clustered_concepts, concept_facades,
)
from backend.design.general_models import UpperFloorProgram, VillaBrief
from backend.design.plan_editing import apply_operations
from backend.main import app

ROOT = Path(__file__).resolve().parents[1] / "frontend/composition"
DESCRIPTION = ("مجلس رجال، طعام ضيوف، حمام ضيوف، مجلس نساء، حمام نساء، صالة عائلية ٢٥ م²، "
               "طعام الأسرة، مطبخ، مستودع، غرفة نوم، حمام خاص")


def reference():
    return json.loads((ROOT / "reference-brief.json").read_text())


def record_result(name, value):
    if output := os.getenv("ANT_FAMILY_EVIDENCE_DIR"):
        folder = Path(output) / "customer-journey"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def test_text_and_table_programs_generate_without_site_constraints():
    brief = {key: value for key, value in reference().items() if key not in ("plot_width", "plot_depth", "setbacks")}
    with TestClient(app) as client:
        draft = client.post("/api/v3/concepts/program-draft", json={
            "brief":brief, "text":DESCRIPTION+"؛ الدور الأول: غرفتان للأبناء ١١ م²؛ عزل خاص",
        })
        assert draft.status_code == 200
        body = draft.json()
        assert len(body["brief"]["rooms"]) == 11
        assert body["unresolved"] == ["عزل خاص"]
        assert body["upper_program"]["children"] == 2
        assert body["upper_program"]["child_area_m2"] == 11
        for program in (brief, body["brief"]):
            result = client.post("/api/v3/concepts/clustered", params={"max_results":2}, json=program)
            assert result.status_code == 200
            data = result.json()
            assert data["site_status"] == "SITE_NOT_ASSESSED"
            assert data["proposals"]
            plan = data["proposals"][0]
            assert "plot_width" not in plan["brief_snapshot"]
            assert "setbacks" not in plan["brief_snapshot"]
        rendered_facades = client.post("/api/v3/concepts/facades", json={"proposal":plan})
        assert rendered_facades.status_code == 200
        assert len(rendered_facades.json()["options"]) == 2
        record_result("text-without-site", data)


def test_small_plot_returns_checked_adapted_program():
    original = VillaBrief.model_validate({**reference(), "plot_width":28, "plot_depth":38})
    failed = clustered_concepts(original, max_results=1)
    assert not failed["proposals"] and failed["fit"]["available_envelope_width_m"] == 22
    recovered = clustered_concepts(original, max_results=1, fit_action="adapt")
    assert recovered["proposals"]
    assert recovered["recovery"]["changes"]
    record_result("adapted-brief", recovered)
    for proposal in recovered["proposals"]:
        assert proposal["validation_009"]["status"] == "PASS"
        assert {room["id"] for room in proposal["brief_snapshot"]["rooms"]} == {r.id for r in original.rooms}


def test_vertical_option_preserves_linked_suite_and_editor_validates_both_levels(tmp_path, monkeypatch):
    data = {**reference(), "plot_width":30, "plot_depth":38}
    for room in data["rooms"]:
        if room["id"] == "elder":
            room.update(min_area=38, min_side=4.5)
    brief = VillaBrief.model_validate(data)
    failed = clustered_concepts(brief, max_results=2)
    assert not failed["proposals"] and failed["fit"]
    recovered = clustered_concepts(brief, max_results=1, fit_action="vertical",
                                  upper_program=UpperFloorProgram(children=2))
    plan, = recovered["proposals"]
    transfer = plan["transferred_suite"]
    moved = {room["id"] for room in transfer.values()}
    ids = {r["id"] for r in plan["brief_snapshot"]["rooms"]}
    assert not moved & ids
    assert {r.id for r in brief.rooms} <= ids | moved
    upper = {r["id"]:r for r in plan["rooms_by_floor"][1]}
    for request, target in (("bedroom","upper-master"), ("bathroom","upper-master-wc")):
        assert net_shape(upper[target], brief.wall_thickness).area >= transfer[request]["min_area"]-1e-6
    assert len(concept_facades(PlanSource(proposal=plan))["options"]) == 2

    monkeypatch.setattr(editor, "STORE", tmp_path)
    initial = editor.create_session(editor.Create(proposal=plan))
    assert initial["exportable"]
    terrace = upper["family-terrace"]
    edited = editor.save_revision(initial["session_id"], editor.Edit(base_version=0, operations=[
        {"type":"resize","room_id":terrace["id"],"floor":1,"width":terrace["width"],"depth":terrace["depth"]-.05},
    ]))
    assert edited["massing_ready"]
    assert edited["geometry_fingerprint"] != initial["geometry_fingerprint"]
    updated = concept_facades(PlanSource(editor_revision={"session_id":initial["session_id"],"version":1}))
    assert updated["version_id"] == edited["version_id"]
    assert updated["revision"] == edited["geometry_fingerprint"]
    record_result("vertical-and-edited", {"recovered":recovered, "edited":edited["proposal"], "facades":updated})


def test_editor_removes_and_reintroduces_activity_and_toggles_existing_partition():
    proposal = json.loads((ROOT / "clustered-sample.json").read_text())["proposals"][0]
    storage = next(room for room in proposal["rooms_by_floor"][0] if room["kind"] == "storage")
    ops = [{"type":"delete_space","room_id":storage["id"]}, {
        "type":"add_space","room_id":"kitchen-1","name":"مخزن جديد","kind":"storage",
        **{key:storage[key] for key in ("x","y","width","depth")},
    }]
    result = apply_operations(proposal, ops)
    assert storage["request_id"] not in {room["id"] for room in result["brief_snapshot"]["rooms"]}
    added = next(room for room in result["rooms_by_floor"][0] if room["name"] == "مخزن جديد")
    assert net_shape(added, .2).equals_exact(net_shape(storage, .2), .00001, normalize=True)
    assert any(link["b"] == added["id"] for link in result["connection_requirements"])
    # A current family connection supports an open passage or a wall with a door.
    from assl.strategies.central_clustered import compose
    proposal = compose(VillaBrief.model_validate(reference()))
    living = next(room for room in proposal["rooms_by_floor"][0] if room["kind"] == "living")
    from assl.strategies.geometry import shared_edges
    from shapely.geometry import LineString
    dining = next(room for room in proposal["rooms_by_floor"][0]
                  if room["kind"] == "dining" and not room.get("guest_entries"))
    link = next(link for link in proposal["connection_requirements"]
                if {link["a"],link["b"]} == {living["id"],dining["id"]})
    neighbor = dining
    edge = max(shared_edges(living, neighbor), key=lambda edge:edge["length"])
    points = [(q,edge["fixed"]) if edge["axis"] == "x" else (edge["fixed"],q) for q in (edge["lo"],edge["hi"])]
    index = next(i for i,p in enumerate(living["polygon"])
                 if LineString([p,living["polygon"][(i+1) % len(living["polygon"])]])
                 .intersection(LineString(points)).length >= 1.2-1e-6)
    operation = {"type":"partition","room_id":living["id"],"edge":index}
    for opened in (True, False):
        result = apply_operations(proposal, [{**operation, "open":opened}])
        updated = next(q for q in result["connection_requirements"] if q["a"] == link["a"] and q["b"] == link["b"])
        assert updated["open_passage"] is opened


def test_very_small_buildable_envelope_keeps_options_available():
    original = {**reference(), "plot_width":12, "setbacks":{"east":4,"west":4,"north":3,"south":3}}
    with TestClient(app) as client:
        for params in ({}, {"fit_action":"vertical"}):
            response = client.post("/api/v3/concepts/clustered", params=params, json=original)
            assert response.status_code == 200
            assert response.json()["proposals"] == []
            assert response.json()["fit"]["available_envelope_width_m"] == 4
            assert response.json()["failures"][0]["reason"] == "BUILDABLE_ENVELOPE_BELOW_SEARCH_SCOPE"
