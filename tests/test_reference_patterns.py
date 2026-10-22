import copy,json
from pathlib import Path
from types import SimpleNamespace
from backend.design.reference_patterns import graph,route,wet_alignment,outlook,checks,PROJECTS,RULES


def floor_with_shortcut(kind='bedroom',zone='family'):
 rooms=[dict(id='K',kind='kitchen',x=0,y=0,width=3,depth=3,request_id='k'),
        dict(id='B',kind=kind,zone=zone,x=3,y=0,width=3,depth=3,request_id='b'),
        dict(id='D',kind='dining',x=6,y=0,width=3,depth=3,request_id='d'),
        dict(id='H',kind='corridor',x=0,y=3,width=9,depth=1.5)]
 walls=[];openings=[]
 for wid,ids,axis,start,end,center in [('KB',['K','B'],'vertical',[3,0],[3,3],[3,1.5]),('BD',['B','D'],'vertical',[6,0],[6,3],[6,1.5]),('KH',['K','H'],'horizontal',[0,3],[3,3],[1.5,3]),('DH',['D','H'],'horizontal',[6,3],[9,3],[7.5,3])]:
  walls.append(dict(id=wid,room_ids=ids,axis=axis,start=start,end=end))
  openings.append(dict(id='O'+wid,wall_id=wid,kind='door',connects=ids,center=center,width=.8))
 return {'id':'GF','rooms':rooms,'walls':walls,'openings':openings,'cells':[rooms[-1]]}


def test_private_and_guest_rooms_cannot_be_shortcuts_but_longer_hall_route_is_used():
 for kind,zone in [('bedroom','family'),('master','family'),('bathroom','family'),('living','guest')]:
  f=floor_with_shortcut(kind,zone);rooms,g=graph(f)
  assert route(rooms,g,'K','D')>6
  f['openings']=[o for o in f['openings'] if o['wall_id']!='KH'];rooms,g=graph(f)
  assert route(rooms,g,'K','D') is None
  result=checks({'floors':[f]},SimpleNamespace(reference_strategy='design-principles-v1'))
  assert result[0]['status']=='FAIL'
  assert checks({'floors':[f]},SimpleNamespace(reference_strategy='none'))==[]


def test_unhosted_or_off_wall_door_cannot_invent_a_service_route():
 f=floor_with_shortcut();f['openings']=[o for o in f['openings'] if o['wall_id']!='KH']
 f['openings'].append(dict(id='fake',wall_id='missing',kind='door',connects=['K','D'],center=[0,0],width=.8))
 rooms,g=graph(f);assert route(rooms,g,'K','D') is None
 f['openings'].append(dict(id='off',wall_id='KH',kind='door',connects=['K','H'],center=[1.5,10],width=.8))
 rooms,g=graph(f);assert route(rooms,g,'K','D') is None


def test_wet_overlap_measures_real_geometry_not_labels_or_floor_names():
 m={'floors':[{'rooms':[dict(id='a',kind='kitchen',request_id='a',x=0,y=0,width=4,depth=4)]},
              {'rooms':[dict(id='b',kind='bathroom',request_id='b',x=0,y=0,width=2,depth=2)]}]}
 assert wet_alignment(m)['ratio']==1
 m['floors'][1]['rooms'][0]['x']=3
 assert wet_alignment(m)['ratio']==.5
 m['floors'][1]['rooms'][0]['x']=10
 assert wet_alignment(m)['ratio']==0
 assert wet_alignment({'floors':m['floors'][:1]})['ratio'] is None


def test_courtyard_window_stops_at_opposite_wing_before_plot_boundary():
 r=dict(id='L',kind='living',request_id='l',x=0,y=0,width=4,depth=4)
 f={'id':'GF','rooms':[r],'cells':[r,dict(id='wing',x=7,y=0,width=2,depth=4)],
    'walls':[dict(id='w',axis='vertical',exterior=True)],
    'openings':[dict(kind='window',wall_id='w',connects=['L'],center=[4,2])]}
 m={'site':{'width':15,'depth':20},'floors':[f]}
 assert outlook(m)[0]['best_unobstructed_own_plot_depth_m']==3
 f['cells']=f['cells'][:1]
 assert outlook(m)[0]['best_unobstructed_own_plot_depth_m']==11


def test_catalogue_has_eight_projects_23_unique_images_and_no_extracted_laws():
 root=Path(__file__).resolve().parents[1]
 c=json.loads((root/'quality_review/reference_library/catalog.json').read_text())
 assert len(c['projects'])==8 and c['unique_images']==23 and c['uploads_including_duplicate']==24
 hashes=[i['sha256'] for p in c['projects'] for i in p['images']]
 assert len(set(hashes))==23 and c['duplicates'][0]['sha256'] in hashes
 assert c['legal_rules_extracted']==0 and not c['personal_data_extracted']
 assert all(not p['raw_images_published'] and not p['legal_compliance_verified'] for p in c['projects'])
 assert set(PROJECTS)=={p['id'] for p in c['projects']}
 assert all(set(r['sources'])<=set(PROJECTS) for r in RULES)
 assert 'LABEL_FIRST' in [i['floor_classification'] for i in c['projects'][1]['images']]


def test_swapping_identical_bedroom_instance_ids_is_not_a_new_design():
 from backend.design.design_selection import difference
 rooms=[dict(id='B1',request_id='children',kind='bedroom',capacity=2,x=0,y=0,width=4,depth=5),dict(id='B2',request_id='children',kind='bedroom',capacity=2,x=6,y=0,width=4,depth=5)]
 a={'floors':[{'id':'FF','rooms':rooms,'cells':rooms}],'design_evaluation':{'metrics':{'normalized_rooms':{'FF:B1':(.2,.5,.4,1),'FF:B2':(.8,.5,.4,1)}}}}
 b=copy.deepcopy(a);b['floors'][0]['rooms'][0]['id']='B2';b['floors'][0]['rooms'][1]['id']='B1'
 b['design_evaluation']['metrics']['normalized_rooms']={'FF:B1':(.8,.5,.4,1),'FF:B2':(.2,.5,.4,1)}
 assert difference(a,b)['semantic_duplicate'] and not difference(a,b)['distinct']
 # A real spatial change to the two-bedroom grouping is still measured.
 b['floors'][0]['rooms'][1]['x']=2;b['floors'][0]['rooms'][1]['y']=5
 b['design_evaluation']['metrics']['normalized_rooms']['FF:B1']=(.4,.8,.4,.5)
 assert 'semantic_duplicate' not in difference(a,b)
