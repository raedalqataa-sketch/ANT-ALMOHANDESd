from backend.design.functional_program import checks
from backend.design.independent_audit import inspect


def suite():
    def room(rid, x, zone, y=.1, width=1.8, depth=3.8):
        return dict(id=rid, x=x, y=y, width=width, depth=depth, zone=zone,
                    kind="bathroom" if rid == "wc" else "living", request_id=rid)

    def wall(rid, x, hosts):
        return dict(id=rid, axis="vertical", start=[x, 0], end=[x, 4],
                    room_ids=hosts, thickness=.2, exterior=len(hosts) == 1)

    def opening(rid, x, wall_id, a, b, **flags):
        return dict(id=rid, kind="door", center=[x, 2], width=1, wall_id=wall_id,
                    connects=[a, b], **flags)

    return dict(
        footprint=dict(x=-1, y=0, width=8, depth=5),
        floors=[dict(id="GF",
                     rooms=[room("guest", .1, "guest"), room("wc", 2.1, "guest"),
                            room("family", 4.1, "family")],
                     walls=[wall("entry", 0, ["guest"]), wall("divider", 2, ["guest", "wc"]),
                            wall("private", 4, ["wc", "family"])],
                     openings=[opening("entry", 0, "entry", "guest", "OUTSIDE", guest_entry=True),
                               opening("wc", 2, "divider", "guest", "wc"),
                               opening("family", 4, "private", "wc", "family",
                                       access_control="family_only")])],
    )


def evidence(model):
    return inspect(model)["floors"][0]["verified_opening_routes"]


def test_verified_door_connects_net_rooms_across_wall_thickness():
    result = evidence(suite())
    assert result["opening_issues"] == []
    assert result["requested_rooms_without_verified_route"] == []
    assert result["guest_privacy"]["guest_rooms_without_guest_only_route"] == []
    assert result["guest_privacy"]["protected_rooms_reachable"] == []


def test_door_beyond_room_face_cannot_create_a_route():
    model = suite()
    model["floors"][0]["rooms"][1]["depth"] = 2
    row = evidence(model)
    assert row["opening_issues"] == [
        {"opening_id": "family", "reasons": ["off_room_face"]},
        {"opening_id": "wc", "reasons": ["off_room_face"]},
    ]
    assert row["requested_rooms_without_verified_route"] == ["family", "wc"]
    assert row["guest_privacy"]["guest_rooms_without_guest_only_route"] == ["wc"]


def test_opening_blocked_by_unrelated_room_cannot_supply_entry():
    model = suite()
    room = dict(id="blocker", x=-.5, y=1.5, width=.6, depth=.7, kind="storage")
    model["floors"][0]["rooms"].append(room)
    row = evidence(model)
    assert row["opening_issues"] == [{"opening_id": "entry", "reasons": ["blocked_by_room"]}]
    assert row["verified_entry_rooms"] == []


def test_overlapping_window_and_door_are_not_verified():
    model = suite()
    openings = model["floors"][0]["openings"]
    openings.append(dict(openings[0], id="window", kind="window", guest_entry=False))
    result = evidence(model)
    assert result["opening_issues"] == [
        {"opening_id": rid, "reasons": ["overlapping_aperture"]} for rid in ("entry", "window")
    ]
    assert result["verified_entry_rooms"] == []


def test_uncontrolled_door_exposure_surfaces_in_v4_report():
    model = suite()
    del model["floors"][0]["openings"][2]["access_control"]
    rows = checks({
        "program": {"status": "PASS", "errors": []},
        "movement": {"unreachable": []},
        "furniture_issues": [],
        "independent_geometry": inspect(model),
        "execution_coordination": {
            "site": {"geometric_status": "PASS"},
            "code": {"status": "PENDING"},
            "structure": {"status": "PENDING"},
            "mep": {"status": "PENDING"},
        },
    })
    row = next(row for row in rows if row["check_id"] == "V4-verified-opening-routes")
    assert row["status"] == "PENDING"
    assert row["evidence"]["floors"]["GF"]["guest_privacy"]["protected_rooms_reachable"] == ["family"]
