"""Compare released alternatives on the same real briefs, with native engines."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
from time import monotonic

from backend.design.architect_planner import ClientIntent, generate_automatic
from backend.design.central_engine import generate_central, write_json
from quality_review.space_efficiency import measure_candidate


def measurements(model):
    floors = measure_candidate(model)["floors"]
    return {
        "candidate": model["candidate_id"],
        "revision": model["model_revision_id"],
        "largest_floor_m2": model["metrics"]["floor_built_m2"],
        "gross_circulation_union_m2": round(sum(f["gross_circulation_union_area_m2"] for f in floors), 4),
        "requested_spaces": model["metrics"]["requested_spaces"],
        "pending_checks": sum(c["status"] == "PENDING" for c in model["checks"]),
    }


def run(item):
    name, raw, output = item
    intent = ClientIntent.model_validate(raw)
    directory = output / name
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for mode in ("reference_v3", "central_v4"):
        start = monotonic()
        try:
            if mode == "reference_v3":
                generated = generate_automatic(intent, directory / mode, constitution_v2=True, generation_v3=True)
            else:
                generated = generate_central(intent, directory / mode)
            result[mode] = {
                "status": generated["status"], "unavailable": generated["unavailable"],
                "alternatives": [measurements(m) for m in generated["candidates"]
                                 if m["release"]["drawing_export_allowed"]],
            }
            if mode == "central_v4":
                result[mode].update(run_id=generated["run_id"], comparison=generated["comparison"])
        except ValueError as error:
            result[mode] = {"status": "REJECTED", "reason": str(error), "alternatives": []}
        result[mode]["seconds"] = round(monotonic() - start, 2)
        print(name, mode, result[mode]["status"], len(result[mode]["alternatives"]), flush=True)
    write_json(directory / "summary.json", result)
    return name, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    briefs = json.loads(Path(__file__).with_name("briefs.json").read_text())
    jobs = [(name, raw, args.out) for name, raw in briefs.items()]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = dict(pool.map(run, jobs))
    write_json(args.out / "benchmark.json", results)
    for name, values in results.items():
        ok = values["central_v4"]["alternatives"]
        if bool(ok) == name.endswith("rejection"):
            raise SystemExit(f"Unexpected generation status for {name}")


if __name__ == "__main__":
    main()
