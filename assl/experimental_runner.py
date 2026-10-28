"""Opt-in ASSL reporting wrapper around the existing generator.

Default behavior stays unchanged. This is not a production API route.
"""
from .experimental_adapter import inspect_candidate

def generate_with_assl(brief, *, assl_diagnostics=False, generator=None, **kwargs):
    if generator is None:
        from backend.design.general_engine import generate_general
        generator = generate_general
    result = generator(brief, **kwargs)
    if not assl_diagnostics:
        return result
    # Do not mutate the existing result or the geometry/release decisions.
    import copy
    enriched = copy.deepcopy(result)
    for candidate in enriched.get("candidates", []):
        candidate["assl_experimental"] = inspect_candidate(brief, candidate)
    enriched["assl_mode"] = "READ_ONLY_DIAGNOSTICS"
    return enriched
