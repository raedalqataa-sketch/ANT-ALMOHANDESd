"""Generate a reproducible, non-executive V3 drawing review packet.

Usage: python -m quality_review.v3_export /tmp/ant-v3-artifacts
The input is synthetic demonstration data, not a client's cadastral survey.
"""
import json
import shutil
import sys
from pathlib import Path

from backend.design.architect_planner import ClientIntent, generate_automatic


def main(target):
    target=Path(target).resolve()
    work=target/"raw"
    target.mkdir(parents=True,exist_ok=True)
    intent=ClientIntent(width=24,depth=32,country="YE",region="الحديدة",city="باجل",
                        family=6,street_edges=["bottom"],main_street="bottom")
    result=generate_automatic(intent,work,constitution_v2=True,generation_v3=True)
    summary={
        "status":"DESIGN_DRAFT_REVIEW_NOT_EXECUTIVE",
        "architectural_process":"adaptive parametric allocation + measured paths + repair re-search",
        "plot_m":[24,32], "location_synthetic":"باجل، الحديدة، اليمن",
        "sample_code_compliance":False,
        "alternatives_returned":len(result["candidates"]),
        "search":result["planning"]["design_selection"],
        "generation_v3":result["planning"]["generation_v3"],
        "alternatives":[],
    }
    for i,model in enumerate(result["candidates"],1):
        rev=model["model_revision_id"]
        copy=[]
        for ext in ("pdf","dxf","json"):
            src=work/(rev+"."+ext)
            if not src.is_file():
                raise RuntimeError("Missing expected export "+str(src))
            dst=target/(f"alternative-{i:02d}."+ext)
            shutil.copyfile(src,dst)
            copy.append(dst.name)
        summary["alternatives"].append({
            "order":i, "source_revision":rev, "files":copy,
            "strategy":model["candidate_id"],
            "functional_intelligence":model["design_evaluation"]["functional_intelligence"],
            "scoring_heuristic":model["design_evaluation"]["heuristic_score"],
            "hard_failures":model["constitution_v2"]["hard_failures"],
            "review_required":model["constitution_v2"]["review_required"],
            "code_approved":False,
        })
    (target/"REVIEW_NOT_EXECUTIVE.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"alternatives":len(result["candidates"]),"path":str(target),
                      "diagnostics":len(result["planning"]["design_selection"]["diagnostics"])}))
    if not result["candidates"]:
        raise RuntimeError("No geometrically valid layout; inspect the JSON diagnostic inputs")


if __name__=="__main__":
    main(sys.argv[1] if len(sys.argv)>1 else "./v3-review-packet")
