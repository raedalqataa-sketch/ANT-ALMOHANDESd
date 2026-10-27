# ANT-ALMOHANDES — Space Efficiency & Architectural Critic (experimental)

Status: SPECIFICATION ONLY. No generator code, accepted drawings, production routes, or deployment modified.

## Baseline and evidence
- Compare against immutable main-branch generation results using identical input, search budget, seed, and output settings.
- Record git SHA, input SHA, candidate IDs, floor, geometry, room areas, corridor union, unallocated pockets, dimensions, doors, furniture, privacy paths, and validation results in machine-readable JSON.
- Separate gross circulation union from net corridors; avoid double-counting overlapping halls.
- Distinguish mandatory code checks from project-specific design targets; unknown site facts must remain PENDING.

## Phase A — Geometry measurement (Shapely + current geometry engine)
- Compute footprint, union of rooms, union of circulation, and leftover polygons after accounting for walls/valid outdoor spaces.
- Detect disconnected slivers/pockets > 0.5 m2 as REVIEW; reject only geometrically invalid overlaps/out-of-bounds by existing rules.
- Measure each room aspect ratio max(width,depth)/min(width,depth); >1.8 requires REVIEW and furnishing proof, not an automatic legal failure.
- Measure physical guest-to-majlis and family circulation routes around obstacles, not through private rooms.
- Store exact polygon evidence and area accounting tolerances; include adversarial examples.

## Phase B — Candidate optimization (OR-Tools + Beam Search)
- Keep the existing generator as baseline. Develop an opt-in experimental path.
- Optimize adjacency, usable room proportions, furniture clearance, privacy, natural opening potential, and circulation footprint simultaneously.
- Hard constraints: all requested rooms, minimum dimensions, site boundary, doors, staircase invariants, no positive-area overlaps.
- Soft objectives: reduce corridor union and unused pockets; minimize detours; prioritize kitchen/dining, guest/bathroom, family zones; discourage long narrow rooms.
- Avoid using lane packing efficiency as a proxy for architectural quality.
- Limit solver time, record infeasible/timeout and fall back explicitly without claiming optimality.

## Phase C — Architectural critic / repair
- Diagnose long guest distributors, excessive room aspect ratio, unreachable doors, blocked furniture clearances, guest/family privacy breaches, dark/unventilated rooms, and unassigned pockets.
- Propose a bounded set of repair actions; regenerate geometry, then rerun independent checks.
- Never silently remove a requested room or relocate a locked staircase. No unverified claim of code compliance.
- Every accepted repair needs a before/after metric and a geometric diff.

## Phase D — Three genuinely different alternatives
- Compare room adjacency graphs, guest/family circulation topology, stair position, and zoning, not just corridor segmentation, rotation, or facade.
- Require three materially different validated options or report a shortfall explicitly; never fabricate variety.

## Phase E — Reference floor plans
- Inventory source images and provenance; extract geometry only where scale and annotations are verifiable.
- Manually validate a gold-standard subset of room labels, door relationships, dimensions, and furniture.
- Establish retrieval/evaluation evidence before proposing model training. OpenCV is installed; PyTorch is not required for this phase.

## Proposed acceptance gates (not building-code minima)
1. No new hard validation failures relative to baseline.
2. Zero unexplained pockets > 0.5 m2 in accepted proposals.
3. No requested rooms dropped or stair positions changed when locked.
4. Every room ratio >1.8 has explicit REVIEW evidence and furniture-fit verification.
5. Guest/family privacy path checks and natural-light/ventilation potential reported per room.
6. Quantify corridor union, gross circulation, usable area, and actual path length before/after; improvement must not be cosmetic or a measurement artifact.
7. Three materially distinct candidates, or explicit insufficiency with diagnostics.
8. PDF/DXF geometric consistency, AC1024 DXF audit, visual review, and regression tests.

## Work approval boundary
This document authorizes only experimental development and testing on this branch. Do not modify approved drawings, main, production deployment, or normative design rules without explicit owner approval.
