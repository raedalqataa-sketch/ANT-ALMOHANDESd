import pytest
from backend.design.architect_planner import ClientIntent, propose


def sample(**changes):
    values = dict(width=20, depth=30, city='الرياض', family=5,
                  street_edges=['bottom'], main_street='bottom')
    values.update(changes)
    return ClientIntent(**values)


def evidence(**updates):
    result = dict(source='scaled_image', area_m2=600, point_count=4,
                  review_required=True)
    result.update(updates)
    return result


def test_measurement_source_is_preserved_in_program_with_pending_survey():
    brief, planning = propose(sample(site_evidence=evidence()))
    assert brief.plot_width == 20 and brief.plot_depth == 30
    assert planning['site_evidence']['source'] == 'scaled_image'
    assert planning['original_intent']['site_evidence']['review_required'] is True
    assert any('مساحيًا' in warning for warning in planning['warnings'])
    assert planning['setbacks']['local_parcel_verified'] is False


def test_manual_intake_remains_backward_compatible():
    _, planning = propose(sample())
    assert planning['site_evidence'] is None


@pytest.mark.parametrize('bad', [
    dict(area_m2=750),
    dict(point_count=1),
    dict(review_required=False),
    dict(source='auto_cadastral'),
])
def test_unverified_or_inconsistent_evidence_rejected(bad):
    with pytest.raises(ValueError):
        sample(site_evidence=evidence(**bad))


def test_gps_site_evidence_is_mandatorily_reviewable_not_a_survey():
    _, planning = propose(sample(site_evidence=evidence(source='gps_corners')))
    assert planning['site_evidence']['review_required']
    assert planning['site_evidence']['point_count'] == 4
    assert 'latitude' not in str(planning['site_evidence'])
