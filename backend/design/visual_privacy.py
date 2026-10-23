"""Sampled 2D guest-entry sightlines through the actual modeled wall openings.

Family-controlled doors are assumed closed; other doors/windows transparent.
No neighbour geometry, heights, full visibility polygon or acoustic assessment.
A clear sample is a review finding, never a privacy certification either way.
"""
from .export import wall_runs


def inspect(model):
    rays=[];exposed=set();entries=[]
    for floor in model.get('floors',[]):
        origins=[o for o in floor['openings'] if o['kind']=='door' and o.get('guest_entry')]
        targets=[r for r in floor['rooms'] if r.get('zone')!='guest' and r['kind'] in ('living','bedroom','master')]
        # A closed, controlled door is opaque: restore its opening as a wall run.
        opaque={**floor,'openings':[o for o in floor['openings'] if o.get('access_control')!='family_only']}
        runs=[(w,a,b) for w in floor['walls'] for a,b in wall_runs(opaque,w)]
        hosts={w['id']:w for w in floor['walls']}
        for entry in origins:
            entries.append(entry['id']);w=hosts.get(entry['wall_id'])
            if not w:continue
            axis=0 if w['axis']=='horizontal' else 1
            starts=[]
            for fraction in (-.3,0,.3):
                a=list(entry['center']);a[axis]+=entry['width']*fraction;starts.append(a)
            for room in targets:
                ends=[[room['x']+room['width']*u,room['y']+room['depth']*v] for u,v in ((.5,.5),(.1,.1),(.1,.9),(.9,.1),(.9,.9))]
                for a in starts:
                    for b in ends:
                        blockers=[]
                        for wall,s,e in runs:
                            idx=0 if wall['axis']=='vertical' else 1;other=1-idx;den=b[idx]-a[idx]
                            if abs(den)<1e-9:continue
                            t=(s[idx]-a[idx])/den;p=a[other]+t*(b[other]-a[other])
                            if 1e-5<t<1-1e-5 and min(s[other],e[other])-1e-6<=p<=max(s[other],e[other])+1e-6:blockers.append(wall['id'])
                        visible=not blockers
                        rays.append({'floor':floor['id'],'entry':entry['id'],'target':room['id'],'start':a,'end':b,'visible':visible,'blocking_walls':sorted(set(blockers))})
                        if visible:exposed.add(room['id'])
    return {'status':'REVIEW' if entries else 'NOT_APPLICABLE','guest_entries':entries,'sampled_rays':rays,
            'sampled_exposed_rooms':sorted(exposed),'certified':False,
            'scope':'sampled 2D rays only; controlled family doors closed; no window-to-neighbour, acoustic, height or full visibility verification'}
