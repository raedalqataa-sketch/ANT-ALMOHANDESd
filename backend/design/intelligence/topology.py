"""Program-first topology intents and partition-invariant functional signatures."""
from typing import Literal
from ..ai_lab.schemas import SearchOption


class TopologyOption(SearchOption):
    policy: Literal['social_front','family_front','service_aligned','relationship_aware','functional_hub','reference_hub']

from itertools import combinations
import networkx as nx
from shapely.geometry import box
from shapely.ops import unary_union
from ..reference_patterns import PROJECTS, RULES


def program_graph(brief):
    spaces=[];relations=[]
    for r in brief.rooms:
        guest=r.floor==0 and (r.kind=='majlis' or r.kind=='bathroom' and any(s in r.name for s in ('ضيف','ضيوف','رجال')))
        zone='guest' if guest else 'service' if r.kind in ('kitchen','laundry','storage') else 'family'
        spaces.append(dict(id=r.id,kind=r.kind,floor=r.floor,count=r.count,zone=zone,min_area_m2=r.min_area,min_side_m=r.min_side,
                           capacity=r.capacity,natural_light='modeled_opening_required; adequacy REVIEW'))
    for a,b in combinations(spaces,2):
        if a['floor']!=b['floor']:continue
        kinds={a['kind'],b['kind']}
        if (a['zone']=='guest') != (b['zone']=='guest'):
            relations.append(dict(a=a['id'],b=b['id'],type='FORBIDDEN_TRANSIT',strength='MANDATORY',basis='guest_family_separation'))
        elif a['zone']==b['zone']=='guest':
            relations.append(dict(a=a['id'],b=b['id'],type='SHARED_PRIVATE_GUEST_NODE',strength='MANDATORY' if brief.separate_guest_entry else 'PREFERRED',basis='separate_guest_entry_program'))
        elif kinds in ({'kitchen','dining'},{'living','dining'},{'bedroom','bathroom'},{'master','bathroom'}):
            relations.append(dict(a=a['id'],b=b['id'],type='PREFERRED_NEAR',strength='PREFERENCE',basis='functional_program_not_legal_distance'))
    return dict(version='functional-topology-004',spaces=spaces,relations=relations,
                required_counts={r.id:r.count for r in brief.rooms},core=dict(required=brief.floors>1,locked_across_floors=True),
                entry_face=brief.entrance_face,legal_approval=False)


def proposals(brief, *, use_references=True):
    """Choose different group/core/guest relations before any cells are fixed.

    Area factors are proposed design targets relative to unchanged requested
    minimums, never reductions to program minima or legal limits.
    """
    graph=program_graph(brief)
    references=list(PROJECTS) if use_references else []
    # Conditional ordering only; unverified image country/dimensions never used.
    preferred='reference_hub' if use_references else 'functional_hub'
    specs=[('spine',preferred,'front','linear'),('adaptive',preferred,'rear','linear'),
           ('spine','social_front','rear','compact_side'),
           ('adaptive','service_aligned','front','side_spine'),('freeform',preferred,'rear','linear')]
    if not any(s['zone']=='guest' for s in graph['spaces']):
        specs=[(f,p,c,'linear') for f,p,c,g in specs]
    return [dict(family=f,policy=p,core_position=c,guest_strategy=g,proposed_area_factor=factor,
                 reference_projects=references,reference_rules=[r['id'] for r in RULES if r['kind']!='deferred'] if references else [],
                 functional_graph=graph,topology_intent=dict(family_hub='central' if f=='spine' else 'distributed',
                     guest_node=g,core=c,service_relation='kitchen_near_dining'))
            for factor in (1.0,1.1,1.2) for f,p,c,g in specs]


def rect(r):
    return box(r['x'],r['y'],r['x']+r['width'],r['y']+r['depth'])


def signature(model):
    """WL hash of functional adjacency/access, entry and relative core location.

    Ordinary hall cells are dissolved before graph construction. Semantic labels
    omit element IDs. No coordinates, policy names or family names enter the hash.
    Core front/centre/rear is relative to actual external family entry, not axis Y.
    WL collisions can only undercount diversity; this is not proof of architecture.
    """
    graph=nx.Graph();floor_evidence=[]
    for f in model['floors']:
        rooms=[r for r in f['rooms'] if r['kind'] not in ('corridor','reserve')]
        shapes={};mapping={};hall_groups=[]
        for i,r in enumerate(rooms):
            key=f['id']+':room:'+str(i);mapping[r['id']]=key
            label=f"{f['id']}:{r['kind']}:{r.get('zone','family')}"
            graph.add_node(key,label=label);shapes[key]=rect(next((c for c in f['cells'] if c['id']==r['id']),r))
        for guest in (False,True):
            members=[c for c in f['cells'] if c['kind']=='corridor' and bool(c.get('guest_distributor'))==guest]
            halls=unary_union([rect(c) for c in members])
            pieces=[] if halls.is_empty else [halls] if halls.geom_type=='Polygon' else list(halls.geoms)
            for i,p in enumerate(pieces):
                key=f['id']+(':guest:' if guest else ':hall:')+str(i)
                graph.add_node(key,label=f['id']+(':guest_movement' if guest else ':family_movement'));shapes[key]=p
                ids={c['id'] for c in members if rect(c).intersection(p).area>1e-6}
                hall_groups.append((key,p,ids,guest))
        for a,b in combinations(shapes,2):
            # Nonzero shared edge, not point proximity, defines gross adjacency.
            if shapes[a].boundary.intersection(shapes[b].boundary).length>1e-5:
                graph.add_edge(a,b,label='shared_boundary')
        for o in f.get('openings',[]):
            if o['kind']!='door':continue
            nodes=[mapping[i] for i in o.get('connects',[]) if i in mapping]
            # Rooms adjoining a dissolved hall connect through hosted door position.
            for key,p,ids,guest in hall_groups:
                if ids.intersection(o.get('connects',[])):nodes.append(key)
            for a,b in combinations(set(nodes),2):graph.add_edge(a,b,label='door')
            if any(i in ('OUTSIDE','EXTERIOR') for i in o.get('connects',[])):
                key=f['id']+':entry:'+str(o.get('guest_entry',False));graph.add_node(key,label='guest_entry' if o.get('guest_entry') else 'family_entry')
                for n in nodes:graph.add_edge(key,n,label='entry')
        cores=[r for r in rooms if r['kind']=='stair']
        entries=[o for o in f.get('openings',[]) if o['kind']=='door' and not o.get('guest_entry') and any(i in ('OUTSIDE','EXTERIOR') for i in o.get('connects',[]))]
        core_rank=[]
        if entries and cores:
            from math import dist
            e=entries[0]['center'];distances=sorted(dist(e,(r['x']+r['width']/2,r['y']+r['depth']/2)) for r in rooms)
            for r in cores:
                distance=dist(e,(r['x']+r['width']/2,r['y']+r['depth']/2));rank=sum(d<distance for d in distances)/max(1,len(distances)-1)
                band='front' if rank<1/3 else 'rear' if rank>=2/3 else 'central'
                graph.nodes[mapping[r['id']]]['label']+=':'+band;core_rank.append(band)
        floor_evidence.append(dict(floor=f['id'],hall_components=sum(not g[3] for g in hall_groups),guest_components=sum(g[3] for g in hall_groups),core_entry_bands=core_rank))
    digest=nx.weisfeiler_lehman_graph_hash(graph,node_attr='label',edge_attr='label',iterations=4)
    return dict(hash=digest,method='functional adjacency/access WL4 + relative core entrance band; halls dissolved',
                floors=floor_evidence,nodes=graph.number_of_nodes(),edges=graph.number_of_edges(),
                labels=sorted(nx.get_node_attributes(graph,'label').values()),legal_rule=False)
