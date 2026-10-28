import copy
import unittest
from types import SimpleNamespace
from assl.experimental_runner import generate_with_assl

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.brief = SimpleNamespace(country="YE")
        self.original = {"candidates": [{"floors": [{"id": "GF", "rooms": [
            {"id": "b1", "kind": "bedroom", "width": 3, "depth": 8}
        ]}], "release": {"drawing_export_allowed": False}}], "status": "DRAFT_REVIEW"}

    def test_off_is_identical(self):
        result = generate_with_assl(self.brief, generator=lambda b: copy.deepcopy(self.original))
        self.assertEqual(result, self.original)

    def test_on_attaches_only_diagnostics(self):
        result = generate_with_assl(self.brief, assl_diagnostics=True,
                                    generator=lambda b: copy.deepcopy(self.original))
        self.assertEqual(result["candidates"][0]["assl_experimental"]["design_warnings"], 1)
        self.assertEqual(result["candidates"][0]["release"], self.original["candidates"][0]["release"])
        self.assertEqual(result["status"], self.original["status"])

    def test_original_unmodified(self):
        before = copy.deepcopy(self.original)
        generate_with_assl(self.brief, assl_diagnostics=True, generator=lambda b: self.original)
        self.assertEqual(self.original, before)

    def test_empty_candidates(self):
        result = generate_with_assl(self.brief, assl_diagnostics=True,
                                    generator=lambda b: {"candidates": []})
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["assl_mode"], "READ_ONLY_DIAGNOSTICS")

if __name__ == "__main__":
    unittest.main()
