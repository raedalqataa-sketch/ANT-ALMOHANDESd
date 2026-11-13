"""Canonical soft spatial-relationship catalogue shared by V3/V4 QA and ASSL.

Weights are design preferences, not statutory requirements. They describe
which room kinds benefit from short usable routes. Geometry, door topology,
privacy and legal checks remain separate validation responsibilities.
"""

# (source_kind, target_kind, normalized_weight, relationship_id, source_rule)
RELATIONSHIPS = (
    ("kitchen", "dining", 1.0, "FOOD_SERVICE", "E007"),
    ("living", "dining", .9, "FAMILY_COMMON", "E013"),
    ("master", "bathroom", .8, "MASTER_BATH_ACCESS", None),
    ("bedroom", "bathroom", .7, "FAMILY_BATH_ACCESS", None),
    ("laundry", "bedroom", .5, "LAUNDRY_SERVICE", "E019"),
    ("stair", "living", .5, "STAIR_FAMILY_ACCESS", "E014"),
)
