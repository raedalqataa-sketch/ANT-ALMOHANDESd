"""Run the 012 search with stage-009 validation and save evidence separately."""
import argparse
import json
from pathlib import Path
from assl.relationship_first_012 import search

def main():
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--layouts", type=int, default=18)
    p.add_argument("--seconds", type=float, default=5.)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise RuntimeError("Evidence output must be empty")
    report, candidates = search(time_limit=args.seconds, limit=args.layouts)
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for index, candidate in enumerate(candidates, 1):
        (args.output / ("candidate_%02d.json" % index)).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report["status"], report["009_review_candidates"], report["attempts"])

if __name__ == "__main__":
    main()
