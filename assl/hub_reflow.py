"""Move grouped rooms toward an actual crossbar, then trim unused hall tails.

Operates on concept rectangles only. Never reshapes rooms, changes floor
program, or steps into the previously reserved stair footprint.
"""
from __future__ import annotations

EPS=1e-6


def move_fork_groups_toward_bridge(cells,lanes,halls):
    """Relocate whole wing groups without changing area, dimensions or order.

    Each north-running lane gets translated toward the junction on the same
    side of its hall. Only rooms fully contained in the lane may move; any
    stair clearance cut out upstream is excluded from lane['depth'] already.
    """
    result=[dict(c) for c in cells]
    if not halls or len(halls)<3:return result
    bridge=next((h for h in halls if h.get('hub_leg')=='bridge'),None)
    if bridge is None:return result
    junction=bridge['y']
    for lane in lanes:
        if lane.get('axis')!='y' or lane['y']+lane['depth']>junction+EPS:
            continue
        lo=lane['y']; hi=lo+lane['depth']
        members=[r for r in result if r.get('kind')!='reserve' and
                 r['x']>=lane['x']-EPS and
                 r['x']+r['width']<=lane['x']+lane['width']+EPS and
                 r['y']>=lo-EPS and r['y']+r['depth']<=hi+EPS]
        if not members:continue
        slack=hi-max(r['y']+r['depth'] for r in members)
        if slack<.15:continue
        for item in members:
            item['y']+=slack
            item['hub_reflow_toward_bridge_m']=round(slack,4)
    return result
