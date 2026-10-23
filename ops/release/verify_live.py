"""Read-only production-site CLIENT engine verification against checked-out GitHub code.

Requires no credentials. Does not publish, mutate, or pass/fail on release
labels alone. Reads the real static browser engine ZIP and verifies source bytes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

REPO = Path(__file__).resolve().parents[2]
DEFAULT_URL = "https://ant-villa-personal.woollybat9.chatgpt.site"
PROOF_FILES = (
    "backend/design/general_engine.py",
    "backend/design/architect_planner.py",
    "backend/design/functional_program.py",
    "backend/design/independent_audit.py",
    "backend/design/allocation_repair.py",
    "backend/design/meander_geometry.py",
    "backend/design/layout_mutations.py",
    "backend/design/execution_coordination.py",
    "backend/design/engineering_selection.py",
)


def _download(url, timeout, size_limit):
    req = Request(url, headers={"User-Agent": "ANT-ALMOHANDES/engine-provenance-check"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status} at {url}")
        data = response.read(size_limit + 1)
        if len(data) > size_limit:
            raise RuntimeError(f"resource exceeds maximum expected size at {url}")
        return data


def inspect_archive(payload, repository=REPO):
    """Compare individual architect engine Python files (including new V4 files)."""
    measurements = []
    with ZipFile(io.BytesIO(payload)) as archive:
        for path in PROOF_FILES:
            wanted = (repository / path).read_bytes()
            if path not in archive.namelist():
                measurements.append({"file": path, "status": "MISSING_ON_SITE"})
                continue
            actual = archive.read(path)
            measurements.append({
                "file": path,
                "status": "MATCH" if actual == wanted else "DIFFERENT",
                "git_sha256": hashlib.sha256(wanted).hexdigest(),
                "site_sha256": hashlib.sha256(actual).hexdigest(),
            })
    return measurements


def verify(base_url=DEFAULT_URL, *, expected_commit=None, timeout=20,
           fetch=_download, repository=REPO):
    root = base_url.rstrip("/")
    result = {
        "site_url": root,
        "expected_git_commit": expected_commit,
        "status": "UNREACHABLE",
        "live_site_published": False,
        "verified_same_engine": False,
        "executive_approved": False,
    }
    try:
        info_bytes = fetch(root + "/client/client-source.json", timeout, 2 * 1024 * 1024)
        info = json.loads(info_bytes)
        engine_bytes = fetch(root + "/client/villa-engine/engine.zip", timeout, 100 * 1024 * 1024)
        live_engine_digest = hashlib.sha256(engine_bytes).hexdigest()
        measurements = inspect_archive(engine_bytes, repository)
        declared_digest = info.get("engine_sha256")
        reported_equals_file = bool(declared_digest) and declared_digest == live_engine_digest
        source_equals_checkout = all(x["status"] == "MATCH" for x in measurements)
        result.update({
            "status": "MATCH" if reported_equals_file and source_equals_checkout else "MISMATCH",
            "live_site_published": True,
            "source_manifest": {
                "engine_version": info.get("engine_version"),
                "planner_version": info.get("planner_version"),
                "selection_revision": info.get("selection_revision"),
                "declared_engine_sha256": declared_digest,
            },
            "engine_url": root + "/client/villa-engine/engine.zip",
            "actual_engine_sha256": live_engine_digest,
            "manifest_matches_download": reported_equals_file,
            "measured_files": measurements,
            "verified_same_engine": reported_equals_file and source_equals_checkout,
        })
    except (HTTPError, URLError, RuntimeError, ValueError, KeyError, BadZipFile, OSError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=DEFAULT_URL)
    parser.add_argument("--expected-commit", default=None)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", type=Path, default=Path("live-engine-proof.json"))
    args = parser.parse_args()
    output = verify(args.site, expected_commit=args.expected_commit, timeout=args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "measured_files"}, indent=2))
    return 0 if output["verified_same_engine"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
