"""Early, bounded side-vestibule allocation; all downstream checks still apply."""
import copy
import math


def inspect_compact(model):
    """Fit the actual furnished/door geometry, not just candidate room areas."""
    from .functional_program import FunctionalGraph, furniture_issues
    from .walkability import floor_access
    from .visual_privacy import inspect
    floor = model['floors'][0]
    guest_ids = {r['id'] for r in floor['rooms'] if r.get('zone') == 'guest'}
    guest_view = {**floor, 'openings': [o for o in floor['openings']
                 if 'OUTSIDE' not in o['connects'] or o.get('guest_entry')]}
    access = floor_access(model, guest_view, allowed_room_ids=guest_ids)
    return dict(guest_access=access, furniture_issues=furniture_issues(model),
                functional_paths=FunctionalGraph(model).inspect(), visual_privacy=inspect(model))


def compact_fit_check(model):
    fit = inspect_compact(model)
    ok = not (fit['guest_access']['unreachable'] or fit['furniture_issues'] or
              fit['functional_paths']['unreachable'] or fit['visual_privacy']['sampled_exposed_rooms'])
    return dict(check_id='guest-compact-furnished-fit', status='PASS' if ok else 'FAIL',
                label='ملاءمة التكوين المدمج للأثاث والأبواب والاتصال وعينات الخصوصية', evidence=fit)


def allocate_compact_side(requests, lanes, t, clear_width, coherent, policy, entry_face, area_factor=None):
    """A tiled three-cell cluster: WC beside majlis, short corner vestibule.

    Proportions below are search heuristics, never statutory limits. All room
    doors, furniture and clearances are rebuilt and validated downstream.
    """
    from .general_engine import allocate
    guests = [r for r in requests if r.get('zone') == 'guest']
    main = [r for r in guests if r['kind'] == 'majlis']
    baths = [r for r in guests if r['kind'] == 'bathroom']
    if len(guests) != 2 or len(main) != 1 or len(baths) != 1 or not main[0].get('separate_guest_entry'):
        return None
    factor = max(1., area_factor or 1.)
    options = []
    for index, lane in enumerate(lanes):
        if lane['axis'] != 'y' or lane['door_side'] not in ('east', 'west'):
            continue
        for proportion in (1., 1.1, 1.2):
            band = max(baths[0]['min_side'], math.sqrt(baths[0]['min_area'] * factor) * proportion) + t
            main_width = lane['width'] - band
            net_width = main_width - t
            if net_width < main[0]['min_side']:
                continue
            main_depth = max(main[0]['min_side'], main[0]['min_area'] * factor / net_width) + t
            bath_depth = max(baths[0]['min_side'], baths[0]['min_area'] * factor / (band-t)) + t
            vestibule_depth = main_depth - bath_depth
            if main_depth > lane['depth'] or min(band-t, vestibule_depth-t) < max(1.6, clear_width):
                continue
            # Prefer balanced rooms and a compact node over a longitudinal hall.
            aspect = max(net_width, main_depth-t) / min(net_width, main_depth-t)
            vestibule_aspect = max(band-t, vestibule_depth-t) / min(band-t, vestibule_depth-t)
            options.append((aspect + vestibule_aspect, index, band, main_width, main_depth, bath_depth))
    for _, index, band, main_width, main_depth, bath_depth in sorted(options):
        lane = lanes[index]
        front = entry_face == 'south'
        start = lane['y'] + lane['depth'] - main_depth if front else lane['y']
        remaining = copy.deepcopy(lanes)
        remaining[index]['depth'] -= main_depth
        if not front:
            remaining[index]['y'] += main_depth
        if remaining[index]['depth'] <= 1e-6:
            remaining.pop(index)
        rest = allocate([copy.deepcopy(r) for r in requests if r not in guests],
                        remaining, t, clear_width, coherent, policy, entry_face)
        if rest is None:
            continue
        left = lane['door_side'] == 'east'
        band_x = lane['x'] if left else lane['x'] + main_width
        main_x = lane['x'] + band if left else lane['x']
        vestibule_depth = main_depth - bath_depth
        bath_y = start if front else start + vestibule_depth
        vestibule_y = start + bath_depth if front else start
        did = 'guest-dist-' + main[0]['id']
        common = dict(guest_composition='compact_side')
        room = dict(copy.deepcopy(main[0]), x=main_x, y=start, width=main_width,
                    depth=main_depth, guest_vestibule=did,
                    door_side='west' if left else 'east', **common)
        bath = dict(copy.deepcopy(baths[0]), x=band_x, y=bath_y, width=band,
                    depth=bath_depth, guest_vestibule=did,
                    door_side='south' if front else 'north', **common)
        vestibule = dict(id=did, kind='corridor', name='موزع ضيوف مدمج', zone='guest',
                         guest_distributor=True, guest_parent=main[0]['id'], x=band_x,
                         y=vestibule_y, width=band, depth=vestibule_depth, **common)
        return rest + [room, bath, vestibule]
    return None


def allocate_side_spine(requests, lanes, t, clear_width, coherent, policy, entry_face, area_factor=None):
    from .general_engine import allocate

    guests = [r for r in requests if r.get('zone') == 'guest']
    majlis = [r for r in guests if r['kind'] == 'majlis']
    baths = [r for r in guests if r['kind'] == 'bathroom']
    if len(majlis) != 1 or len(baths) != 1 or len(guests) != 2:
        return None
    if not majlis[0].get('separate_guest_entry'):
        return None
    for index, lane in enumerate(lanes):
        if lane['axis'] != 'y' or lane['door_side'] not in ('east', 'west'):
            continue
        passage = max(1.6, clear_width) + t
        room_width = lane['width'] - passage
        net_width = room_width - t
        if net_width < majlis[0]['min_side']:
            continue
        # Keep the requested functional area; room shape/furniture checks decide
        # whether this particular rectangle can be used, never just its area.
        factor = max(1., area_factor or 1.)
        main_depth = max(majlis[0]['min_side'], factor * majlis[0]['min_area'] / net_width,
                         net_width / 2.8) + t
        bath_width = max(baths[0]['min_side'], math.sqrt(factor * baths[0]['min_area'])) + t
        bath_depth = max(baths[0]['min_side'], factor * baths[0]['min_area'] / (bath_width-t)) + t
        length = main_depth + bath_depth
        if bath_width > room_width or length > lane['depth']:
            continue
        # A longitudinal vestibule may not consume more gross movement area
        # than the current transverse vestibule in the same lane.
        if length > lane['width'] + 1e-6:
            continue
        remaining_lanes = copy.deepcopy(lanes)
        target = remaining_lanes[index]
        front = policy == 'social_front' and entry_face == 'south'
        start = lane['y'] + lane['depth'] - length if front else lane['y']
        if front:
            target['depth'] -= length
        else:
            target['y'] += length
            target['depth'] -= length
        if target['depth'] <= 1e-6:
            remaining_lanes.pop(index)
        rest = allocate([copy.deepcopy(r) for r in requests if r not in guests],
                        remaining_lanes, t, clear_width, coherent, policy, entry_face)
        if rest is None:
            continue
        outer_left = lane['door_side'] == 'east'
        dx = lane['x'] if outer_left else lane['x'] + room_width
        rx = lane['x'] + passage if outer_left else lane['x']
        bathroom_x = rx if outer_left else rx + room_width - bath_width
        distributor_id = 'guest-dist-' + majlis[0]['id']
        common = dict(guest_composition='side_spine')
        distributor = dict(id=distributor_id, kind='corridor', name='موزع ضيوف جانبي',
                           zone='guest', guest_distributor=True, guest_parent=majlis[0]['id'],
                           x=dx, y=start, width=passage, depth=length, **common)
        room = dict(copy.deepcopy(majlis[0]), x=rx, y=start+bath_depth,
                    width=room_width, depth=main_depth, guest_vestibule=distributor_id,
                    door_side='west' if outer_left else 'east', **common)
        bath = dict(copy.deepcopy(baths[0]), x=bathroom_x, y=start,
                    width=bath_width, depth=bath_depth, guest_vestibule=distributor_id,
                    door_side='west' if outer_left else 'east', **common)
        return rest + [room, bath, distributor]
    return None
