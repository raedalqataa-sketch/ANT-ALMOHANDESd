"""Independent tests of real geometry, door hosts, and the privacy boundary."""
import copy
import pytest
from tests.test_general import brief
from backend.design.general_engine import search,materialize,make_guest_distributor,validate_general
from backend.design.general_quality import privacy_evidence

@pytest.fixture(scope='module')
def generated():
    b=brief();m=materialize(b,'L',search(b,'L'))
    return b,m


def test_real_distributor_has_closed_walls_and_three_hosted_doors(generated):
    b,m=generated;f=m['floors'][0]
    assert make_guest_distributor(f,b,m['model_revision_id'])
    dist=next(r for r in f['rooms'] if r.get('guest_distributor'))
    assert dist['area_m2']>0 and min(dist['width'],dist['depth'])>=b.corridor_width
    ports=[o for o in f['openings'] if o['kind']=='door' and dist['id'] in o['connects']]
    assert len(ports)==3
    assert any(a['room_id']==dist['id'] and a.get('dimension') for a in f['annotations'])
    assert any(o.get('guest_entry') and 'OUTSIDE' in o['connects'] for o in ports)
    assert not privacy_evidence(m)['family_rooms_exposed']
    assert all(r.get('guest_vestibule') for r in f['rooms'] if r.get('request_id') and r.get('zone')=='guest')


@pytest.mark.parametrize('tamper',['wall','off_wall','wrong_host','direct_wc','family_door','net_geometry','wc_net_position','wc_cell_position'])
def test_broken_geometry_is_rejected_even_with_cached_success(generated,tamper):
    b,source=generated;m=copy.deepcopy(source);f=m['floors'][0]
    dist=next(r for r in f['rooms'] if r.get('guest_distributor'))
    entry=next(o for o in f['openings'] if o.get('guest_entry'))
    wc=next(r for r in f['rooms'] if r.get('guest_parent') and r['kind']=='bathroom')
    maj=next(r for r in f['rooms'] if r['kind']=='majlis')
    if tamper=='wall':f['walls']=[w for w in f['walls'] if w['id']!=entry['wall_id']]
    elif tamper=='off_wall':entry['center'][0]+=.37;entry['center'][1]+=.37
    elif tamper=='wrong_host':entry['wall_id']=next(w['id'] for w in f['walls'] if dist['id'] not in w['room_ids'])
    elif tamper=='direct_wc':next(o for o in f['openings'] if o['kind']=='door' and wc['id'] in o['connects'])['connects']=[wc['id'],maj['id']]
    elif tamper=='family_door':f['openings'].append(dict(kind='door',connects=[dist['id'],next(r['id'] for r in f['rooms'] if r['kind']=='corridor' and not r.get('guest_distributor'))]))
    elif tamper=='wc_net_position':wc['x']+=.2
    elif tamper=='wc_cell_position':next(c for c in f['cells'] if c['id']==wc['id'])['x']+=.2
    else:dist['width']+=.2
    assert f['guest_distributor_constructed'] is True
    assert make_guest_distributor(f,b,m['model_revision_id']) is False
    assert next(c for c in validate_general(m,b) if c['check_id']=='guest-distributor-geometry')['status']=='FAIL'


def test_majlis_without_guest_bath_still_has_independent_vestibule():
    b=brief();b.rooms=[r for r in b.rooms if 'ضيف' not in r.name]
    m=materialize(b,'L',search(b,'L'))
    assert any(r.get('guest_distributor') for r in m['floors'][0]['rooms'])
    assert make_guest_distributor(m['floors'][0],b,m['model_revision_id'])
