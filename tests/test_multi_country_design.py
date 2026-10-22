import pytest
from backend.design.architect_planner import ClientIntent, propose
from backend.design.general_models import VillaBrief, Setbacks, SpaceRequest


def request(**changes):
    payload=dict(width=24, depth=32, country='YE', region='الحديدة', city='باجل',
                 family=6, street_edges=['bottom'], main_street='bottom',
                 output_level='standard', design_priority='usability')
    payload.update(changes)
    return ClientIntent(**payload)


def test_yemen_plot_preserves_correct_jurisdiction_with_unverified_setbacks():
    brief, plan=propose(request())
    assert brief.country=='YE'
    assert brief.region=='الحديدة'
    assert brief.city=='باجل'
    assert brief.apply_saudi_rules is False
    assert brief.municipality==''
    assert plan['setbacks']['source']['status']=='UNVERIFIED_DESIGN_ASSUMPTION'
    assert plan['setbacks']['local_parcel_verified'] is False
    assert any('اليمن' in warning for warning in plan['warnings'])
    assert plan['original_intent']['country']=='YE'


def test_saudi_region_preserved_and_saudi_lookups_remain_scoped_to_sa():
    brief, plan=propose(request(country='SA',region='الرياض',city='الرياض'))
    assert brief.country=='SA' and brief.apply_saudi_rules
    assert brief.region=='الرياض'
    assert plan['setbacks']['source']['source']


def test_manual_governorate_entry_is_allowed_without_city():
    brief, _=propose(request(region='محافظة أدخلها العميل',city=''))
    assert brief.city=='محافظة أدخلها العميل'


def test_tier_changes_real_requested_room_areas_and_objective_is_recorded():
    econ,_=propose(request(output_level='economy',design_priority='efficiency'))
    lux,plan=propose(request(output_level='luxury',design_priority='prestige'))
    econ_rooms={r.id:r for r in econ.rooms}
    lux_rooms={r.id:r for r in lux.rooms}
    assert lux_rooms['auto-living'].min_area>econ_rooms['auto-living'].min_area
    assert lux_rooms['auto-majlis'].min_area>econ_rooms['auto-majlis'].min_area
    assert plan['original_intent']['design_priority']=='prestige'


def test_investment_classification_is_not_fake_single_family_apartments():
    req=request(building='investment')
    assert req.building=='investment'
    with pytest.raises(ValueError,match='الاستثماري'):
        propose(req)


def test_yemen_cannot_accidentally_enable_saudi_rules():
    kwargs=dict(project_name='مخطط',plot_width=20,plot_depth=30,floors=1,
                setbacks=Setbacks(north=2,south=4,east=2,west=2),
                country='YE',apply_saudi_rules=True,rooms=[SpaceRequest(
                    id='living',name='معيشة',kind='living',floor=0,min_area=20,min_side=3)])
    with pytest.raises(ValueError,match='السعودية'):
        VillaBrief(**kwargs)


def test_invalid_jurisdiction_rejected():
    with pytest.raises(ValueError):
        request(country='US')
