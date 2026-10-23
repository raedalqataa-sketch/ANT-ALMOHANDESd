# Architectural engineering toolchain / أدوات المحرك الهندسي

This branch installs and smoke-tests **backend** dependencies for geometry, constraint
optimization, graph analysis, image preprocessing, and PDF parsing. The application
remains in draft mode; installing these packages does not by itself upgrade plan
quality or certify buildability.

## Setup

The backend uses **Python 3.11** (see `Dockerfile`).

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q tests/test_engineering_toolchain.py
python -m pytest -q
```

Or build the existing `Dockerfile`:
```bash
docker build -t ant-almohandes:engineering-toolchain .
```

- **OR-Tools**: future layout-constraint solver, currently smoke-tested independently.
- **Shapely**: robust 2D geometry and overlap checks.
- **NetworkX**: functional adjacency and circulation graphs.
- **OpenCV headless**: raster preprocessing, without a desktop GUI.
- **pypdf + pypdfium2**: PDF metadata/vector text access and raster rendering.
- **ezdxf** (already present): DXF R2010 output.
- **pytest** (already present): automated regression checks.

Do not treat PDF/image parsing as authoritative site dimension or street-boundary
recognition; scanned drawings and map coordinates still require validation of
scale, north, provenance, street data, and parcel boundaries.

## Frontend and browser test tools

The repository also includes `client_web` (Vite/React), installed with `npm ci`.
Three.js and its type definitions are installed in `client_web` for future
3D viewing features; no 3D scene or architectural output is changed by
installation alone. Playwright is installed as a development dependency,
with a browser smoke-test workflow. The browser runs in CI rather than the
production FastAPI image. Both `package.json` and `package-lock.json` were
updated using `npm install`; do not hand-edit npm lockfile metadata.

To run the browser smoke test locally:
```bash
cd client_web
npm ci
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

## Safety/release

- Work on a branch and use a pull request.
- Existing published architecture, approved drawings, and outputs are unchanged.
- Check Python package license obligations and dependency security prior to
  production release.
- CI verifies compatibility; professional architectural/code review remains
  required for any "executive-ready" claim.

## V4 integration (opt-in only)

The `generation_v4=True` path now invokes:

1. `independent_audit.inspect` in `functional_program.assess`. Shapely
   checks real room rectangles for positive-area overlaps and for parts outside
   the measured footprint envelope. Hard geometric faults block export through
   the ordinary V4 `checks` contract. NetworkX measures the physical
   door/corridor adjacency graph; unreachable rooms yield a **PENDING**
   circulation-review item, not invented fire-egress approval.
2. `engineering_selection.choose_distinct_subset` via
   `design_selection.select(..., optimization='cp_sat')`. Only candidates
   already permitted by geometry and other checks enter the CP-SAT portfolio.
   The solver maximizes the number of materially different designs (up to
   three), then prefers better-scoring plans; it never fabricates duplicates.
   The solver reports its status and whether that portfolio selection is
   optimal. This is **not proof of optimal floor allocation**.
3. `tests/test_engineering_integration_v4.py` verifies fault injection and
   CP-SAT's improvement over greedy selection. The existing real V4 integration
   test verifies GEOS and CP-SAT evidence appears on generated drawings.

**Legacy and V3 remain unchanged.** V4 remains explicitly requested and
draft-only. Outdoor balcony/yard and future investment parcel approval require
independent surveying and local-code review. The approved villa-almahfad
requirements JSON at `requirements/villa-almahfad.json` specifies **20 × 30 m**
and does not establish street edges, frontage or enforceable setbacks.

The raster parser libraries are dependencies ready for a later *explicitly
specified, calibrated* intake flow; they do not convert unscaled images into
surveyed land or prove street ownership. Three.js is installed in the client,
but no fabricated 3D building model is generated.

## Extended V4 geometry and execution-evidence gates

A fifth orthogonal family, `meander`, now connects three variable-width
room clusters by two lateral corridor junctions. It is searched by default
**only in the opt-in V4 generator** and remains bounded by rectangular
land plots and right-angled cell geometry. Tests verify actual corridor
continuity and absence of spatial overlaps.

The older V4 room allocation search has a CP-SAT fallback if its greedy/beam
packing runs out of capacity. It assigns the **same room bundles** to other
lanes, without reducing requested area or splitting the guest suite. This
is followed by the ordinary wall/door/furniture construction and independent
geometry, access and functional validation. It does not mutate an
already approved drawing.

If the initial V4 proposals fail or do not provide three distinct valid
designs, the repair search can also try the meandering corridor and other
alternative morphologies. `layout_rebuild.replacement_evidence` compares
a rejected candidate with a complete new valid draft and records **actual
room center displacements, room size differences and corridor changes**,
rejecting a changed brief, changed room IDs, floor change, locked source
or any failed output. This is whole-plan replacement, not arbitrary
face dragging on a validated execution drawing.

`execution_coordination.assess` checks the **gross** occupied cells against
the plot buildable rectangle inferred from entered setbacks. Violations
produce `V4-site-gross-envelope: FAIL`. It also exposes detailed
**PENDING** inputs for parcel/street verification, municipality-specific
rules, structural grids and geotechnical calculations, sanitary risers,
electrical and HVAC routes, life safety and multidisciplinary signoff.
A wet-room stacking report is **only a spatial coordination hint**. It is
not an MEP calculation, structural verification or evidence that country
or local building-code compliance was approved.

Relevant tests:

```bash
python -m pytest -q tests/test_meander_geometry.py
python -m pytest -q tests/test_execution_coordination_v4.py
python -m pytest -q tests/test_allocation_repair.py
python -m pytest -q tests/test_v4_engine.py
```

**Release policy:** V4 returns DRAFT_REVIEW with executive approval false.
Do not merge, publish or advertise construction-ready drawings unless all
CI checks pass and the missing survey, code, structure and MEP requirements
have been independently completed and licensed reviewers have signed.
