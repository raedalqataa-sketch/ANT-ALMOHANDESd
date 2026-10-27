"""Independent, non-statutory diagnosis of unassigned geometry.

Gross cells are the placement grid, including half-wall allowances. The
published footprint is made from those cells, so it cannot itself reveal a
slit left by removing part of a cell. A local morphological closing supplies
only a *diagnostic* envelope for gaps up to ``max_gap_width_m``. Wider exterior
recesses need an explicitly approved assignable envelope to be judged.
"""
import argparse
import json
import math
from pathlib import Path

from shapely import set_precision
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def _rect(item):
    return set_precision(box(item['x'], item['y'], item['x'] + item['width'],
                             item['y'] + item['depth']), 1e-6)


def _pieces(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    return [p for part in getattr(geometry, 'geoms', ()) for p in _pieces(part)]


def _wall(wall):
    x0, y0 = wall['start']
    x1, y1 = wall['end']
    half = wall['thickness'] / 2
    return set_precision(box(min(x0, x1) - half, min(y0, y1) - half,
                             max(x0, x1) + half, max(y0, y1) + half), 1e-6)


def _known_intentional_voids(model, floor):
    voids = []
    for field in ('lightwells', 'courtyards', 'vertical_openings', 'atria'):
        for item in floor.get(field, []):
            if all(k in item for k in ('x', 'y', 'width', 'depth')):
                voids.append((field, item.get('id'), _rect(item)))
    for arrival in model.get('stair_arrivals', []):
        if arrival['floor_id'] == floor['id'] and arrival.get('void'):
            voids.append(('stair_arrival_void', arrival.get('room_id'),
                          _rect(arrival['void'])))
    return voids


def _known_solids(model, floor):
    solids = [_wall(w) for w in floor.get('walls', [])]
    for source in (floor, model):
        for field in ('columns', 'structural_elements'):
            for item in source.get(field, []):
                if item.get('floor_id', floor['id']) == floor['id'] and all(
                        k in item for k in ('x', 'y', 'width', 'depth')):
                    solids.append(_rect(item))
    return unary_union(solids) if solids else Polygon()


def _rounded_bounds(region):
    x0, y0, x1, y1 = region.bounds
    return dict(x=round(x0, 5), y=round(y0, 5),
                width=round(x1 - x0, 5), depth=round(y1 - y0, 5))


def measure_model(model, *, max_gap_width_m=.5):
    """Measure candidate cells; never change generation or acceptance data.

    The width is a *search scale*, not an architectural or legal threshold.
    """
    if not math.isfinite(max_gap_width_m) or max_gap_width_m <= 0:
        raise ValueError('max_gap_width_m must be finite and positive')
    floors = []
    for floor in model['floors']:
        cells = floor['cells']
        occupied = unary_union([_rect(c) for c in cells]) if cells else Polygon()
        reserves = [c for c in cells if c.get('kind') == 'reserve']
        reserve_area = unary_union([_rect(c) for c in reserves]).area if reserves else 0
        # Square corners preserve orthogonal areas. Slightly exceed half width
        # so a slit exactly max_gap_width_m wide is included.
        radius = max_gap_width_m / 2 + 1e-7
        closed = occupied.buffer(radius, join_style=2).buffer(-radius, join_style=2)
        enclosed = unary_union([Polygon(p.exterior) for p in _pieces(occupied)])
        envelope = closed.union(enclosed)
        residual = envelope.difference(occupied)
        intentional = _known_intentional_voids(model, floor)
        intentional_union = unary_union([shape for _, _, shape in intentional]) if intentional else Polygon()
        unallocated = residual.difference(intentional_union)
        intended = residual.intersection(intentional_union)
        solids = _known_solids(model, floor)
        regions = []
        for region in sorted(_pieces(unallocated), key=lambda p: (p.bounds[1], p.bounds[0])):
            if region.area <= 1e-7:
                continue
            outline = region.minimum_rotated_rectangle
            coords = list(outline.exterior.coords)
            sides = sorted((sum((a - b) ** 2 for a, b in zip(coords[i], coords[i + 1])) ** .5
                            for i in range(4)))
            short, long = sides[0], sides[-1]
            regions.append(dict(
                type='narrow_slit' if short <= max_gap_width_m + 1e-6 and long >= 2 * short else 'unused_pocket',
                status='UNALLOCATED_DESIGN_DIAGNOSTIC',
                gross_area_m2=round(region.area, 5),
                net_area_after_known_walls_m2=round(region.difference(solids).area, 5),
                bounds_m=_rounded_bounds(region),
                polygon_m=[(round(x, 5), round(y, 5)) for x, y in region.exterior.coords[:-1]],
                nearby_cell_ids=[c['id'] for c in cells if _rect(c).distance(region) < 1e-6],
            ))
        floors.append(dict(
            floor_id=floor['id'],
            diagnostic_envelope_area_m2=round(envelope.area, 5),
            occupied_gross_cell_area_m2=round(occupied.area, 5),
            declared_reserve_area_m2=round(reserve_area, 5),
            unallocated_gross_area_m2=round(unallocated.area, 5),
            unallocated_net_after_known_walls_m2=round(unallocated.difference(solids).area, 5),
            intentional_void_area_m2=round(intended.area, 5),
            intentional_voids=[dict(kind=kind, id=key) for kind, key, _ in intentional],
            unallocated_regions=regions,
        ))
    return dict(candidate_id=model.get('candidate_id'),
                model_revision_id=model.get('model_revision_id'), floors=floors)


def report_generation(result, *, max_gap_width_m=.5):
    return dict(schema_version='unallocated-geometry-diagnostic-1',
                status='DESIGN_DIAGNOSTIC_NOT_ACCEPTANCE',
                basis=dict(source='gross occupied cells, locally closed to detect narrow gaps',
                           max_gap_width_m=max_gap_width_m,
                           limit='wider exterior recesses and unmodelled structural elements require review; intentional voids require explicit metadata',
                           gross_area='gap in placement grid before deducting walls',
                           net_area='gap after deducting modelled walls and structural elements',
                           reserve='labeled flexible reserve cells are counted separately, not called accidental geometry gaps'),
                alternatives=[measure_model(m, max_gap_width_m=max_gap_width_m)
                              for m in result['candidates']])


def main():
    parser = argparse.ArgumentParser(description='Write a separate diagnostic JSON; no acceptance change.')
    parser.add_argument('generation_result', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = json.loads(args.generation_result.read_text(encoding='utf-8'))
    args.output.write_text(json.dumps(report_generation(result), ensure_ascii=False, indent=2,
                                      allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
