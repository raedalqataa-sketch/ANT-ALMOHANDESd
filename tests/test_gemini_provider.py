"""Gemini provider integration tests; no live API key or network required."""
import json
from fastapi.testclient import TestClient
from backend.main import app
import backend.design.general_api as api


def sample_brief():
    return {
        "project_name": "اختبار Gemini",
        "plot_width": 20,
        "plot_depth": 30,
        "floors": 2,
        "setbacks": {"north": 2, "south": 3, "east": 2, "west": 2},
        "rooms": [
            {"id": "guest", "name": "مجلس", "kind": "majlis", "floor": 0,
             "count": 1, "min_area": 24, "min_side": 3.5, "capacity": 0},
            {"id": "bed", "name": "غرفة نوم", "kind": "bedroom", "floor": 1,
             "count": 1, "min_area": 16, "min_side": 3.2, "capacity": 2},
        ],
    }


def test_gemini_status_does_not_claim_connection(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    result = TestClient(app).get("/api/v3/ai-status").json()
    assert result["configured"] is True
    assert result["provider"] == "gemini"
    assert result["connected"] is False
    assert result["model"] == "gemini-2.5-flash"


def test_gemini_missing_key_returns_configuration_error(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = TestClient(app).post(
        "/api/v3/interpret",
        json={"brief": sample_brief(), "text": "أضف غرفة نوم"},
    )
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_gemini_proposal_is_validated_and_requires_review(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured = {}

    def fake_gemini(**kwargs):
        captured.update(kwargs)
        payload = kwargs["payload"]
        return json.dumps({
            "rooms": payload["brief"]["rooms"],
            "unresolved": ["تأكيد خصوصية مدخل الضيوف"],
        }, ensure_ascii=False)

    monkeypatch.setattr(api, "generate_general", lambda *_: (_ for _ in ()).throw(AssertionError("engine must not run")))
    monkeypatch.setattr("backend.design.gemini_provider.generate_gemini_json", fake_gemini, raising=False)
    # The API imports the provider function lazily, so replace the provider module directly.
    import backend.design.gemini_provider as provider
    monkeypatch.setattr(provider, "generate_gemini_json", fake_gemini)
    response = TestClient(app).post(
        "/api/v3/interpret",
        json={"brief": sample_brief(), "text": "أضف غرفة نوم"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "REVIEW_REQUIRED"
    assert body["provider"] == "gemini"
    assert body["unresolved"] == ["تأكيد خصوصية مدخل الضيوف"]
    assert body["source_text"] == "أضف غرفة نوم"
    assert captured["model"] == "gemini-2.5-flash"
    assert "Saudi" not in captured["prompt"]


def test_gemini_invalid_rooms_are_rejected_without_mutation(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    import backend.design.gemini_provider as provider
    monkeypatch.setattr(provider, "generate_gemini_json", lambda **_: json.dumps({
        "rooms": [{"id": "broken", "kind": "not-a-room-kind"}],
        "unresolved": [],
    }))
    response = TestClient(app).post(
        "/api/v3/interpret",
        json={"brief": sample_brief(), "text": "أضف غرفة نوم"},
    )
    assert response.status_code == 502
    assert "لم تتغير المدخلات" in response.json()["detail"]


def test_invalid_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "unknown")
    response = TestClient(app).post(
        "/api/v3/interpret",
        json={"brief": sample_brief(), "text": "أضف غرفة نوم"},
    )
    assert response.status_code == 503
