"""Select verified V4 draft plans from a benchmark artifact into a review ZIP."""
import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import ezdxf
from pypdf import PdfReader


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package(artifact_path, output_path, *, source_commit):
    artifact_path=Path(artifact_path)
    output_path=Path(output_path)
    selections=[]
    chosen={}
    with zipfile.ZipFile(artifact_path) as source:
        names=set(source.namelist())
        for result_name in sorted(name for name in names if name.endswith('/v4/result.json')):
            result=json.loads(source.read(result_name))
            candidates=result.get('candidates',[])
            if len(candidates)!=3:
                continue
            geometries=[row.get('geometry_sha256') for row in candidates]
            if None in geometries or len(set(geometries))!=3:
                raise ValueError(f'non-distinct geometry in {result_name}')
            briefs=[row.get('brief') for row in candidates]
            if any(brief!=briefs[0] for brief in briefs[1:]):
                raise ValueError(f'client brief changed between alternatives: {result_name}')
            case=result_name.split('/')[0]
            for index,row in enumerate(candidates,1):
                if row.get('status')!='DRAFT_REVIEW' or not row.get('release',{}).get('drawing_export_allowed'):
                    raise ValueError(f'unverified candidate in {result_name}')
                if row['release'].get('executive_issue_allowed') or any(c.get('status')=='FAIL' for c in row.get('checks',[])):
                    raise ValueError(f'unsafe candidate in {result_name}')
                revision=row['model_revision_id']
                base=f'{case}/v4/{revision}'
                paths=[base+extension for extension in ('.json','.pdf','.dxf','-GF.svg','-SITE.svg')]
                if row.get('brief',{}).get('floors',1)>1:
                    paths.append(base+'-FF.svg')
                missing=[path for path in paths if path not in names]
                if missing:
                    raise ValueError(f'missing exports: {missing}')
                model=json.loads(source.read(base+'.json'))
                if model.get('model_revision_id')!=revision or model.get('geometry_sha256')!=row['geometry_sha256']:
                    raise ValueError(f'export does not match validated model: {revision}')
                if len(PdfReader(io.BytesIO(source.read(base+'.pdf'))).pages)<1:
                    raise ValueError(f'empty PDF: {revision}')
                with tempfile.NamedTemporaryFile(suffix='.dxf') as tmp:
                    tmp.write(source.read(base+'.dxf'))
                    tmp.flush()
                    drawing=ezdxf.readfile(tmp.name)
                if drawing.dxfversion!='AC1024' or drawing.header.get('$INSUNITS')!=6:
                    raise ValueError(f'DXF version or units incorrect: {revision}')
                for path in paths:
                    chosen[path]=source.read(path)
                selections.append({
                    'case':case,'alternative':index,'candidate_id':row['candidate_id'],
                    'model_revision_id':revision,'geometry_sha256':row['geometry_sha256'],
                    'status':'DRAFT_REVIEW','files':paths,
                    'pending_checks':sum(c.get('status')=='PENDING' for c in row.get('checks',[])),
                })
        if not selections:
            raise ValueError('no verified three-alternative V4 cases in source artifact')
        chosen['matrix.json']=source.read('matrix.json')
    manifest={
        'source_commit':source_commit,
        'source_artifact_sha256':sha256(artifact_path.read_bytes()),
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'scope':'Architectural draft review only; not a permit, executive drawing, or professional approval',
        'cases':sorted({row['case'] for row in selections}),
        'alternatives':selections,
        'files_sha256':{name:sha256(data) for name,data in sorted(chosen.items())},
    }
    readme=('حزمة مراجعة معمارية أولية\n\n'
            'المقترحات المرفقة مسودات DRAFT_REVIEW لحالات اختبار اصطناعية. '
            'لم تصدر لها موافقة قانونية أو إنشائية أو مهنية.\n'
            'لكل حالة ثلاثة بدائل مختلفة في بصمة الهندسة، وتحتوي ملفات PDF وDXF R2010 وJSON ومعاينات SVG.\n'
            'يبيّن release-manifest.json التزام المصدر وبصمات كل ملف.\n').encode()
    chosen['README_AR.txt']=readme
    manifest['files_sha256']['README_AR.txt']=sha256(readme)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as target:
        for name,data in sorted(chosen.items()):
            target.writestr(name,data)
        target.writestr('release-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    manifest=package(args.artifact,args.output,source_commit=args.source_commit)
    print(json.dumps({'output':str(args.output),'cases':manifest['cases'],
                      'alternatives':len(manifest['alternatives']),
                      'sha256':sha256(args.output.read_bytes())},ensure_ascii=False))


if __name__=='__main__':
    main()
