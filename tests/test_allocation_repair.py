from backend.design.allocation_repair import reassign_bundles
from backend.design.general_engine import allocate, length_for


def make_room(code, area=10):
    return dict(id=code,request_id=code,kind='bedroom',name=code,zone='family',
                min_area=area,min_side=2.0)


def test_solver_reassigns_all_rooms_without_dropping_or_shrinking():
    lanes=[
        dict(x=0.,y=0.,width=3.2,depth=8.0,axis='y',door_side='east'),
        dict(x=5.,y=0.,width=3.2,depth=8.0,axis='y',door_side='west')]
    bundles=[[make_room('a',12)],[make_room('b',12)],[make_room('c',8)]]
    state=reassign_bundles(bundles,lanes,.2,length_for)
    assert state is not None
    used,groups=state
    assert sorted(r['id'] for g in groups for r in g)==['a','b','c']
    assert all(u<=8 for u in used)
    placed=allocate([dict(q) for bundle in bundles for q in bundle],lanes,.2,
                    policy='relationship_aware')
    assert placed
    assert sorted(r['id'] for r in placed if r.get('request_id'))==['a','b','c']


def test_solver_refuses_infeasible_program():
    lanes=[dict(x=0.,y=0.,width=3.,depth=4.,axis='y',door_side='east')]
    assert reassign_bundles([[make_room('too-large',40)]],lanes,.2,length_for) is None


def test_solver_does_not_split_guest_distributor_bundle():
    lanes=[dict(x=0.,y=0.,width=5.,depth=14.,axis='y',door_side='east'),
           dict(x=7.,y=0.,width=5.,depth=14.,axis='y',door_side='west')]
    parent=dict(id='M',request_id='M',kind='majlis',name='Majlis',zone='guest',
                min_area=24,min_side=3.5)
    wc=dict(id='W',request_id='W',kind='bathroom',name='WC',zone='guest',
            min_area=4,min_side=1.6,guest_parent='M')
    distributor=dict(id='H',kind='corridor',name='Hall',zone='guest',
                     guest_parent='M',guest_distributor=True,min_area=0,min_side=1.6)
    state=reassign_bundles([[parent,wc,distributor],[make_room('bed')]],
                           lanes,.2,length_for)
    assert state is not None
    _,groups=state
    assert any({r['id'] for r in group}>={'M','W','H'} for group in groups)
