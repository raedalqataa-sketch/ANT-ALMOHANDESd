"""Read-only geometry diagnostics for generated residential alternatives.

These measurements do not participate in search, validation, selection, or export.
The room target is the current program's design minimum, optionally multiplied
by its disclosed V4 design factor; neither value is a statutory maximum.
"""
import argparse
import json
from pathlib import Path

from shapely import set_precision
from shapely.geometry import box
from shapely.ops import unary_union


EPS = 1e-6


def _area(rectangle):
    return rectangle['width'] * rectangle['depth']


def _round(value):
    return round(value, 5)


def _gross_circulation_union_area(floor):
    """Area of gross corridor geometry, independent of cell partition or labels."""
    footprints = [set_precision(box(cell['x'], cell['y'],
                                    cell['x'] + cell['width'],
                                    cell['y'] + cell['depth']), 1e-6)
                  for cell in floor['cells'] if cell['kind'] == 'corridor']
    return unary_union(footprints).area if footprints else 0.0


def _junction_positions(hall, other, axis):
    """Projected contacts between two gross corridor cells, if any."""
    if axis == 'y':
        cross, length, breadth = 'x', 'y', 'width'
    else:
        cross, length, breadth = 'y', 'x', 'depth'
    h0, h1 = hall[length], hall[length] + hall['depth' if axis == 'y' else 'width']
    o0, o1 = other[length], other[length] + other['depth' if axis == 'y' else 'width']
    cross_overlap = min(hall[cross] + hall[breadth], other[cross] + other[breadth]) - max(hall[cross], other[cross])
    if cross_overlap > EPS:
        if abs(o1 - h0) <= EPS:
            return [h0]
        if abs(h1 - o0) <= EPS:
            return [h1]
    if (abs(hall[cross] + hall[breadth] - other[cross]) <= EPS or
            abs(other[cross] + other[breadth] - hall[cross]) <= EPS):
        lo, hi = max(h0, o0), min(h1, o1)
        if hi - lo > EPS:
            return [(lo + hi) / 2]
    return []


def _dead_ends(floor):
    """Exposed centerline tails up to the first physical door or hall junction.

    This is a geometric screening signal, not a declaration that an architect
    may delete the passage. Guest vestibules have their own area measurement.
    """
    halls = [c for c in floor['cells'] if c['kind'] == 'corridor' and not c.get('guest_distributor')]
    tails = []
    for hall in halls:
        axis = 'y' if hall['depth'] >= hall['width'] else 'x'
        length = 'depth' if axis == 'y' else 'width'
        start, end = hall[axis], hall[axis] + hall[length]
        events = [o['center'][0 if axis == 'x' else 1]
                  for o in floor['openings']
                  if o['kind'] == 'door' and hall['id'] in o['connects']
                  and start - EPS <= o['center'][0 if axis == 'x' else 1] <= end + EPS]
        for other in halls:
            if other is not hall:
                events.extend(_junction_positions(hall, other, axis))
        if not events:
            tails.append({'corridor_id': hall['id'], 'end': 'unserved', 'length_m': _round(end - start)})
            continue
        first, last = min(events), max(events)
        for side, distance in (('start', first - start), ('end', end - last)):
            if distance > EPS:
                tails.append({'corridor_id': hall['id'], 'end': side, 'length_m': _round(distance)})
    return tails


def measure_candidate(model):
    """Return per-floor net area, circulation, room and vestibule diagnostics."""
    brief = model['brief']
    program = {r['id']: r for r in brief['rooms']}
    factor = brief.get('proposed_room_area_factor')
    floors = []
    for floor in model['floors']:
        rooms = floor['rooms']
        usable = sum(_area(r) for r in rooms if r['kind'] != 'reserve')
        ordinary = sum(_area(r) for r in rooms if r['kind'] == 'corridor' and not r.get('guest_distributor'))
        guest = sum(_area(r) for r in rooms if r.get('guest_distributor'))
        measured_rooms = []
        for room in rooms:
            request_id = room.get('request_id')
            if not request_id:
                continue
            request = program.get(request_id)
            actual = _area(room)
            minimum = request['min_area'] if request else None
            target = minimum * factor if minimum is not None and factor is not None else minimum
            measured_rooms.append({
                'room_id': room['id'], 'request_id': request_id, 'kind': room['kind'],
                'width_m': _round(room['width']), 'depth_m': _round(room['depth']),
                'aspect_ratio': _round(max(room['width'], room['depth']) / min(room['width'], room['depth'])),
                'actual_area_m2': _round(actual),
                'program_area_m2': _round(minimum) if minimum is not None else None,
                'proposed_target_area_m2': _round(target) if target is not None else None,
                'area_delta_vs_target_m2': _round(actual - target) if target is not None else None,
            })
        tails = _dead_ends(floor)
        floors.append({
            'floor_id': floor['id'], 'net_usable_area_m2': _round(usable),
            'ordinary_corridor_area_m2': _round(ordinary),
            'guest_distributor_area_m2': _round(guest),
            'corridor_area_m2': _round(ordinary + guest),
            'gross_circulation_union_area_m2': _round(_gross_circulation_union_area(floor)),
            'corridor_share_of_usable': _round((ordinary + guest) / usable) if usable > EPS else None,
            'potential_dead_end_length_m': _round(sum(t['length_m'] for t in tails)),
            'potential_dead_ends': tails, 'rooms': measured_rooms,
        })
    return {
        'candidate_id': model['candidate_id'], 'model_revision_id': model['model_revision_id'],
        'basis': {'status': 'DESIGN_DIAGNOSTIC_NOT_STATUTORY',
                  'usable_area': 'sum of net room areas except reserve; includes stair and all corridors',
                  'corridor_area': 'net ordinary corridors plus net guest distributors',
                  'gross_circulation_union_area': 'geometric union of gross corridor cells, including guest distributor; overlapping areas counted once; diagnostic, not net usable area',
                  'dead_ends': 'gross corridor centerline from exposed end to nearest hosted door or corridor junction; screening proxy only',
                  'room_target': 'current program min_area times optional proposed_room_area_factor; design target, not a legal maximum',
                  'proposed_room_area_factor': factor},
        'floors': floors,
    }


def report_generation(result):
    """Measure the alternatives present in a generation result without mutating it."""
    return {'schema_version': 'space-efficiency-diagnostic-1',
            'alternatives': [measure_candidate(model) for model in result['candidates']]}


def write_report(result, destination):
    report = report_generation(result)
    Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='Measure existing generated alternatives; do not regenerate them.')
    parser.add_argument('generation_result', type=Path, help='Existing result.json with candidates')
    parser.add_argument('output', type=Path, help='Separate space-efficiency JSON report')
    args = parser.parse_args()
    write_report(json.loads(args.generation_result.read_text(encoding='utf-8')), args.output)


if __name__ == '__main__':
    main()
