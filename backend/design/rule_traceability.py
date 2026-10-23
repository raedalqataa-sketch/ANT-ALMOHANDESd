"""Complete rule inventory with conservative, evidence-bound implementation status.

A catalogue entry is not an implemented rule. Broad visual guidance is at most
partial even when narrow underlying geometry passes. Original 143-rule source
lacks project-level lineage; exclusions cannot retroactively certify that source.
"""
from collections import Counter
from .constitution_v2 import policy_bundle, MANUS_CROSSWALK, GATE_CHECKS

# Deliberately small, audited crosswalk. A token covers only the stated subset.
VISUAL={
 'A007':('-site',),'A010':('SITE-rear-corner',),'A015':('guest-route',),
 'A027':('guest-distributor-access',),'A033':('guest-distributor-geometry',),
 'A038':('-door-sweeps',),'A050':('guest-route',),
 'A058':('REF-functional-route',),'A060':('-door-sweeps',),
 'A072':('V4-functional-paths',),'A083':('V4-functional-paths',),
 'A089':(),'A109':('-sizes',),
 'A110':('-door-sweeps','V4-furniture-clearance'),
 'A112':('-fixtures','V4-furniture-clearance'),
 'A118':('-openings','V4-furniture-clearance'),
 'A133':('vertical-core',),
}
RELATION_IDS={'E007','E013','E014','E019'}

def matrix(model):
    source=policy_bundle();checks=model.get('checks',[]);rows=[]
    for category,key in (('visual','prior_visual_extraction_143_rules'),('relationship','functional_relationships'),('constraint','manus_constraints_adapted'),('gate','validation_gates')):
        for rule in source[key]:
            rid=rule['id'];tokens=()
            if category=='visual':tokens=VISUAL.get(rid,())
            if category=='relationship' and rid in RELATION_IDS:tokens=('V4-functional-paths',)
            if category=='constraint':tokens=GATE_CHECKS.get(MANUS_CROSSWALK[rid],())
            if category=='gate':tokens=GATE_CHECKS.get(rid,())
            groups=[[c for c in checks if t in c.get('check_id','')] for t in tokens]
            evidence=[c for g in groups for c in g];complete=bool(groups) and all(groups)
            # Do not turn a broad principle into implemented via one partial validator.
            implementation='PARTIALLY_COMPLETED' if tokens else 'NOT_IMPLEMENTED'
            runtime='FAIL' if any(c['status']=='FAIL' for c in evidence) else 'REVIEW'
            if complete and all(c['status'] in ('PASS','NOT_APPLICABLE') for c in evidence):runtime='PASS_PARTIAL_SCOPE_ONLY'
            # A relationship must have actual measured routes, not a global PASS on no pairs.
            relation=[r for r in model.get('functional_program_v4',{}).get('movement',{}).get('routes',[]) if r.get('source_rule')==rid] if category=='relationship' else None
            if category=='relationship':
                evidence=[]
                if relation:
                    implementation='PARTIALLY_COMPLETED';runtime='FAIL' if any(r['status']=='UNREACHABLE' for r in relation) else 'PASS_PARTIAL_SCOPE_ONLY'
                else:runtime='REVIEW'
            rows.append({'rule_id':rid,'category':category,'inputs':['brief','floors.rooms','walls','openings','furniture'],
                'applicability':rule.get('applicability',rule.get('when',rule.get('applies','requires_case_review'))),
                'enforcement':list(tokens),'evidence_check_ids':sorted({c['check_id'] for c in evidence}),
                'relationship_evidence':relation,'test':(['tests/test_reference_patterns.py','tests/test_v4_engine.py'] if tokens else []),
                'implementation_status':implementation,'runtime_status':runtime,
                'pending_reason':'only the named geometric subset is enforced; remaining meaning needs review' if tokens else 'no verified enforcement/test crosswalk for this complete rule',
                'source_provenance':'PENDING_PROJECT_LEVEL_REVALIDATION_AFTER_P02_P05_EXCLUSION' if category=='visual' else 'design_policy_not_statutory_code'})
    return {'revision':'rule-traceability-4','rule_count':len(rows),'counts':dict(Counter(r['implementation_status'] for r in rows)),
            'rows':rows,'complete_code_coverage':False,'legal_approval':False,
            'source_note':'143 original policy statements retained as supplied specification; their visual project-level lineage is unknown. They are not newly inferred from excluded projects or claimed as six-project-verified rules.'}
