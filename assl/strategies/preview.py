"""Small isolated live snapshots. No acceptance flags or editable/export schema."""
from copy import deepcopy


def emit_preview(observer,objects,phase,label,opening_model=None,furniture=None):
    if observer is None:return
    keys=('id','kind','name','x','y','width','depth','polygon','request_id')
    projected=[deepcopy({k:r[k] for k in keys if k in r}) for r in objects]
    frame=dict(schema='assl-preview-1',verified=False,phase=phase,label=label,
               rooms_by_floor=[[r for r in projected if r['kind']!='corridor']],
               halls_by_floor=[[r for r in projected if r['kind']=='corridor']])
    if opening_model is not None:frame['opening_model_009']=deepcopy(opening_model)
    if furniture is not None:frame['furniture_by_floor']=deepcopy(furniture)
    observer(frame)
