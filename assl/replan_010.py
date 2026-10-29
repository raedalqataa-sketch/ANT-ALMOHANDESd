"""Transactional bounded geometric search, never promote a remaining critic FAIL."""
import copy,hashlib,json
from .layout_critic_010 import critique
from .openings_009 import construct,validate,shared_edge

def fingerprint(p):
 fields=('id','request_id','kind','zone','x','y','width','depth')
 return hashlib.sha256(json.dumps([[sorted([{k:r[k] for k in fields if k in r} for r in floor],key=lambda r:r.get('id','')) for floor in p[key]] for key in ('rooms_by_floor','halls_by_floor')],sort_keys=True).encode()).hexdigest()

def proposals(p):
 for fi,halls in enumerate(p['halls_by_floor']):
  for i,h in enumerate(halls):
   q=copy.deepcopy(p);q['halls_by_floor'][fi].pop(i);yield q,dict(operation='remove_hall',floor=fi,index=i)
   # Trim ends conservatively; only a complete 009 revalidation can authorize it.
   axis='y' if h['depth']>=h['width'] else 'x';extent='depth' if axis=='y' else 'width'
   for amount in (.5,1.,2.):
    if h[extent]-amount<1.2:continue
    for end in ('start','end'):
     if fi==0 and h.get('id')=='family-entry-spur' and end=='start':continue
     q=copy.deepcopy(p);r=q['halls_by_floor'][fi][i];r[extent]-=amount
     if end=='start':r[axis]+=amount
     yield q,dict(operation='trim_hall',floor=fi,index=i,amount=amount,end=end)
 for fi,rooms in enumerate(p['rooms_by_floor']):
  for i,a in enumerate(rooms):
   if not a.get('request_id') or a.get('zone')=='guest':continue
   for j,b in enumerate(rooms[i+1:],i+1):
    if not b.get('request_id') or b.get('zone')=='guest':continue
    q=copy.deepcopy(p)
    for key in ('x','y','width','depth'):q['rooms_by_floor'][fi][i][key],q['rooms_by_floor'][fi][j][key]=b[key],a[key]
    yield q,dict(operation='swap_rooms',floor=fi,rooms=[a['id'],b['id']])

def acceptable_change(before,after):
 # No improvement on one floor may conceal regressions on the other.
 for a,b in zip(before['floors'],after['floors']):
  for key in ('union_m2','longest_run_m','room_excess_m2','mean_access_m'):
   if a[key] is None or b[key] is None or b[key]>a[key]+1e-5:return False
  old={(r['source'],r['target_kind']):r['distance_m'] for r in a['relationships']}
  for r in b['relationships']:
   value=old.get((r['source'],r['target_kind']))
   if value is not None and (r['distance_m'] is None or r['distance_m']>value+1e-5):return False
 return len(after['defects'])<=len(before['defects']) and any(b[k]<a[k]-1e-5 for a,b in zip(before['floors'],after['floors']) for k in ('union_m2','longest_run_m','mean_access_m'))

def replan(brief,source,budget=40,limits=None):
 best=copy.deepcopy(source);original=fingerprint(source);base=critique(brief,best,limits);current=base;history=[];attempt=0
 stairs=lambda p:[[{k:r[k] for k in ('x','y','width','depth')} for r in f if r['kind']=='stair'] for f in p['rooms_by_floor']]
 while attempt<budget and current['defects']:
  accepted=False
  for q,operation in __import__('itertools').chain(__import__('itertools').islice(proposals(best),max(1,(budget-attempt)//2)),global_repacking(brief,best)):
   if attempt>=budget:break
   attempt+=1;entry=dict(attempt=attempt,**operation,before_hash=fingerprint(best),after_hash=fingerprint(q) if q is not None else None,accepted=False)
   if q is None:
    entry['reason']='GLOBAL_PACKING_FAILED';history.append(entry);continue
   trial=construct(brief,q);qa=validate(brief,trial)
   if qa['status']!='PASS' or stairs(trial)!=stairs(source):entry['reason']='HARD_CONSTRAINT';entry['issues']=qa['issues']
   else:
    new=critique(brief,trial,limits)
    if fingerprint(q)!=fingerprint(best) and acceptable_change(current,new):
     trial['validation_009']=qa;best=trial;current=new;entry['accepted']=True;entry['reason']='MEASURED_NONREGRESSING_CHANGE';accepted=True
    else:entry['reason']='NO_MEASURED_GAIN_OR_REGRESSION'
   history.append(entry)
   if accepted:break
  if not accepted:break
 return dict(status='ACCEPT' if not current['defects'] and validate(brief,best)['status']=='PASS' else 'REJECT_AND_REPLAN_UNRESOLVED',best=best,before=base,after=current,history=history,original_hash=original,final_hash=fingerprint(best),original_preserved=fingerprint(source)==original,limitations=['bounded fixed-stair search; no guarantee of solving all architectural defects','no furniture, legal/daylight adequacy unresolved'])

def global_repacking(brief,p):
 """New packing around a fixed stair/entry core, not archival alternative reuse."""
 from .free_layout_solver import pack_floor
 W=brief.plot_width-brief.setbacks.east-brief.setbacks.west-brief.wall_thickness
 D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-brief.wall_thickness
 for seed in range(3):
  q=copy.deepcopy(p);good=True
  for fi,(rooms,halls) in enumerate(zip(p['rooms_by_floor'],p['halls_by_floor'])):
   stair=next(r for r in rooms if r['kind']=='stair')
   core=[h for h in halls if h.get('id') in ('family-hub','family-entry-spur','family-growth-node')]
   guests=[r for r in rooms if r.get('zone')=='guest' or r.get('guest_distributor')]
   state,reason=pack_floor([{k:v for k,v in r.items() if k not in ('x','y','width','depth')} for r in rooms if r.get('request_id')],W,D,brief.wall_thickness,seed,(core,stair),guests,beam_width=6,max_branches=4,protect_large_rooms=W<18)
   if state is None:good=False;break
   q['rooms_by_floor'][fi]=state.rooms;q['halls_by_floor'][fi]=state.halls
  yield (q if good else None),dict(operation='global_fixed_core_repacking',seed=seed)
