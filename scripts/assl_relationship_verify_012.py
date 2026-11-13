"""Run the 012 MILP feedback loop through real 008/009/010 gates.

This command must not call the geometry-only search() helper: only the
feedback search records actual gate evidence and can produce review candidates.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assl import relationship_first_012 as solver
from assl.stage012_feedback_search import run_search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/assl_architecture_cases.json"))
    parser.add_argument("--case", default="sa-corner")
    parser.add_argument("--layouts", type=int, default=18)
    parser.add_argument("--repacks", type=int, default=4)
    parser.add_argument("--seconds", type=float, default=5.)
    args = parser.parse_args()

    if args.case != "sa-corner":
        parser.error("Stage 012 currently supports only the sa-corner case; other cases are unverified.")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise RuntimeError("Evidence output must be empty")

    from backend.design.general_models import VillaBrief
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    case = next((item for item in fixture["cases"] if item["id"] == args.case), None)
    if case is None:
        parser.error(f"Case not found in fixture: {args.case}")
    brief = VillaBrief.model_validate(case["brief"])
    baseline = json.loads(solver.SOURCE_009.read_text(encoding="utf-8"))

    report, candidates = run_search(
        brief, baseline,
        max_layouts=args.layouts,
        repacks=args.repacks,
        seconds=args.seconds,
    )
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for index, candidate in enumerate(candidates, 1):
        path = args.output / ("candidate_%02d.json" % index)
        path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        report["status"],
        "attempted=", report["attempted"],
        "accepted_candidates=", report["accepted_candidates"],
        "distinct_topologies=", report["distinct_topology_count"],
        "three_verified=", report["three_structural_alternatives_verified"],
    )
    return 0 if report["three_structural_alternatives_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
