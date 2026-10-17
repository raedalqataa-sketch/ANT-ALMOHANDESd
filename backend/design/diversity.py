"""Geometry-based diversity audit for proposed floor-plan alternatives.

Does not mistake different building dimensions for different architectural topologies.
Only uses room adjacency and room-to-exterior connections represented by wall/door data.
"""
from collections import Counter


def topology_signature(model):
    floors = []
    for floor in model["floors"]:
        rooms = {room["id"]: room for room in floor["rooms"]}
        edges = []
        for opening in floor["openings"]:
            if opening["kind"] != "door":
                continue
            a, b = opening["connects"]
            if a not in rooms:
                continue
            kind_a = (rooms[a]["kind"], rooms[a]["zone"])
            kind_b = ("EXTERIOR", "outside") if b == "EXTERIOR" else (
                (rooms[b]["kind"], rooms[b]["zone"]) if b in rooms else ("UNKNOWN", "unknown")
            )
            edges.append(tuple(sorted((kind_a, kind_b))))
        floors.append((floor["id"], tuple(sorted(edges))))
    return tuple(sorted(floors))


def diversity_report(candidates):
    signatures = [topology_signature(c) for c in candidates]
    distinct = len(set(signatures))
    return {
        "candidate_count": len(candidates),
        "distinct_topology_count": distinct,
        "distinct_topologies_confirmed": distinct == len(candidates),
        "status": "DIVERSE" if distinct == len(candidates) else "REPEATED_TOPOLOGY",
        "note_ar": (
            "البدائل ذات شبكات علاقات مختلفة وفق الأبواب الممثلة؛ لا يثبت ذلك جودة التخطيط."
            if distinct == len(candidates)
            else "بعض البدائل تعيد شبكة العلاقات نفسها مع تغيير الأبعاد؛ لا تُعرض كحلول معمارية مستقلة."
        ),
    }
