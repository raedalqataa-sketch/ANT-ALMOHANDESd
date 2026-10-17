from backend.design.massing import propose_massing


def test_massing_families_are_not_only_rectangular():
    result = propose_massing(30, 40, 4, 5, 16, 22)
    assert {x["family"] for x in result} == {"RECTANGULAR", "L_SHAPE", "U_SHAPE", "STEPPED"}
    assert all(x["status"] == "CONCEPT_UNVALIDATED" for x in result)
    assert len({x["envelope_area_m2"] for x in result}) >= 3


def test_massing_rectangles_inside_plot():
    result = propose_massing(30, 40, 4, 5, 16, 22)
    for shape in result:
        for r in shape["rectangles"]:
            assert 0 <= r["x"] and 0 <= r["y"]
            assert r["x"] + r["width"] <= 30
            assert r["y"] + r["depth"] <= 40


def test_massing_rejects_out_of_plot():
    import pytest
    with pytest.raises(ValueError):
        propose_massing(12, 15, 2, 2, 16, 22)
