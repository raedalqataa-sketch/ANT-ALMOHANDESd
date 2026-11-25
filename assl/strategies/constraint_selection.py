"""CP-SAT beam selection over real geometric states, never architectural approval.

Keep the existing family-wing quotas and require maximum topology coverage
inside each quota. CP-SAT then chooses lower-cost states within those guards.
"""
from collections import Counter,defaultdict


def _load_cp_model():
    try:
        from ortools.sat.python import cp_model
        return cp_model
    except ImportError:return None


def require_ortools():
    module=_load_cp_model()
    if module is None:raise ValueError('ORTOOLS_UNAVAILABLE:requires-native-Python-runtime')
    return module


def _geometry_key(state):
    return tuple((r['id'],tuple(tuple(p) for p in r['polygon'])) for r in sorted(state['objects'],key=lambda r:r['id']))


def _groups(state):
    first=state['trace'][0];root=next(r for r in state['objects'] if r['id']==first['root'])
    placement=(first['root'],first['host'],first['side'],first['rotation'],round(root['x'],6),round(root['y'],6))
    topology=tuple((x['root'],x['host'],x['side']) for x in state['trace'])
    return placement,topology


def _selection_problem(states,baseline,limit):
    if not 1<=limit<=48:raise ValueError('CP_BEAM_LIMIT_OUT_OF_RANGE')
    unique=[];seen=set()
    for state in sorted(states,key=lambda s:s['score']):
        key=_geometry_key(state)
        if key not in seen:seen.add(key);unique.append(state)
    indices={id(s):i for i,s in enumerate(unique)}
    if len(baseline)!=min(limit,len(unique)) or any(id(s) not in indices for s in baseline):raise ValueError('INVALID_CP_BEAM_BASELINE')
    hinted={indices[id(s)] for s in baseline};quotas=Counter(_groups(s)[0] for s in baseline)
    groups=defaultdict(lambda:defaultdict(list))
    for i,state in enumerate(unique):
        placement,topology=_groups(state);groups[placement][topology].append(i)
    return unique,hinted,quotas,groups


def select_beam_local(states,baseline,*,limit=48):
    """Exact solution of the same partition quotas/coverage and additive rank cost.

    If q <= topology count, take the cheapest q distinct bucket heads. Otherwise
    every bucket must contribute its cheapest head; fill the remaining q slots
    with the cheapest unused ranks. Placement quotas make groups independent.
    This is not a general integer-programming or architectural feasibility solver.
    """
    unique,hinted,quotas,groups=_selection_problem(states,baseline,limit)
    chosen=[]
    for placement,topologies in groups.items():
        q=quotas[placement]
        if not q:continue
        heads=sorted(bucket[0] for bucket in topologies.values())
        if q<=len(heads):chosen.extend(heads[:q])
        else:
            chosen.extend(heads)
            remaining=sorted(i for bucket in topologies.values() for i in bucket[1:])
            chosen.extend(remaining[:q-len(heads)])
    selected=sorted(chosen)
    report=dict(backend='local-exact',status='NO_PRUNING_NEEDED' if len(unique)<=limit else 'OPTIMAL',
                eligible=len(unique),selected=len(selected),cp_sat_used=False,optimality_proven=True,
                architectural_optimality_proven=False,objective_before=sum(hinted),objective_after=sum(selected),
                changed=set(selected)!=hinted,family_placements=len(quotas))
    return [unique[i] for i in selected],report


def select_beam(states,baseline,*,limit=48):
    cp=require_ortools()
    unique,hinted,quotas,groups=_selection_problem(states,baseline,limit)
    report=dict(backend='ortools-cp-sat',eligible=len(unique),selected=len(baseline),
                architectural_optimality_proven=False,cp_sat_used=False)
    if len(unique)<=limit:return baseline,dict(report,status='NO_PRUNING_NEEDED',optimality_proven=True)
    model=cp.CpModel();picked=[model.new_bool_var('state_'+str(i)) for i in range(len(unique))]
    model.add(sum(picked)==len(baseline))
    for placement,topologies in groups.items():
        quota=quotas[placement];all_indices=[i for bucket in topologies.values() for i in bucket]
        model.add(sum(picked[i] for i in all_indices)==quota)
        if not quota:continue
        covered=[]
        for bucket in topologies.values():
            flag=model.new_bool_var('topology_'+str(len(model.proto.variables)))
            total=sum(picked[i] for i in bucket)
            model.add(total>=flag);model.add(total<=len(bucket)*flag)
            model.add_hint(flag,int(any(i in hinted for i in bucket)));covered.append(flag)
        model.add(sum(covered)>=min(quota,len(topologies)))
    for i,var in enumerate(picked):model.add_hint(var,int(i in hinted))
    # Ranks come from measured geometric packing cost, not arbitrary room IDs.
    model.minimize(sum(i*var for i,var in enumerate(picked)))
    solver=cp.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.random_seed=1
    solver.parameters.max_time_in_seconds=.5;solver.parameters.max_deterministic_time=.1
    status=solver.solve(model)
    if status not in (cp.OPTIMAL,cp.FEASIBLE):raise ValueError('ORTOOLS_BEAM_NO_SOLUTION:'+solver.status_name(status))
    chosen=[i for i,var in enumerate(picked) if solver.value(var)]
    report.update(status=solver.status_name(status),cp_sat_used=True,optimality_proven=status==cp.OPTIMAL,
                  objective_before=sum(hinted),objective_after=sum(chosen),wall_time_s=solver.wall_time,
                  changed=set(chosen)!=hinted,family_placements=len(quotas))
    return [unique[i] for i in chosen],report
