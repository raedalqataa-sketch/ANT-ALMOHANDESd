"""Initial V2.1 input checks; partial coverage, never an approval gate alone."""
def result(rule_id,status,reason):
    return dict(rule_id=rule_id,status=status,reason=reason)

def validate_program(document):
    rid="INPUT-001"
    if not isinstance(document,dict) or document.get("program") is None:
        return result(rid,"needs_data","program missing")
    rows=document["program"]
    if not isinstance(rows,list) or not rows:
        return result(rid,"fail","program must be a nonempty list")
    seen=set()
    missing=False
    for row in rows:
        if not isinstance(row,dict):
            return result(rid,"fail","invalid program item")
        if any(row.get(k) is None for k in ("id","count","allowed_floors","required")):
            missing=True
            continue
        key=row["id"]
        count=row["count"]
        floors=row["allowed_floors"]
        if not isinstance(key,str) or not key.strip() or key in seen:
            return result(rid,"fail","invalid or duplicate identifier")
        seen.add(key)
        if not isinstance(row["required"],bool) or type(count) is not int or count<1:
            return result(rid,"fail","invalid count or required flag")
        if not isinstance(floors,list) or not floors:
            return result(rid,"fail","invalid allowed floors")
    if missing:
        return result(rid,"needs_data","program item evidence missing")
    return result(rid,"pass","program identifiers, counts and floor lists present")

def validate_adjacency_conflicts(document):
    rid="INPUT-004"
    rows=document.get("program") if isinstance(document,dict) else None
    if not isinstance(rows,list) or not rows:
        return result(rid,"needs_data","program missing")
    missing=False
    for row in rows:
        if not isinstance(row,dict):
            return result(rid,"needs_data","invalid program item")
        a,b=row.get("adjacency_required"),row.get("adjacency_forbidden")
        if not isinstance(a,list) or not isinstance(b,list) or any(not isinstance(x,str) for x in a+b):
            missing=True
            continue
        if set(a)&set(b):
            return result(rid,"fail","same adjacency required and forbidden")
    return result(rid,"needs_data","full mandatory conflict analysis not implemented" if not missing else "adjacency evidence missing")
