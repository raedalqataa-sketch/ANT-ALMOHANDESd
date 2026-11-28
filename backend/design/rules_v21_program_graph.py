"""V2.1 program graph, before geometric allocation.

Edges describe requested relationships, not proven door connectivity.
Unknown targets remain unresolved rather than being silently dropped.
"""
from collections import Counter

def build_program_graph(document):
    rows=document.get("program")
    if not isinstance(rows,list) or not rows:
        raise ValueError("program missing")
    nodes={}
    for row in rows:
        key=row.get("id")
        if not isinstance(key,str) or not key or key in nodes:
            raise ValueError("invalid or duplicate program id")
        nodes[key]={k:row.get(k) for k in ("type","count","required","allowed_floors","privacy_zone","area_min_m2","area_target_m2","area_max_m2")}
    edges=[]
    unresolved=[]
    conflicts=[]
    for row in rows:
        source=row["id"]
        relations={}
        for field in ("adjacency_required","adjacency_forbidden"):
            values=row.get(field)
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values):
                unresolved.append({"source":source,"field":field,"reason":"missing or invalid relationship list"})
                continue
            relations[field]=set(values)
            for target in sorted(set(values)):
                edge={"source":source,"target":target,"kind":field}
                if target not in nodes:
                    unresolved.append(dict(edge,reason="target not resolved to program id"))
                else:
                    edges.append(edge)
        for target in sorted(relations.get("adjacency_required",set()) & relations.get("adjacency_forbidden",set())):
            conflicts.append({"source":source,"target":target,"reason":"required and forbidden"})
    pairs={}
    for edge in edges:
        pair=tuple(sorted((edge["source"],edge["target"])))
        pairs.setdefault(pair,set()).add(edge["kind"])
    for pair,kinds in sorted(pairs.items()):
        if len(kinds)>1:
            conflicts.append({"source":pair[0],"target":pair[1],"reason":"contradictory undirected adjacency"})
    return {"nodes":nodes,"edges":edges,"unresolved":unresolved,"conflicts":conflicts,
            "status":"fail" if conflicts else "needs_data" if unresolved else "graph_ready"}

def check_program_counts(document, realized_counts):
    """PROGRAM-001: counts keyed by original program ID; no geometry inference."""
    if not isinstance(realized_counts,dict):
        return {"rule_id":"PROGRAM-001","status":"needs_data"}
    graph=build_program_graph(document)
    missing=[]; violations=[]
    for key,node in graph["nodes"].items():
        if node["required"] is False:
            continue
        expected=node["count"]
        if node["required"] is not True or type(expected) is not int or expected<1 or type(realized_counts.get(key)) is not int:
            missing.append(key)
        elif realized_counts[key]!=expected:
            violations.append(key)
    return {"rule_id":"PROGRAM-001","status":"fail" if violations else "needs_data" if missing else "pass",
            "violations":violations,"missing":missing}
