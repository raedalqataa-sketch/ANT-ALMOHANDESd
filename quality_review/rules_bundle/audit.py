"""Inspect the supplied reference package without activating its rules."""
import hashlib
import json
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2]/'constitution'/'references'/'floor_plan_rules_v1.json'
OUT = Path(__file__).resolve().parent

def pointer(document, ref):
    node = document
    for part in ref.strip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node

def main():
    doc = json.loads(SOURCE.read_text())
    sources = {s['source_id']: s for s in doc['source_documents']}
    catalogs = doc['rule_catalog']
    ids = [r['rule_id'] for rules in catalogs.values() for r in rules]+[c['id'] for c in doc['user_constraints']]
    hash_failures=[]
    pointers=[]
    refs=[]
    for s in sources.values():
        raw=json.dumps(s['content'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        actual=hashlib.sha256(raw).hexdigest()
        if actual != s['content_sha256_canonical_json']:
            hash_failures.append(s['source_id'])
    for item in doc['source_index']:
        try:
            if pointer(doc,item['embedded_pointer']) != sources[item['source_id']]['content']:
                pointers.append(item['source_id'])
        except (KeyError,IndexError,ValueError,TypeError):
            pointers.append(item['source_id'])
    for rules in catalogs.values():
        for rule in rules:
            for ref in rule.get('source_refs',[]):
                if ref not in sources:
                    refs.append({'rule_id':rule['rule_id'],'ref':ref})
            if 'source_details_pointer' in rule:
                try:
                    pointer(doc,rule['source_details_pointer'])
                except (KeyError,IndexError,ValueError,TypeError):
                    pointers.append(rule['rule_id'])
    findings={
        'filename':SOURCE.name,
        'file_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'json_valid':True,
        'embedded_source_count':len(sources),
        'catalog_counts':{k:len(v) for k,v in catalogs.items()},
        'explicit_constraint_count':len(doc['user_constraints']),
        'unique_rule_constraint_ids':len(set(ids)),
        'duplicate_rule_constraint_ids':[k for k,n in Counter(ids).items() if n>1],
        'source_hash_method':'UTF-8, ensure_ascii=False, sort_keys=True, separators=(comma,colon)',
        'source_hash_mismatches':hash_failures,
        'unresolved_catalog_source_refs':refs,
        'source_pointer_errors':pointers,
        'counts_match':doc['counts']=={'source_documents':len(sources),'canonical_engine_rules':len(catalogs['canonical_engine_rules']),'adopted_image_patterns':len(catalogs['adopted_image_patterns']),'explicit_user_constraints':len(doc['user_constraints']),'proposed_engineering_specification_rules':len(catalogs['proposed_engineering_specification'])},
        'verification_limits':['Checks validate the supplied JSON internal consistency, not the historical authenticity of its embedded sources.','The current application engine is not certified by reference text or by its SITE_V9 implementation snapshot.','No rules were activated and no application or project parameters were changed.','Not a full semantic conflict audit of all embedded source text.'],
        'known_gaps':doc['known_gaps'],
    }
    (OUT/'audit_results.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2))
    print(json.dumps(findings,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
