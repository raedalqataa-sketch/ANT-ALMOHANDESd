"""Bounded opt-in re-furnishing of the men's majlis to repair guest-only access.

Runs before the immutable geometry fingerprint is issued. Changes ONLY the
furniture group inside an existing majlis, not requested rooms, partitions,
doors, setbacks, council dimensions, or user constraints. V4 still validates.
"""
from __future__ import annotations
import copy


def attempt_guest_furniture_repair(model, revision, *,
                                    floor_access=None, furnish_floor=None,
                                    max_choices=8):
    """Return measured evidence. Original furniture is restored on failure.

    Optional dependency injection supports deterministic unit tests. At runtime
    uses exactly the project's existing furnishing and 0.60m movement routines.
    """
    if floor_access is None:
        from backend.design.walkability import floor_access
    if furnish_floor is None:
        from backend.design.furnishing import furnish_floor
    floor=next((f for f in model.get('floors',[]) if f.get('id')=='GF'),None)
    if floor is None:
        return {'status':'UNRESOLVED','reason':'GROUND_FLOOR_MISSING'}
    guests={r['id'] for r in floor['rooms'] if r.get('zone')=='guest'}
    councils=[r for r in floor['rooms'] if r['id'] in guests and r.get('kind')=='majlis']
    dist=next((r['id'] for r in floor['rooms'] if r.get('guest_distributor')
               and r['id'] in guests and
               any(o.get('guest_entry') and r['id'] in o.get('connects',[])
                   for o in floor['openings'])),None)
    if not councils:
        return {'status':'NOT_APPLICABLE'}
    if not dist:
        return {'status':'UNRESOLVED','reason':'EXTERIOR_GUEST_DISTRIBUTOR_NOT_FOUND'}
    def access():
        return floor_access(model,floor,step=.20,body_width=.60,
                            start_room_id=dist,allowed_room_ids=guests)
    initial=access().get('unreachable',[])
    if not initial:
        return {'status':'ALREADY_ACCESSIBLE','changed':False}
    # Repair only if a council is inaccessible; do not silently alter a
    # bathroom or the family's plan to make a blocked route look successful.
    targets=[r for r in councils if r['id'] in initial]
    if not targets:
        return {'status':'NOT_REPAIRED','reason':'NON_COUNCIL_GUEST_ROUTE_BLOCKED',
                'before_unreachable':initial,'changed':False}
    results=[]
    for room in targets:
        rid=room['id']
        before_furniture=copy.deepcopy(floor['furniture'])
        before_decorations=copy.deepcopy(floor.get('decorations',[]))
        before_counts=copy.deepcopy(floor.get('furnishing_choice_counts',{}))
        before_notes=copy.deepcopy(floor.get('furnishing_notes',[]))
        count=before_counts.get(rid,0)
        fixed=False
        for choice in range(1,min(max_choices,max(1,count))):
            floor['furniture']=copy.deepcopy([q for q in before_furniture
                                              if q.get('room_id')!=rid])
            floor['decorations']=copy.deepcopy([q for q in before_decorations
                                               if q.get('room_id')!=rid or q.get('kind')!='rug'])
            floor['furnishing_notes']=copy.deepcopy(before_notes)
            all_rooms=floor['rooms']
            try:
                floor['rooms']=[room]
                furnish_floor(floor,revision,{rid:choice})
            finally:
                floor['rooms']=all_rooms
            furnished=[q for q in floor['furniture'] if q.get('room_id')==rid]
            if not any(q.get('kind')=='sofa' for q in furnished):
                continue
            remaining=access().get('unreachable',[])
            if not any(r['id'] in remaining for r in councils):
                fixed=True
                for i,q in enumerate(floor['furniture']):
                    q['id']=floor['id']+f'-F{i+1:03}'
                results.append({'room_id':rid,'choice_index':choice,
                                'status':'REPAIRED',
                                'after_unreachable':remaining})
                break
        if not fixed:
            floor['furniture']=before_furniture
            floor['decorations']=before_decorations
            floor['furnishing_choice_counts']=before_counts
            floor['furnishing_notes']=before_notes
            results.append({'room_id':rid,'status':'NOT_REPAIRED'})
    after=access().get('unreachable',[])
    return {'status':'REPAIRED' if not after else 'NOT_REPAIRED',
            'changed':any(r['status']=='REPAIRED' for r in results),
            'before_unreachable':initial,'after_unreachable':after,
            'attempts':results,
            'design_approval':False,'legal_approval':False,
            'scope':'Existing council furnishing templates only; no structural or program changes'}
