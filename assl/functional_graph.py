"""Architecture-first room relationships before geometric lane allocation.

Relationship groups are *preferences*, not legal restrictions. The original
requested room IDs, counts, zones and minimum dimensions remain unchanged.
No furniture and no detailed opening geometry are used here.
"""
from __future__ import annotations

PRIORITY_PAIRS=(
    ('kitchen','dining',3),
    ('master','bathroom',2),
    ('bedroom','bathroom',1),
    ('living','dining',1),
)


def relation_graph(bundles):
    rooms=[r for bundle in bundles for r in bundle if r.get('request_id')]
    nodes=[{'id':r['id'],'kind':r['kind'],'zone':r.get('zone','family'),
            'requested_min_area_m2':r['min_area']}
           for r in rooms]
    relationships=[]
    for kind_a,kind_b,priority in PRIORITY_PAIRS:
        a=[r for r in rooms if r.get('kind')==kind_a and r.get('zone')!='guest']
        b=[r for r in rooms if r.get('kind')==kind_b and r.get('zone')!='guest']
        for left in a:
            for right in b:
                relationships.append({'from':left['id'],'to':right['id'],
                                      'priority':priority,'type':'PREFERRED_ADJACENCY',
                                      'requires_same_room_lane':False,
                                      'legal_obligation':False})
    return {'nodes':nodes,'relationships':relationships,
            'preserves_client_program':True,'furniture_used':False}


def pair_functional_bundles(bundles):
    """Pair high-value functional neighbors for pre-placement beam search.

    Does not enforce artificial room combinations; the caller must fall back
    to original independent bundles if grouped packing is infeasible.
    """
    original=[[r for r in group] for group in bundles]
    flattened=[r for g in original for r in g if r.get('request_id')]
    id_before=[r['id'] for r in flattened]
    groups=[[r for r in group] for group in original]
    tombstones=set();applied=[]
    def available(group):
        return (len(group)==1 and bool(group[0].get('request_id'))
                and group[0].get('zone')!='guest')
    for kind_a,kind_b,priority in PRIORITY_PAIRS:
        left=next((i for i,group in enumerate(groups)
                   if i not in tombstones and available(group) and
                   group[0]['kind']==kind_a),None)
        right=next((i for i,group in enumerate(groups)
                    if i not in tombstones and i!=left and available(group) and
                    group[0]['kind']==kind_b),None)
        if left is None or right is None:continue
        first,second=min(left,right),max(left,right)
        # Keep each room independent geometrically, but reserve the same
        # lane to favor direct proximity in the next architectural step.
        groups[first]=groups[first]+groups[second]
        tombstones.add(second)
        applied.append({'rooms':[groups[first][0]['id'],groups[first][1]['id']],
                        'relation':kind_a+'~'+kind_b,'priority':priority})
    result=[g for i,g in enumerate(groups) if i not in tombstones]
    id_after=[r['id'] for g in result for r in g if r.get('request_id')]
    if sorted(id_before)!=sorted(id_after) or len(id_before)!=len(id_after):
        raise ValueError('Functional grouping changed room program')
    return {'bundles':result,'applied_pairs':applied,
            'original_request_ids':id_before,
            'room_count_unchanged':True,
            'guest_bundles_untouched':True}
