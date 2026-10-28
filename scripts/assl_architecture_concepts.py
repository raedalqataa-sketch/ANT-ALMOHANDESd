"""Create 3 architecture-first pre-furniture concept proposals.

Usage:
  python scripts/assl_architecture_concepts.py input-brief.json output-dir
The input brief uses the existing VillaBrief Pydantic schema. Not for
construction; only preliminary geometry, not legal/code or engineering approval.
"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.architectural_composer import compose_architecture
from assl.architecture_preview import render_concept_svg


def run(brief_path,output_dir):
    brief=VillaBrief.model_validate(json.loads(Path(brief_path).read_text(encoding='utf-8')))
    result=compose_architecture(brief)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    for n,option in enumerate(result['options'],1):
        svg=render_concept_svg(option,title=f'Architecture Proposal {n} — {option["family"]}')
        (out/f'architecture_concept_{n}.svg').write_text(svg,encoding='utf-8')
    (out/'architecture_quality.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit(__doc__)
    result=run(sys.argv[1],sys.argv[2])
    print(json.dumps({
        'requested':result['requested_count'],
        'generated':result['generated_count'],
        'families':[o['family'] for o in result['options']],
        'stage':result['stage'],
        'not_for_construction':True},ensure_ascii=False))
    if result['generated_count']<result['requested_count']:
        raise SystemExit('The engine could not produce three distinct eligible concepts; inspect architecture_quality.json')
