"""Conservative opening and access checks on explicit room boundaries."""
def check_access(rooms, walls, entry_ids, door_width_mm=900):
    ids={r["id"] for r in rooms}
    graph={i:set() for i in ids}
    doors=[]
    for w in walls:
        owners=w["rooms"]
        if len(owners)!=2 or w["length_mm"]<door_width_mm+200:continue
        a,b=owners
        # Only explicitly designated circulation spaces may connect independent rooms.
        if not any(i.startswith("circulation:") for i in owners):continue
        graph[a].add(b);graph[b].add(a)
        doors.append(dict(wall_id=w["id"],rooms=owners,width_mm=door_width_mm,offset_mm=(w["length_mm"]-door_width_mm)/2))
    reached=set(entry_ids)&ids
    queue=list(reached)
    while queue:
        for n in graph[queue.pop()]-reached:
            reached.add(n);queue.append(n)
    missing=sorted(ids-reached)
    return dict(status="fail" if missing else "needs_data",unreachable=missing,door_proposals=doors,entry_verified=False,windows_verified=False,privacy_verified=False)
