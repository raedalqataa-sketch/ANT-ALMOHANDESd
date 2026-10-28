"""Reproduce opt-in guest route QA on genuine archived generator JSON.

Usage:
  python scripts/assl_guest_archive_check.py archive.zip report.json

Requires the original project dependencies; does not regenerate or alter plans.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from assl.guest_geometry_qa import generator_check

CASES=('sa-corner','sa-large','ye-medium')
ORIGINAL_CHECKS=('guest-route','guest-distributor-access','GF-walkability')


def audit_archive(input_zip):
    rows=[]
    with zipfile.ZipFile(input_zip) as archive:
        for case in CASES:
            path=f'{case}/v4/result.json'
            original=archive.read(path)
            result=json.loads(original)
            for index,model in enumerate(result['candidates'],1):
                check=generator_check(model)
                rows.append({
                    'case':case,
                    'alternative':index,
                    'original_sha256':hashlib.sha256(original).hexdigest(),
                    'revision_id':model.get('model_revision_id'),
                    'original_checks':{c['check_id']:c['status']
                                       for c in model.get('checks',[])
                                       if c.get('check_id') in ORIGINAL_CHECKS},
                    'assl_status':check['status'],
                    'guest_walkability_status':check['evidence'].get('walkability_status'),
                    'issues':check['evidence'].get('issues',[]),
                    'council_aspect_ratios':check['evidence'].get('majlis_shapes',[]),
                })
    statuses={status:sum(row['assl_status']==status for row in rows)
              for status in ('PASS','FAIL','NOT_APPLICABLE')}
    return {'mode':'ARCHIVED_OUTPUT_INDEPENDENT_RECHECK',
            'fresh_generation_executed':False,
            'baseline_legal_certification':False,
            'geometry_modified':False,
            'body_width_m':.60,'raster_step_m':.20,
            'advisory_majlis_max_aspect_ratio':2.2,
            'counts':statuses,'total':len(rows),'results':rows}


if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit(__doc__)
    report=audit_archive(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'count':report['total'],'statuses':report['counts']},ensure_ascii=False))
