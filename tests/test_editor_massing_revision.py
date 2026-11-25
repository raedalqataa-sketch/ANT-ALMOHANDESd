import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.design import blender_render, plan_editor_api, progress_stream
from backend.design.general_api import (
    MassingRequest,
    RenderRequest,
    concept_massing,
    stream_render,
)


def test_saved_editor_geometry_is_pinned_through_massing_and_render(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_editor_api, "STORE", tmp_path)
    sample = Path(__file__).resolve().parents[1] / "frontend/composition/clustered-sample.json"
    proposal = json.loads(sample.read_text())["proposals"][0]
    initial = plan_editor_api.create_session(plan_editor_api.Create(proposal=proposal))
    sid = initial["session_id"]
    operation = {"type": "wall", "room_id": "men-wc-1", "edge": 0, "offset": 0.05}
    saved = plan_editor_api.save_revision(
        sid, plan_editor_api.Edit(base_version=0, operations=[operation])
    )
    assert saved["massing_ready"]
    assert saved["geometry_fingerprint"] != initial["geometry_fingerprint"]

    draft = plan_editor_api.save_revision(
        sid,
        plan_editor_api.Edit(
            base_version=1, operations=[{"type": "move", "room_id": "men-wc-1", "dx": 1, "dy": 0}]
        ),
    )
    assert not draft["massing_ready"]
    with pytest.raises(HTTPException, match="EDITOR_REVISION_FAILED_CHECKS"):
        concept_massing(MassingRequest(editor_revision={"session_id": sid, "version": 2}))

    # A newer draft cannot change the exact saved revision selected for rendering.
    source = {"editor_revision": {"session_id": sid, "version": 1}}
    massing = concept_massing(MassingRequest(**source))
    assert {style["id"] for style in massing["styles"]} == {
        "classical", "mediterranean", "modern", "najdi",
    }
    assert massing["version_id"] == saved["version_id"]
    assert massing["revision"] == massing["geometry_fingerprint"] == saved["geometry_fingerprint"]

    monkeypatch.setattr(progress_stream, "stream_work", lambda operation: operation(lambda *_: None))

    def capture(model, style_id, camera, progress):
        assert model["styles"] == massing["styles"]
        return {"revision": model["revision"], "style": style_id, "camera": camera}

    monkeypatch.setattr(blender_render, "render_image", capture)
    request = RenderRequest(
        **source, revision=massing["revision"], version_id=saved["version_id"],
        style="classical", camera={"yaw": -0.86, "pitch": 0.24, "zoom": 1},
    )
    image = stream_render(request)
    assert image["revision"] == image["geometry_fingerprint"] == saved["geometry_fingerprint"]
    assert image["version_id"] == saved["version_id"]
    assert image["style"] == "classical"
    assert image["camera"]["yaw"] == -0.86

    for mismatch in ({"revision": "0" * 64}, {"version_id": draft["version_id"]}):
        with pytest.raises(ValueError, match="تغيّرت مراجعة المسقط"):
            stream_render(request.model_copy(update=mismatch))
