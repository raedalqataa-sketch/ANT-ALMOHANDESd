"""Authoritative program graph and true positional diversity for relational search."""
import math,hashlib
from backend.design.general_engine import expanded_program
from assl.guest_groups import prepare_program
from .geometry import shape,shared_edges

SCHEMA='assl-relational-1'

def compile_program(brief):
 a=brief.automatic_features
 if any((a.lightwell,a.roof_annex,a.balcony,a.service_yard)) or brief.regulatory_geometry is not None or brief.notes.strip():raise ValueError('UNRESOLVED_RELATIONAL_REQUIREMENTS')
 if a.main_street_faces and brief.entrance_face not in a.main_street_faces:raise ValueError('ENTRANCE_NOT_ON_ALLOWED_STREET')
 rows=[]
 for floor in range(brief.floors):rows.extend(dict(r,floor=floor) for r in prepare_program(brief,expanded_program(brief,floor)))
 if any(r['kind']=='majlis' for r in rows) and not brief.guest_groups:raise ValueError('UNRESOLVED_GUEST_MEMBERSHIP')
 groups=[]
 for entry in sorted({g.entry or g.id for g in brief.guest_groups}):
  own=[r for r in rows if entry in r.get('guest_entries',[])]
  councils=sorted([r for r in own if r['kind']=='majlis'],key=lambda r:(-r['min_area'],r['id']))
  if not councils:raise ValueError('GUEST_ENTRY_WITHOUT_COUNCIL:'+entry)
  groups.append((entry,councils,[r for r in own if r['kind']=='bathroom']))
 groups.sort(key=lambda g:(-len(g[1]),-sum(r['min_area'] for r in g[1]),g[0]))
 entries={'main-foyer':groups[0][0] if groups else None,'family-foyer':groups[1][0] if len(groups)>1 else None}
 for group in groups[2:]:entries['guest-foyer-'+hashlib.sha256(group[0].encode()).hexdigest()[:10]]=group[0]
 hosts={r['id']:[node for node,key in entries.items() if key in r.get('guest_entries',[]) and key is not None] for r in rows if r.get('guest_entries')}
 byrequest={r.id:[row['id'] for row in rows if row['request_id']==r.id] for r in brief.rooms}
 relations=[dict(sources=byrequest[r.source],targets=byrequest[r.target],relation=r.relation,max_distance_m=r.max_distance_m) for r in brief.spatial_requirements]
 access_hosts={}
 for r in rows:
  if r.get('guest_entries'):continue
  if r['kind']=='kitchen':access_hosts[r['id']]=[x['id'] for x in rows if x['kind']=='dining' and x['floor']==r['floor']]
  elif r['kind']=='laundry':access_hosts[r['id']]=[x['id'] for x in rows if x['kind']=='kitchen' and x['floor']==r['floor']]
 return dict(requests=rows,groups=groups,entries=entries,hosts=hosts,access_hosts=access_hosts,guest_rooms=sorted(hosts),relations=relations)


def program_view(brief):
 g=compile_program(brief);by={}
 for r in g['requests']:by.setdefault(r['kind'],[]).append(r)
 return g['requests'],by,g['groups']


def positional_signature(p):
 """Canonical relative centre orders, invariant to global D4 and translation.

 Dimensional-only changes that keep all activity centre orders have the same
 signature. Independent activity rearrangement can differ; mirrored full plans
 never count twice. This is a positional criterion, not graph non-isomorphism.
 """
 rows=sorted([r for r in p['rooms_by_floor'][0] if r.get('request_id') or r['kind']!='stair'],key=lambda r:r['id'])
 # Unit geometry tests may have no request metadata: these are still activities.
 centres=[(r['id'],shape(r).centroid.x,shape(r).centroid.y) for r in rows]
 def sign(v):return 0 if abs(v)<1e-6 else 1 if v>0 else -1
 candidates=[]
 for swap in (False,True):
  for sx in (-1,1):
   for sy in (-1,1):
    points=[(rid,sx*(y if swap else x),sy*(x if swap else y)) for rid,x,y in centres]
    candidates.append(tuple((a[0],b[0],sign(b[1]-a[1]),sign(b[2]-a[2])) for i,a in enumerate(points) for b in points[i+1:]))
 return min(candidates) if candidates else ()


def geometric_relation_issues(brief,p,*,partial=False,compiled=None):
 graph=compile_program(brief) if compiled is None else compiled;ids={r['id']:r for r in p['rooms_by_floor'][0]};issues=[]
 for relation in graph['relations']:
  if relation['relation']=='near':continue
  targets=[ids[r] for r in relation['targets'] if r in ids]
  for source in relation['sources']:
   if source not in ids or not targets:
    if not partial:issues.append('MISSING_RELATION_ENTITY:'+source)
    continue
   contacts=[max((e['length'] for e in shared_edges(ids[source],t)),default=0) if relation['relation']=='adjacent' else shape(ids[source]).boundary.intersection(shape(t).boundary).length for t in targets]
   good=any(c>=1.2-1e-6 for c in contacts) if relation['relation']=='adjacent' else all(c<1e-6 for c in contacts)
   if not good and partial and relation['relation']=='adjacent' and len(targets)<len(relation['targets']):continue
   if not good:issues.append('CLIENT_'+relation['relation'].upper()+':'+source)
 return issues


def attachment_signature(p):
 """Dimensions cannot create a new attachment topology. No trace, no claim."""
 if not p.get('relational_trace'):return None
 ids={r['id']:r for r in p['rooms_by_floor'][0]+p['halls_by_floor'][0]}
 label=lambda rid:ids.get(rid,{}).get('request_id') or rid
 vectors={'E':(1,0),'W':(-1,0),'N':(0,1),'S':(0,-1)};out=[]
 for swap in (False,True):
  for sx in (-1,1):
   for sy in (-1,1):
    def transform(v):return (round(sx*(v[1] if swap else v[0]),6),round(sy*(v[0] if swap else v[1]),6))
    rows=[]
    for item in p['relational_trace']:
     side=transform(vectors[item['side']]);orientation=()
     if item.get('activities',1)>1:
      angle=math.radians(item['rotation']);orientation=transform((math.cos(angle),math.sin(angle)))
     rows.append((label(item['root']),label(item['host']),side,orientation))
    out.append(tuple(sorted(rows)))
 return min(out)
