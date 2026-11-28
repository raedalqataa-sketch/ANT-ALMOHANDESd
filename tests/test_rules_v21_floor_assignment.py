from backend.design.rules_v21_floor_assignment import assign_floors


def test_single_floor_assignment():
    doc={"program":[{"id":"bed","count":2,"required":True,"allowed_floors":["ground"],"area_min_m2":12}]}
    result=assign_floors(doc,{"ground":30})
    assert result["status"]=="assignment_ready"
    assert len(result["assignments"])==2
    assert result["remaining_m2"]["ground"]==6


def test_infeasible_floor_assignment():
    doc={"program":[{"id":"bed","count":2,"required":True,"allowed_floors":["ground"],"area_min_m2":12}]}
    result=assign_floors(doc,{"ground":20})
    assert result["status"]=="fail"


def test_does_not_place_on_forbidden_floor():
    doc={"program":[{"id":"bed","count":1,"required":True,"allowed_floors":["upper"],"area_min_m2":12}]}
    result=assign_floors(doc,{"ground":100,"upper":20})
    assert result["status"]=="assignment_ready"
    assert result["assignments"][0]["floor"]=="upper"
