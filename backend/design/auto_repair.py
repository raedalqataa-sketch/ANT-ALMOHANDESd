"""Bounded, transactional SAME-model door/furniture repairs, with rollback.

Never changes the brief, room count, room geometry, legal limits or stair core.
A step must remove an existing failed check, introduce no new failed checks and
preserve pending obligations. Logs rejected attempts too. This is not a complete
room/massing/MEP repair solver; those remain explicit capabilities not implemented.
"""
import copy,hashlib,json
from .general_quality import door_geometry
from .furnishing import furnish_floor


def fingerprint(model):
    data={k:model.get(k) for k in ('floors','stairs','stair_arrivals','parking','service_yard','regulatory_geometry')}
    def clean(obj):
        if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items() if k not in ('revision_id','annotations','furnishing_choice_counts','furnishing_notes','decorations')}
        if isinstance(obj,(list,tuple)):return [clean(v) for v in obj]
        return obj
    return hashlib.sha256(json.dumps(clean(data),sort_keys=True,allow_nan=False).encode()).hexdigest()

def _failures(rows):return {r['check_id'] for r in rows if r['status']=='FAIL'}

def _invariants(model):
    return {k:copy.deepcopy(model.get(k)) for k in ('brief','stairs','stair_arrivals','regulatory_geometry','site','footprint')},[
        (f['id'],copy.deepcopy(f['rooms']),copy.deepcopy(f['cells']),copy.deepcopy(f['walls'])) for f in model['floors']]

def _sync_swing(floor,door):
    if door.get('door_style')=='sliding':return
    g=door_geometry(floor,door);h=g['hinge'];r=g['radius'];u=g['closed_direction'];v=g['open_direction']
    points=[h,[h[0]+r*u[0],h[1]+r*u[1]],[h[0]+r*v[0],h[1]+r*v[1]],[h[0]+r*(u[0]+v[0]),h[1]+r*(u[1]+v[1])]]
    door['swing_rect']=dict(x=min(p[0] for p in points),y=min(p[1] for p in points),
                            width=max(p[0] for p in points)-min(p[0] for p in points),depth=max(p[1] for p in points)-min(p[1] for p in points))

class ArchitectureAutoRepairEngine:
    def __init__(self,validator,max_attempts=8):self.validator=validator;self.max_attempts=max_attempts
    def repair(self,model):
        current=copy.deepcopy(model);initial=self.validator(current);current['checks']=initial
        history=[];initial_digest=fingerprint(current);invariants=_invariants(current)
        while _failures(current['checks']) and len(history)<self.max_attempts:
            accepted=False
            for operation,element,mutate in self._operations(current):
                if len(history)>=self.max_attempts:break
                trial=copy.deepcopy(current);before=_failures(current['checks']);before_hash=fingerprint(current)
                mutate(trial)
                # Reindex furniture to prevent duplicate symbols after replacing groups.
                for f in trial['floors']:
                    for i,q in enumerate(f['furniture']):q['id']=f['id']+f'-F{i+1:03}'
                rows=self.validator(trial);after=_failures(rows)
                obligations={r['check_id'] for r in current['checks'] if r['status'] in ('PENDING','REVIEW')}
                retained={r['check_id'] for r in rows if r['status'] in ('PENDING','REVIEW')}
                safe=_invariants(trial)==invariants and after<before and obligations<=retained
                log={'operation':operation,'element':element,'before_failed':sorted(before),'after_failed':sorted(after),
                     'before_geometry_sha256':before_hash,'after_geometry_sha256':fingerprint(trial),
                     'accepted':safe,'reason':'removed failure without new failure or program/site change' if safe else 'rolled back: no strict improvement or invariant/obligation changed',
                     'impact':{'room_area_change_m2':0,'room_program_changed':False,'setbacks_changed':False},
                     'before_checks':copy.deepcopy(current['checks']),'after_checks':copy.deepcopy(rows)}
                history.append(log)
                if safe:
                    trial['checks']=rows;current=trial;accepted=True;break
            if not accepted:break
        current['auto_repair_v4']={'revision':'same-model-repair-4','attempt_budget':self.max_attempts,'attempts':history,
              'accepted_steps':sum(h['accepted'] for h in history),'remaining_failures':sorted(_failures(current['checks'])),
              'initial_geometry_sha256':initial_digest,'final_geometry_sha256':fingerprint(current),
              'unsupported_repairs':['room_move_swap_resize','corridor_rebuild','stair_relocation','massing_rebuild','MEP_coordination']}
        current['geometry_sha256']=fingerprint(current)
        return current
    def _operations(self,model):
        failed=_failures(model['checks'])
        for fi,f in enumerate(model['floors']):
            if not any(code.startswith(f['id']) or code.startswith('V4-') for code in failed):continue
            # Hinge reversal is limited to ordinary room doors; external/security/core
            # openings need specialist direction constraints and are never flipped here.
            collision_ids={q.get('door') for c in model['checks'] if c['check_id']==f['id']+'-door-sweeps' for q in c.get('evidence',{}).get('collisions',[])}
            for oi,o in enumerate(f['openings']):
                if o['kind']!='door' or o.get('door_style')=='sliding' or o['id'] not in collision_ids:continue
                room=next((r for r in f['rooms'] if r['id']==o['connects'][0]),{})
                if o.get('main_entry') or o.get('guest_entry') or room.get('kind') in ('stair','corridor') or o.get('access_control'):continue
                def flip(m,fi=fi,oi=oi):
                    floor=m['floors'][fi];d=floor['openings'][oi];d['hinge_end']='high' if d.get('hinge_end','low')=='low' else 'low';_sync_swing(floor,d)
                yield 'reverse_door_hinge',o['id'],flip
                wall=next(w for w in f['walls'] if w['id']==o['wall_id']);axis=0 if wall['axis']=='horizontal' else 1
                lo=min(wall['start'][axis],wall['end'][axis])+wall['thickness']/2+.12+o['width']/2
                hi=max(wall['start'][axis],wall['end'][axis])-wall['thickness']/2-.12-o['width']/2
                for fraction in (.5,.25,.75):
                    if hi<lo:continue
                    def move(m,fi=fi,oi=oi,axis=axis,value=lo+fraction*(hi-lo)):
                        floor=m['floors'][fi];d=floor['openings'][oi];d['center'][axis]=value;_sync_swing(floor,d)
                    yield 'relocate_door_on_same_host',o['id'],move
            for ri,r in enumerate(f['rooms']):
                if not r.get('request_id'):continue
                issues={q.get('room') for c in model['checks'] if c['check_id']=='V4-furniture-clearance' for q in c.get('evidence',{}).get('invalid',[])}
                inaccessible={q for c in model['checks'] if c['check_id']==f['id']+'-walkability' for q in c.get('evidence',{}).get('unreachable',[])}
                if r['id'] not in issues|inaccessible:continue
                for choice in range(1,min(f.get('furnishing_choice_counts',{}).get(r['id'],0),5)):
                    def refurnish(m,fi=fi,ri=ri,choice=choice):
                        floor=m['floors'][fi];room=floor['rooms'][ri];all_rooms=floor['rooms']
                        floor['furniture']=[q for q in floor['furniture'] if q['room_id']!=room['id']]
                        floor['decorations']=[q for q in floor.get('decorations',[]) if q.get('room_id')!=room['id']]
                        try:floor['rooms']=[room];furnish_floor(floor,m['model_revision_id'],{room['id']:choice})
                        finally:floor['rooms']=all_rooms
                    yield 'replace_complete_furniture_group',r['id'],refurnish
