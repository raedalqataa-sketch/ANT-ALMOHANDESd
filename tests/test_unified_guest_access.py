from unittest import TestCase

from assl.strategies.guest_access import check_guest_wc_routes


class GuestAccessTest(TestCase):
    def test_foyer_route_allowed_and_family_route_rejected(self):
        rooms = [
            {"id": "council", "kind": "majlis", "guest_entries": ["men"]},
            {"id": "wc", "kind": "bathroom", "guest_entries": ["men"]},
            {"id": "living", "kind": "living"},
        ]
        halls = [{"id": "foyer", "guest_entry": "men"}]
        for connector, expected in [("foyer", "PASS"), ("living", "FAIL")]:
            with self.subTest(connector=connector):
                doors = [
                    {"connects": [a, b], "roles": ["guest:men"]}
                    for a, b in [("council", connector), (connector, "wc")]
                ]
                result = check_guest_wc_routes({
                    "rooms_by_floor": [rooms],
                    "halls_by_floor": [halls],
                    "opening_model_009": [{"doors": doors}],
                })
                self.assertEqual(result["status"], expected)
