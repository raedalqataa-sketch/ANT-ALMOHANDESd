"""Experimental hosted openings and geometric body routes, no furnishings.

Lengths in metres. .90m doors/.60m body/.15m jambs are disclosed design
parameters, not newly asserted legal provisions. Daylight/airflow remain unresolved.
"""
import copy
import heapq
import math
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union

EPS=1e-6

def shape(r):return box(r['x'],r['y'],r['x']+r['width'],r['y']+r['depth'])

def shared_edge(a,b):
 boundary=shape(a).boundary.intersection(shape(b).boundary)
 if boundary.is_empty or boundary.length<EPS or boundary.geom_type!='LineString':return None
 (x,y),(xx,yy)=boundary.coords[0],boundary.coords[-1]
 axis='x' if abs(y-yy)<EPS else 'y'
 lo,hi=sorted((x,xx) if axis=='x' else (y,yy))
 return dict(axis=axis,fixed=y if axis=='x' else x,lo=lo,hi=hi,length=hi-lo)

def opening_fits(o,edge):
 if not edge or o.get('axis')!=edge['axis'] or not all(math.isfinite(v) for v in o['center']+[o['width']]) or o['width']<=0:return False
 a=0 if edge['axis']=='x' else 1
 return abs(o['center'][1-a]-edge['fixed'])<EPS and o['center'][a]-o['width']/2>=edge['lo']-EPS and o['center'][a]+o['width']/2<=edge['hi']+EPS

def accessible(doors,start,target,private):
 graph={}
 for d in doors:
  a,b=d['connects'];graph.setdefault(a,set()).add(b);graph.setdefault(b,set()).add(a)
 seen={start};todo=[start]
 while todo:
  a=todo.pop()
  for b in graph.get(a,()):
   if b in private and b!=target:continue
   if b not in seen:seen.add(b);todo.append(b)
 return target in seen

def shortest_path(region,start,end,body=.6):
 """Visibility graph in inward-offset free polygon; a centreline alone is not proof."""
 free=region.buffer(-body/2,join_style=2)
 if free.is_empty:return None
 s,e=Point(start),Point(end)
 parts=[free] if free.geom_type=='Polygon' else list(getattr(free,'geoms',[]))
 poly=next((p for p in parts if p.buffer(1e-7).covers(s) and p.buffer(1e-7).covers(e)),None)
 if poly is None:return None
 points=[tuple(start),tuple(end)]+list(poly.exterior.coords)[:-1]
 for hole in poly.interiors:points+=list(hole.coords)[:-1]
 cover=poly.buffer(1e-7);graph=[[] for _ in points]
 for i,p in enumerate(points):
  for j in range(i):
   if cover.covers(LineString([p,points[j]])):
    d=math.dist(p,points[j]);graph[i].append((j,d));graph[j].append((i,d))
 dist={0:0};prev={};q=[(0,0)]
 while q:
  cost,i=heapq.heappop(q)
  if cost!=dist[i]:continue
  if i==1:
   ids=[i]
   while ids[-1]!=0:ids.append(prev[ids[-1]])
   return dict(points=[points[k] for k in reversed(ids)],length_m=round(cost,4),body_width_m=body)
  for j,d in graph[i]:
   if cost+d<dist.get(j,math.inf):dist[j]=cost+d;prev[j]=i;heapq.heappush(q,(cost+d,j))
 return None

def exposed_edges(room,objects):
 """Subtract actual contacting rectangles, rather than trusting 'exterior' tags."""
 r=room;x,y,w,d=(r[k] for k in ('x','y','width','depth'))
 edges=[dict(axis='x',fixed=y,lo=x,hi=x+w),dict(axis='x',fixed=y+d,lo=x,hi=x+w),dict(axis='y',fixed=x,lo=y,hi=y+d),dict(axis='y',fixed=x+w,lo=y,hi=y+d)]
 result=[]
 for e in edges:
  pieces=[(e['lo'],e['hi'])]
  for other in objects:
   if other is room:continue
   shared=shared_edge(r,other)
   if not shared or shared['axis']!=e['axis'] or abs(shared['fixed']-e['fixed'])>EPS:continue
   nxt=[]
   for a,b in pieces:
    if shared['hi']<=a or shared['lo']>=b:nxt.append((a,b));continue
    if shared['lo']>a:nxt.append((a,shared['lo']))
    if shared['hi']<b:nxt.append((shared['hi'],b))
   pieces=nxt
  result.extend(dict(e,lo=a,hi=b,length=b-a) for a,b in pieces if b-a>EPS)
 return result

def centre(edge,width,fraction):
 v=edge['lo']+.15+width/2+fraction*(edge['length']-.3-width)
 return [v,edge['fixed']] if edge['axis']=='x' else [edge['fixed'],v]

def cut(o,t):
 x,y=o['center'];w=o['width'];return box(x-w/2,y-t,x+w/2,y+t) if o['axis']=='x' else box(x-t,y-w/2,x+t,y+w/2)

def inward(o,r,distance):
 p=list(o['center']);a=1 if o['axis']=='x' else 0
 mid=r['y']+r['depth']/2 if a else r['x']+r['width']/2
 p[a]+=distance*(1 if mid>p[a] else -1)
 return p

def swing(o,r,t):
 """A 90-degree leaf swept sector, inside the receiving room's clear net area."""
 a=0 if o['axis']=='x' else 1;hinge=inward(o,r,t/2+.001);hinge[a]-=o['width']/2
 mid=inward(o,r,t/2+.1);sign=1 if mid[1-a]>o['center'][1-a] else -1
 pts=[hinge]
 for i in range(19):
  angle=math.pi/2*i/18;p=list(hinge);p[a]+=o['width']*math.cos(angle);p[1-a]+=sign*o['width']*math.sin(angle);pts.append(p)
 from shapely.geometry import Polygon
 return Polygon(pts)

def window_clear(w,r,objects,t):
 if not all(math.isfinite(v) for v in (*w['center'],w['width'],w['height'],w['operable_fraction'])) or w['width']<=0 or w['height']<=0 or not 0<w['operable_fraction']<=1:return False
 inside=inward(w,r,t/2+.4);out=[2*w['center'][i]-inside[i] for i in (0,1)]
 a=0 if w['axis']=='x' else 1;normal=1-a;sign=1 if out[normal]>w['center'][normal] else -1
 lo=list(w['center']);hi=list(w['center']);lo[a]-=w['width']/2;hi[a]+=w['width']/2
 lo[normal]+=sign*(t/2+.01);hi[normal]=out[normal]
 probe=box(min(lo[0],hi[0]),min(lo[1],hi[1]),max(lo[0],hi[0]),max(lo[1],hi[1]))
 if any(probe.intersection(shape(q).buffer(t/2,join_style=2)).area>EPS for q in objects if q['id']!=r['id']):return False
 return True

def construct(brief,proposal,fraction=.5):
 """Build new opening decisions on a copy; never change rooms or stairs."""
 p=copy.deepcopy(proposal);floors=[];t=brief.wall_thickness
 p.pop('validation_009',None);p.pop('repair_history_009',None);p.pop('relocations_009',None)
 for fi,(rooms,halls) in enumerate(zip(p['rooms_by_floor'],p['halls_by_floor'])):
  hs=[dict(h,id=f'hall-{fi}-{i}') for i,h in enumerate(halls)]
  objects=rooms+hs;doors=[];windows=[];errors=[]
  for r in rooms:
   if r.get('guest_distributor'):continue
   hosts=([v for v in rooms if v.get('guest_distributor')] if r.get('zone')=='guest' else hs)
   edges=[(h,shared_edge(r,h)) for h in hosts];edges=[(h,e) for h,e in edges if e and e['length']>=1.2-EPS]
   if not edges:errors.append('NO_DOOR_HOST:'+r['id']);continue
   h,e=max(edges,key=lambda v:v[1]['length']);o=dict(id=f'door-{fi}-{len(doors)}',kind='door',axis=e['axis'],center=centre(e,.9,fraction),width=.9,connects=[h['id'],r['id']],receiving_room=r['id'])
   doors.append(o)
  if fi==0:
   for label,targets in [('family-entry',[h for h in hs if halls[int(h['id'].split('-')[-1])].get('id')=='family-entry-spur']),('guest-entry',[r for r in rooms if r.get('guest_distributor')])]:
    if not targets:errors.append('MISSING_ENTRY_TARGET:'+label);continue
    target=targets[0];edges=exposed_edges(target,objects)
    if label=='family-entry':
     a='x' if brief.entrance_face in ('south','north') else 'y'
     fixed=(target['y'] if brief.entrance_face=='south' else target['y']+target['depth'] if brief.entrance_face=='north' else target['x']+target['width'] if brief.entrance_face=='east' else target['x'])
     edges=[e for e in edges if e['axis']==a and abs(e['fixed']-fixed)<EPS]
    edges=[e for e in edges if e['length']>=1.3-EPS]
    if not edges:errors.append('NO_EXTERIOR_ENTRY_EDGE:'+label);continue
    e=max(edges,key=lambda v:v['length']);doors.append(dict(id=label,kind='door',axis=e['axis'],center=centre(e,1.,fraction),width=1.,connects=['OUTSIDE',target['id']],receiving_room=target['id']))
  for r in rooms:
   if r['kind'] not in ('bedroom','master','kitchen','bathroom'):continue
   choices=[]
   for e in exposed_edges(r,objects):
    if e['length']<1.1:continue
    o=dict(id=f'window-{fi}-{len(windows)}',kind='window',axis=e['axis'],center=centre(e,.8,fraction),width=.8,height=1.2,operable_fraction=.5,room_id=r['id'])
    if any(cut(o,.2).intersects(cut(d,.2)) for d in doors) or not window_clear(o,r,objects,t):continue
    choices.append((e['length'],o))
   if choices:windows.append(max(choices,key=lambda v:v[0])[1])
   else:errors.append('NO_WINDOW_INTERVAL:'+r['id'])
  floors.append(dict(index=fi,rooms=rooms,halls=hs,doors=doors,windows=windows,construction_errors=errors))
 p['opening_model_009']=floors
 return p

def validate(brief,p):
 """Rebuild evidence from coordinates/hosts; never trust stored status flags."""
 from .free_layout_audit import audit_preliminary_concept
 audit=audit_preliminary_concept(brief,p);issues=list(audit['issues']);evidence=[];t=brief.wall_thickness
 model=p.get('opening_model_009')
 if not model or len(model)!=brief.floors:return dict(status='FAIL',issues=['MISSING_ACTUAL_OPENINGS'],floors=[],legal='UNRESOLVED')
 for fi,f in enumerate(model):
  rooms=p['rooms_by_floor'][fi];halls=[dict(h,id=f'hall-{fi}-{i}') for i,h in enumerate(p['halls_by_floor'][fi])];objects=rooms+halls;ids={r['id']:r for r in objects}
  doors=f['doors'];valid=[];routes=[];windows=[]
  for o in doors:
   a,b=o['connects'];r=ids.get(b);other=ids.get(a)
   if r is None:issues.append('BAD_DOOR_TARGET');continue
   edges=exposed_edges(r,objects) if a=='OUTSIDE' else [shared_edge(r,other)] if other else []
   if o['width']<.9-EPS or not any(opening_fits(o,e) for e in edges):issues.append('INVALID_DOOR_HOST:'+o['id']);continue
   if not shape(r).buffer(-t/2).buffer(.003).covers(swing(o,r,t)):
    issues.append('DOOR_SWEEP_OUTSIDE_NET_ROOM:'+o['id']);continue
   # Family doors must never create a shortcut across a private room.
   if a!='OUTSIDE' and not (other['kind']=='corridor' and (bool(other.get('guest_distributor'))==(r.get('zone')=='guest'))):
    issues.append('PRIVATE_OR_MIXED_TRANSIT:'+o['id']);continue
   valid.append(o)
  for i,a in enumerate(valid):
   for b in valid[i+1:]:
    if cut(a,t/2).intersection(cut(b,t/2)).area>EPS or swing(a,ids[a['receiving_room']],t).intersection(swing(b,ids[b['receiving_room']],t)).area>EPS:
     issues.append('DOOR_OPENING_OR_SWEEP_COLLISION:'+a['id']+':'+b['id'])
  guest_ids={r['id'] for r in rooms if r.get('zone')=='guest'}
  # Gross hall union eroded as one shape avoids fictitious internal hall walls.
  family_halls=unary_union([shape(h) for h in halls]).buffer(-t/2,join_style=2)
  if fi==0:
   entry=next((d for d in valid if d['id']=='family-entry'),None)
   start=inward(entry,ids[entry['connects'][1]],.6) if entry else None
   if not entry:issues.append('NO_VALID_FAMILY_ENTRY')
  else:
   stair=next((r for r in rooms if r['kind']=='stair'),None)
   sd=next((d for d in valid if stair and stair['id'] in d['connects']),None)
   host=ids.get(sd['connects'][0]) if sd else None
   start=inward(sd,host,.6) if host else None
  for r in rooms:
   if r.get('guest_distributor'):continue
   door=next((d for d in valid if r['id'] in d['connects']),None)
   if door is None:issues.append('ROOM_WITHOUT_VALID_DOOR:'+r['id']);continue
   if r['id'] in guest_ids:
    ge=next((d for d in valid if d['id']=='guest-entry'),None);v=ids[door['connects'][0]]
    region=shape(v).buffer(-t/2).union(shape(r).buffer(-t/2)).union(cut(door,t))
    origin=inward(ge,v,.6) if ge else None
   else:
    region=family_halls.union(shape(r).buffer(-t/2)).union(cut(door,t));origin=start
   target=inward(door,r,.65)
   route=shortest_path(region,origin,target) if origin else None
   if not route:issues.append('NO_BODY_ROUTE:'+r['id'])
   else:routes.append(dict(room_id=r['id'],guest=r['id'] in guest_ids,**route))
  if fi==0:
   ge=next((d for d in valid if d['id']=='guest-entry'),None)
   if not ge:issues.append('NO_VALID_GUEST_ENTRY')
   # Audit guest graph from the vestibule, not merged OUTSIDE entry nodes.
   v=next((r for r in rooms if r.get('guest_distributor')),None)
   internal=[d for d in valid if 'OUTSIDE' not in d['connects']]
   if v and any(accessible(internal,v['id'],r['id'],set()) for r in rooms if r.get('zone')!='guest' and not r.get('guest_distributor')):issues.append('GUEST_FAMILY_GRAPH_LEAK')
   # Geometric outdoor route inside the plot, around actual occupied footprint.
   W=brief.plot_width;D=brief.plot_depth;ox=brief.setbacks.west+t/2;oy=brief.setbacks.south+t/2
   outdoor=box(-ox,-oy,W-ox,D-oy).difference(unary_union([shape(r) for r in objects]).buffer(t/2,join_style=2))
   for entry_id in ('guest-entry','family-entry'):
    entry=next((d for d in valid if d['id']==entry_id),None)
    if entry is None:continue
    receiving=ids[entry['connects'][1]];inside=inward(entry,receiving,.65)
    out=[2*entry['center'][i]-inside[i] for i in (0,1)]
    face=brief.entrance_face
    street=([out[0],-oy+.4] if face=='south' else [out[0],D-oy-.4] if face=='north' else [W-ox-.4,out[1]] if face=='east' else [-ox+.4,out[1]])
    ext=shortest_path(outdoor,street,out)
    if not ext:issues.append('NO_OUTDOOR_APPROACH:'+entry_id)
    else:routes.append(dict(room_id=entry_id+'-EXTERIOR',guest=entry_id=='guest-entry',**ext))
  for r in rooms:
   if r['kind'] not in ('bedroom','master','kitchen','bathroom'):continue
   found=[]
   for w in f['windows']:
    if w['room_id']!=r['id']:continue
    es=exposed_edges(r,objects)
    if not all(math.isfinite(v) for v in (w['height'],w['operable_fraction'])) or not any(opening_fits(w,e) for e in es) or w['width']<=0 or w['height']<=0 or not 0<w['operable_fraction']<=1:continue
    if any(cut(w,.2).intersects(cut(d,.2)) for d in doors):continue
    if not window_clear(w,r,objects,t):continue
    found.append(w['id'])
   windows.append(dict(room_id=r['id'],status='PASS' if found else 'FAIL',windows=found))
   if not found:issues.append('NO_VERIFIED_EXTERIOR_WINDOW:'+r['id'])
  evidence.append(dict(floor=fi,valid_doors=len(valid),routes=routes,windows=windows))
 return dict(status='PASS' if not issues else 'FAIL',issues=issues,floors=evidence,legal='UNRESOLVED',daylight_airflow='UNRESOLVED',visual_privacy='UNRESOLVED',furniture_used=False,body_width_m=.6,door_width_design_m=.9)

def _opening_revision(brief,proposal):
 """Bounded placement corrections only; best failure retained, source immutable."""
 trials=[];best=None
 for fraction in (.5,.25,.75,0.,1.):
  p=construct(brief,proposal,fraction);report=validate(brief,p)
  trials.append(dict(fraction=fraction,status=report['status'],issues=report['issues']))
  if best is None or len(report['issues'])<len(best[1]['issues']):best=p,report
  if report['status']=='PASS':break
 best[0]['validation_009']=best[1];best[0]['repair_history_009']=trials
 return best[0]


def revise(brief,proposal):
 """Strictly improving bounded room moves; fixed stair and original immutable."""
 from .free_layout_audit import audit_preliminary_concept
 t=brief.wall_thickness
 best=_opening_revision(brief,proposal);history=[]
 for round_index in range(10):
  failures=best['validation_009']['issues']
  targets={v.split(':',1)[1] for v in failures if isinstance(v,str) and ':' in v}
  improved=False
  for fi,rooms in enumerate(best['rooms_by_floor']):
   for ri,r in enumerate(rooms):
    if r['id'] not in targets or r['kind']=='stair' or r.get('guest_distributor'):continue
    for shift in (.25,-.25,.5,-.5,.75,-.75,1.,-1.,1.5,-1.5,2.,-2.):
     for axis in ('x','y'):
      candidate=copy.deepcopy(best);candidate['rooms_by_floor'][fi][ri][axis]+=shift
      if audit_preliminary_concept(brief,candidate)['status']!='PRELIMINARY_CONSISTENT':continue
      trial=_opening_revision(brief,candidate)
      if len(trial['validation_009']['issues'])>=len(best['validation_009']['issues']):continue
      history.append(dict(round=round_index,room=r['id'],axis=axis,delta_m=shift,
                          before=len(best['validation_009']['issues']),after=len(trial['validation_009']['issues'])))
      best=trial;improved=True;break
     if improved:break
    if improved:break
   if improved:break
  if not improved:
   for fi,rooms in enumerate(best['rooms_by_floor']):
    for ri,r in enumerate(rooms):
     if r['id'] not in targets or r.get('zone')=='guest' or not r.get('request_id'):continue
     candidates=[]
     rotated=copy.deepcopy(best);rr=rotated['rooms_by_floor'][fi][ri];rr['width'],rr['depth']=rr['depth'],rr['width'];candidates.append((rotated,'rotate',r['id']))
     for j,other in enumerate(rooms):
      if j==ri or not other.get('request_id') or other.get('zone')=='guest':continue
      trial=copy.deepcopy(best);first=trial['rooms_by_floor'][fi][ri];second=trial['rooms_by_floor'][fi][j]
      for key in ('x','y','width','depth'):first[key],second[key]=second[key],first[key]
      candidates.append((trial,'swap',other['id']))
     # Re-shape an adjacent predecessor instead of dropping a required room.
     for j,other in enumerate(rooms):
      if not other.get('request_id') or other.get('zone')=='guest' or j==ri:continue
      if abs(other['y']+other['depth']-r['y'])>EPS:continue
      for shift in (.25,.5):
       nd=other['depth']-shift
       if nd-t<other['min_side']:continue
       nw=max(other['width'],other['min_area']/(nd-t)+t)
       for west in (False,True):
        trial=copy.deepcopy(best);first=trial['rooms_by_floor'][fi][j];second=trial['rooms_by_floor'][fi][ri]
        first['depth']=nd;first['width']=nw
        if west:first['x']-=nw-other['width']
        second['y']-=shift
        candidates.append((trial,'reshape_shared_boundary',other['id']))
     from .free_layout_solver import anchors
     seen=set()
     for hall in best['halls_by_floor'][fi]:
      for width,depth in ((r['width'],r['depth']),(r['depth'],r['width'])):
       for seed in range(4):
        for position in anchors(hall,width,depth,seed):
         key=tuple(position[k] for k in ('x','y','width','depth'))
         if key in seen:continue
         seen.add(key);trial=copy.deepcopy(best)
         trial['rooms_by_floor'][fi][ri].update({k:position[k] for k in ('x','y','width','depth')})
         candidates.append((trial,'reattach_to_hall',hall.get('id','hall')))
     for candidate,operation,other_id in candidates:
      if audit_preliminary_concept(brief,candidate)['status']!='PRELIMINARY_CONSISTENT':continue
      trial=_opening_revision(brief,candidate)
      if len(trial['validation_009']['issues'])>=len(best['validation_009']['issues']):continue
      history.append(dict(round=round_index,room=r['id'],operation=operation,other=other_id,before=len(best['validation_009']['issues']),after=len(trial['validation_009']['issues'])))
      best=trial;improved=True;break
     if improved:break
    if improved:break
  if not improved or best['validation_009']['status']=='PASS':break
 best['relocations_009']=history
 return best
