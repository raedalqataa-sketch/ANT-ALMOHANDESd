"""Parametric orthogonal massing for the experimental V3 geometric search.

No prescribed L, U or stepped silhouette: independent front/rear setbacks on
both wings generate an envelope from its actually occupied rooms and hall cells.
This is a bounded, orthogonal search, not unrestricted polygon optimization.
"""
import math


def adaptive_topology(width, depth, corridor, center_fraction, split_fraction):
    if min(width, depth, corridor) <= 0:
        return None
    center = width * center_fraction
    left_edge = center - corridor / 2
    right_edge = center + corridor / 2
    if left_edge <= 0 or right_edge >= width:
        return None
    split = depth * split_fraction
    if min(split, depth - split) < 5.0:
        return None

    def inlet(maximum, band, side):
        # Continuous variations in setbacks, not templates keyed to a facade type.
        phase = (center_fraction * 5.7 + split_fraction * 3.9 + side * 1.4
                 + band * 1.9) * math.pi
        amount = .08 + .92 * (1 + math.sin(phase)) / 2
        return min(maximum * .16, 1.35) * amount

    hall = [{"x": left_edge, "y": 0, "width": corridor, "depth": depth}]
    lanes = []
    for band, (y, size) in enumerate(((0, split), (split, depth - split))):
        left_inlet = inlet(left_edge, band, 0)
        right_inlet = inlet(width - right_edge, band, 1)
        left_width = left_edge - left_inlet
        right_width = width - right_edge - right_inlet
        if min(left_width, right_width) < 2.8:
            return None
        lanes.extend([
            dict(x=left_inlet, y=y, width=left_width, depth=size,
                 axis="y", door_side="east"),
            dict(x=right_edge, y=y, width=right_width, depth=size,
                 axis="y", door_side="west"),
        ])
    return hall, lanes
