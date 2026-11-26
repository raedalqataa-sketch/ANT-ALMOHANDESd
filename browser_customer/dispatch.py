"""Run customer requests through the same validated Python engine in WebAssembly."""
import base64
import json
import re
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from backend.design import general_api as concepts, plan_editor_api as editor

EDITOR = "/api/editor/sessions"
CONCEPTS = "/api/v3/concepts/"
SESSION = re.compile(r"[a-f0-9]{32}")


def _handle(url, body, progress):
    path = url.path
    if path == CONCEPTS + "clustered/stream":
        options = {key: values[-1] for key, values in parse_qs(url.query).items()}
        count = int(options.pop("max_results", "2"))
        first = options.pop("first_floor", "false") == "true"
        action = options.pop("fit_action", None)
        if count not in (1, 2) or action not in (None, "adapt", "vertical"):
            raise ValueError("INVALID_COMPOSITION_OPTIONS")
        upper = concepts.UpperFloorProgram.model_validate(options)
        progress(4, "التحقق من برنامج العميل")
        return concepts._composition_result(
            concepts.PROPOSAL_BRIEF.validate_python(body), count, first, upper, action, progress
        )
    if path == CONCEPTS + "program-draft":
        return concepts.composition_program_draft(concepts.CompositionDescription.model_validate(body))
    if path == CONCEPTS + "facades":
        return concepts.concept_facades(concepts.PlanSource.model_validate(body))
    if path == CONCEPTS + "massing/stream":
        return concepts._massing_for_request(concepts.MassingRequest.model_validate(body), progress)
    if path == EDITOR:
        return editor.create_session(editor.Create.model_validate(body))
    if path.startswith(EDITOR + "/"):
        sid, *parts = path[len(EDITOR) + 1:].split("/")
        if parts == ["geometry"]:
            return editor.geometry_preview(sid, editor.Edit.model_validate(body))
        if parts == ["preview"]:
            return editor.preview(sid, editor.Edit.model_validate(body))
        if parts == ["revisions"]:
            return editor.save_revision(sid, editor.Edit.model_validate(body))
        if not parts:
            return editor.get_session(sid)
        if len(parts) == 4 and parts[0] == "revisions" and parts[2] == "files":
            file = editor.download(sid, int(parts[1]), parts[3])
            return {"filename": file.filename, "bytes": base64.b64encode(file.path.read_bytes()).decode()}
    raise HTTPException(404, "BROWSER_OPERATION_UNAVAILABLE")


def dispatch(path, payload, snapshot, emit):
    url = urlsplit(path)
    session = url.path.removeprefix(EDITOR + "/").split("/")[0]
    body = json.loads(payload)
    if url.path.startswith(CONCEPTS) and isinstance(body, dict):
        session = (body.get("editor_revision") or {}).get("session_id", "")
    if snapshot and SESSION.fullmatch(session):
        for name, content in json.loads(snapshot).items():
            if re.fullmatch(r"session\.json|revision-[0-9]+\.json", name):
                editor._atomic(editor._folder(session) / name, content)

    def progress(percent, detail, *_):
        emit(json.dumps({"percent": percent, "detail": detail}, ensure_ascii=False))

    try:
        result = _handle(url, body, progress)
    except HTTPException as exc:
        return json.dumps({"status": exc.status_code, "data": {"detail": exc.detail}}, ensure_ascii=False)
    except ValueError as exc:
        return json.dumps({"status": 422, "data": {"detail": str(exc)}}, ensure_ascii=False)

    reply = {"status": 200, "data": result}
    if url.path == EDITOR or url.path == f"{EDITOR}/{session}/revisions":
        sid = result["session_id"]
        folder = editor._folder(sid)
        reply["session"] = sid
        reply["snapshot"] = {
            name: json.loads((folder / name).read_text())
            for name in ("session.json", f"revision-{result['version']}.json")
        }
    return json.dumps(reply, ensure_ascii=False, allow_nan=False)
