"""Z03 accepts direct access or a route through the assigned guest foyer."""
from collections import defaultdict


def check_guest_wc_routes(proposal):
    results = []
    for rooms, halls, openings in zip(
        proposal["rooms_by_floor"], proposal["halls_by_floor"],
        proposal["opening_model_009"], strict=True,
    ):
        for council in (r for r in rooms if r["kind"] == "majlis"):
            for entry in council.get("guest_entries", ()):
                foyers = {r["id"] for r in halls if r.get("guest_entry") == entry}
                toilets = [r for r in rooms if r["kind"] == "bathroom"
                           and entry in r.get("guest_entries", ())]
                for toilet in toilets:
                    start, target = council["id"], toilet["id"]
                    allowed = foyers | {start, target}
                    graph = defaultdict(list)
                    for opening in openings["doors"]:
                        a, b = opening["connects"]
                        if {a, b} <= allowed and f"guest:{entry}" in opening.get("roles", ()):
                            graph[a].append(b)
                            graph[b].append(a)
                    paths = {start: [start]}
                    queue = [start]
                    for node in queue:
                        for neighbor in graph[node]:
                            if neighbor not in paths:
                                paths[neighbor] = paths[node] + [neighbor]
                                queue.append(neighbor)
                    path = paths.get(target)
                    results.append({"guest_entry": entry, "council": start,
                                    "guest_wc": target, "path": path,
                                    "status": "PASS" if path else "FAIL"})
    status = "NOT_APPLICABLE" if not results else (
        "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL")
    return {"rule": "Z03", "status": status, "routes": results}
