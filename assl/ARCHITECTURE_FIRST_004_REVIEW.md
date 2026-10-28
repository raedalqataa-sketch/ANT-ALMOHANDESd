# ARCHITECTURE-FIRST 004 — Geometry audit

**Scope:** Preliminary room/core/hall composition without furniture. No door/window verification, executive drawing or legal approval.

## Architectural corrections

- Variable customer-program room widths and upper aspect thresholds, with reserved exterior recesses instead of bloating rooms.
- Guest council, guest bathroom and short guest vestibule placed together on the outer wing edge; formerly a guest vestibule could stretch across a 9.1–13.3m-wide wing. New vestibules are about 3.3m wide.
- Reserved stair and guest vestibule are now visible in all concept SVGs.
- Connected-hall and stair-core geometric prechecks. Hall rectangle union, long straight runs, bathroom and service relationships, exterior entry potential are now measured (not statutory certification).
- A true geometry action moves underfilled front cluster room groups toward the central junction, keeping room dimensions and program intact, then shortens the unserved corridor tail. The already-reserved stair depth remains protected.
- Full concept wrapper emits three diverse families when feasible without invoking furnishing.

## Measured cluster result: before -> after geometric recenter

| Synthetic brief | Sum of room/hall rectangles over both floors (m2) | Hall rectangles including guest distributor (m2) | Family hall rectangle union over two floors (m2) |
|---|---|---|---|
| SA corner 20x25m | 280.064 -> 275.461 | 72.782 -> 68.178 | 66.8417 -> 62.2381 |
| SA large 40x32m | 408.767 -> 404.081 | 103.740 -> 88.012 | 97.6351 -> 81.9075 |
| YE medium 24x32m | 272.494 -> 267.998 | 65.917 -> 61.421 | 59.9768 -> 55.4809 |

Across all three selected two-floor cluster concepts, family hallway geometric union decreased 24.8271 m2 and gross rectangle sum decreased 13.785 m2. Hall union measures schematic hallway rectangles, NOT a traversable walking-path union. Same case and layout family, but winner geometry can differ after re-ranking.

## Evidence and remaining risks

Evidence: GitHub Actions architecture-concept artifacts, six alternatives for same cluster-family cases before/after recenter, plus separate linear/adaptive and meander variants. All outputs remain nonexecutive.

The long linear-hall families still exist and require architect review; neither lower area nor shorter run alone guarantees professional quality. Opening dimensions, independent physical guest route, visual privacy, actual street access, natural light/ventilation sufficiency, stairs and furniture clearance, DXF/PDF and full regressions remain **unverified** in this concept-only stage. The external façade checks are *potential only*. Missing local legal evidence remains UNRESOLVED.

Only the experimental branch was changed. No production main merge or deployment.
