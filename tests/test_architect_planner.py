import pytest
from backend.design.architect_planner import ClientIntent,propose,generate_automatic
from backend.design.saudi_rules import required_setbacks

def intent(**kw):return ClientIntent(**{'width':24,'depth':32,'city':'الرياض','family':6,'street_edges':['bottom'],'main_street':'bottom','street_widths':{'bottom':15},**kw})
@pytest.mark.parametrize('family',range(1,13))
def test_program_proposes_exact_sleeping_capacity_and_source_bound_setbacks(family):
 b,p=propose(intent(family=family));assert sum(r.count*r.capacity for r in b.rooms)==family
 assert b.setbacks.model_dump()==required_setbacks(b)
 assert p['setbacks']['local_parcel_verified'] is False
 assert all(r.min_area>0 and r.min_side>0 for r in b.rooms)
 assert all(any(r.floor==f for r in b.rooms) for f in range(b.floors))
def test_orientation_rotates_dimensions_streets_and_entrance_together():
 b,p=propose(intent(north_edge='right'));assert (b.plot_width,b.plot_depth)==(32,24)
 assert b.entrance_face=='east' and b.boundary_widths['east']==15
 assert p['original_intent']['width']==24
 assert p['orientation']['edge_mapping']['right']=='north'
def test_unknown_street_width_stays_pending_not_a_fabricated_rule():
 b,p=propose(intent(street_widths={}));assert 'south' not in b.boundary_widths
 assert b.setbacks.south==6 and p['setbacks']['unknown_street_faces']==['south']
def test_accessible_bedroom_and_office_are_actual_program_constraints():
 b,p=propose(intent(accessible_bedroom=True,office=True));assert next(r for r in b.rooms if r.kind=='master').floor==0
 assert any(r.kind=='office' and r.floor==0 for r in b.rooms)
 assert any(r.kind=='bathroom' and r.floor==0 and r.id=='auto-ground-bath' for r in b.rooms)
def test_invalid_street_or_unsupported_building_is_rejected():
 with pytest.raises(ValueError):intent(street_edges=['top'])
 with pytest.raises(ValueError):intent(building='apartment')
def test_real_automatic_generation_exports_all_topologies_and_preserves_planning(tmp_path):
 import json,ezdxf
 result=generate_automatic(intent(),tmp_path)
 viable=[m for m in result['candidates'] if m['release']['drawing_export_allowed']]
 assert {m['candidate_id'] for m in viable}=={'L','U','stepped'}
 for m in viable:
  assert sum(r['count']*r['capacity'] for r in m['brief']['rooms'])==6
  j=json.loads((tmp_path/(m['model_revision_id']+'.json')).read_text());assert j['planning']==result['planning']
  d=ezdxf.readfile(tmp_path/(m['model_revision_id']+'.dxf'));assert d.dxfversion=='AC1024' and not d.audit().errors
  assert not m['release']['executive_issue_allowed']
@pytest.mark.parametrize('options',[{'family':2,'majlis':False},{'family':8,'accessible_bedroom':True,'office':True}])
def test_changed_household_changes_actual_program_without_dropping_requests(options,tmp_path):
 b,p=propose(intent(**options));result=generate_automatic(intent(**options),tmp_path)
 assert result['candidates'] or result['unavailable']
 for m in result['candidates']:
  assert sum(r['count']*r['capacity'] for r in m['brief']['rooms'])==options['family']
  if not m['release']['drawing_export_allowed']:
   assert any(c['status']=='FAIL' for c in m['checks'])
  else:assert sum(bool(r.get('request_id')) for f in m['floors'] for r in f['rooms'])==sum(r.count for r in b.rooms)
def test_explicit_single_floor_and_street_setback_changes_are_preserved():
 b,p=propose(intent(floors='one',street_widths={'bottom':40}));assert b.floors==1 and b.setbacks.south==6
 assert all(r.floor==0 for r in b.rooms)
 with pytest.raises(ValueError):intent(street_widths={'bottom':float('nan')})
