import copy,json
from itertools import combinations
import pytest
from backend.design.architect_planner import ClientIntent,propose,generate_automatic
from backend.design.design_selection import difference,evaluate,select
from backend.design.general_models import VillaBrief
from backend.design.general_engine import validate_general,export_general_model

def intent(**kw):return ClientIntent(**{'width':24,'depth':32,'city':'الرياض','family':6,'street_edges':['bottom'],**kw})

@pytest.mark.parametrize('level',['economy','standard','luxury'])
@pytest.mark.parametrize('priority',['efficiency','usability','prestige'])
def test_tiers_and_priorities_independent_and_legacy_fields_migrate(level,priority):
 b,p=propose(intent(output_level=level,design_priority=priority))
 assert p['original_intent']['output_level']==level and p['original_intent']['design_priority']==priority
 assert sum(r.count*r.capacity for r in b.rooms)==6
 assert b.corridor_width=={'economy':1.3,'standard':1.5,'luxury':1.65}[level]
 # Priority ranks layouts; it must not silently rewrite required program areas.
 other,_=propose(intent(output_level=level,design_priority='usability'))
 assert b.rooms==other.rooms

def test_house_program_and_circulation_differ_from_villa_without_losing_capacity():
 villa,_=propose(intent(building='villa'));house,_=propose(intent(building='house'))
 assert house.building_type=='house' and villa.building_type=='villa'
 assert house.corridor_width<villa.corridor_width
 assert sum(r.min_area*r.count for r in house.rooms)<sum(r.min_area*r.count for r in villa.rooms)
 assert {r.id for r in house.rooms}=={r.id for r in villa.rooms}

@pytest.fixture(scope='module')
def real_results(tmp_path_factory):
 folder=tmp_path_factory.mktemp('adaptive-real');i=intent(country='YE',region='محافظة يدوية',city='مدينة يدوية',district='مديرية يدوية',neighborhood='حي يدويا')
 return i,folder,generate_automatic(i,folder)

def test_actual_three_are_distinct_not_renamed_copies_and_keep_program(real_results):
 i,folder,result=real_results
 assert len(result['candidates'])==3
 assert result['planning']['design_selection']['search_variants_examined']>=7
 for a,b in combinations(result['candidates'],2):assert difference(a,b)['distinct']
 for m in result['candidates']:
  assert not [c for c in validate_general(m,VillaBrief(**m['brief'])) if c['status']=='FAIL']
  assert sum(bool(r.get('request_id')) for f in m['floors'] for r in f['rooms'])==sum(r['count'] for r in result['planning']['program'])
  assert m['design_option']['advantages'] and m['design_evaluation']['metrics']['functional_routes']
  assert m['design_evaluation']['metrics']['mean_functional_route_m']>0

def test_yemen_exports_never_apply_saudi_rules_and_retain_manual_location(real_results):
 import ezdxf
 i,folder,result=real_results
 for m in result['candidates']:
  checks=m['checks'];assert not any(c['check_id'].startswith('SA-') for c in checks)
  assert all(c['status']=='PENDING' for c in checks if c['check_id'].startswith('YE-'))
  assert len([c for c in checks if c['check_id'].startswith('YE-')])==5
  assert m['brief']['district']==i.district and m['brief']['neighborhood']==i.neighborhood
  assert m['parking_basis']['jurisdiction']=='YE'
  exported=json.loads((folder/(m['model_revision_id']+'.json')).read_text())
  assert exported['planning']['original_intent']['country']=='YE'
  d=ezdxf.readfile(folder/(m['model_revision_id']+'.dxf'));assert d.dxfversion=='AC1024' and not d.audit().errors
  assert not list(d.modelspace().query('HATCH SOLID TRACE 3DFACE'))
  from backend.design.general_drawing import review_drawing,drawing
  labels=' '.join(p.get('text','') for p in review_drawing(m).items)
  assert 'momah.gov.sa' not in labels
  layers={p['layer'] for p in drawing(m,m['floors'][0],site_view=True).items}
  assert {'NORTH','STREET'}<=layers


def test_real_objective_scores_change_and_duplicate_names_do_not_make_diversity(real_results):
 i,_,result=real_results;m=result['candidates'][0]
 scores=[evaluate(m,i.model_copy(update={'design_priority':p}))['heuristic_score'] for p in ('efficiency','usability','prestige')]
 assert len(set(scores))==3
 clone=copy.deepcopy(m);clone['candidate_id']='renamed-shape';clone['design_option']['title']='اسم مختلف'
 assert not difference(m,clone)['distinct'] and len(select([m,clone]))==1

def test_failed_candidate_never_fills_third_slot_or_exports(real_results,tmp_path):
 _,_,result=real_results;m=copy.deepcopy(result['candidates'][0]);m['release']['drawing_export_allowed']=False
 m['checks'].append({'check_id':'GF-overlap','status':'FAIL'})
 assert select([m])==[]
 with pytest.raises(ValueError):export_general_model(m,VillaBrief(**m['brief']),tmp_path)
 assert not list(tmp_path.glob('*.pdf')) and not list(tmp_path.glob('*.dxf'))
