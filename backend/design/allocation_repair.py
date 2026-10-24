"""Fallback CP-SAT room-bundle reassignment for a failed greedy/beam packing.

Preserves *every* requested space, requested floor, guest bundle, minimum area
and side. It modifies candidate *assignment*, not accepted walls or client brief.
"""
import math
import time
try:
    from ortools.sat.python import cp_model
except ImportError:  # OR-Tools has no wheel for the bundled Pyodide runtime.
    cp_model = None


def _bounded_python_assignment(bundles, lanes, lengths, capacities, feasible, budget_s):
    """Preserve exact capacity constraints when CP-SAT cannot run in a browser."""
    scale=1000
    integer_lengths=[[math.ceil(value*scale-1e-7) if math.isfinite(value) else math.inf
                      for value in row] for row in lengths]
    remaining=[math.floor(value*scale+1e-7) for value in capacities]
    order=sorted(range(len(bundles)), key=lambda i:(len(feasible[i]),
                  -min(integer_lengths[i][j] for j in feasible[i]),i))
    assignment=[None]*len(bundles)
    best=None
    best_cost=math.inf
    deadline=time.monotonic()+max(0.,budget_s)

    def search(position, cost):
        nonlocal best,best_cost
        if time.monotonic()>deadline:
            return
        if position==len(order):
            if cost<best_cost:
                best_cost=cost
                best=assignment.copy()
            return
        i=order[position]
        for j in feasible[i]:
            size=integer_lengths[i][j]
            if size>remaining[j] or cost+j+1>=best_cost:
                continue
            remaining[j]-=size
            assignment[i]=j
            search(position+1,cost+j+1)
            remaining[j]+=size
            assignment[i]=None

    search(0,0)
    if best is None:
        return None
    groups=[[] for _ in lanes]
    used=[0.]*len(lanes)
    for i,j in enumerate(best):
        groups[j].extend(bundles[i])
        used[j]+=lengths[i][j]
    if any(value>capacity+1e-5 for value,capacity in zip(used,capacities)):
        return None
    return used,groups


def reassign_bundles(bundles, lanes, wall_thickness, length_for, *, budget_s=0.4):
    capacities=[lane['depth' if lane['axis']=='y' else 'width'] for lane in lanes]
    if not bundles or not lanes or len(bundles)>32 or len(lanes)>12:
        return None
    scale=1000
    lengths=[[sum(length_for(r,lane,wall_thickness) for r in bundle)
              for lane in lanes] for bundle in bundles]
    feasible={i:[j for j,value in enumerate(row)
                 if math.isfinite(value) and value <= capacities[j]+1e-6]
              for i,row in enumerate(lengths)}
    if any(not v for v in feasible.values()):return None
    if cp_model is None:
        return _bounded_python_assignment(bundles,lanes,lengths,capacities,feasible,budget_s)
    model=cp_model.CpModel()
    assignments={(i,j):model.new_bool_var(f'b{i}_l{j}')
                 for i in range(len(bundles)) for j in feasible[i]}
    for i in range(len(bundles)):
        model.add(sum(assignments[i,j] for j in feasible[i])==1)
    for j,capacity in enumerate(capacities):
        model.add(sum(math.ceil(lengths[i][j]*scale-1e-7)*assignments[i,j]
                      for i in range(len(bundles)) if (i,j) in assignments)
                  <=math.floor(capacity*scale+1e-7))
    # Deterministic physical compactness; not a statutory or executive score.
    model.minimize(sum((j+1)*assignments[i,j] for i,j in assignments))
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=budget_s
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=0
    state=solver.solve(model)
    if state not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None
    groups=[[] for _ in lanes]
    used=[0.]*len(lanes)
    for i,bundle in enumerate(bundles):
        j=next(j for j in feasible[i] if solver.value(assignments[i,j]))
        groups[j].extend(bundle)
        used[j]+=lengths[i][j]
    if any(u>capacity+1e-5 for u,capacity in zip(used,capacities)):return None
    return used,groups
