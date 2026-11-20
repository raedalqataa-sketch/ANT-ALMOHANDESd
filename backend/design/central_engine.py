"""Site-aware orchestration and release contract for the central engine."""
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from uuid import uuid4

from .architect_planner import ClientIntent, generate_automatic
from .auto_repair import fingerprint
from .window_clearance import inspect_window_clearance

PROFILE = "site-v4"
SCHEMA = "central-design-v1"
REQUIRED_CHECKS = frozenset({
    "V4-program", "V4-functional-paths", "V4-furniture-clearance", "V4-geos-independent",
})
FILE_TYPES = {"pdf", "dxf", "json", "svg"}
RUN_ID = re.compile(r"[a-f0-9]{32}")
PREFIX = "/api/central/v1/runs"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verified_files(candidate, source):
    """Reject incomplete, changed or unreviewed drawing sets before release."""
    release = candidate["release"]
    if not release["drawing_export_allowed"]:
        return None
    checks = {row["check_id"]: row["status"] for row in candidate["checks"]}
    if (release["executive_issue_allowed"] or "FAIL" in checks.values()
            or any(checks.get(key) != "PASS" for key in REQUIRED_CHECKS)):
        return None
    revision = candidate["model_revision_id"]
    if candidate["geometry_sha256"] != fingerprint(candidate):
        return None
    audit = candidate.get("export_audit", {})
    if (audit.get("audit_errors") != 0 or audit.get("dxf_version") != "AC1024"
            or audit.get("model_revision_id") != revision):
        return None
    downloads = candidate["downloads"]
    previews = candidate["previews"]
    if set(downloads) != {"pdf", "dxf", "json"} or set(previews) != {"SITE", *(f["id"] for f in candidate["floors"])}:
        return None
    expected = {ext: f"{revision}.{ext}" for ext in downloads} | {
        f"preview-{key}": f"{revision}-{key}.svg" for key in previews
    }
    for links, prefix in ((downloads, ""), (previews, "preview-")):
        if any(url != "/api/files/" + expected[prefix + key] for key, url in links.items()):
            return None
    for filename in expected.values():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+\.(pdf|dxf|json|svg)", filename):
            return None
        path = source / filename
        if not path.is_file() or not path.stat().st_size:
            return None
    try:
        drawing_record = json.loads((source / expected["json"]).read_bytes())
        if fingerprint(drawing_record) != candidate["geometry_sha256"]:
            return None
    except (ValueError, TypeError, KeyError):
        return None
    return expected


def diagnostic(candidate):
    """Measure actual geometry without altering the engine's preference order."""
    from quality_review.space_efficiency import measure_candidate
    from quality_review.unallocated_geometry import measure_model

    utilization = measure_candidate(candidate)
    residuals = measure_model(candidate)
    window_review = inspect_window_clearance(candidate)
    return {
        "revision": candidate["model_revision_id"],
        "largest_floor_m2": candidate["metrics"]["floor_built_m2"],
        "gross_circulation_union_m2": round(sum(
            f["gross_circulation_union_area_m2"] for f in utilization["floors"]), 4),
        "diagnostic_unallocated_gross_m2": round(sum(
            f["unallocated_gross_area_m2"] for f in residuals["floors"]), 5),
        "functional_paths": len(candidate["functional_program_v4"]["movement"]["routes"]),
        "unreachable_paths": len(candidate["functional_program_v4"]["movement"]["unreachable"]),
        "pending_checks": sum(check["status"] == "PENDING" for check in candidate["checks"]),
        "window_clearance_diagnostic": window_review,
    }


def generate_central(intent: ClientIntent, output_dir: Path):
    """Generate via V4 and publish the admitted files as one isolated run."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    with TemporaryDirectory(prefix=".central-", dir=root) as temp:
        staging = Path(temp)
        generated = generate_automatic(intent, staging / "engine", generation_v4=True)
        release_dir = staging / "release"
        release_dir.mkdir()
        result = {
            "schema_version": SCHEMA, "profile": PROFILE, "run_id": run_id,
            "status": "BLOCKED", "candidates": [],
            "unavailable": list(generated["unavailable"]), "planning": generated["planning"],
            "scope": generated["scope"], "ai": generated["ai"],
            "comparison": [], "files": {},
        }
        for candidate in generated["candidates"]:
            source = staging / "engine"
            files = verified_files(candidate, source)
            if files is None:
                result["unavailable"].append({
                    "family": candidate["candidate_id"], "label": "إصدار الرسم",
                    "reason": "تعذّر التحقق من تطابق الهندسة والفحوص وملفات الإصدار.",
                })
                continue
            metrics = diagnostic(candidate)
            links = {key: f"{PREFIX}/{run_id}/files/{name}" for key, name in files.items()}
            model = dict(candidate, downloads={key: links[key] for key in candidate["downloads"]},
                         previews={key: links[f"preview-{key}"] for key in candidate["previews"]})
            for key, filename in files.items():
                target = release_dir / filename
                if key == "json":
                    write_json(target, model)
                else:
                    # Rename within staging to keep the original verified bytes.
                    (source / filename).rename(target)
                blob = target.read_bytes()
                result["files"][filename] = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
            result["candidates"].append(model)
            result["comparison"].append(metrics)
        if result["candidates"]:
            result["status"] = "DRAFT_REVIEW"
        result["candidate_count"] = len(result["candidates"])
        write_json(release_dir / "result.json", result)
        release_dir.rename(root / run_id)
    return result


def find_file(root, run_id, filename):
    """Serve files referenced by the isolated release manifest only."""
    if not RUN_ID.fullmatch(run_id) or Path(filename).name != filename:
        return None
    directory = Path(root) / run_id
    manifest = directory / "result.json"
    if not manifest.is_file():
        return None
    result = json.loads(manifest.read_bytes())
    recorded = result["files"].get(filename)
    path = directory / filename
    if (not recorded or path.suffix.lstrip(".") not in FILE_TYPES
            or not path.is_file() or path.stat().st_size != recorded["bytes"]):
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != recorded["sha256"]:
        return None
    return path
