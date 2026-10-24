# Aspect-aware wing search implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let V4 search consider proportionate bedroom geometry before it spends validation budget and chooses a villa mass.

**Architecture:** The existing V4 search enumerates and sizes complete room wings, then ranks them mostly by gross area and massing. Reuse the same 2:1 sleeping-room quality threshold already enforced by portfolio selection as the first search rank, with the existing massing score as tie-break. Keep direct and older brief searches on their prior score order; do not change statutory checks.

**Tech Stack:** Python 3.12, Pytest, existing geometric search and V4 validator.

**Spec:** Follow-on to the 2026-10-24 program-sized massing correction, prompted by production version 32's long central hall and viable balanced search candidates being ranked after elongated candidates.

## Global constraints

- Preserve all requested spaces, setbacks, doors, furniture and export gating.
- Bedroom ratio 2:1 is a design heuristic, not a legal threshold.
- Preserve the older search order when `proposed_room_area_factor` is absent.
- Publish only after complete Python/Node/benchmark/production checks.

## Review focus

- A top-ranked geometry can pass proportion checks but fail physical validation; bounded alternatives remain available.
- Cases with no balanced geometry still show actual failure, not a fabricated third design.
- Smaller/one-floor and large plots must not lose valid alternatives.
- A compact bedroom wing can trade against corridor length; inspect both metrics.
- DXF `AC1024` and PDF output must still match the actual selected geometry.

---

### Task 1: Rank balanced wings during geometry search

**Files:** `backend/design/general_engine.py`, `tests/test_adaptive_selection.py`.

**Interfaces:** `search()` computes sleeping-room aspect from net cell dimensions. For program-sized V4 briefs, balanced candidates rank ahead of elongated ones, then retain existing massing score order.

- [x] Add a failing real-brief search test showing spine chooses an elongated bedroom despite balanced candidates in its pool.
- [x] Observe the failure with ratio 2.59.
- [x] Implement quality-first ordering for V4 and preserve legacy ordering.
- [x] Run focused search and portfolio tests; update a prior diagnostic expectation because all examined V4 layouts can now be balanced.

### Task 2: Verify, merge and publish

- [ ] Run the full test suite, five-case V4 matrix, PDF/DXF audit, and browser generation.
- [ ] Check that the selected plans improve actual measured circulation or functional routes; document any trade-offs.
- [ ] Merge only green checks and publish from merged `main` to the existing Site.
- [ ] Run strict live proof and production SA/YE browser QA.
