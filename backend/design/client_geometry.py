"""Experimental geometry search; coordinates in metres."""
from itertools import permutations
from .client_wings import allocate_wings

def generate_geometry(program, envelopes, corridor_width=1.8):
    if corridor_width<=0 or set(envelopes)!=set(range(program.floor_count)):
        return {'status':'needs_data','layouts':[]}
    capacities={}
    for f,(x,y,w,d) in envelopes.items():
        if w<=0 or d<=corridor_width:
            return {'status':'needs_data','layouts':[]}
        capacities[f]=w*(d-corridor_width)
    allocation=allocate_wings(program,capacities)
    if allocation['status']!='allocation_ready':
        return {'status':allocation['status'],'layouts':[]}
    floors=[]
    for f,(x,y,w,d) in envelopes.items():
        groups=[v for k,v in allocation['wings'].items() if k.startswith(str(f)+':')]
        best=None
        for order in permutations(groups):
            for split in range(1,len(order)):
                for ratio in (.4,.5,.6):
                    depths=((d-corridor_width)*ratio,(d-corridor_width)*(1-ratio))
                    rooms=[]
                    for side,wing_groups in enumerate((order[:split],order[split:])):
                        cursor=x
                        for group in wing_groups:
                            for row in group:
                                depth=depths[side]
                                width=row['target_m2']/depth
                                if min(width,depth)<2 or max(width,depth)/min(width,depth)>2.8:break
                                rooms.append(dict(row,x=cursor,y=y if side==0 else y+depths[0]+corridor_width,width=width,depth=depth))
                                cursor+=width
                            else:continue
                            break
                        if cursor>x+w+1e-8:break
                    else:
                        if len(rooms)!=sum(map(len,groups)):continue
                        def adjacent(a,b):
                            return ((abs(a['x']+a['width']-b['x'])<1e-7 or abs(b['x']+b['width']-a['x'])<1e-7) and min(a['y']+a['depth'],b['y']+b['depth'])-max(a['y'],b['y'])>1e-7)
                        if any(not any(b['program_id']==t and adjacent(a,b) for b in rooms) for a in rooms for t in a['adjacency_required']):continue
                        if any(b['program_id'] in a['adjacency_forbidden'] and adjacent(a,b) for a in rooms for b in rooms):continue
                        span=max(a['x']+a['width'] for a in rooms)-x
                        score=span*corridor_width
                        if best is None or score<best[0]:
                            best=(score,{'floor':f,'rooms':rooms,'corridor':{'x':x,'y':y+depths[0],'width':span,'depth':corridor_width}})
        if best is None:return {'status':'no_candidate_in_search_family','layouts':[]}
        floors.append(best[1])
    return {'status':'geometry_candidate','layouts':floors,'accepted':False,'pending':['external entrances','wall and opening generation','vertical core coordination','regulatory and visual review']}
