from shapely.geometry import box

def test_shared_edge_rejects_point_and_narrow_contact():
 from assl.openings_009 import shared_edge
 a=dict(x=0,y=0,width=3,depth=3)
 assert shared_edge(a,dict(x=3,y=3,width=2,depth=2)) is None
 assert shared_edge(a,dict(x=3,y=2.5,width=2,depth=2))['length']==.5

def test_body_route_goes_around_obstacle_and_rejects_slit():
 from assl.openings_009 import shortest_path
 region=box(0,0,8,8).difference(box(3,0,5,6))
 route=shortest_path(region,(1,1),(7,1))
 assert route and route['length_m']>12
 assert shortest_path(box(0,0,4,.4),(1,.2),(3,.2),body=.6) is None

def test_private_transit_not_in_access_graph():
 from assl.openings_009 import accessible
 doors=[dict(connects=['entry','bed']),dict(connects=['bed','kitchen'])]
 assert not accessible(doors,'entry','kitchen',{'bed'})

def test_off_host_opening_is_rejected():
 from assl.openings_009 import opening_fits
 wall=dict(axis='x',fixed=0,lo=0,hi=3,length=3)
 assert opening_fits(dict(axis='x',center=[1.5,0],width=.9),wall)
 assert not opening_fits(dict(axis='x',center=[1.5,1],width=.9),wall)

def test_repair_does_not_mutate_source_or_move_stairs():
 import copy,json
 from pathlib import Path
 from backend.design.general_models import VillaBrief
 from assl.free_layout_solver import solve_free_concepts
 from assl.openings_009 import revise
 case=json.loads((Path(__file__).parent/'fixtures/assl_architecture_cases.json').read_text())['cases'][2]
 brief=VillaBrief.model_validate(case['brief'])
 source=solve_free_concepts(brief,seeds=range(2),max_results=1,topologies=('axial',),orient_to_frontage=True)['proposals'][0]
 original=copy.deepcopy(source);result=revise(brief,source)
 assert source==original
 assert [[r for r in f if r['kind']=='stair'] for f in result['rooms_by_floor']]==[[r for r in f if r['kind']=='stair'] for f in source['rooms_by_floor']]
 assert 'relocations_009' in result

def test_window_label_does_not_override_actual_outdoor_obstruction():
 from assl.openings_009 import window_clear
 r=dict(id='r',x=0,y=0,width=4,depth=4)
 w=dict(axis='x',center=[2,0],width=.8,height=1.2,operable_fraction=.5)
 obstacle=dict(id='block',x=0,y=-2,width=4,depth=1.9)
 assert window_clear(w,r,[r],.2)
 assert not window_clear(w,r,[r,obstacle],.2)

def valid_case():
 import json
 from pathlib import Path
 from backend.design.general_models import VillaBrief
 root=Path(__file__).parent/'fixtures'
 return VillaBrief.model_validate(json.loads((root/'assl_architecture_cases.json').read_text())['cases'][0]['brief']),json.loads((root/'assl_openings_009_valid.json').read_text())

def test_actual_nine_case_fixture_has_valid_access_without_furnishing():
 from assl.openings_009 import validate
 b,p=valid_case();assert validate(b,p)['status']=='PASS'

def test_duplicate_door_geometry_cannot_pass():
 import copy
 from assl.openings_009 import validate
 b,p=valid_case();p['opening_model_009'][0]['doors'].append(copy.deepcopy(p['opening_model_009'][0]['doors'][0]))
 assert validate(b,p)['status']=='FAIL'

def test_detached_window_and_removed_entry_cannot_pass():
 from assl.openings_009 import validate
 b,p=valid_case();p['opening_model_009'][0]['windows'][0]['center'][0]+=1
 assert validate(b,p)['status']=='FAIL'
 b,p=valid_case();p['opening_model_009'][0]['doors']=[d for d in p['opening_model_009'][0]['doors'] if d['id']!='guest-entry']
 assert validate(b,p)['status']=='FAIL'

def test_perpendicular_or_nonfinite_opening_cannot_pass():
 from assl.openings_009 import validate
 b,p=valid_case();w=p['opening_model_009'][0]['windows'][0];w['axis']='x' if w['axis']=='y' else 'y'
 assert validate(b,p)['status']=='FAIL'
 b,p=valid_case();p['opening_model_009'][0]['windows'][0]['height']=float('nan')
 assert validate(b,p)['status']=='FAIL'

def test_full_window_span_must_be_unobstructed():
 from assl.openings_009 import validate
 b,p=valid_case();w=p['opening_model_009'][0]['windows'][3];w.update(axis='x',center=[6.6,7.25],width=.8)
 assert validate(b,p)['status']=='FAIL'
