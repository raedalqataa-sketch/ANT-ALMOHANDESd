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
