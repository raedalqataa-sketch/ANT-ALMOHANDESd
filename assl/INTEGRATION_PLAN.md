# ASSL Space Optimizer — experimental gate (2026-10-28)

## Implemented on the experimental branch
- Draft legal rule resolver with source status, no legal certification/enforcement.
- Read-only room diagnostics and existing-alternative selection.
- **Opt-in pre-materialization search ranking** in backend/design/general_engine.py:
  \`generate_general(brief, assl_space_optimize=True)\`.
- Existing default is \`assl_space_optimize=False\`; normal HTTP route is unchanged.
- Candidate scoring uses request-aware room excess, soft aspect ratios, original
  geometric search cost and an approximate hall-rectangle proxy.
- Original geometric validation remains authoritative. Scoring never overrides
  failed guest privacy, basic furniture clearance, local legal uncertainty or drawing release gates.
- Test coverage: prior 21 unit cases, 14 optimizer cases, and 4 static
  wiring/syntax cases (39 written; CI run must be verified).

## Archived evidence (NOT fresh generation)
Artifact: \`github-actions-artifact-12700763630.zip\`.
Running \`python scripts/assl_archive_benchmark.py artifact.zip report.json\`
re-evaluates three genuine generator outputs generated from synthetic briefs:
- SA corner: 288.69 -> 276.75 m2 gross, movement 52.61 -> 52.40 m2.
- SA large: baseline retained (412.66 m2, movement 73.08 m2);
  the smaller option regressed circulation and was deliberately not recommended.
- YE medium: 296.60 -> 284.16 m2 gross, movement 62.17 -> 52.87 m2.
Aggregated selection savings: **24.38 m2 gross; 9.51 m2 reported circulation**.
All recommended geometries **already existed** in the archived result. This is
selection improvement, not newly synthesized geometry or evidence of
fresh-generator performance. Source files and published drawings are unchanged.

## Required next verification gates before any deployment
1. Verify GitHub Actions branch run logs: \`assl-experimental.yml\` and full regression suite.
2. Execute full current generator on fixed brief/seed pairs with flag OFF versus ON,
   including PDF and DXF output, and preserve original program and geometry hashes.
3. Independently compare room shape, exact circulation union, windows, direct
   natural ventilation, furniture, guest access and actual walking paths.
4. Require no new failed checks or regression in critical/previously passed checks.
5. Compare search/runtime cost and meaningful plan diversity with >=3 candidates.
6. Review pending daylight/ventilation/privacy, and acquire authoritative local legal sources.
7. Obtain owner approval separately before main merge, live integration or rollout.

## Non-goals/risks
- Cannot declare a legal PASS for unverified national or local code.
- Hall rectangle area is a search proxy, NOT traversable circulation union.
- An existing-alternative re-ranker is NOT an automated geometric repairer.
- This branch is on ANT-ALMOHANDESd (secondary repo); production primary
  ANT-ALMOHANDES remains untouched.
