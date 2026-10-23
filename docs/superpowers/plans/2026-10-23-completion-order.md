# Completion Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the new 13-stage order against the existing ANT-ALMOHANDES engine, publish only verifiable drafts, and record every remaining engineering limit.

**Architecture:** Keep the existing Python generation and Site checkout. Add release provenance around the real browser engine, run independent geometry and browser checks, and retain unsupported capabilities as explicit blockers rather than fabricated plans.

**Tech Stack:** Python 3.11+, Pytest, Shapely, OR-Tools, NetworkX, React/Vite, Node test runner, Playwright, GitHub Actions, Sites.

**Spec:** User PDF `1-ANT_ALMOHANDES_CODEX_COMPLETION_ORDER_AR (1).pdf`, supplied 2026-10-23.

## Global Constraints

- Preserve the existing repository, Git history, public Site ID, `/client/` route, and previous published version for rollback.
- Keep P02/P05 excluded from design-reference analysis; active corpus P01/P03/P04/P06/P07/P08 (6 projects, 19 unique images).
- Export DXF AC1024 and line-only plans; never export a failed critical candidate or call a draft an approved executive drawing.
- Do not apply Saudi regulations to Yemen or invent legal rules from reference-plan images.
- Do not require paid APIs for basic generation.

## Review Focus

- An older Site can carry a truthful internal ZIP hash while still differing from GitHub: the strict gate compares ZIP source bytes and the checked-out Git SHA.
- A Site manifest can match the ZIP while serving stale JavaScript: the strict gate downloads and hashes every listed client file.
- A changed plan can retain old export files: the engine reruns geometry and functional checks before export.
- A small or unusual plot can yield fewer than three valid alternatives: preserve the request and explain search exhaustion.
- A locked revision can be mutated by a repair operation: reject mutation until an authorized new revision exists.

---

### Task 1: Bind a release to source and served bytes

**Files:** `ops/release/manifest.py`, `ops/release/verify_live.py`, `client_web/build_site.py`, `tests/test_release_manifest.py`, `tests/test_live_release_provenance.py`.

**Interfaces:** `write_release_manifest(client_dir, git_commit, build_number, built_at)` produces `client/release-manifest.json`; `verify(..., strict_release=True)` proves source, SHA, and served assets.

- [x] Add a failing test for a stale commit, a tampered client script, and a real bundle hash.
- [x] Observe the tests fail for the missing behavior.
- [x] Generate a manifest from the actual build output and compare live downloaded bytes.
- [x] Run focused tests and verify all pass.
- [ ] Commit, merge, build from the merged SHA, publish to the existing Site, and run the live proof.

### Task 2: Make a failed release proof fail a visible gate

**Files:** `.github/workflows/live-engine-proof.yml`, `.github/workflows/live-release-gate.yml`.

**Interfaces:** Pre-release monitor is labeled informational; `workflow_dispatch` release gate exits nonzero for `MISMATCH` or missing manifest.

- [x] Separate the informational monitor from the blocking gate.
- [ ] Run the gate on `main` after production publication and retain its artifact.

### Task 3: Reassess architectural gaps without weakening acceptance

**Files:** `quality_review/v4/EXECUTION_STATE_AR.md`, `quality_review/completion_order/status.json`, relevant engine modules and tests for any feasible new corrective work.

**Interfaces:** Each phase and requirement records `COMPLETED`, `PARTIAL`, `BLOCKED`, or `NOT_IMPLEMENTED`, with concrete file/test evidence and no legal approval claim.

- [ ] Cross-check every PDF item against current `main`, including the newer room mutation and independent audit code.
- [ ] Implement independently testable geometry/repair corrections supported by present input data.
- [ ] Mark polygon survey, full local law, structural/MEP approval, and investment generation accurately where not implemented.

### Task 4: Exercise real alternatives and downloads

**Files:** `quality_review/v4_benchmark.py`, QA evidence artifacts, browser/e2e tests where needed.

**Interfaces:** Matrix records candidate counts, statuses, measured geometry, time, PDF/DXF/JSON outcomes and the 20×30m family-9 case without assuming unprovided legal setbacks.

- [ ] Run `python -m pip check` and complete Python/Node/React/Playwright checks.
- [ ] Run the V4 matrix and independent PDF/DXF opening checks.
- [ ] Test the exact deployed client, automatic generation, and downloads in Saudi and Yemen sample journeys.

### Task 5: Publish and hand over traceable evidence

**Files:** Site source checkout, `web_studio/deployment.json`, final Arabic report and JSON status ledger.

**Interfaces:** Publish only the existing `appgprj_6ad2972fcff881919ea4894cc4f51c22`; retain exact Site version/deployment IDs and old version for rollback.

- [ ] Merge only after branch checks pass.
- [ ] Save/deploy a bundle built from merged `main` and record the live version.
- [ ] Run strict live release gate and browser QA; preserve `MATCH` evidence.
- [ ] Deliver usable URL, PR, SHA, sample artifacts, and remaining blockers in Arabic.
