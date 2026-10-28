"""Offline benchmark: recommend from genuine archived ANT generator outputs.

Usage:
  python scripts/assl_archive_benchmark.py path/to/artifact.zip result.json
This is NOT fresh generation and does NOT change any original drawing.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from assl.space_optimizer import rank_existing_candidates
from assl.core import score_room

CASES=("sa-corner","sa-large","ye-medium")

def _warning_count(model):
    return sum(
        score_room(room["kind"],room["width"],room["depth"])["status"]=="DESIGN_WARNING"
        for floor in model["floors"] for room in floor["rooms"]
        if room["kind"] in ("bedroom","master","majlis","living","kitchen")
    )

def _measure(model):
    metrics=model["metrics"]
    return {"gross_built_m2":round(sum(metrics["floor_built_by_id"].values()),3),
            "circulation_m2":round(metrics["circulation_m2"],3),
            "design_warnings":_warning_count(model)}

def run(path):
    report=[]
    with zipfile.ZipFile(path) as bundle:
        for case in CASES:
            filename=f"{case}/v4/result.json"
            source=bundle.read(filename)
            candidates=json.loads(source)["candidates"]
            original=candidates[0]
            ranked=rank_existing_candidates(candidates)
            index=ranked["recommended_original_index"]
            if index is None:
                report.append({"case":case,"status":"UNRESOLVED_NO_SAFE_CANDIDATE"})
                continue
            selected=candidates[index]
            before,after=_measure(original),_measure(selected)
            assert selected["brief"]==original["brief"]
            assert selected["release"]["drawing_export_allowed"] is True
            assert not any(c["status"]=="FAIL" for c in selected["checks"])
            assert after["gross_built_m2"]<=before["gross_built_m2"]+1e-6
            assert after["circulation_m2"]<=before["circulation_m2"]+1e-6
            report.append({
                "case":case,"status":"SAFE_EXISTING_ALTERNATIVE",
                "source_file_sha256":hashlib.sha256(source).hexdigest(),
                "original_revision":original["model_revision_id"],
                "selected_revision":selected["model_revision_id"],
                "changed_candidate":index!=0,
                "before":before,"after":after,
                "gross_delta_m2":round(after["gross_built_m2"]-before["gross_built_m2"],3),
                "circulation_delta_m2":round(after["circulation_m2"]-before["circulation_m2"],3),
                "protected_checks_original":ranked["ranking"][0]["protected_checks"],
                "protected_checks_selected":ranked["ranking"][index]["protected_checks"]
            })
    measured=[r for r in report if r["status"]=="SAFE_EXISTING_ALTERNATIVE"]
    return {"mode":"HISTORICAL_RE_RANKING_ONLY",
            "fresh_generation_executed":False,
            "geometry_modified":False,
            "legal_compliance_certified":False,
            "cases":report,
            "total_saved_built_m2":round(-sum(r["gross_delta_m2"] for r in measured),3),
            "total_saved_circulation_m2":round(-sum(r["circulation_delta_m2"] for r in measured),3)}

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit(__doc__)
    output=run(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"gross_saved":output["total_saved_built_m2"],
                      "circulation_saved":output["total_saved_circulation_m2"]}))
