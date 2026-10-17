# Architectural engine V0.4 — implementation contract

Status: development only. Existing main branch and approved rule references remain unchanged.

## Confirmed code findings
- `backend/design/generator.py` uses one hard-coded two-wing layout and changes footprint sizes, not functional arrangements.
- `backend/design/validators.py` checks room overlap, reachability, physical windows, and door envelopes, but reports ventilation adequacy, sightlines, stair headroom, parking maneuver, and executive dimensions as PENDING.
- `backend/design/export.py` exports review drawings, not approved construction documentation.
- `backend/design/api.py` ranks alternatives by failure/pending counts and circulation/footprint size; this is not an architectural-quality score.

## Next implementation gates
1. Preserve current generator as `legacy_v03` and use a versioned strategy selector.
2. Introduce at least three distinct plan topology families: courtyard/perimeter, compact-core, and separated guest/family wings; only select families feasible under the actual site constraints.
3. Generate functional adjacency graphs from requirements and enforce separate male guest and family circulation, kitchen/dining adjacency, and bedroom privacy.
4. Add geometry-level checks for bathroom, bedroom, and kitchen external openings, daylight and ventilation *quantities* only when an approved criterion is supplied; otherwise PENDING.
5. Add usable door and furniture clearances, window/door conflicts, and room accessibility tests; never substitute generic assumptions for local code.
6. Preserve traceable input fields and expose actionable Excel import errors (sheet, row, field, expected value) without modifying the accepted brief.
7. Compare alternatives by distinct topology, privacy and circulation metrics, not only footprint dimensions.
8. Export drawings for REVIEW only until all applicable release gates pass and responsible engineer explicitly approves.

## Required tests
- Three candidates must not be geometrically identical when alternatives are requested and feasible.
- Guest path cannot pass through private family rooms.
- Bedrooms, kitchens and bathrooms without external windows must FAIL the physical-window check.
- Unknown local regulations must remain PENDING.
- No FAIL geometry may be exported as a drawing.
- Imported Arabic Excel data must preserve values and identify invalid rows.
- Approved or locked revisions must never be overwritten.

No implementation or deployment claim is made by this contract.
