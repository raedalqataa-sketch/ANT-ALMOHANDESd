# Architectural Alternatives Engine — Phase 1

Status: development specification; not executable generator and not Saudi code certification.

## Reference policy
Exclude the paired adjacent-villas project from the architectural reference dataset. Other user-approved villas may inform design heuristics; no copied floor plans. Confirm actual reference files before deriving dimensions.

## Candidate pipeline
1. Validate site polygon, street frontage, orientation, setbacks, occupancy and room program. Missing binding values block compliance claims.
2. Build an adjacency graph with hard constraints: independent guest/family access where required, room minimums when verified, non-overlapping polygons, circulation, stairs alignment and natural ventilation.
3. Generate at least three meaningfully distinct feasible massing and zoning candidates using deterministic seeds: compact courtyard, articulated frontage, and service-spine. Skip a typology if infeasible and report why.
4. Allocate room polygons and wall/opening geometry, then test door swings, privacy sightlines, furniture clearance, daylight/ventilation access and cross-floor cores.
5. Rank only valid candidates; reject hard violations before scoring.
6. Export chosen candidate and evaluation report to PDF and DXF AC1015 (AutoCAD 2000) or AC1024 (AutoCAD 2010). Require AC1024 for requested DXF 2010.

## Proposed soft scoring (0–100)
- functional adjacency: 25
- privacy: 25
- circulation efficiency: 15
- daylight and ventilation: 15
- buildable-area efficiency: 10
- architectural articulation and facade coherence: 10

All weights are provisional, not regulatory. Hard violations always disqualify. Provide reasons and evidence for each score.

## Test cases
- Three seeds yield distinct valid layouts on a feasible 12.5 x 20 m plot.
- No room polygon overlap or boundary escape.
- Stair/elevator core aligned across floors.
- Guest circulation does not cross private bedrooms.
- Wet rooms have verifiable ventilation strategy.
- DXF export header reports $ACADVER = AC1024.
- Missing setbacks or authoritative rule source produces a warning/block, never a fabricated compliance pass.
- Existing approved output remains unchanged until explicit review and merge.

## Implementation next
Locate existing generator geometry models, candidate interfaces, scoring and exporters. Implement the pipeline behind a feature flag with regression tests; compare candidates against the approved reference set. Keep this branch isolated until test and engineering review.
