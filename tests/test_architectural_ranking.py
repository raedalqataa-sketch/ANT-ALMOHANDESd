import pytest
from backend.design.architectural_ranking import score_candidate, rank_candidates, WEIGHTS


def test_complete_evidence():
    result = score_candidate({key: 1 for key in WEIGHTS})
    assert result["eligible"] and result["score"] == 100


def test_missing_evidence_is_not_a_pass():
    result = score_candidate({"privacy": 1})
    assert not result["eligible"]
    assert result["score"] is None
    assert "circulation" in result["pending"]


def test_hard_violation_disqualifies():
    result = score_candidate({key: 1 for key in WEIGHTS}, hard_failures=["room_overlap"])
    assert not result["eligible"] and result["score"] is None


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), True, "1"])
def test_invalid_evidence_rejected(bad):
    with pytest.raises(ValueError):
        score_candidate({key: bad for key in WEIGHTS})


def test_rank_valid_before_incomplete():
    good = {"id": "good", "metrics": {key: .8 for key in WEIGHTS}}
    unknown = {"id": "unknown", "metrics": {"privacy": 1}}
    assert rank_candidates([unknown, good])[0]["id"] == "good"
