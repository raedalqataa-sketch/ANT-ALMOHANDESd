"""Opt-in reproducible JSON comparison of materialized residential candidates.

Input schema:
{"candidates":[{"candidate_id":"A","baseline_score":1.2,"model":{
 "space_audit_envelopes":{"GF":{"x":0,"y":0,"width":12,"depth":15}},
 "floors":[{"id":"GF","rooms":[...]}]}}]}
Only diagnostic ranking is produced; no drawing generation or approval.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .space_efficiency_ranking import compare_candidates
from .architectural_critic import critique


def build_report(payload):
    items = payload["candidates"]
    if not isinstance(items, list) or not items:
        raise ValueError("nonempty candidates list required")
    ids = [str(item["candidate_id"]) for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("candidate IDs must be unique")
    ranked = compare_candidates(items)
    return {"schema": "ant-space-efficiency-comparison-v1",
            "ranking": ranked,
            "critiques": {str(item["candidate_id"]): critique(item["model"])
                          for item in items},
            "decision": "REVIEW_REQUIRED",
            "not_checked": ["program equivalence", "site equivalence",
                            "locked staircase", "furniture and routes",
                            "daylight and ventilation", "privacy",
                            "PDF/DXF consistency", "architectural diversity"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = build_report(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
