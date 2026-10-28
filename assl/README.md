# ASSL Regulatory Core v0.2 (experimental)

This module is an **isolated, non-enforcing draft** for architectural standards in ANT-ALMOHANDES.

## Layers
1. National building codes and statutes
2. Municipal and planning overlays
3. Project-specific approved conditions
4. Internal architectural design guidance

## Safety of interpretation
- A design guideline is **not** a legal code.
- A source mentioned in a research report is **not** automatically authenticated against the current legal edition.
- Missing local zoning data is **UNRESOLVED**, not PASS.
- Saudi SBC guide-derived numerical rules require confirmation against the controlling 2024 clauses.
- Yemen building law executive regulations remain unauthenticated in the supplied research.
- No validator or generation pipeline is activated by these files.

## Next milestones
1. Audit existing repository modules and integration points.
2. Verify each legal clause against an authoritative current source, with page/section and effective date.
3. Add versioned rules, deterministic applicability resolution and conflict reporting.
4. Add tests for boundaries, overrides, unresolved sources and exception approvals.
5. Integrate behind a disabled feature flag, then compare generated floorplans.
6. Require owner approval before merge, deployment or production enforcement.
