"""Export current default candidates and their evidence for human review.

Run: python -m quality_review.export_v04 --output quality_review/exports/v04
No image synthesis or architectural quality score is used.
"""
import argparse
import json
import shutil
from pathlib import Path
from backend.design.api import design, OUT
from backend.design.models import DesignOptions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('quality_review/exports/v04'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    result=design(DesignOptions())
    summary={k:result[k] for k in ('ranking_reason','search_limit')}
    summary['candidates']=[]
    for model in result['candidates']:
        family=model['search']['family']
        for ext,url in model['downloads'].items():
            shutil.copyfile(OUT/Path(url).name,args.output/f'{family}.{ext}')
        for floor,url in model['previews'].items():
            shutil.copyfile(OUT/Path(url).name,args.output/f'{family}-{floor}.svg')
        summary['candidates'].append({k:model[k] for k in ('model_revision_id','geometry_sha256','search','metrics','release')})
        print(f"{family}: {model['metrics']['failed_checks']} FAIL; {model['metrics']['pending_checks']} PENDING")
    (args.output/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
