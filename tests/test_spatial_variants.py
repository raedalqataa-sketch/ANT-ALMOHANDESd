from copy import deepcopy
from backend.design.spatial_variants import mirror_candidate


def test_mirror_does_not_mutate_source_and_is_involution():
    model = {
        "site": {"width": 20, "depth": 30},
        "footprint": {"x": 2, "y": 3, "width": 14, "depth": 20},
        "parking": [{"x": 1, "y": 23, "width": 2.5, "depth": 5}],
        "stairs": [{"x": 3, "y": 4, "width": 2.6, "depth": 3}],
        "floors": [{"rooms": [{"x": 3, "y": 4, "width": 4, "depth": 5}],
                    "furniture": [{"x": 4, "y": 5, "width": 1, "depth": 2}],
                    "walls": [{"start": (3, 4), "end": (3, 9)}],
                    "openings": [{"center": (3, 6), "face": "west",
                                  "swing_rect": {"x": 3, "y": 5, "width": .9, "depth": .9}}]}],
        "search": {"orientation_search": False},
        "assumptions": [],
    }
    original = deepcopy(model)
    mirrored = mirror_candidate(model)
    assert model == original
    assert mirrored["footprint"]["x"] == 4
    assert mirrored["floors"][0]["openings"][0]["face"] == "east"
    assert mirrored["floors"][0]["walls"][0]["start"] == (17, 4)
    restored = mirror_candidate(mirrored)
    assert restored["footprint"] == original["footprint"]
    assert restored["floors"] == original["floors"]
