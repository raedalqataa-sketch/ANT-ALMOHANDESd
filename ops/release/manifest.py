"""Bind a public client build to its Git source and actual engine ZIP bytes."""

import hashlib
import json
from pathlib import Path


def write_release_manifest(client_dir: Path, *, git_commit: str,
                           build_number: str, built_at: str) -> dict:
    client_dir = Path(client_dir)
    if len(git_commit) != 40 or any(char not in "0123456789abcdef" for char in git_commit):
        raise ValueError("release manifest requires a full Git commit SHA")
    required = ("villa-engine/engine.zip", "client-source.json", "index.html",
                "villa-engine/generate/automatic-runtime.js")
    for relative in required:
        if not (client_dir / relative).is_file():
            raise FileNotFoundError(f"release is missing {relative}")
    files = {}
    for path in sorted(client_dir.rglob("*")):
        if path.is_file() and path.name != "release-manifest.json":
            relative = path.relative_to(client_dir).as_posix()
            files[f"client/{relative}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = json.loads((client_dir / "client-source.json").read_text())
    manifest = {
        "schema_version": 1,
        "git_commit": git_commit,
        "engine_version": metadata.get("engine_version"),
        "planner_version": metadata.get("planner_version"),
        "reference_patterns_revision": metadata.get("reference_patterns_revision"),
        "build_number": str(build_number),
        "built_at": built_at,
        "bundle_sha256": files["client/villa-engine/engine.zip"],
        "files": files,
        "executive_approval": False,
    }
    (client_dir / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest
