import json
import hashlib
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from .models import DesignOptions
from .requirements import project_profile, rules_summary, import_brief
from .generator import generate_candidates
from .validators import validate_model, release_decision
from .export import svg, export_pdf, export_dxf
from .furniture_symbols import SYMBOL_VERSION

router=APIRouter(prefix='/api/v2',tags=['architectural-drafts'])
OUT=Path(__file__).resolve().parents[2]/'outputs'


@router.get('/project')
def get_project():
    return {'profile':project_profile(),'rules':rules_summary(),
            'supported_scope':'ثلاث عائلات تنظيم وكتلة للمحفد مع بحث فرش وخلوص؛ لا ضمان لتغطية كل الحلول',
            'version':'0.4.1',
            'export_formats':{'dxf':{'label':'AutoCAD 2010 DXF','acadver':'AC1024','units':'m'}},
            'requirements_import':'معاينة وربط مصدر Excel المعتمد؛ النصوص الجديدة لا تفسر تلقائيًا'}


@router.post('/import-excel')
async def import_excel_brief(file:UploadFile=File(...)):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(400,'ارفع ملف XLSX')
    data=await file.read(5_000_001)
    if len(data)>5_000_000:
        raise HTTPException(413,'حجم الملف أكبر من 5 ميغابايت')
    try:
        return import_brief(data)
    except Exception as exc:
        raise HTTPException(422,f'تعذرت معاينة مدخلات الفيلا: {exc}')


def coverage(model):
    ids={r['id'].split('-',1)[1] for f in model['floors'] for r in f['rooms']}
    mapping={'men_majlis':'men','men_washbasins':'men-wash','men_wc':'men-bath','women_majlis':'women',
             'family_lounge':'living','family_dining':'dining','daily_living':'living','master_bedroom':'master',
             'master_dressing':'dressing','master_bathroom':'master-bath','children_bedrooms':'child1',
             'shared_family_bathroom':'family-bath','main_kitchen':'kitchen','laundry':'laundry','stairs':'stair','home_office':'office','prep_kitchen':'prep-kitchen','private_bedroom_bathroom':'child-bath'}
    result=[]
    for p in model['profile']['preferred_spaces']:
        present=mapping.get(p['id']) in ids
        if p['id']=='daily_living':present=any(r['kind']=='living' for f in model['floors'] if f['id']=='FF' for r in f['rooms'])
        if p['id']=='garden':present=any(f['kind']=='garden' for f in model.get('site_features',[]))
        if p['id'] in ('usable_roof','courtyard_outdoor_seating'):
            present=any(f.get('outdoor_furniture') for f in model['floors'])
        combined=p['id']=='pantry' and 'storage' in ids
        result.append(dict(id=p['id'],label=p['label'],requirement_priority='preferred',
                           status='PROPOSED_COMBINED_SPACE' if combined else 'PROPOSED_IN_CANDIDATE' if present else 'DEFERRED_PREFERENCE',
                           source_ref='EXCEL_PREFERRED_PROGRAM',reason='مؤن ومستودع مشترك كمقترح؛ ليسا فراغين مستقلين' if combined else 'مقترح يحتاج اعتماد الأبعاد والسعة والاستعمال' if present else 'الطلب محفوظ ولم يُدرج في هذا البديل'))
    return result


@router.post('/design')
def design(options:DesignOptions):
    try:
        models=generate_candidates(options)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    OUT.mkdir(exist_ok=True)
    candidates=[]
    for model in models:
        model.setdefault('presentation',{})['furniture_symbols']=SYMBOL_VERSION
        def canonical(value):
            if isinstance(value,dict):return {k:canonical(v) for k,v in value.items() if k not in ('revision_id','model_revision_id')}
            if isinstance(value,list):return [canonical(v) for v in value]
            return value
        geometry={k:model[k] for k in ('floors','stairs','parking','footprint')}
        model['geometry_sha256']=hashlib.sha256(json.dumps(canonical(geometry),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        checks=validate_model(model,options.confirmed_opening_faces)
        release=release_decision(checks)
        revision=model['model_revision_id']
        model['numeric_tolerance']={'meters':1e-6,'source':'PROPOSED_NUMERIC_COMPUTATION_TOLERANCE','not_legal_standard':True}
        model['change_record']={'revision_id':revision,'parent_revision_id':None,'type':'NEW_UNAPPROVED_CANDIDATE',
                                'locked_approved_versions_changed':False,'parameters':options.model_dump(exclude={'project_profile'})}
        model['checks']=checks
        model['release']=release
        model['preference_coverage']=coverage(model)
        model['metrics']={'footprint_m2':round(model['footprint']['width']*model['footprint']['depth'],2),
                          'net_rooms_m2':round(sum(r['area_m2'] for f in model['floors'] for r in f['rooms']),2),
                          'circulation_m2':round(sum(r['area_m2'] for f in model['floors'] for r in f['rooms'] if r['kind']=='corridor'),2),
                          'bed_capacity':sum(q['capacity'] for f in model['floors'] for q in f['furniture']),
                          'passed_checks':sum(c['status']=='PASS' for c in checks),'pending_checks':sum(c['status']=='PENDING' for c in checks),
                          'failed_checks':sum(c['status']=='FAIL' for c in checks),
                          'family_label_ar':model['search'].get('family_label_ar','التوزيع السابق'),
                          'floor_built_m2':{f['id']:f.get('gross_area_proposed_m2',round(model['footprint']['width']*model['footprint']['depth'],2)) for f in model['floors']},
                          'circulation_ratio':round(sum(r['area_m2'] for f in model['floors'] for r in f['rooms'] if r['kind']=='corridor')/sum(r['area_m2'] for f in model['floors'] for r in f['rooms']),4),
                          'longest_corridor_m':round(max((max(r['width'],r['depth']) for f in model['floors'] for r in f['rooms'] if r['kind']=='corridor'),default=0),2),
                          'dining_seats':sum(q.get('seats',0) for f in model['floors'] for q in f['furniture'] if q['kind']=='dining_chair'),
                          'bedroom_count_proposed':options.bedroom_count}
        model['downloads']={'json':f'/api/files/{revision}.json'}
        model['previews']={}
        if release['drawing_export_allowed']:
            for f in model['floors']:
                name=f'{revision}-{f["id"]}.svg'
                (OUT/name).write_text(svg(model,f),encoding='utf-8')
                model['previews'][f['id']]=f'/api/files/{name}'
            (OUT/f'{revision}-SITE.svg').write_text(svg(model,model['floors'][0],site_view=True),encoding='utf-8')
            model['previews']['SITE']=f'/api/files/{revision}-SITE.svg'
            model['export_audit']=export_dxf(model,OUT/f'{revision}.dxf')
            export_pdf(model,OUT/f'{revision}.pdf')
            model['downloads'].update({ext:f'/api/files/{revision}.{ext}' for ext in ('dxf','pdf')})
        (OUT/f'{revision}.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
        candidates.append(model)
    # Deterministic comparison, not a fabricated overall architectural quality score.
    candidates.sort(key=lambda c:(c['metrics']['failed_checks'],c['metrics']['pending_checks'],c['metrics']['longest_corridor_m'],c['metrics']['circulation_ratio'],c['metrics']['footprint_m2']))
    return {'status':'DRAFT_REVIEW','candidates':candidates,
            'ranking_reason':'الأقل فشلًا ثم المعلقات ثم طول أكبر موزع ونسبة الموزعات الصريحة ومساحة المبنى. معايير مقارنة جزئية وليست درجة جودة معمارية شاملة.',
            'search_limit':'ثلاث عائلات تنظيم مختلفة مع بدائل فرش وفحص حركة؛ البحث محدود وليس ضمانًا لأفضل حل ممكن.'}
