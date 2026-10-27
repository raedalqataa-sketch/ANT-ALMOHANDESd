# Architectural Intelligence 004 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated opt-in functional search and geometric evaluation path, prove improvements or report failures against fixed baseline cases.

**Architecture:** Preserve the existing allocator, V4 validator, exports and default API behavior. Add topology intents before allocation; vary proposed room expansion targets (never program minimums), core position and guest configurations, materialize through the existing engine, and select a structurally diverse non-dominated portfolio. Extend AI lab behind a default-off flag; AI remains an adviser. Reuse the existing reference catalogue with explicit conditioning/ablation, not claimed training.

**Tech Stack:** Python/Pydantic, Shapely, NetworkX, existing PDF/DXF and V4 path validators.

**Spec:** quality_review/intelligence_004/task.json (user supplied execution authorization).

## Global Constraints
- No main merge, production deployment, billing or secret disclosure.
- Commit/push only working branch after tests pass.
- No changes to statutory rules, program minimums, acceptance gates or exports.
- Baseline 32be0b0, deterministic seed 0; preserve unrelated dirty worktree.
- Missing old constitution files and unmeasured reference dimensions must stay explicitly unknown.

## Review Focus
- Split/relabelled halls cannot fabricate circulation savings; inspect union and path-buffer union separately.
- Same topology with altered coordinates must not count as structurally different.
- A smaller guest vestibule cannot conceal more total movement or unusable room proportions.
- Missing daylight/source data must not become PASS.
- Reference ablation must change actual proposed search order/selection and expose zero effects honestly.

### Task 1: Audit and immutable baseline
- [ ] Hash/snapshot all prior tracked/untracked files outside repository; create dedicated branch from published baseline.
- [ ] Run original suite, audit real API -> propose -> search -> allocate -> materialize -> validation -> export path.
- [ ] Write baseline_audit.md, constitution_gap_matrix.json, reference_usage_evidence.md with real paths and missing references.

### Task 2: Functional topology and independent diagnostics
Files: backend/design/intelligence/{topology,metrics}.py; tests/test_architectural_intelligence.py.
Interfaces: topology.program_graph(brief) -> dict; topology.proposals(brief, use_references=True) -> list[dict]; metrics.inspect(model) -> dict; topology.signature(model) -> dict.
- [ ] Add failing tests for privacy relations, actual signature invariance under hall splitting/room ID renaming, changed core/guest topology, 0.72m² slit evidence, circulation double counting, elongated furnished rooms as REVIEW not invented statutory failure.
- [ ] Implement from existing program/doors/room/corridor polygons, V4 paths and void detector. Report room clearance and daylight coverage with explicit scope.
- [ ] Run new unit tests.

### Task 3: Bounded experimental engine + AI integration
Files: backend/design/intelligence/engine.py; ai_lab/{schemas,pipeline}.py; tests/test_architectural_intelligence_engine.py.
Interfaces: engine.run(intent, output_dir, *, use_references=True, options=None, budget=12, emit_drawings=True) -> dict.
- [ ] Add failing opt-in/atomic-validation/original-unchanged tests.
- [ ] Propose topology/core/guest alternatives before geometry; vary 1.0/1.1/1.2 proposed area factors without changing any requested minimum. All dimensions/furniture/paths remain authoritative in V4.
- [ ] Preserve original baseline candidates as fallback; actual topology signatures define portfolio incompatibility. Report missing alternatives rather than invent diversity.
- [ ] Add bounded failure ledger, measured trade-offs and reference provenance; send topology context/metrics to existing JSON adviser only when explicitly opted in. No live calls in this task without a newly verified quota/billing budget.
- [ ] Run integration tests.

### Task 4: Paired benchmark, exports, review and branch publication
Files: quality_review/intelligence_004/{benchmark.py,results.json,REPORT_AR.md}, manual read-only CI workflow.
- [ ] Run sa600, ye-medium, sa-corner and negative geometry tests; diagnose stored Gemini A/B/C, retain exact inputs and per-candidate evidence.
- [ ] Export only accepted drafts with original exporters; independently read PDFs/DXFs, compare export audit geometry hashes and images with corridor/path/void overlays.
- [ ] Report per-case distributions/median/range, gains and regressions; reference ablation; no quality claims from test counts.
- [ ] Run complete regression suite + branch review; scan changes for secrets/unrelated files; commit/push isolated branch only. Manual CI contains no secrets or deployment.
