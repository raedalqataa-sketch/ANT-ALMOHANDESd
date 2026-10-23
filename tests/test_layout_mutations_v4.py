"""Only unapproved, constraint-fitting cells may be moved or resized."""
from copy import deepcopy
import pytest

from backend.design.layout_mutations import mutation_variants
from backend.design.auto_repair import ArchitectureAutoRepairEngine


def shape(identifier,y,*,kind="bedroom",zone="family",area=14):
    return dict(id=identifier,request_id=identifier,kind=kind,zone=zone,
                min_area=area,min_side=3.0,x=0.,y=y,width=4.,depth=5.,
                door_side="east")


def sample():
    return {"floors":[[shape("A",0.),shape("B",5.),
                       shape("G",10.,zone="guest")]],
            "score":5,"alternatives":[{"unrelated":"large historical pool"}]}


def test_swaps_move_whole_room_entities_without_moving_guest_or_corridor():
    original=sample();unchanged=deepcopy(original)
    variants=list(mutation_variants(original,.2))
    assert original==unchanged
    sw=next(v for v in variants if v["local_reflow"]["operation"]=="swap_room_locations")
    a,b,g=sw["floors"][0]
    assert a["id"]=="A" and a["y"]==5.
    assert b["id"]=="B" and b["y"]==0.
    assert g==unchanged["floors"][0][2]
    assert "alternatives" not in sw


def test_boundary_shift_repositions_room_and_changes_both_depths_conservatively():
    original=sample()
    variants=list(mutation_variants(original,.2))
    shifts=[v for v in variants if v["local_reflow"]["operation"]=="shift_shared_room_boundary"]
    assert len(shifts)==2
    for v in shifts:
        a,b,_=v["floors"][0]
        assert abs(a["y"]+a["depth"]-b["y"])<1e-7
        assert abs(a["depth"]+b["depth"]-10)<1e-7
        assert (a["width"]-.2)*(a["depth"]-.2)>=a["min_area"]
        assert (b["width"]-.2)*(b["depth"]-.2)>=b["min_area"]


def test_does_not_mutate_or_resize_guests_stairs_and_unfit_rooms():
    plan=sample()
    plan["floors"][0][1]["min_area"]=18.1  # 0.45 m shrink would be below 18.1
    variants=list(mutation_variants(plan,.2))
    assert all(v["floors"][0][2]==plan["floors"][0][2] for v in variants)
    assert all(v["local_reflow"]["operation"]!="shift_shared_room_boundary"
               or v["local_reflow"]["delta_m"]!=0.45 for v in variants)
    assert not list(mutation_variants(plan,.2,limit=0))


@pytest.mark.parametrize("status", ["APPROVED", "LOCKED"])
def test_approved_layout_cannot_be_mutated_in_place(status):
    plan=sample()
    plan["release"]={"status":status}
    with pytest.raises(ValueError,match="approved or locked"):
        list(mutation_variants(plan,.2))


@pytest.mark.parametrize("status", ["APPROVED", "LOCKED"])
def test_approved_model_cannot_enter_local_auto_repair(status):
    model={"release":{"status":status}}
    engine=ArchitectureAutoRepairEngine(lambda model: [])
    with pytest.raises(ValueError,match="approved or locked"):
        engine.repair(model)
