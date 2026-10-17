"""Mirror a draft villa geometry horizontally without changing its functional program.

This is a spatial exploration operation, not a new adjacency topology or an
architectural-quality claim. The original candidate is not mutated.
"""
from copy import deepcopy


def mirror_candidate(source):
    model = deepcopy(source)
    site_width = model["site"]["width"]

    def mirror_rect(obj):
        obj["x"] = round(site_width - obj["x"] - obj["width"], 8)

    mirror_rect(model["footprint"])
    for parking in model["parking"]:
        mirror_rect(parking)
    for stair in model["stairs"]:
        mirror_rect(stair)
    for floor in model["floors"]:
        for room in floor["rooms"]:
            mirror_rect(room)
        for fixture in floor["furniture"]:
            mirror_rect(fixture)
        for wall in floor["walls"]:
            wall["start"] = (round(site_width - wall["start"][0], 8), wall["start"][1])
            wall["end"] = (round(site_width - wall["end"][0], 8), wall["end"][1])
            if wall.get("axis", "horizontal" if wall["start"][1] == wall["end"][1] else "vertical") == "horizontal" and wall["start"][0] > wall["end"][0]:
                wall["start"], wall["end"] = wall["end"], wall["start"]
        for opening in floor["openings"]:
            opening["center"] = (round(site_width - opening["center"][0], 8), opening["center"][1])
            if opening.get("swing_rect"):
                mirror_rect(opening["swing_rect"])
            if opening.get("face") == "east":
                opening["face"] = "west"
            elif opening.get("face") == "west":
                opening["face"] = "east"
    model["search"]["spatial_transform"] = "MIRROR_EAST_WEST"
    model["search"]["orientation_search"] = False
    model["assumptions"].append(
        "انعكاس هندسي استكشافي شرق/غرب فقط؛ لم تتغير علاقات الغرف ولم تتحقق الواجهات المسموحة."
    )
    return model
