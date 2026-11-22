"""Compare actual generated V3/V4 candidates from v4_benchmark matrix.json.

Does not invent interior envelopes, infer circulation union, or claim that
synthetic test briefs are real customer plots. Read-only; no approval.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def compare_matrix(rows):
    output = []
    for case in rows:
        modes = {}
        for mode, entry in case.get("modes", {}).items():
            samples = []
            for sample in entry.get("samples", []):
                metrics = sample.get("metrics", {})
                samples.append({
                    "candidate": sample.get("candidate"),
                    "revision": sample.get("revision"),
                    "heuristic_score": sample.get("score"),
                    "generator_metrics": metrics,
                    "pdf": sample.get("pdf"),
                    "dxf": sample.get("dxf"),
                })
            modes[mode] = {"candidate_count": len(samples), "samples": samples}
        output.append({"case_id": case.get("id"),
                       "synthetic_input": case.get("synthetic", True),
                       "modes": modes,
                       "assessment": "MEASURED_GENERATOR_OUTPUTS_ONLY"})
    return {"schema": "ant-real-generator-comparison-v1",
            "source": "quality_review.v4_benchmark matrix.json",
            "cases": output,
            "approved": False,
            "not_proven": ["true circulation union", "interior-envelope leftover",
                           "furniture-clear routes", "natural daylight and ventilation",
                           "privacy", "architectural quality", "customer-site suitability"],
            "note": "Metrics are the generator's actual reported metrics, not independently remeasured areas."}


def main(argv=None):
    argv = argv or sys.argv[1:]
    source, dest = map(Path, argv)
    result = compare_matrix(json.loads(source.read_text(encoding="utf-8")))
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
