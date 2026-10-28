"""Architecture-only benchmark over three saved synthetic villa briefs.

Generates concept geometry without drawing doors/windows, creating furniture,
calling V4/full rendering or issuing DXF/PDF. Full validation is a later stage.
"""
from pathlib import Path
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.design.general_models import VillaBrief
from assl.architectural_composer import compose_architecture
from assl.architecture_preview import render_concept_svg


def run(fixtures,out_dir):
    cases=json.loads(Path(fixtures).read_text(encoding='utf-8'))['cases']
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for item in cases:
        case_id=item['id']
        brief=VillaBrief.model_validate(item['brief'])
        begin=time.monotonic()
        result=compose_architecture(brief)
        elapsed=time.monotonic()-begin
        case_dir=out/case_id
        case_dir.mkdir(exist_ok=True)
        (case_dir/'architecture_quality.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        for index,option in enumerate(result['options'],1):
            svg=render_concept_svg(option,title=f'{case_id} / {option["family"]} / concept {index}')
            (case_dir/f'concept_{index}.svg').write_text(svg,encoding='utf-8')
        rows=[dict(family=o['family'],
                   gross=o['quality']['gross_rectangles_m2'],
                   halls=o['quality']['hall_rectangle_area_m2'],
                   warning_count=len(o['quality']['hard_issues']),
                   score=o['quality']['architecture_score']) for o in result['options']]
        reports.append(dict(case=case_id,number_generated=result['generated_count'],
                            target=result['requested_count'],elapsed_s=round(elapsed,2),
                            options=rows,unavailable=result['unavailable_families']))
    summary={'stage':'PRELIMINARY_ARCHITECTURAL_COMPOSITION_ONLY',
             'not_legal_approval':True,'not_for_construction':True,
             'furniture_used':False,'doors_and_windows_not_verified':True,
             'results':reports}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    fixture=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'tests/fixtures/assl_architecture_cases.json'
    output=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'architecture-smoke'
    result=run(fixture,output)
    for row in result['results']:
        print(row['case'],'generated',row['number_generated'],'/',row['target'],
              'elapsed',row['elapsed_s'],'seconds')
    if any(x['number_generated']<3 for x in result['results']):
        raise SystemExit('ARCHITECTURE_COMPOSITION_SHORTFALL: fewer than three acceptable independent plans; see summary.json')
