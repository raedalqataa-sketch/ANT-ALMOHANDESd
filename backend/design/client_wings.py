"""Program-driven allocation; not yet geometric layout."""
from .client_program import ClientProgram

def allocate_wings(program: ClientProgram, net_capacities_m2: dict[int,float], max_states=100000):
    if set(net_capacities_m2)!=set(range(program.floor_count)) or any(not 0<v<float('inf') for v in net_capacities_m2.values()):
        return {'status':'needs_data','reason':'Explicit positive net capacity required per floor'}
    remaining=dict(net_capacities_m2)
    items=[(r,i+1) for r in program.rooms if r.required for i in range(r.count)]
    items.sort(key=lambda x:(len(set(x[0].allowed_floors)),-x[0].area_min_m2,x[0].id,x[1]))
    if len(items)>200:
        return {'status':'needs_data','reason':'Instance limit exceeded'}
    assigned=[]
    states=0
    def visit(index):
        nonlocal states
        states+=1
        if states>max_states:return False
        if index==len(items):return True
        r,i=items[index]
        for f in sorted(set(r.allowed_floors),key=lambda f:(-remaining[f],f)):
            if remaining[f]+1e-9<r.area_min_m2:continue
            remaining[f]-=r.area_min_m2
            assigned.append({'program_id':r.id,'instance':i,'kind':r.kind,'floor':f,'wing':r.privacy_zone,'min_m2':r.area_min_m2,'target_m2':r.area_target_m2,'max_m2':r.area_max_m2,'adjacency_required':r.adjacency_required,'adjacency_forbidden':r.adjacency_forbidden})
            if visit(index+1):return True
            assigned.pop()
            remaining[f]+=r.area_min_m2
            if states>max_states:return False
        return False
    if not visit(0):
        return {'status':'needs_data' if states>max_states else 'infeasible_capacity','states':states}
    wings={}
    for row in assigned:
        key=f"{row['floor']}:{row['wing']}"
        wings.setdefault(key,[]).append(row)
    return {'status':'allocation_ready','wings':wings,'remaining_m2':remaining,'optional_pending':[r.id for r in program.rooms if not r.required],'geometry_verified':False,'adjacency_verified':False}
