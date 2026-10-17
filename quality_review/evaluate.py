"""Reproducible local assessment of the unchanged rectangle-packing engine.
Run from repository root: python -m quality_review.evaluate
"""
import json
import random
import time
from pathlib import Path
from itertools import combinations
from backend.main import Project, Room, layout, generate, validate
import backend.main as engine

HERE = Path(__file__).resolve().parent
SEED = 20261017
EPS = 1e-7


def project(width, depth, rooms, title='اختبار'):
    return Project(title=title, plot_width=width, plot_depth=depth,
                   rooms=[Room(name=f'R{i+1}', width=w, depth=d, kind='bedroom') for i, (w, d) in enumerate(rooms)])


def geometry_errors(p, rooms):
    errors = []
    expected = {r.name: r for r in p.rooms}
    if len(rooms) != len(expected) or {r['name'] for r in rooms} != set(expected):
        errors.append('missing_or_duplicate_rooms')
    for r in rooms:
        if r['x'] < -EPS or r['y'] < -EPS or r['x']+r['width'] > p.plot_width+EPS or r['y']+r['depth'] > p.plot_depth+EPS:
            errors.append('out_of_bounds')
        original = expected[r['name']]
        if abs(original.width-r['width']) > EPS or abs(original.depth-r['depth']) > EPS:
            errors.append('dimension_changed')
    for a, b in combinations(rooms, 2):
        overlap_x = min(a['x']+a['width'], b['x']+b['width'])-max(a['x'], b['x'])
        overlap_y = min(a['y']+a['depth'], b['y']+b['depth'])-max(a['y'], b['y'])
        if overlap_x > EPS and overlap_y > EPS:
            errors.append('overlap')
    return errors


def known_tiling(rng, width, depth, count):
    # Split rectangles, retaining a concrete feasible arrangement as a witness.
    rectangles = [(0, 0, width, depth)]
    while len(rectangles) < count:
        candidates = [i for i, (_, _, w, h) in enumerate(rectangles) if w >= 2 or h >= 2]
        if not candidates:
            break
        i = rng.choice(candidates)
        x, y, w, h = rectangles.pop(i)
        vertical = w >= 2 and (h < 2 or rng.choice([True, False]))
        if vertical:
            cut = rng.randint(1, w-1)
            rectangles.extend([(x, y, cut, h), (x+cut, y, w-cut, h)])
        else:
            cut = rng.randint(1, h-1)
            rectangles.extend([(x, y, w, cut), (x, y+cut, w, h-cut)])
    rng.shuffle(rectangles)
    return rectangles


def main():
    rng = random.Random(SEED)
    summary = {'seed': SEED, 'geometry_tolerance_m': EPS, 'scope': 'fixed orientations; synthetic samples, not a real-world success rate'}
    accepted = rejected = 0
    violations = []
    elapsed = []
    for i in range(1200):
        pw, pd = rng.randint(5, 40), rng.randint(5, 40)
        dims = [(rng.randint(5, pw*10)/10, rng.randint(5, pd*10)/10) for _ in range(rng.randint(1, 25))]
        p = project(pw, pd, dims)
        start = time.perf_counter()
        try:
            rooms = layout(p)
        except ValueError:
            rejected += 1
            continue
        elapsed.append((time.perf_counter()-start)*1000)
        accepted += 1
        errors = geometry_errors(p, rooms)
        if errors:
            violations.append({'case': i, 'errors': errors})
    summary['random_geometry'] = {'total': 1200, 'accepted': accepted, 'rejected': rejected, 'invalid_accepted_layouts': violations,
                                  'max_successful_layout_ms': round(max(elapsed), 3)}
    failures = []
    for i in range(300):
        pw, pd = rng.randint(6, 20), rng.randint(6, 20)
        witness = known_tiling(rng, pw, pd, rng.randint(3, 12))
        p = project(pw, pd, [(w, h) for _, _, w, h in witness])
        witness_rooms = [dict(name=r.name, x=x, y=y, width=w, depth=h)
                         for r, (x, y, w, h) in zip(p.rooms, witness)]
        assert not geometry_errors(p, witness_rooms)
        assert abs(sum(w*h for _, _, w, h in witness)-pw*pd) < EPS
        try:
            errors = geometry_errors(p, layout(p))
            if errors:
                raise AssertionError(errors)
        except ValueError:
            failures.append({'case': i, 'project': p.model_dump(), 'feasible_witness': witness})
    summary['guaranteed_feasible_tilings'] = {'total': 300, 'accepted': 300-len(failures), 'false_rejections': len(failures),
                                             'false_rejection_percent': round(len(failures)/3, 1), 'witnesses_saved_in': 'tiling_failures.json'}
    nested = project(6, 6, [(4, 6), (2, 3), (2, 3)], 'توزيع ممكن يرفضه المحرك')
    try:
        layout(nested)
        summary['nested_counterexample_rejected'] = False
    except ValueError:
        summary['nested_counterexample_rejected'] = True
    bad_order = project(10, 4, [(6, 2), (6, 2), (4, 2), (4, 2)])
    good_order = project(10, 4, [(6, 2), (4, 2), (6, 2), (4, 2)])
    try:
        layout(bad_order)
        bad_rejected = False
    except ValueError:
        bad_rejected = True
    summary['input_order_dependency'] = {'first_order_rejected': bad_rejected, 'second_order_accepted': len(layout(good_order)) == 4}
    p = project(9, 9, [(3, 3)]*9)
    rooms = layout(p)
    interior = [r['name'] for r in rooms if r['x'] > EPS and r['y'] > EPS and r['x']+r['width'] < p.plot_width-EPS and r['y']+r['depth'] < p.plot_depth-EPS]
    summary['enclosed_bedrooms'] = {'interior_rooms_without_plot_boundary_contact': interior, 'checks': validate(p),
                                     'note': 'Boundary contact alone does not establish ventilation; no windows or courtyards are modeled.'}
    changed = p.model_copy(deep=True)
    for room in changed.rooms:
        room.kind = 'bathroom'
    geometry = lambda rs: [(r['x'], r['y'], r['width'], r['depth']) for r in rs]
    summary['kind_changes_do_not_affect_geometry'] = geometry(layout(p)) == geometry(layout(changed))
    summary['deterministic'] = layout(p) == layout(p)
    export_dir = HERE/'exports'
    export_dir.mkdir(exist_ok=True)
    original_out = engine.OUT
    engine.OUT = export_dir
    try:
        exported = generate(p)
    finally:
        engine.OUT = original_out
    import ezdxf
    dxf = ezdxf.readfile(export_dir/f"{exported['job_id']}.dxf")
    entities = list(dxf.modelspace().query('LWPOLYLINE[layer=="ROOM"]'))
    export_errors = []
    for r, entity in zip(rooms, entities):
        coords = list(entity.get_points('xy'))
        expected = (r['x'], p.plot_depth-r['y']-r['depth'], r['x']+r['width'], p.plot_depth-r['y'])
        actual = (min(x for x,y in coords), min(y for x,y in coords), max(x for x,y in coords), max(y for x,y in coords))
        if any(abs(a-b)>EPS for a,b in zip(actual, expected)):
            export_errors.append(r['name'])
    audit = dxf.audit()
    summary['dxf'] = {'units_meters': dxf.header['$INSUNITS'] == 6, 'room_rectangles': len(entities),
                      'geometry_mismatches': export_errors, 'audit_errors': len(audit.errors),
                      'note': 'Checked with ezdxf; not opened in an independent CAD application.'}
    summary['pdf'] = {'file': f"exports/{exported['job_id']}.pdf", 'checks': 'signature and page rendering; not engineering completeness'}
    (HERE/'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (HERE/'tiling_failures.json').write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
