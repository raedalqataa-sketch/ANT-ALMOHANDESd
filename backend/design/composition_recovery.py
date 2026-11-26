"""Offer explicit program changes or a verified vertical arrangement."""
from .general_engine import search_feasibility_evidence
from .general_models import TransferredSuite, VillaBrief


def attach_fit_evidence(result, brief):
    if result["proposals"]:
        return result
    evidence = search_feasibility_evidence(brief)
    reasons = [str(item.get("reason", "")) for item in result.get("failures", [])]
    measured_mismatch = any("envelope" in reason.lower() or "UPPER PROGRAM EXCEEDS" in reason for reason in reasons)
    if measured_mismatch or evidence["classification"] == "PROVEN_ENVELOPE_SHORTFALL":
        result["fit"] = evidence
    return result


def narrower_programs(brief):
    """Retain functions and relationships; propose smaller minima explicitly."""
    disposable = {
        "majlis", "dining", "bedroom", "master", "storage", "bathroom", "kitchen",
    }
    for factor in (0.90, 0.80, 0.70):
        changes, rooms = [], []
        for room in brief.rooms:
            data = room.model_dump()
            if room.kind in disposable:
                data["min_area"] = max(3., round(room.min_area*factor, 2))
                data["min_side"] = max(1.4, round(room.min_side*factor**.5, 2))
            if data["min_area"] != room.min_area or data["min_side"] != room.min_side:
                changes.append({"name":room.name, "old_area":room.min_area, "new_area":data["min_area"],
                                "old_side":room.min_side, "new_side":data["min_side"]})
            rooms.append(data)
        if changes:
            yield VillaBrief.model_validate({**brief.model_dump(), "rooms":rooms}), changes


def recover(brief, action, max_results, *, upper_program=None, first_floor=False, progress=None):
    from assl.strategies.clustered import solve_client_clustered
    from assl.strategies.clustered_multilevel import family_proposals

    def fail(reason):
        return attach_fit_evidence({"status":"REJECT_AND_REPLAN", "proposals":[],
                                    "requested_results":max_results, "failures":[{"reason":reason}]}, brief)

    if action == "adapt":
        for index, (candidate, changes) in enumerate(narrower_programs(brief)):
            if progress:
                progress(15+25*index, "البحث عن برنامج أصغر مع الحفاظ على الوظائف")
            result = (family_proposals(candidate, max_results, upper_program=upper_program) if first_floor
                      else solve_client_clustered(candidate, max_results=max_results))
            if result["proposals"]:
                result["recovery"] = {"action":"adapt", "changes":changes}
                return result
        return fail("ADAPTED_PROGRAM_NOT_FOUND")

    # Keep guest and service requirements on the ground; only a linked private
    # suite may be moved by this family-stack template.
    suites = [(room, bath) for room in brief.rooms if room.kind in ("bedroom","master")
              for bath in brief.rooms if bath.ensuite_for == room.id]
    if brief.floors != 1 or len(suites) != 1:
        return fail("VERTICAL_REQUIRES_ONE_LINKED_BEDROOM_SUITE")
    bedroom, bathroom = suites[0]
    moved_ids = {bedroom.id, bathroom.id}
    if any({relation.source, relation.target} & moved_ids for relation in brief.spatial_requirements):
        return fail("VERTICAL_SUITE_HAS_FIXED_SAME_FLOOR_RELATION")
    try:
        suite = TransferredSuite(bedroom=bedroom, bathroom=bathroom)
        ground = VillaBrief.model_validate({
            **brief.model_dump(), "rooms":[r for r in brief.rooms if r.id not in moved_ids],
        })
    except ValueError:
        return fail("VERTICAL_REQUIRES_ONE_LINKED_BEDROOM_SUITE")
    result = family_proposals(ground, max_results, progress, upper_program=upper_program, transferred_suite=suite)
    if not result["proposals"]:
        result = family_proposals(ground, max_results, upper_program=upper_program,
                                  transferred_suite=suite, terrace_side="south")
    if result["proposals"]:
        result["recovery"] = {"action":"vertical", "moved":[bedroom.name,bathroom.name]}
    return attach_fit_evidence(result, brief)
