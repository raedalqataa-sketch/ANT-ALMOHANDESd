"""V2.1 reference registry. Structural validation is not engineering validation."""
import hashlib
import json
from collections import Counter
from pathlib import Path

REFERENCE_SHA256 = "c218e8b906bb32cef810fb0966a3b529eee7c9d9678d4f7e215e78990a681a95"

def load_reference(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Reference differs from approved V2.1 source")
    doc = json.loads(raw)
    rules = doc["rules"]
    tests = doc["tests"]
    ids = {r["id"] for r in rules}
    if len(rules) != 83 or len(ids) != 83 or len(tests) != 249:
        raise ValueError("Unexpected reference coverage")
    if len({t["id"] for t in tests}) != len(tests):
        raise ValueError("Duplicate test ID")
    if any(t["rule_id"] not in ids for t in tests):
        raise ValueError("Unknown rule reference")
    if any(n != 3 for n in Counter(t["rule_id"] for t in tests).values()) or {t["rule_id"] for t in tests} != ids:
        raise ValueError("Incomplete test specification coverage")
    return doc

def coverage_manifest(doc):
    """Unmapped rules remain explicitly unresolved; no inferred pass."""
    return [{"rule_id": r["id"], "validator_key": r["validator_key"],
             "severity": r["severity"], "implementation_status": "unmapped",
             "test_status": "not_run", "test_ids": [t["id"] for t in doc["tests"] if t["rule_id"] == r["id"]]}
            for r in doc["rules"]]
