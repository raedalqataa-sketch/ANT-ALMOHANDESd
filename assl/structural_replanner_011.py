"""Balanced, deduplicated architectural search. No furniture or statutory limits."""
import copy,hashlib,json,itertools,math
from collections import Counter
from .openings_009 import validate,_opening_revision,shared_edge,shape
from .layout_critic_010 import critique
from .replan_010 import acceptable_change

OPERATIONS=('move_room','move_group','rotate_room','swap_rooms','repartition','move_node','merge_nodes','new_node','remove_corridor','rebuild')

def physical_hash(p):
 return hashlib.sha256(json.dumps([[sorted([tuple(r[k] for k in ('x','y','width','depth'))+(r.get('kind'),r.get('zone','family')) for r in f],key=str) for f in p[key]] for key in ('rooms_by_floor','halls_by_floor')],sort_keys=True).encode()).hexdigest()

def stairs(p):return [[tuple(r[k] for k in ('x','y','width','depth')) for r in f if r['kind']=='stair'] for f in p['rooms_by_floor']]

def stair_valid(source,p,locked):
 s=stairs(p)
 return bool(s) and all(len(f)==1 for f in s) and all(f==s[0] for f in s) and (not locked or s==stairs(source))

def relations(brief):
 return dict(required=['requested rooms and minima','door access','aligned stair','direct exterior openings'],
             preferred=[['living','dining','kitchen'],['bedroom','bathroom'],['master','bathroom']],
             separated=[['guest','family']],source='program + explicit owner functional requirements; distance limits remain 010 design indicators')

def _local(p,category):
 for fi,rooms in enumerate(p['rooms_by_floor']):
  eligible=[i for i,r in enumerate(rooms) if r.get('request_id') and r.get('zone')!='guest']
  halls=p['halls_by_floor'][fi]
  if category in ('move_room','rotate_room'):
   for shift in (.5,-.5,1.,-1.):
    for i in eligible:
     q=copy.deepcopy(p);r=q['rooms_by_floor'][fi][i]
     if category=='move_room':r['x']+=shift
     else:r['width'],r['depth']=r['depth'],r['width'];r['y']+=shift
     yield q,dict(floor=fi,room=rooms[i]['id'],shift=shift)
  elif category=='move_group':
   groups=[('living','dining','kitchen'),('bedroom','master','bathroom')]
   for shift in (.5,-.5,1.,-1.):
    for group in groups:
     q=copy.deepcopy(p)
     for i in eligible:
      if rooms[i]['kind'] in group:q['rooms_by_floor'][fi][i]['y']+=shift
     yield q,dict(floor=fi,group=group,shift=shift)
  elif category in ('swap_rooms','repartition'):
   for i,j in itertools.combinations(eligible,2):
    q=copy.deepcopy(p);a,b=q['rooms_by_floor'][fi][i],q['rooms_by_floor'][fi][j]
    if category=='swap_rooms':
     for k in ('x','y','width','depth'):a[k],b[k]=b[k],a[k]
    else:
     edge=shared_edge(a,b)
     if not edge:continue
     axis='y' if edge['axis']=='x' else 'x';extent='depth' if axis=='y' else 'width'
     first,second=(a,b) if a[axis]<b[axis] else (b,a)
     first[extent]+=.25;second[axis]+=.25;second[extent]-=.25
    yield q,dict(floor=fi,rooms=[a['id'],b['id']])
  elif category in ('move_node','remove_corridor','new_node'):
   for i,h in enumerate(halls):
    q=copy.deepcopy(p);target=q['halls_by_floor'][fi]
    if category=='move_node':target[i]['x']+=.5
    elif category=='remove_corridor':target.pop(i)
    else:target.append(dict(x=h['x']+h['width'],y=h['y'],width=1.5,depth=1.5,kind='corridor',id='011-new-node'))
    yield q,dict(floor=fi,index=i)
  elif category=='merge_nodes':
   for i,j in itertools.combinations(range(len(halls)),2):
    a,b=halls[i],halls[j]
    if not shared_edge(a,b):continue
    x=min(a['x'],b['x']);y=min(a['y'],b['y']);xx=max(a['x']+a['width'],b['x']+b['width']);yy=max(a['y']+a['depth'],b['y']+b['depth'])
    q=copy.deepcopy(p);q['halls_by_floor'][fi]=[h for k,h in enumerate(q['halls_by_floor'][fi]) if k not in (i,j)]+[dict(x=x,y=y,width=xx-x,depth=yy-y,kind='corridor',id='011-merged-node')]
    yield q,dict(floor=fi,indices=[i,j])

def rebuild(brief,p,locked=False):
 """Repack a new functional core in local frontage coordinates; stair may move."""
 from .free_layout_solver import rect,pack_floor,guest_suite
 from .topology_options import local_envelope,transform_candidate
 t=brief.wall_thickness;W=brief.plot_width-brief.setbacks.east-brief.setbacks.west-t;D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
 w,d=local_envelope(W,D,brief.entrance_face)
 if locked:
  from .replan_010 import global_repacking
  yield from global_repacking(brief,p);return
 for hy in (2.5,3.75,1.5):
  for fraction in (.4,.5,.6):
   hx=round(w*fraction*4)/4
   core=[rect(hx,hy,2.5,2.5,kind='corridor',id='family-hub'),rect(hx+.5,0,1.5,hy,kind='corridor',id='family-entry-spur'),rect(hx+.5,hy+2.5,1.5,1.5,kind='corridor',id='family-growth-node')]
   stair=rect(hx+2.5,hy,3.,4.6,kind='stair',id='shared-stair',name='درج متطابق بين الأدوار')
   floors=[];walk=[];reason=None
   for fi,old in enumerate(p['rooms_by_floor']):
    requests=[{k:v for k,v in r.items() if k not in ('x','y','width','depth','guest_vestibule')} for r in old if r.get('request_id')]
    guests,reason=guest_suite(requests,core[0],w,d,t) if fi==0 else ([],None)
    if reason:break
    state,reason=pack_floor(requests,w,d,t,int(hy*4+fraction*10),(core,stair),guests,beam_width=10,max_branches=4,protect_large_rooms=w<18,priority_order=('kitchen','dining','living','master','bedroom','bathroom'),shape_grid=.05,portal_contact=1.2)
    if state is None:break
    floors.append(state.rooms);walk.append(state.halls)
   if len(floors)!=brief.floors:yield None,dict(hub=[hx,hy],failure=reason);continue
   moved=transform_candidate(dict(floors=floors,halls_by_floor=walk),w,d,brief.entrance_face)
   q=copy.deepcopy(p);q['rooms_by_floor']=moved['floors'];q['halls_by_floor']=moved['halls_by_floor'];yield q,dict(hub=[hx,hy],stair_movable=True)

def schedule(brief,p,per_class=3,locked=False):
 """Independent quotas; round robin prevents the local-prefix bias of010."""
 current=p() if callable(p) else p
 streams={c:iter(rebuild(brief,current,locked) if c=='rebuild' else _local(current,c)) for c in OPERATIONS};anchor=physical_hash(current);seen={anchor}
 counts=Counter()
 for round_index in range(per_class):
  for c in OPERATIONS:
   current=p() if callable(p) else p
   if physical_hash(current)!=anchor:
    anchor=physical_hash(current);seen.add(anchor)
    streams={k:iter(rebuild(brief,current,locked) if k=='rebuild' else _local(current,k)) for k in OPERATIONS}
   for _ in range(100):
    item=next(streams[c],None)
    if item is None:yield None,dict(category=c,reason='NO_MORE_DISTINCT_PROPOSALS');break
    q,details=item
    if q is not None:
     h=physical_hash(q)
     if h in seen:continue
     seen.add(h)
    counts[c]+=1;yield q,dict(category=c,**details);break

def replan(brief,source,per_class=3,stair_locked=False,limits=None):
 base=critique(brief,source,limits);best=copy.deepcopy(source);current=base;history=[];stats={c:Counter() for c in OPERATIONS}
 if not base['defects']:return dict(status='ACCEPT',best=best,before=base,after=base,history=[],categories={},relations=relations(brief),original_hash=physical_hash(source),final_hash=physical_hash(best),stair_locked=stair_locked)
 for candidate,operation in schedule(brief,lambda:best,per_class,stair_locked):
  c=operation['category'];stats[c]['considered']+=1;entry=dict(**operation,accepted=False)
  if candidate is None:entry['reason']=operation.get('reason','PACKING_FAILED');stats[c]['unavailable']+=1;history.append(entry);continue
  entry['before_hash']=physical_hash(best);entry['candidate_hash']=physical_hash(candidate)
  entry['geometry']={k:candidate[k] for k in ('rooms_by_floor','halls_by_floor')}
  if not stair_valid(source,candidate,stair_locked):entry['reason']='STAIR_CONSTRAINT'
  else:
   trial=_opening_revision(brief,candidate);qa=validate(brief,trial)
   if qa['status']!='PASS':entry['reason']='HARD_CONSTRAINT';entry['issues']=qa['issues']
   else:
    new=critique(brief,trial,limits);entry['critique']=new
    if acceptable_change(current,new):
     best=trial;best['validation_009']=qa;current=new;entry['accepted']=True;entry['reason']='MEASURED_NONREGRESSING_GAIN';stats[c]['accepted']+=1
    else:entry['reason']='NO_GAIN_OR_REGRESSION'
  stats[c]['tested']+=1;history.append(entry)
 return dict(status='ACCEPT' if not current['defects'] else 'REJECT_AND_REPLAN_UNRESOLVED',best=best,before=base,after=current,history=history,categories={k:dict(v) for k,v in stats.items()},relations=relations(brief),stair_locked=stair_locked,original_hash=physical_hash(source),final_hash=physical_hash(best))

def circulation_function_review(brief,p):
 """Necessity in this layout only, never proof that no better layout exists."""
 rows=[]
 for fi,halls in enumerate(p['halls_by_floor']):
  doors=p['opening_model_009'][fi]['doors']
  for i,hall in enumerate(halls):
   served=[d['connects'][1] for d in doors if d['connects'][0]==f'hall-{fi}-{i}']
   q=copy.deepcopy(p);q['halls_by_floor'][fi].pop(i)
   trial=_opening_revision(brief,q);qa=validate(brief,trial)
   rows.append(dict(floor=fi,node=i,served_rooms=served,serves_only_one_room=len(served)==1,
                    deletion_valid=qa['status']=='PASS',deletion_failures=qa['issues'],
                    necessity='REMOVABLE_IN_CURRENT_LAYOUT' if qa['status']=='PASS' else 'REQUIRED_IN_CURRENT_LAYOUT',
                    global_necessity='UNRESOLVED'))
 return rows
