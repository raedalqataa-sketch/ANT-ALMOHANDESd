"""Verify the actual browser-downloaded model against native geometry and CAD."""
import json
from pathlib import Path
import ezdxf
from backend.design.general_engine import generate_general
from backend.design.general_models import VillaBrief
p=Path('/workspace/automatic-browser-qa')
browser=json.loads((p/'features.json').read_text())
b=VillaBrief(**browser['brief']);native=generate_general(b,p/'native')
m=next(m for m in native['candidates'] if m['candidate_id']==browser['candidate_id'])
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if k not in ('revision_id','model_revision_id')}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,float):return round(x,6)
    return x
for key in ('floors','stairs','stair_arrivals','parking','service_yard','footprint','regulatory_geometry','metrics'):
    assert clean(m[key])==clean(browser[key]),key
cad=ezdxf.readfile(p/'features.dxf');assert cad.dxfversion=='AC1024' and not cad.audit().errors
assert not list(cad.modelspace().query('HATCH SOLID'))
evidence={'native_wasm_geometry_parity':['floors including cells/rooms/walls/openings/furniture/annotations','stairs','stair_arrivals','parking','service_yard','footprint','regulatory_geometry','metrics'],'float_tolerance_m':.000001,'dxf_version':cad.dxfversion,'dxf_audit_errors':0,'HATCH_SOLID_count':0,'executive_approval':False}
(p/'export-evidence.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence))
