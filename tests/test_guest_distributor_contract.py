"""Non-negotiable architectural contract for the men's guest distributor.

These tests deliberately fail until real, bounded distributor geometry exists.
Do not skip or xfail: a blocked export is safer than a falsely approved plan.
"""
from types import SimpleNamespace

from backend.design.general_engine import make_guest_distributor


def room(room_id, kind, **extra):
    return {"id": room_id, "kind": kind, **extra}


def door(*connects, **extra):
    return {"kind": "door", "connects": list(connects), **extra}


def floor(rooms, doors):
    return {"rooms": rooms, "openings": doors}


BRIEF = SimpleNamespace(separate_guest_entry=True)


def test_guest_bathroom_must_not_be_reached_through_majlis():
    f = floor(
        [room("majlis", "majlis", zone="guest"),
         room("wc", "bathroom", guest_parent="majlis")],
        [door("majlis", "OUTSIDE", guest_entry=True),
         door("majlis", "wc")],
    )
    assert make_guest_distributor(f, BRIEF, "test") is False


def test_shared_family_corridor_is_not_a_guest_distributor():
    f = floor(
        [room("majlis", "majlis", zone="guest"),
         room("wc", "bathroom", guest_parent="majlis"),
         room("hall", "corridor")],
        [door("hall", "majlis"), door("hall", "wc"),
         door("hall", "OUTSIDE", guest_entry=True)],
    )
    assert make_guest_distributor(f, BRIEF, "test") is False


def test_distributor_requires_all_three_direct_connections():
    rooms = [room("majlis", "majlis", zone="guest"),
             room("wc", "bathroom", guest_parent="majlis"),
             room("vestibule", "corridor", guest_distributor=True)]
    doors = [door("vestibule", "majlis"),
             door("vestibule", "wc"),
             door("vestibule", "OUTSIDE", guest_entry=True)]
    assert make_guest_distributor(floor(rooms, doors), BRIEF, "test") is True
    for index in range(len(doors)):
        assert make_guest_distributor(
            floor(rooms, doors[:index] + doors[index + 1:]), BRIEF, "test"
        ) is False
