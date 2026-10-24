"""Stage pinned, locally served Pyodide engineering wheels for the client worker."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def _download(url):
    with urlopen(url, timeout=40) as response:
        payload = response.read(15 * 1024 * 1024 + 1)
    if len(payload) > 15 * 1024 * 1024:
        raise ValueError("Pyodide engineering wheel is unexpectedly large")
    return payload


def prepare_browser_dependencies(runtime_dir, wheels_dir, studio_manifest_path,
                                 client_manifest_path, *, fetch=_download):
    runtime_dir, wheels_dir = Path(runtime_dir), Path(wheels_dir)
    studio_manifest_path, client_manifest_path = Path(studio_manifest_path), Path(client_manifest_path)
    manifest = json.loads(studio_manifest_path.read_text())
    lock = json.loads((runtime_dir / "pyodide-lock.json").read_text())
    staged = {}
    for package, destination in (("shapely", runtime_dir), ("networkx", wheels_dir)):
        package_info = lock["packages"][package]
        filename, expected = package_info["file_name"], package_info["sha256"]
        if Path(filename).name != filename or not filename.endswith(".whl"):
            raise ValueError(f"unsafe Pyodide wheel filename: {filename}")
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / filename
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            payload = path.read_bytes()
        else:
            url = f"https://cdn.jsdelivr.net/pyodide/v{manifest['pyodide_version']}/full/{filename}"
            payload = fetch(url)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"Pyodide {package} wheel SHA-256 differs from runtime lock")
        path.write_bytes(payload)
        staged[package] = filename
    client_manifest = dict(manifest)
    client_manifest["pure_wheels"] = list(dict.fromkeys([*manifest["pure_wheels"], staged["networkx"]]))
    client_manifest["engineering_wasm_packages"] = ["shapely"]
    client_manifest["engineering_wheel_sha256"] = {
        name: lock["packages"][name]["sha256"] for name in staged
    }
    client_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    client_manifest_path.write_text(json.dumps(client_manifest, ensure_ascii=False, indent=2) + "\n")
    return client_manifest
