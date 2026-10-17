"""Functional zoning hypotheses for nonrectangular villa concepts.

This stage assigns program zones to conceptual wings, not physical rooms.
No CAD geometry, egress or natural-light compliance is asserted.
"""
from collections import defaultdict


ZONE_RULES = {
    "guest": {"required": ("men_majlis", "men_bath"), "entrance": "men"},
    "family": {"required": ("family_living", "women_majlis"), "entrance": "family"},
    "service": {"required": ("kitchen", "family_dining"), "entrance": "family"},
    "private": {"required": ("bedrooms", "family_bath"), "entrance": "family"},
}

CONCEPTS = {
    "L_SHAPE": {
        "guest": "short_wing",
        "family": "long_wing",
        "service": "junction",
        "private": "long_wing_upper",
    },
    "U_SHAPE": {
        "guest": "left_wing",
        "family": "base_wing",
        "service": "base_wing",
        "private": "right_wing",
    },
    "STEPPED": {
        "guest": "front_step",
        "family": "middle",
        "service": "middle",
        "private": "rear_step",
    },
    "RECTANGULAR": {
        "guest": "guest_edge",
        "family": "family_core",
        "service": "service_edge",
        "private": "private_edge",
    },
}


def propose_functional_zones(envelope, requested_zones=None):
    family = envelope["family"]
    if family not in CONCEPTS:
        raise ValueError("Unsupported building massing")
    requested_zones = tuple(requested_zones or ZONE_RULES)
    unknown = set(requested_zones) - set(ZONE_RULES)
    if unknown:
        raise ValueError(f"Unknown functional zones: {sorted(unknown)}")
    assignments = [
        {"zone": zone, "conceptual_wing": CONCEPTS[family][zone],
         "program": list(ZONE_RULES[zone]["required"]),
         "entrance_group": ZONE_RULES[zone]["entrance"]}
        for zone in requested_zones
    ]
    return {
        "family": family,
        "assignments": assignments,
        "relationships": [
            {"from": "men_majlis", "to": "men_bath", "rule": "ADJACENT_OR_GUEST_ONLY"},
            {"from": "kitchen", "to": "family_dining", "rule": "ADJACENT"},
            {"from": "family_living", "to": "bedrooms", "rule": "FAMILY_ONLY_CIRCULATION"},
        ],
        "hard_constraints": [
            "NO_GUEST_THROUGH_FAMILY_PRIVATE",
            "SEPARATE_MEN_AND_FAMILY_ENTRY_PATHS",
            "NATURAL_OPENINGS_FOR_BEDROOM_KITCHEN_BATHROOM",
            "STAIR_CONNECTS_BOTH_FLOORS",
            "PLOT_AND_LOCAL_CODE_REVIEW",
        ],
        "status": "ZONING_HYPOTHESIS_NOT_ROOM_LAYOUT",
    }


def check_zoning_hypothesis(proposal):
    assignments = proposal["assignments"]
    by_zone = {a["zone"]: a for a in assignments}
    issues = []
    if "guest" in by_zone and "private" in by_zone:
        if by_zone["guest"]["entrance_group"] == by_zone["private"]["entrance_group"]:
            issues.append("GUEST_AND_PRIVATE_ENTRANCE_NOT_SEPARATED")
    if "service" in by_zone and "family" in by_zone:
        if by_zone["service"]["entrance_group"] != by_zone["family"]["entrance_group"]:
            issues.append("KITCHEN_AND_DINING_CIRCULATION_DISCONNECTED")
    return {"status": "FAIL" if issues else "PENDING_GEOMETRY", "issues": issues}
