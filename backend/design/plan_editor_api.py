"""Local prototype editor sessions: immutable baseline, checked saved revisions."""
import copy,json,os,re,threading,math
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,ConfigDict,Field
from .plan_editing import refresh_and_validate,apply_operations
from shapely.errors import ShapelyError

router=APIRouter(prefix='/api/editor',tags=['manual-plan-editor'])
STORE=Path(__file__).resolve().parents[2]/'outputs'/'editor'
LOCK=threading.RLock()

class Create(BaseModel):
    model_config=ConfigDict(extra='forbid')
    proposal:dict
class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base_version:int=Field(ge=0)
    operations:list[dict]=Field(default_factory=list,max_length=120)


def _folder(sid):
    if not re.fullmatch('[a-f0-9]{32}',sid):raise HTTPException(404,'SESSION_NOT_FOUND')
    return STORE/sid


def _load(sid):
    try:return json.loads((_folder(sid)/'session.json').read_text())
    except FileNotFoundError:raise HTTPException(404,'SESSION_NOT_FOUND')


def _atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.'+uuid4().hex+'.tmp')
    try:temp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False));os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def _evaluate(baseline,operations):
    try:return refresh_and_validate(baseline,operations)
    except (ValueError,KeyError,TypeError,IndexError,ShapelyError) as e:raise HTTPException(422,str(e))


def _public(session,revision):
    return dict(session_id=session['id'],version=revision['version'],operations=revision['operations'],
                **revision['result'],saved_at=revision['saved_at'],editor_url='/editor?session='+session['id'])


@router.post('/sessions')
def create_session(request:Create):
    proposal=request.proposal
    if len(json.dumps(proposal))>1_000_000:raise HTTPException(413,'PROPOSAL_TOO_LARGE')
    # A bounded supported-schema import; all status flags are recomputed.
    if proposal.get('schema') not in ('assl-clustered-1','assl-clustered-2','assl-relational-1'):raise HTTPException(422,'UNSUPPORTED_EDITOR_SCHEMA')
    try:
        from .general_models import VillaBrief
        from assl.strategies.clustered import _program
        from assl.strategies.geometry import shape
        if len(proposal['rooms_by_floor'])!=1 or len(proposal['halls_by_floor'])!=1:raise ValueError('EDITOR_GROUND_FLOOR_ONLY')
        objects=proposal['rooms_by_floor'][0]+proposal['halls_by_floor'][0]
        if proposal['schema']=='assl-clustered-2':
            from assl.strategies.central_clustered import program
            expected,_,_=program(VillaBrief.model_validate(proposal['brief_snapshot']))
        elif proposal['schema']=='assl-relational-1':
            from assl.strategies.relational import program_view
            expected,_,_=program_view(VillaBrief.model_validate(proposal['brief_snapshot']))
        else:expected,_,_=_program(VillaBrief.model_validate(proposal['brief_snapshot']))
        requests={r['id']:r for r in expected}
        if len(objects)>80 or len({r['id'] for r in objects})!=len(objects):raise ValueError('EDITOR_GEOMETRY_LIMIT')
        for r in objects:
            if not 3<=len(r['polygon'])<=256:raise ValueError('EDITOR_GEOMETRY_LIMIT')
            if any(len(v)!=2 or any(not isinstance(n,(int,float)) or not math.isfinite(n) or abs(n)>200 for n in v) for v in r['polygon']):raise ValueError('INVALID_SOURCE_COORDINATES')
            if any(not isinstance(r[k],(int,float)) or not math.isfinite(r[k]) for k in ('x','y','width','depth')) or r['width']<=0 or r['depth']<=0:raise ValueError('INVALID_SOURCE_DIMENSIONS')
            if not shape(r).is_valid or shape(r).area<.1:raise ValueError('INVALID_SOURCE_POLYGON')
            if r['kind']!='stair' and ('arcs' in r or 'stair' in r):raise ValueError('UNSUPPORTED_CURVE_METADATA')
            req=requests.get(r['id'])
            if r.get('request_id'):
                if not req or any(r.get(k)!=req.get(k) for k in ('request_id','kind','min_area','min_side','guest_entries')):raise ValueError('SOURCE_PROGRAM_METADATA_MISMATCH')
            elif r['id']=='stair-core':
                if r['kind']!='stair':raise ValueError('INVALID_STAIR_SOURCE')
            elif r not in proposal['halls_by_floor'][0] or r['kind']!='corridor':raise ValueError('UNSUPPORTED_SOURCE_ENTITY')
    except (KeyError,TypeError,IndexError,ValueError,ShapelyError) as e:raise HTTPException(422,str(e))
    result=_evaluate(proposal,[]);sid=uuid4().hex
    revision=dict(version=0,operations=[],result=result,saved_at=datetime.now(timezone.utc).isoformat())
    session=dict(id=sid,baseline=copy.deepcopy(proposal),version=0)
    with LOCK:
        _atomic(_folder(sid)/'revision-0.json',revision);_atomic(_folder(sid)/'session.json',session)
    return _public(session,revision)


@router.get('/sessions/{sid}')
def get_session(sid:str):
    with LOCK:
        session=_load(sid);revision=json.loads((_folder(sid)/f"revision-{session['version']}.json").read_text())
    return _public(session,revision)


@router.post('/sessions/{sid}/geometry')
def geometry_preview(sid:str,request:Edit):
    with LOCK:
        session=_load(sid)
        if session['version']!=request.base_version:raise HTTPException(409,'STALE_REVISION:reload-before-saving')
    try:
        p=apply_operations(session['baseline'],request.operations)
        from assl.strategies.geometry import net_shape
        return dict(proposal=p,verified=False,areas={r['id']:round(net_shape(r,p['brief_snapshot']['wall_thickness']).area,4) for r in p['rooms_by_floor'][0]+p['halls_by_floor'][0]})
    except (ValueError,KeyError,TypeError,IndexError,ShapelyError) as e:raise HTTPException(422,str(e))


@router.post('/sessions/{sid}/preview')
def preview(sid:str,request:Edit):
    with LOCK:
        session=_load(sid)
        if session['version']!=request.base_version:raise HTTPException(409,'STALE_REVISION:reload-before-saving')
        baseline=session['baseline']
    return dict(**_evaluate(baseline,request.operations),operations=request.operations,version=request.base_version)


@router.post('/sessions/{sid}/revisions')
def save_revision(sid:str,request:Edit):
    with LOCK:
        session=_load(sid)
        if session['version']!=request.base_version:raise HTTPException(409,'STALE_REVISION:reload-before-saving')
        if session['version']>=200:raise HTTPException(422,'REVISION_LIMIT')
        result=_evaluate(session['baseline'],request.operations);version=session['version']+1
        revision=dict(version=version,operations=request.operations,result=result,saved_at=datetime.now(timezone.utc).isoformat())
        _atomic(_folder(sid)/f'revision-{version}.json',revision)
        session['version']=version;_atomic(_folder(sid)/'session.json',session)
    return _public(session,revision)


@router.get('/sessions/{sid}/revisions/{version}/files/{ext}')
def download(sid:str,version:int,ext:str):
    if ext not in ('json','pdf','dxf') or version<0:raise HTTPException(404)
    with LOCK:
        session=_load(sid);folder=_folder(sid)
        try:revision=json.loads((folder/f'revision-{version}.json').read_text())
        except FileNotFoundError:raise HTTPException(404,'REVISION_NOT_FOUND')
        p=revision['result']['proposal'];path=folder/f'proposal-{version}.{ext}'
        if ext=='json':_atomic(path,p)
        else:
            # Revalidate saved geometry; no trusted PASS flags or stale draw files.
            result=_evaluate(session['baseline'],revision['operations'])
            if not result['exportable']:raise HTTPException(422,dict(code='EXPORT_BLOCKED',issues=result['issues']))
            from .general_models import VillaBrief
            brief=VillaBrief.model_validate(session['baseline']['brief_snapshot']);p=result['proposal']
            if ext=='pdf':
                from assl.strategies.presentation import pdf
                pdf(brief,p,path)
            else:
                from assl.strategies.export import export_dxf
                export_dxf(brief,p,path)
    return FileResponse(path,filename=f'ANT-edited-v{version}.{ext}')
