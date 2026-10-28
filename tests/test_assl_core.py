"""Pure experimental ASSL tests; no modifications to generator runtime."""
import unittest
from assl.core import load_rules, resolve_rules, validate_metrics, score_room

class ASSLCoreTests(unittest.TestCase):
    def test_rules_load(self):
        self.assertEqual(len(load_rules()["rules"]), 4)

    def test_country_filter(self):
        self.assertEqual(len(resolve_rules("YE", context={"space_type": "habitable_room"})), 2)
        self.assertEqual(len(resolve_rules("SA", context={"space_type": "habitable_room"})), 2)

    def test_missing_local_is_unresolved(self):
        rules = resolve_rules("YE", context={"space_type": "habitable_room"})
        results = validate_metrics(rules, {"space.net_floor_area": 10})
        self.assertEqual(results[1]["status"], "UNRESOLVED")

    def test_draft_does_not_claim_legal_pass(self):
        rule = resolve_rules("YE", context={"space_type": "habitable_room"})[0]
        self.assertEqual(validate_metrics([rule], {"space.net_floor_area": 12}, enforcement_enabled=True)[0]["status"], "DRAFT_MATCH")
        self.assertFalse(validate_metrics([rule], {"space.net_floor_area": 12})[0]["legal_compliance_certified"])

    def test_unauthenticated_local_is_unresolved(self):
        rules = resolve_rules("SA", local_values={"SA-LOCAL-SETBACK": {"value": 3, "approved": False}})
        self.assertEqual(rules[-1]["resolution_status"], "UNRESOLVED")

    def test_approved_local_is_still_non_enforcing_in_draft(self):
        rules = resolve_rules("SA", local_values={"SA-LOCAL-SETBACK": {"value": 3, "approved": True, "source_url": "https://example.org/approved-plan"}})
        self.assertEqual(validate_metrics([rules[-1]], {"site.front_setback": 2})[0]["status"], "DRAFT_MISMATCH")

    def test_long_bedroom_warning(self):
        self.assertIn("elongated_room", score_room("bedroom", 3, 8)["reasons"])

    def test_non_legal_design(self):
        self.assertFalse(score_room("bedroom", 4, 4)["is_legal_assessment"])

if __name__ == "__main__":
    unittest.main()
