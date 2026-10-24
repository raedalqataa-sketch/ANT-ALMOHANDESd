# Program-sized villa massing implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce oversized rooms in automatic V4 villa plans while retaining three genuinely distinct, validated alternatives where the existing search can find them.

**Architecture:** Keep the existing Python search, room allocations, and validation. Apply a disclosed design area growth target to corridor-facing rooms of every automatic V4 topology before materialization; trimming occurs toward the exterior so the corridor edge and doors remain hosted. The previous behavior remains the default for saved briefs and direct engine callers.

**Tech Stack:** Python 3.12, Pydantic, Pytest, existing V4 geometric engine, Sites browser runtime.

**Spec:** User's 2026-10-24 instruction to implement the previously recommended room-area and massing correction.

## Global constraints

- Preserve `VillaBrief` input compatibility and existing stored project data.
- Do not misrepresent a design area ratio as a Saudi or Yemeni building-code limit.
- Never remove required rooms or allow failed geometry, furnishings, circulation, privacy, or regulation checks to be exported.
- Keep the existing production `/client/` URL and DXF `AC1024` line-only output.

## Review focus

- A target room area can be impossible because of its minimum side or furniture: preserve the minimum and report remaining excess.
- Trimming a wing can break corridor contact or opening geometry: validate physical doors and full V4 checks.
- A compact candidate can leave too few distinct options: return only actual validated alternatives and report why.
- Luxury still needs larger rooms than economy: the proposed minimum areas are already tier-scaled before search.
- Old JSON briefs lack the new field: default must preserve their behavior.

---

### Task 1: Bound automatic V4 room expansion across families

**Files:** `backend/design/adaptive_geometry.py`, `backend/design/general_engine.py`, `backend/design/general_models.py`, `backend/design/architect_planner.py`, `tests/test_adaptive_functional_v3.py`.

**Interfaces:** `moderate_room_expansion(cells, wall_thickness, area_factor=None)` retains legacy per-kind ratios unless `area_factor` is supplied. `VillaBrief.proposed_room_area_factor` defaults to `None`; automatic V4 sets it to `1.2`. This is a design heuristic on proposed minimum area, never a legal rule.

- [x] Write a focused failing test for the 1.2 factor preserving corridor edges, net minimum area, minimum side, aspect ratio, and the caller's input.
- [x] Watch that test fail for missing behavior.
- [x] Implement the optional factor and apply it to each V4 room wing regardless of topology family.
- [x] Run the focused tests and ensure legacy default tests still pass.

### Task 2: Verify actual multi-option outcomes

**Files:** `tests/test_adaptive_selection.py`, `quality_review/v4/EXECUTION_STATE_AR.md`.

**Interfaces:** Actual V4 outputs report the area growth policy in planning and retain a measured `program_excess_ratio`. The accepted 24×32m six-person Saudi and Yemeni examples should keep three distinct plans and show measured excess below 0.30; no candidate may be exported with failed checks.

- [x] Add failing integration assertions for actual room areas, three distinct selections, and disclosed area policy.
- [x] Watch them fail against the current implementation.
- [x] Implement the smallest planner/reporting changes needed.
- [x] Run focused integration, then the full Python/Node suite and real export matrix checks; production browser verification follows publication.
- [x] Record cases beyond search coverage: Saudi small plot and Yemen one-floor yield zero valid options; no fake exports.

### Task 3: Merge and publish verified source

**Files:** Existing Site source checkout and release artifacts.

- [ ] Commit and push the passing branch; create a PR and wait for checks.
- [ ] Merge into `main`, then confirm all main checks pass.
- [ ] Build Site assets from exact merged SHA, save and publish a new version to the existing project.
- [ ] Verify live source manifest and exercise actual SA/YE browser journeys and PDF/DXF/JSON downloads.
