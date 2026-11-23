"""Bounded graph-guided branch reattachment around existing polygon core seeds.

Existing core/stair geometry is reused. Activity branches, host selection,
orientation and unpinned private rooms are actual search decisions. This is a
finite constructive search, never a proof of site infeasibility.
"""
import copy,math
from collections import defaultdict,deque,Counter
from shapely.geometry import box,Point,LineString
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
from .geometry import entity,shape,net_shape,axial_edges,shared_edges,exposed_edges,sized,chamfer
from .relational import compile_program,SCHEMA,positional_signature,geometric_relation_issues,attachment_signature


def _seed(brief,graph):
 from .clustered import _compose
 if not graph['groups']:return _private_seed(brief,graph)
 needed=set()
 for kind in ('living','dining','kitchen'):
  rs=[r for r in graph['requests'] if r['kind']==kind]
  if not rs:raise ValueError('MISSING_SEED_ACTIVITY:'+kind)
  needed.add(rs[0]['request_id'])
 private_store=next((r for r in graph['requests'] if r['kind']=='storage' and not r.get('guest_entries')),None)
 if private_store:needed.add(private_store['request_id'])
 for index,group in enumerate(graph['groups'][:2]):
  needed.update(r['request_id'] for r in group[1][:2 if index==0 else 1])
  wc=next((r for r in group[2] if len(r['guest_entries'])==1),None)
  if wc:needed.add(wc['request_id'])
 rooms=[r.model_copy(update={'count':1}) for r in brief.rooms if r.id in needed]
 groups=[]
 for group in brief.guest_groups:
  if (group.entry or group.id) not in {g[0] for g in graph['groups'][:2]}:continue
  owned=[rid for rid in group.rooms if rid in needed]
  if owned:groups.append(group.model_copy(update={'rooms':owned}))
 raw=brief.model_dump();raw.update(rooms=[r.model_dump() for r in rooms],guest_groups=[g.model_dump() for g in groups],spatial_requirements=[])
 from backend.design.general_models import VillaBrief
 seed=_compose(VillaBrief.model_validate(raw),1 if brief.compact_core else 0)
 expected={r['id']:r for r in graph['requests']}
 for r in seed['rooms_by_floor'][0]:
  if r['id'] in expected:r.update(copy.deepcopy(expected[r['id']]))
 seed.update(schema=SCHEMA,strategy='relational',composition_profile='relational-search',brief_snapshot=brief.model_dump(mode='json'))
 # Entry aliases are authoritative to the full graph, not inferred from location.
 for e in seed['entries']:e['guest_entry']=graph['entries'][e['node']]
 for node in seed['halls_by_floor'][0]:
  if node['id']=='family-foyer':node['name']='مدخل الأسرة والضيافة' if len(graph['groups'])>1 else 'مدخل الأسرة'
  node['guest_entry']=graph['entries'].get(node['id'])
 seed['assumptions']=['Ground-floor conceptual composition. Core seed reused; activity branches and extra rooms are search decisions.',
  'Guest memberships follow the brief. Family and the secondary guest group share a controlled vestibule under the current reference-compatible entry policy.',
  'Structure, headroom, legal/daylight performance, parking and upper floors remain unresolved.']
 return seed


def _private_seed(brief,graph):
 from .stairs import make_stair
 t=brief.wall_thickness;by={}
 for r in graph['requests']:by.setdefault(r['kind'],[]).append(r)
 if any(not by.get(k) for k in ('living','dining','kitchen')):raise ValueError('MISSING_SEED_ACTIVITY:living-dining-kitchen')
 rooms=[];nodes=[];links=[];F=3.;fw=max(2.5,brief.corridor_width+.3);sw=fw+1.3;cut=.65
 def put(req,poly):
  r=entity(req['id'],req['kind'],poly,**{k:v for k,v in req.items() if k not in ('id','kind')});rooms.append(r);return r
 def node(rid,poly,name):
  r=entity(rid,'corridor',poly,name=name,zone='family',movement_node=True);nodes.append(r);return r
 def link(a,b,controlled=False):links.append(dict(a=a['id'],b=b['id'],roles=['family'],controlled=controlled))
 main=node('main-foyer',box(0,0,fw,F),'بهو المدخل')
 req=by['living'][0];w,d=sized(req,t,corners=('sw','se','ne'),cut=cut);living=put(req,chamfer(sw,F,w,d,('sw','se','ne'),cut))
 corner=box(sw,F,sw+cut,F+cut).difference(shape(living))
 core=node('social-node',box(fw,0,sw+cut+1.2,F).union(corner),'موزع الأسرة');link(main,core);link(core,living,True)
 stair=make_stair(brief,0,F,sw,'u-shaped' if brief.compact_core else 'semicircular');rooms.append(stair);link(core,stair,True)
 req=by['dining'][0];dw,dd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2));dy=F-1.4;dining=put(req,chamfer(-dw,dy,dw,dd));link(main,dining)
 req=by['kitchen'][0];kw,kd=sized(req,t,fixed_depth=max(req['min_side']+t,4.2));kitchen=put(req,chamfer(-kw,dy+dd,kw,kd));link(dining,kitchen)
 if by.get('storage'):
  req=by['storage'][0];pw,pd=sized(req,t,fixed_depth=3.6);store=put(req,chamfer(-kw-pw,dy+dd,pw,pd));link(kitchen,store)
 family=node('family-foyer',box(sw+w-cut,F+2.4,sw+w+2.5,F+d+1.5).difference(shape(living)),'مدخل الأسرة');link(family,living,True)
 objects=rooms+nodes;angle={'south':0,'east':90,'north':180,'west':270}[brief.entrance_face]
 polygons=[rotate(shape(r),angle,origin=(0,0)) for r in objects];x,y,xx,yy=unary_union(polygons).bounds
 W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-t;D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-t
 if xx-x>W or yy-y>D:raise ValueError('PRIVATE_SEED_EXCEEDS_ENVELOPE')
 dx=(W-xx+x)/2-x;dy=(D-yy+y)/2-y;theta=math.radians(angle)
 for r,g in zip(objects,polygons):
  if r.get('stair'):r['stair']['rotation_deg']=angle
  for arc in r.get('arcs',[]):
   a,b=arc['center'];arc['center']=[a*math.cos(theta)-b*math.sin(theta)+dx,a*math.sin(theta)+b*math.cos(theta)+dy];arc['start_angle']+=angle;arc['end_angle']+=angle
  r.update(_entity_move(r,translate(g,dx,dy)))
 return dict(schema=SCHEMA,strategy='relational',rooms_by_floor=[rooms],halls_by_floor=[nodes],entries=[dict(node=n,guest_entry=e) for n,e in graph['entries'].items()],connection_requirements=links,brief_snapshot=brief.model_dump(mode='json'),assumptions=['Ground-floor conceptual plan; structure, code, daylight performance, parking and vertical design unresolved.'])


def _entity_move(r,poly):
 meta={k:copy.deepcopy(v) for k,v in r.items() if k not in ('id','kind','polygon','x','y','width','depth')}
 return entity(r['id'],r['kind'],poly,**meta)


def _tasks(seed,graph):
 ids={r['id']:r for r in seed['rooms_by_floor'][0]+seed['halls_by_floor'][0]};tasks=[];assigned=set()
 living=next(r for r in seed['rooms_by_floor'][0] if r['kind']=='living')
 tasks.append(dict(root=living['id'],rows=[living,ids['family-foyer']],hosts=['social-node'],controlled=True,roles=['family']))
 assigned|={living['id'],'family-foyer'}
 dining=next(r for r in seed['rooms_by_floor'][0] if r['kind']=='dining');chain=[dining]
 kitchen=next(r for r in seed['rooms_by_floor'][0] if r['kind']=='kitchen');chain.append(kitchen)
 chain.extend(r for r in seed['rooms_by_floor'][0] if r['kind']=='storage' and not r.get('guest_entries'))
 tasks.append(dict(root=dining['id'],rows=chain,hosts=['main-foyer','social-node']))
 assigned|={r['id'] for r in chain}
 for r in seed['rooms_by_floor'][0]:
  if r['id'] in assigned or r['kind']=='stair':continue
  hosts=graph['hosts'].get(r['id'],['family-foyer'])
  if r['kind']=='bathroom' and graph['groups'] and r.get('guest_entries')==[graph['groups'][0][0]]:hosts=hosts+['social-node']
  tasks.append(dict(root=r['id'],rows=[r],hosts=hosts));assigned.add(r['id'])
 # Explicitly compile every extra requested instance. No absent room can vanish.
 present=set(ids)
 private_extra=[r for r in graph['requests'] if r['id'] not in present and not r.get('guest_entries') and r['kind'] not in ('storage','kitchen')]
 family_hosts=['family-foyer',living['id']]
 if len(private_extra)>=3:
  hub=entity('family-distributor-1','corridor',box(0,0,2.5,3),name='موزع أسرة',zone='family',movement_node=True)
  tasks.insert(1,dict(root=hub['id'],rows=[hub],hosts=[living['id']],controlled=True,roles=['family']))
  family_hosts.insert(1,hub['id'])
 for node,entry in graph['entries'].items():
  if node in ids:continue
  h=entity(node,'corridor',box(0,0,2.5,3),name='بهو ضيافة مستقل',zone='shared',movement_node=True,guest_entry=entry)
  tasks.insert(1,dict(root=node,rows=[h],hosts=[living['id'],'family-foyer'],controlled=True,roles=['family']))
 for r in graph['requests']:
  if r['id'] in present:continue
  hosts=graph['hosts'].get(r['id'])
  if hosts is None:
   if r['id'] in graph['access_hosts']:hosts=graph['access_hosts'][r['id']]
   elif r['kind']=='storage':hosts=[kitchen['id'],'family-foyer']
   else:hosts=family_hosts
  tasks.append(dict(root=r['id'],request=r,rows=None,hosts=hosts))
 removed={r['id'] for task in tasks for r in task.get('rows') or []}
 fixed=[r for r in ids.values() if r['id'] not in removed]
 return tasks,fixed


def _options(task,t):
 if task['rows'] is not None:return [task['rows']]
 req=task['request'];result=[]
 corners=('sw','se','ne','nw') if req['kind'] in ('majlis','living','bedroom','master','office') else ()
 for extra in (0.,.4):
  w,d=sized(req,t,fixed_depth=max(req['min_side']+t,math.sqrt(req['min_area'])+t)+extra,corners=corners,cut=.35)
  row=entity(req['id'],req['kind'],chamfer(0,0,w,d,corners,.35),**{k:v for k,v in req.items() if k not in ('id','kind')})
  result.append([row])
 return result


def _placements(task,objects,t,W,D):
 ids={r['id']:r for r in objects};obstacles=[shape(r) for r in objects];bounds=box(0,0,W,D);seen=set()
 for rows in _options(task,t):
  for angle in (0,90,180,270):
   polygons=[rotate(shape(r),angle,origin=(0,0)) for r in rows]
   root=next(poly for r,poly in zip(rows,polygons) if r['id']==task['root'])
   for host_id in task['hosts']:
    if host_id not in ids:continue
    host=ids[host_id]
    for h in exposed_edges(host,objects):
     if h['length']<1.2-1e-6:continue
     for edge in axial_edges(root):
      if edge['axis']!=h['axis'] or edge['length']<1.2-1e-6:continue
      a=0 if h['axis']=='x' else 1;normal=1-a
      shifts=[h['lo']-edge['lo'],h['hi']-edge['hi'],(h['lo']+h['hi']-edge['lo']-edge['hi'])/2,h['lo']+1.2-edge['hi'],h['hi']-1.2-edge['lo']]
      for parallel in shifts:
       delta=[0.,0.];delta[a]=parallel;delta[normal]=h['fixed']-edge['fixed']
       key=(angle,host_id,round(delta[0],7),round(delta[1],7),round(root.area,7))
       if key in seen:continue
       seen.add(key)
       placed=[translate(poly,*delta) for poly in polygons]
       if any(not bounds.buffer(1e-7).covers(g) for g in placed):continue
       if any(g.intersection(obstacle).area>1e-6 for g in placed for obstacle in obstacles):continue
       out=[_entity_move(r,g) for r,g in zip(rows,placed)];rootrow=next(r for r in out if r['id']==task['root'])
       # A shared-service room requires independent real contacts to all foyers.
       actual_hosts=task['hosts'] if task.get('request',{}).get('guest_entries') else [host_id]
       if len(actual_hosts)>1 and task.get('request',{}).get('guest_entries'):
        if any(k not in ids or max((e['length'] for e in shared_edges(rootrow,ids[k])),default=0)<1.2-1e-6 for k in actual_hosts):continue
       elif max((e['length'] for e in shared_edges(rootrow,host)),default=0)<1.2-1e-6:continue
       probe=[(h['lo']+h['hi'])/2,h['fixed']] if h['axis']=='x' else [h['fixed'],(h['lo']+h['hi'])/2]
       normal_axis=1 if h['axis']=='x' else 0;probe[normal_axis]+=.001
       outward=-1 if shape(host).covers(Point(probe)) else 1
       side=('N' if outward>0 else 'S') if h['axis']=='x' else ('E' if outward>0 else 'W')
       yield out,actual_hosts,dict(root=task['root'],host=host_id,side=side,rotation=angle,activities=sum(bool(r.get('request_id')) for r in rows))


def _exposed_entries(objects,entries,mass=None,geometries=None):
 # Inspect the occupied boundary once, instead of rebuilding every room pair
 # for every facade edge. This is a necessary partial check, not acceptance.
 geometries=geometries or [shape(r) for r in objects]
 mass=mass if mass is not None else unary_union(geometries)
 boundary=mass.boundary
 for r,g in zip(objects,geometries):
  needed=1.3 if r['id'] in entries else .8 if r.get('request_id') and r['kind']!='storage' else 0
  if not needed:continue
  exposed=g.boundary.intersection(boundary)
  lines=[exposed] if exposed.geom_type=='LineString' else list(getattr(exposed,'geoms',[]));lengths=[]
  for line in lines:
   if line.geom_type!='LineString':continue
   coords=list(line.coords)
   for a,b in zip(coords,coords[1:]):
    if abs(a[0]-b[0])<1e-6 or abs(a[1]-b[1])<1e-6:lengths.append(math.dist(a,b))
  # A total smaller than the required opening cannot ever provide a host.
  # Fragmented longer exposure is retained for the unchanged final host check.
  if sum(lengths)<needed-1e-6:return False
 return True


def _entry_reserve(brief,objects,entries,mass=None):
 """Necessary continuous outdoor body-access reservation before beam pruning.

 All possible hosted entry centres are considered as a segment, not a few
 sampled doors. Adding occupied rooms cannot restore a lost outdoor component.
 Final door sweeps and actual routes still use unchanged 009.
 """
 t=brief.wall_thickness;ox=brief.setbacks.west+t/2;oy=brief.setbacks.south+t/2
 mass=mass if mass is not None else unary_union([shape(r) for r in objects])
 free=box(-ox,-oy,brief.plot_width-ox,brief.plot_depth-oy).difference(mass.buffer(t/2,join_style=2)).buffer(-.3,join_style=2)
 if free.is_empty:return False
 face=brief.entrance_face;W=brief.plot_width;D=brief.plot_depth
 street=LineString([(-ox+.3,-oy+.4),(W-ox-.3,-oy+.4)]) if face=='south' else LineString([(-ox+.3,D-oy-.4),(W-ox-.3,D-oy-.4)]) if face=='north' else LineString([(W-ox-.4,-oy+.3),(W-ox-.4,D-oy-.3)]) if face=='east' else LineString([(-ox+.4,-oy+.3),(-ox+.4,D-oy-.3)])
 parts=[free] if free.geom_type=='Polygon' else list(getattr(free,'geoms',[]));accessible=unary_union([part for part in parts if part.intersects(street)]).buffer(1e-7)
 ids={r['id']:r for r in objects}
 for node in entries:
  if node not in ids:continue
  r=ids[node];found=False
  for edge in exposed_edges(r,objects):
   if edge['length']<1.3-1e-6:continue
   axis=0 if edge['axis']=='x' else 1;normal=1-axis;mid=r['y']+r['depth']/2 if normal else r['x']+r['width']/2
   outside=edge['fixed']+(.65 if mid<edge['fixed'] else -.65)
   a=[0.,0.];b=[0.,0.];a[axis]=edge['lo']+.65;b[axis]=edge['hi']-.65;a[normal]=b[normal]=outside
   candidate=Point(a) if math.dist(a,b)<1e-7 else LineString([a,b])
   if accessible.intersects(candidate):found=True;break
  if not found:return False
 return True


def _movement_feasible(objects):
 from assl.layout_critic_010 import corridor_metrics,DEFAULTS
 return corridor_metrics([r for r in objects if r['kind']=='corridor'])['longest_run_m']<=DEFAULTS['long_run_m']


def _entry_witness(brief,objects,entries):
 from assl.openings_009 import choose_guest_entry,_outdoor_region
 ids={r['id']:r for r in objects};outdoor=_outdoor_region(brief,objects)
 return all(node in ids and choose_guest_entry(brief,ids[node],exposed_edges(ids[node],objects),objects,[],outdoor=outdoor) is not None for node in entries)


def _retain(states,limit):
 # Preserve distinct private-wing placements before cheap public-room prefixes
 # consume the beam. Cost orders alternatives inside each placement.
 groups={};seen=set()
 for state in sorted(states,key=lambda s:s['score']):
  key=tuple((r['id'],tuple(tuple(p) for p in r['polygon'])) for r in sorted(state['objects'],key=lambda r:r['id']))
  if key in seen:continue
  seen.add(key);first=state['trace'][0];root=next(r for r in state['objects'] if r['id']==first['root'])
  placement=(first['root'],first['host'],first['side'],first['rotation'],round(root['x'],6),round(root['y'],6))
  topology=tuple((x['root'],x['host'],x['side']) for x in state['trace'])
  groups.setdefault(placement,{}).setdefault(topology,deque()).append(state)
 queues=deque(deque(group.values()) for group in groups.values());out=[]
 while queues and len(out)<limit:
  configurations=queues.popleft();q=configurations.popleft();out.append(q.popleft())
  if q:configurations.append(q)
  if configurations:queues.append(configurations)
 return out


def _candidate(seed,objects,links,trace):
 p=copy.deepcopy(seed);p['rooms_by_floor']=[[r for r in objects if r['kind']!='corridor']];p['halls_by_floor']=[[r for r in objects if r['kind']=='corridor']]
 p['connection_requirements']=links;p['relational_trace']=trace
 return p


def solve_relational(brief,*,max_results=3,beam_limit=48,max_checked=12,progress=None,on_candidate=None,on_frame=None,optimizer='ortools'):
 if optimizer not in ('ortools','python','local'):raise ValueError('UNKNOWN_RELATIONAL_OPTIMIZER:'+str(optimizer))
 if not 1<=max_results<=3 or not 1<=beam_limit<=48 or not 1<=max_checked<=12:raise ValueError('RELATIONAL_BUDGET_OUT_OF_RANGE')
 if progress:progress('composition',0,1,'تحليل برنامج العميل والعلاقات')
 try:graph=compile_program(brief)
 except ValueError as e:return dict(strategy='relational',status='NEEDS_INPUT',proposals=[],rejected=[],failures=[dict(reason=str(e))])
 if brief.floors!=1:return dict(strategy='relational',status='UNSUPPORTED',proposals=[],failures=[{'reason':'UNSUPPORTED_RELATIONAL_VERTICAL_COMPOSITION'}],rejected=[],program_graph=graph)
 try:seed=_seed(brief,graph)
 except ValueError as e:return dict(strategy='relational',status='UNRESOLVED',proposals=[],failures=[{'reason':str(e)}],rejected=[])
 if optimizer=='ortools':
  from .constraint_selection import require_ortools,select_beam
  require_ortools()
 elif optimizer=='local':
  from .constraint_selection import select_beam_local as select_beam
 tasks,fixed=_tasks(seed,graph);moved={task['root'] for task in tasks}
 links=[copy.deepcopy(link) for link in seed['connection_requirements'] if link['b'] not in moved]
 # The family foyer->living edge is internal to the moved branch and stays.
 living=next(r for r in seed['rooms_by_floor'][0] if r['kind']=='living')
 family_link=next(l for l in seed['connection_requirements'] if l['a']=='family-foyer' and l['b']==living['id'])
 links.append(copy.deepcopy(family_link))
 W=brief.plot_width-brief.setbacks.west-brief.setbacks.east-brief.wall_thickness;D=brief.plot_depth-brief.setbacks.north-brief.setbacks.south-brief.wall_thickness
 states=[dict(objects=fixed,links=links,trace=[],score=0.)];stats=dict(beam_limit=beam_limit,checked=0,placements=0,stages=[],max_checked=max_checked,entry_reservation_rejected=0,corridor_reservation_rejected=0,final_rejections={},optimizer=dict(requested=optimizer,backend={'ortools':'ortools-cp-sat','python':'bounded-python','local':'local-exact'}[optimizer],stages=[],architectural_optimality_proven=False))
 from .preview import emit_preview
 emit_preview(on_frame,fixed,'composition','النواة والمداخل قبل توزيع بقية الكتل')
 for task_index,task in enumerate(tasks):
  next_states=[]
  for state_index,state in enumerate(states):
   if progress:progress('composition',task_index+state_index/len(states),len(tasks),'توزيع الكتل: '+task['root'])
   for rows,hosts,decision in _placements(task,state['objects'],brief.wall_thickness,W,D):
    stats['placements']+=1;objects=state['objects']+rows
    if any(r['kind']=='corridor' for r in rows) and not _movement_feasible(objects):
     stats['corridor_reservation_rejected']+=1;continue
    geometries=[shape(r) for r in objects];mass=unary_union(geometries)
    if not _exposed_entries(objects,graph['entries'],mass,geometries):continue
    if not _entry_reserve(brief,objects,graph['entries'],mass):
     stats['entry_reservation_rejected']+=1;continue
    if brief.spatial_requirements:
     pseudo=dict(rooms_by_floor=[[r for r in objects if r.get('request_id')]])
     if geometric_relation_issues(brief,pseudo,partial=True,compiled=graph):continue
    newlinks=state['links']+[dict(a=h,b=task['root'],**{k:task[k] for k in ('roles','controlled') if k in task}) for h in hosts]
    # Living hosts are real controlled family transitions, never guest transit.
    for link in newlinks[-len(hosts):]:
     if link['a']==living['id'] or task['root']==living['id']:link.update(roles=['family'],controlled=True)
    x,y,xx,yy=mass.bounds
    score=(xx-x)*(yy-y)-mass.area
    next_states.append(dict(objects=objects,links=newlinks,trace=state['trace']+[decision],score=score))
  states=_retain(next_states,beam_limit)
  if optimizer in ('ortools','local') and next_states:
   states,report=select_beam(next_states,states,limit=beam_limit);states=_retain(states,beam_limit)
   stats['optimizer']['stages'].append(dict(root=task['root'],**report))
  stats['stages'].append(dict(root=task['root'],hosts=task['hosts'],survivors=len(states),feasible=len(next_states)))
  if states:emit_preview(on_frame,states[0]['objects'],'composition','تجربة تموضع '+next(r.get('name','فراغ') for r in states[0]['objects'] if r['id']==task['root']))
  if not states:return dict(strategy='relational',status='UNRESOLVED',proposals=[],rejected=[],failures=[dict(reason='BOUNDED_SEARCH_CANNOT_PLACE:'+task['root'])],search=stats)
 if progress:progress('composition',1,1,'اكتمل البحث عن تكوينات أولية')
 from .openings import construct_clustered
 from .furnishing import furnish_clustered
 from assl.openings_009 import validate
 from assl.layout_critic_010 import critique
 accepted=[];rejected=[];signatures=set();attachments=set()
 # Interleave distinct position orders before spending full validation budget.
 for state in states:
  mass=unary_union([shape(r) for r in state['objects']])
  reason='DISCONNECTED_BUILDING_FOOTPRINT' if mass.geom_type!='Polygon' else 'UNPROGRAMMED_ENCLOSED_VOID' if mass.interiors else 'NO_HOSTED_OUTDOOR_ENTRY_WITNESS' if not _entry_witness(brief,state['objects'],graph['entries']) else None
  if reason:
   stats['final_rejections'][reason]=stats['final_rejections'].get(reason,0)+1;continue
  if stats['checked']>=max_checked or len(accepted)>=max_results:break
  p=_candidate(seed,state['objects'],state['links'],state['trace']);p['entries']=[dict(node=n,guest_entry=e) for n,e in graph['entries'].items()]
  signature=positional_signature(p)
  attachment=attachment_signature(p)
  if attachment is None or signature in signatures or attachment in attachments:continue
  stats['checked']+=1
  index=stats['checked']-1
  if progress:progress('checking',index,max_checked,'إنشاء الأبواب والنوافذ للمقترح '+str(index+1))
  p=construct_clustered(brief,p)
  emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'openings','إنشاء الأبواب والنوافذ',p['opening_model_009'])
  if progress:progress('checking',index+.25,max_checked,'توزيع الأثاث والتحقق من استعمال الفراغات')
  p=furnish_clustered(brief,p)
  emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'furnishing','تجربة توزيع الأثاث',p['opening_model_009'],p['furniture_by_floor'])
  emit_preview(on_frame,p['rooms_by_floor'][0]+p['halls_by_floor'][0],'checking','التحقق من الحركة والخصوصية',p['opening_model_009'],p['furniture_by_floor'])
  if progress:progress('checking',index+.5,max_checked,'فحص الاتصال والخصوصية والأبواب 009')
  p['validation_009']=validate(brief,p)
  if progress:progress('checking',index+.75,max_checked,'فحص العلاقات ومسافات الحركة 010')
  p['quality_010']=critique(brief,p)
  if progress:progress('checking',index+1,max_checked,'اكتمل فحص المقترح '+str(index+1))
  p['id']='relational-'+str(stats['checked']);p['composition_profile']='relational-'+str(len(accepted)+1)
  if p['validation_009']['status']=='PASS' and p['quality_010']['status']=='ACCEPTABLE_DESIGN_INDICATORS':
   accepted.append(p);signatures.add(signature);attachments.add(attachment)
   if on_candidate:on_candidate(p)
  else:rejected.append(p)
 return dict(strategy='relational',status='CONCEPTS_READY_FOR_REVIEW' if accepted else 'UNRESOLVED',proposals=accepted,rejected=rejected,failures=[] if len(accepted)>=max_results else [dict(reason='INSUFFICIENT_VALID_DISTINCT_COMPOSITIONS',requested=max_results,accepted=len(accepted))],search=stats,program_graph=graph,supported_scope='Bounded ground-floor search with living/dining/kitchen; explicit guest memberships when councils are requested; counted private rooms and service access. No universal feasibility guarantee; independent family/secondary-guest vestibules, vertical composition, unstructured notes and regulatory extras unresolved.')
