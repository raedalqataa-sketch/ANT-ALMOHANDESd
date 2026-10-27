# Customer engine UI implementation plan

Goal: make the reviewed architectural intelligence path accessible from the actual customer intake and provide an honest Gemini-assisted path with server-only credentials.

Architecture: retained React intake → same-origin Gemini JSON adviser (optional) → existing browser Python geometry and authoritative validation → existing PDF/DXF. Legacy mode remains available. No API keys in browser bundles, no inferred paid authorization, no fake Gemini fallback.

- [x] Add failing contract tests for missing credentials, authentication, free-tier guard, malformed/duplicate advice and provider errors.
- [x] Add browser-safe Python entry point reusing existing topology/validation/export. Test legacy, new mode and structured advice rejection.
- [x] Add Arabic provider selection, real connection status, explicit remote data consent and measured result summary; wire bridge/worker.
- [x] Preserve assets and audience; add bounded server adviser, safe configuration and deployment tests.
- [x] Run complete Python/JS suite, browser intake-to-export checks and independent review; publish reviewed customer UI.

Review focus: missing runtime secret; quota/billing guard; stale client results; invalid advice; accepted geometry/export gating. Actual Gemini inference remains blocked until hosted secret + confirmed free-tier configuration exist. Native Sites starter scripts were unavailable; preserve existing static assets, use documented ESM fetch artifact interface if hosted Worker packaging supports retained assets, and verify before publication.

Evidence: Python336 passed (one existing Starlette deprecation warning); Node40 passed; fresh runtime + integration builds passed; actual browser intake produced3 accepted models, zero detected gaps, PDF/DXF downloads. Gemini live inference NOT run: runtime secret absent. Hosted deployment verification follows packaging.
