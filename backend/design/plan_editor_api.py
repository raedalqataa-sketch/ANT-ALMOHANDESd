"""Local prototype editor sessions: immutable baseline, checked saved revisions."""
import copy,json,os,re,threading,math
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter,HTTPException
from assl.strategies.guest_access import check_guest_wc_routes
from assl.strategies.styled_massing import geometry_fingerprint
from fastapi.responses import FileResponse
from pydantic import BaseModel,ConfigDict,Field
from .plan_editing import refresh_and_validate,apply_operations,room_areas
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


def _identity(sid, revision):
    return {
        "version_id": f"{sid}:{revision['version']}",
        "geometry_fingerprint": geometry_fingerprint(revision['result']['proposal']),
    }


def _massing_ready(result):
    proposal = result['proposal']
    return (
        result['exportable']
        and 'first_floor' not in proposal
        and len(proposal['rooms_by_floor']) == len(proposal['halls_by_floor'])
        and len(proposal['rooms_by_floor']) in (1, 2)
        and check_guest_wc_routes(proposal)['status'] != 'FAIL'
    )


def load_massing_revision(sid, version):
    with LOCK:
        session = _load(sid)
        if not 1 <= version <= session['version']:
            raise HTTPException(404, 'REVISION_NOT_FOUND')
        try:
            revision = json.loads((_folder(sid) / f'revision-{version}.json').read_text())
        except FileNotFoundError:
            raise HTTPException(404, 'REVISION_NOT_FOUND')
    proposal = revision['result']['proposal']
    if not _massing_ready(revision['result']):
        raise HTTPException(422, 'EDITOR_REVISION_FAILED_CHECKS')
    return proposal, _identity(sid, revision)


def _public(session, revision):
    return {
        'session_id': session['id'],
        'version': revision['version'],
        'operations': revision['operations'],
        **revision['result'],
        **_identity(session['id'], revision),
        'massing_ready': _massing_ready(revision['result']),
        'saved_at': revision['saved_at'],
        'editor_url': '/editor?session=' + session['id'],
    }



@router.post('/sessions')
def create_session(request:Create):
    proposal=request.proposal
    if len(json.dumps(proposal))>1_000_000:raise HTTPException(413,'PROPOSAL_TOO_LARGE')
    # A bounded supported-schema import; all status flags are recomputed.
    if proposal.get('schema') not in ('assl-clustered-1','assl-clustered-2','assl-relational-1'):raise HTTPException(422,'UNSUPPORTED_EDITOR_SCHEMA')
    try:
        from .general_models import PROPOSAL_BRIEF
        from assl.strategies.clustered import _program
        from assl.strategies.geometry import shape
        brief = PROPOSAL_BRIEF.validate_python(proposal["brief_snapshot"])
        if "first_floor" in proposal or len(proposal["rooms_by_floor"]) == 2:
            if proposal["schema"] != "assl-clustered-2":
                raise ValueError("EDITOR_UNSUPPORTED_MULTI_FLOOR")
            from assl.strategies.clustered_multilevel import check_family_proposal
            proposal = check_family_proposal(brief, proposal)
        if len(proposal["rooms_by_floor"]) != len(proposal["halls_by_floor"]) or len(proposal["rooms_by_floor"]) not in (1, 2):
            raise ValueError("EDITOR_UNSUPPORTED_MULTI_FLOOR")
        objects=proposal['rooms_by_floor'][0]+proposal['halls_by_floor'][0]
        if proposal['schema']=='assl-clustered-2':
            from assl.strategies.central_clustered import program
            expected,_,_=program(brief)
        elif proposal['schema']=='assl-relational-1':
            from assl.strategies.relational import program_view
            expected,_,_=program_view(brief)
        else:expected,_,_=_program(brief)
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
        return dict(proposal=p,verified=False,areas=room_areas(p))
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
            from .general_models import PROPOSAL_BRIEF, VillaBrief
            p=result['proposal']
            brief=PROPOSAL_BRIEF.validate_python(p['brief_snapshot'])
            if len(p["rooms_by_floor"]) != 1 or (ext == "pdf" and not isinstance(brief, VillaBrief)):
                raise HTTPException(422, 'EDITOR_DOCUMENT_FORMAT_UNAVAILABLE')
            if ext=='pdf':
                from assl.strategies.presentation import pdf
                pdf(brief,p,path)
            else:
                from assl.strategies.export import export_dxf
                export_dxf(brief,p,path)
    return FileResponse(path,filename=f'ANT-edited-v{version}.{ext}')
