"""Actual polygon overlays must reconcile against emitted floor cells and walls."""
from copy import deepcopy
from types import SimpleNamespace
from backend.design.saudi_2024_overlay import evaluate, valid_polygon, polygon_intersection


def room(id, x, y, width, depth):
    return dict(id=id, x=x, y=y, width=width, depth=depth, kind='bedroom')


def wall(id, room_id, a, b, axis):
    return dict(id=id, start=a, end=b, axis=axis, room_ids=[room_id], exterior=True)


def sketch():
    gf=room('GF-A',2,2,4,6)
    ff=room('FF-A',5,14,6,3)
    return {
        'site':{'width':20,'depth':20},
        'regulatory_geometry':{},
        'footprint':{'polygons_by_floor':{
            'FF':[[[5,14],[11,14],[11,17],[5,17]]],
            'GF':[[[2,2],[6,2],[6,8],[2,8]]]}},
        'floors':[
            {'id':'GF','cells':[gf], 'rooms':[gf],
             'walls':[wall('GF-W1','GF-A',[6,2],[6,8],'vertical')],
             'openings':[dict(id='GF-O1',kind='window',wall_id='GF-W1',center=[6,4])]},
            {'id':'FF','cells':[ff], 'rooms':[ff],
             'walls':[wall('FF-W1','FF-A',[5,17],[11,17],'horizontal')],
             'openings':[]},
        ],
        'metrics': {'floor_built_by_id':{'GF':24,'FF':18}},
    }


def brief():
    return SimpleNamespace(boundary_widths={'south':15,'north':0,'east':0,'west':0},
                           setbacks=SimpleNamespace(north=2,south=3,east=2,west=2))


def check(model,key):
    return next(x for x in evaluate(model,brief()) if x['check_id']=='SA-2024-'+key)


def test_orthogonal_geometry_parser_excludes_self_intersection():
    assert valid_polygon([[1,1],[4,1],[4,3],[1,3]])
    assert not valid_polygon([[1,1],[4,1],[1,3],[4,3]]) # diagonal
    assert not valid_polygon([[1,1],[4,1],[4,4],[3,4],[3,2],[2,2],[2,4],[1,4],[1,1]])
    assert polygon_intersection([[0,0],[1,0],[1,1],[0,1]],
                                [[1,0],[2,0],[2,1],[1,1]]) is False
    assert polygon_intersection([[0,0],[1,0],[1,1],[0,1]],
                                [[.5,0],[2,0],[2,1],[.5,1]]) is True


def test_lightwell_requires_clear_occupied_geometry_and_real_window():
    m=sketch()
    m['regulatory_geometry']={'light_wells':[{
        'id':'LW1','width_m':2,'length_m':2,'storeys_served':1,
        'opposing_windows':False,'polygon':[[6,3],[8,3],[8,5],[6,5]],
        'window_ids':['GF-O1']}]}
    assert check(m,'lightwell-opening-overlay')['status']=='PASS'
    m['regulatory_geometry']['light_wells'][0]['polygon']=[[5,3],[7,3],[7,5],[5,5]]
    assert check(m,'lightwell-opening-overlay')['status']=='FAIL'
    m['regulatory_geometry']['light_wells'][0]['polygon']=[[6,3],[8,3],[8,5],[6,5]]
    m['regulatory_geometry']['light_wells'][0]['window_ids']=['missing']
    assert check(m,'lightwell-opening-overlay')['status']=='FAIL'
    m['regulatory_geometry']['light_wells'][0].pop('polygon')
    assert check(m,'lightwell-opening-overlay')['status']=='PENDING'


def test_annex_polygon_measures_area_and_parent_boundary():
    m=sketch()
    m['regulatory_geometry']={'roof_annex':{
        'area_m2':9,'polygon':[[6,14],[9,14],[9,17],[6,17]]}}
    # South touches the lower-floor south facade (0 m; required 1.5 m)
    assert check(m,'annex-footprint-overlay')['status']=='FAIL'
    m['regulatory_geometry']['roof_annex']={
        'area_m2':2,'polygon':[[7,14.5],[9,14.5],[9,15.5],[7,15.5]]}
    assert check(m,'annex-footprint-overlay')['status']=='PASS'
    m['regulatory_geometry']['roof_annex']['area_m2']=4
    assert check(m,'annex-footprint-overlay')['status']=='FAIL'
    m['regulatory_geometry']['roof_annex']['polygon']=[[7,14.5],[12,14.5],[12,15.5],[7,15.5]]
    m['regulatory_geometry']['roof_annex']['area_m2']=5
    assert check(m,'annex-footprint-overlay')['status']=='PENDING' # cantilever needs special assessment


def test_projection_reconciles_depth_and_setback():
    m=sketch()
    m['regulatory_geometry']={'projections':[{
        'id':'P1','floor_id':'FF','face':'south','kind':'balcony',
        'depth_m':1.0,'within_setback':True,'crosses_property_line':False,
        'polygon':[[7,17],[9,17],[9,18],[7,18]]}]}
    assert check(m,'projection-geometry-overlay')['status']=='PASS'
    m['regulatory_geometry']['projections'][0]['depth_m']=1.5
    assert check(m,'projection-geometry-overlay')['status']=='FAIL'
    m['regulatory_geometry']['projections'][0]['depth_m']=1
    m['regulatory_geometry']['projections'][0]['face']='west'
    assert check(m,'projection-geometry-overlay')['status']=='FAIL'


def test_facade_equipment_uses_measured_wall_intersections():
    m=sketch()
    m['regulatory_geometry']={'facades':[{
        'face':'south','faces_main_street':True,'inventory_complete':True,
        'equipment':[{'id':'AC1','x':7,'y':16.9,'width':.7,'depth':.3,'floor_id':'FF'}]}]}
    assert check(m,'facade-equipment-overlay')['status']=='FAIL'
    m['regulatory_geometry']['facades'][0]['equipment']=[]
    assert check(m,'facade-equipment-overlay')['status']=='PASS'
    m['regulatory_geometry']['facades'][0]['inventory_complete']=None
    assert check(m,'facade-equipment-overlay')['status']=='PENDING'


def test_partial_data_never_certifies_geometry():
    m=sketch()
    for k in ('lightwell-opening-overlay','annex-footprint-overlay',
              'projection-geometry-overlay','facade-equipment-overlay'):
        assert check(m,k)['status']=='PENDING'
        assert check(m,k)['source']['sbc_full_text_verified'] is False
