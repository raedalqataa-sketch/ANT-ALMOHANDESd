"""Independent measured design critic. All limits are advisory, not law."""
import math
from shapely.geometry import LineString
from shapely.ops import unary_union
from .openings_009 import shape,shortest_path,inward,cut,validate,shared_edge

DEFAULTS=dict(long_run_m=6.,kitchen_dining_m=10.,bed_bath_m=12.,max_aspect=2.5,max_excess=1.5)

def corridor_metrics(halls, *, region=None):
 u=unary_union([shape(h) for h in halls]) if region is None else region
 longest=0.
 if u.is_empty:return dict(union_m2=0.,longest_run_m=0.)
 x,y,xx,yy=u.bounds
 # Continuous sections of dissolved geometry; splitting cells cannot alter runs.
 polys=[u] if u.geom_type=='Polygon' else list(u.geoms)
 xs=sorted({p[0] for poly in polys for p in poly.exterior.coords});ys=sorted({p[1] for poly in polys for p in poly.exterior.coords})
 for axis,levels in [('x',xs),('y',ys)]:
  for a,b in zip(levels,levels[1:]):
   v=(a+b)/2;line=LineString([(v,y-1),(v,yy+1)]) if axis=='x' else LineString([(x-1,v),(xx+1,v)])
   intersection=u.intersection(line);parts=list(intersection.geoms) if hasattr(intersection,'geoms') else [intersection]
   longest=max(longest,max((p.length for p in parts),default=0))
 return dict(union_m2=round(u.area,5),longest_run_m=round(longest,5))

def critique(brief,p,limits=None):
 if p.get('schema') in ('assl-clustered-1','assl-clustered-2','assl-relational-1'):
  from .strategies.validation import critique_clustered
  return critique_clustered(brief,p,limits)
 limits={**DEFAULTS,**(limits or {})};qa=validate(brief,p);defects=[];floors=[];t=brief.wall_thickness
 if qa['status']!='PASS':defects.append(dict(type='HARD_VALIDATION',evidence=qa['issues']))
 for fi,(rooms,halls,opened) in enumerate(zip(p['rooms_by_floor'],p['halls_by_floor'],p.get('opening_model_009',[]))):
  all_halls=halls+[r for r in rooms if r.get('guest_distributor')];m=corridor_metrics(all_halls);m['floor']=fi
  m['configuration_m2']=unary_union([shape(r) for r in rooms+halls]).area;m['movement_ratio']=m['union_m2']/m['configuration_m2']
  routes=qa['floors'][fi]['routes'] if len(qa['floors'])>fi else [];lengths=[r['length_m'] for r in routes if not r['room_id'].endswith('EXTERIOR')]
  m['mean_access_m']=sum(lengths)/len(lengths) if lengths else None
  m['max_access_m']=max(lengths,default=None);m['room_excess_m2']=sum(max(0,(r['width']-t)*(r['depth']-t)-r['min_area']) for r in rooms if r.get('request_id'))
  m['relationships']=[];family=unary_union([shape(h) for h in halls]).buffer(-t/2,join_style=2)
  for kind,target,limit in [('kitchen','dining',limits['kitchen_dining_m']),('dining','living',12.),('bedroom','bathroom',limits['bed_bath_m']),('master','bathroom',limits['bed_bath_m'])]:
   for room in [r for r in rooms if r['kind']==kind and r.get('zone')!='guest']:
    door=next((d for d in opened['doors'] if d['connects'][1]==room['id']),None);options=[]
    for other in [r for r in rooms if r['kind']==target and r.get('zone')!='guest']:
     od=next((d for d in opened['doors'] if d['connects'][1]==other['id']),None)
     if door and od:
      region=family.union(shape(room).buffer(-t/2)).union(shape(other).buffer(-t/2)).union(cut(door,t)).union(cut(od,t))
      route=shortest_path(region,inward(door,room,.65),inward(od,other,.65))
      if route:options.append((route['length_m'],other['id']))
    value=min(options) if options else (None,None)
    m['relationships'].append(dict(source=room['id'],target_kind=target,target=value[1],distance_m=value[0]))
    if value[0] is None or value[0]>limit:defects.append(dict(type='FUNCTIONAL_DISTANCE',floor=fi,room=room['id'],distance_m=value[0],limit_m=limit))
  if m['longest_run_m']>limits['long_run_m']:defects.append(dict(type='LONG_CORRIDOR',floor=fi,value=m['longest_run_m'],limit=limits['long_run_m']))
  m['unused_dead_branches']=[];m['door_node_distances']=[]
  for i,hall in enumerate(halls):
   hid=f'hall-{fi}-{i}';doors=[d for d in opened['doors'] if hid in d['connects']]
   degree=sum(shared_edge(hall,h) is not None for j,h in enumerate(halls) if j!=i)
   if not doors and degree==1:
    m['unused_dead_branches'].append(dict(index=i,area_m2=shape(hall).area))
    defects.append(dict(type='UNUSED_DEAD_BRANCH',floor=fi,index=i))
   for door in doors:
    route=shortest_path(family,(hall['x']+hall['width']/2,hall['y']+hall['depth']/2),inward(door,hall,.6))
    m['door_node_distances'].append(dict(door=door['id'],node=hid,distance_m=route['length_m'] if route else None))
  m['proportions']=[]
  for room in rooms:
   if not room.get('request_id'):continue
   w,d=room['width']-t,room['depth']-t;aspect=max(w,d)/min(w,d);excess=w*d/room['min_area'];m['proportions'].append(dict(id=room['id'],aspect=aspect,area_factor=excess))
   if aspect>limits['max_aspect'] or excess>limits['max_excess']:defects.append(dict(type='ROOM_PROPORTION_OR_EXCESS',floor=fi,room=room['id'],aspect=aspect,area_factor=excess))
  # Potential unused movement is measured, never equated with deletable waste.
  routed=unary_union([LineString(r['points']).buffer(.3) for r in routes if len(r['points'])>1])
  m['off_measured_routes_m2']=max(0,unary_union([shape(h) for h in all_halls]).difference(routed).area)
  floors.append(m)
 return dict(status='REJECT_AND_REPLAN' if defects else 'ACCEPTABLE_DESIGN_INDICATORS',defects=defects,floors=floors,limits=limits,legal='UNRESOLVED',daylight_airflow='UNRESOLVED',scope='unrouted hall area is screening, not confirmed waste; physical portal/body paths; no furnishing')
