"""Opt-in ASSL reporting wrapper around the existing generator.

Default behavior stays unchanged. This is not a production API route.
"""
from .experimental_adapter import inspect_candidate

def generate_with_assl(brief, *, assl_diagnostics=False, assl_rank_existing=False, generator=None, **kwargs):
    if generator is None:
        from backend.design.general_engine import generate_general
        generator = generate_general
    result = generator(brief, **kwargs)
    if not (assl_diagnostics or assl_rank_existing):
        return result
    # Do not mutate the existing result or the geometry/release decisions.
    import copy
    enriched = copy.deepcopy(result)
    if assl_diagnostics:
        for candidate in enriched.get("candidates", []):
            candidate["assl_experimental"] = inspect_candidate(brief, candidate)
        enriched["assl_mode"] = "READ_ONLY_DIAGNOSTICS"
    if assl_rank_existing:
        from .space_optimizer import rank_existing_candidates
        enriched["assl_space_recommendation"] = rank_existing_candidates(result.get("candidates", []))
    return enriched
