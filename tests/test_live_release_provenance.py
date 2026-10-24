"""Deterministic mocks for publication proof; no external site or secrets needed."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from ops.release.verify_live import PROOF_FILES, inspect_archive, verify


def test_strict_release_rejects_old_site_commit_even_when_engine_files_match():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, all_engine=True, repository_commit="new-commit")
    manifest = json.dumps({
        "git_commit": "older-commit",
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {
            "client/villa-engine/engine.zip": hashlib.sha256(payload).hexdigest(),
            "client/client-source.json": hashlib.sha256(info).hexdigest(),
            "client/index.html": hashlib.sha256(b"<html></html>").hexdigest(),
            "client/villa-engine/generate/automatic-runtime.js": hashlib.sha256(b"runtime").hexdigest(),
        },
    }).encode()

    def fake_get(url, timeout, limit):
        if url.endswith("release-manifest.json"):
            return manifest
        if url.endswith("client-source.json"):
            return info
        if url.endswith("engine.zip"):
            return payload
        if url.endswith("index.html"):
            return b"<html></html>"
        return b"runtime"

    proof = verify("https://example.invalid", expected_commit="new-commit",
                   strict_release=True, fetch=fake_get)
    assert proof["status"] == "MISMATCH"
    assert not proof["verified_same_engine"]
    assert proof["release_manifest_matches"] is False


def test_strict_release_matches_commit_and_downloaded_bundle_hashes():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, all_engine=True, repository_commit="new-commit")
    manifest = json.dumps({
        "git_commit": "new-commit",
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {
            "client/villa-engine/engine.zip": hashlib.sha256(payload).hexdigest(),
            "client/client-source.json": hashlib.sha256(info).hexdigest(),
            "client/index.html": hashlib.sha256(b"<html></html>").hexdigest(),
            "client/villa-engine/generate/automatic-runtime.js": hashlib.sha256(b"runtime").hexdigest(),
        },
    }).encode()

    def fake_get(url, timeout, limit):
        if url.endswith("release-manifest.json"):
            return manifest
        if url.endswith("client-source.json"):
            return info
        if url.endswith("engine.zip"):
            return payload
        if url.endswith("index.html"):
            return b"<html></html>"
        return b"runtime"

    proof = verify("https://example.invalid", expected_commit="new-commit",
                   strict_release=True, fetch=fake_get)
    assert proof["status"] == "MATCH"
    assert proof["release_manifest_matches"]


def test_strict_release_recognizes_only_verified_cloudflare_html_injection():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, all_engine=True, repository_commit="new-commit")
    source_html = b"<!doctype html><html><body><main>Client</main></body></html>"
    cloudflare_script = (b"<script>(function(){function c(){window.__CF$cv$params={};"
                         b"var a='/cdn-cgi/challenge-platform/scripts/jsd/main.js';}"
                         b"})();</script>")
    injected_html = source_html.replace(b"</body>", cloudflare_script + b"</body>")
    files = {
        "client/villa-engine/engine.zip": payload,
        "client/client-source.json": info,
        "client/index.html": source_html,
        "client/villa-engine/generate/automatic-runtime.js": b"runtime",
    }
    manifest = json.dumps({
        "git_commit": "new-commit", "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {name: hashlib.sha256(value).hexdigest() for name, value in files.items()},
    }).encode()

    def fake_get(url, timeout, limit):
        if url.endswith("release-manifest.json"):
            return manifest
        if url.endswith("client/index.html"):
            return injected_html
        return next(value for name, value in files.items() if url.endswith(name))

    proof = verify("https://example.invalid", expected_commit="new-commit",
                   strict_release=True, fetch=fake_get)
    assert proof["status"] == "MATCH"
    assert proof["transport_html_injection_detected"] == ["client/index.html"]
    assert next(item for item in proof["release_files_checked"]
                if item["file"] == "client/index.html")["status"] == "MATCH_AFTER_CLOUDFLARE_REMOVAL"

    modified = injected_html.replace(b"Client", b"Tampered")
    def tampered_get(url, timeout, limit):
        return modified if url.endswith("client/index.html") else fake_get(url, timeout, limit)
    rejected = verify("https://example.invalid", expected_commit="new-commit",
                      strict_release=True, fetch=tampered_get)
    assert rejected["status"] == "MISMATCH"


def test_strict_release_rejects_tampered_client_script():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, all_engine=True, repository_commit="new-commit")
    script = b"original-client-code"
    manifest = json.dumps({
        "git_commit": "new-commit",
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {
            "client/villa-engine/engine.zip": hashlib.sha256(payload).hexdigest(),
            "client/client-source.json": hashlib.sha256(info).hexdigest(),
            "client/index.html": hashlib.sha256(b"<html></html>").hexdigest(),
            "client/villa-engine/generate/automatic-runtime.js": hashlib.sha256(script).hexdigest(),
        },
    }).encode()

    def fake_get(url, timeout, limit):
        if url.endswith("release-manifest.json"):
            return manifest
        if url.endswith("client-source.json"):
            return info
        if url.endswith("engine.zip"):
            return payload
        if url.endswith("index.html"):
            return b"<html></html>"
        return b"tampered-client-code"

    proof = verify("https://example.invalid", expected_commit="new-commit",
                   strict_release=True, fetch=fake_get)
    assert proof["status"] == "MISMATCH"
    assert proof["release_manifest_matches"] is False


def test_strict_release_rejects_conflicting_client_source_commit():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, all_engine=True)
    manifest = json.dumps({
        "git_commit": "new-commit",
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {
            "client/villa-engine/engine.zip": hashlib.sha256(payload).hexdigest(),
            "client/client-source.json": hashlib.sha256(info).hexdigest(),
            "client/index.html": hashlib.sha256(b"index").hexdigest(),
            "client/villa-engine/generate/automatic-runtime.js": hashlib.sha256(b"runtime").hexdigest(),
        },
    }).encode()

    def fake_get(url, timeout, limit):
        if url.endswith("release-manifest.json"):
            return manifest
        if url.endswith("client-source.json"):
            return info
        if url.endswith("engine.zip"):
            return payload
        return b"index" if url.endswith("index.html") else b"runtime"

    proof = verify("https://example.invalid", expected_commit="new-commit",
                   strict_release=True, fetch=fake_get)
    assert proof["status"] == "MISMATCH"


def make_bundle(root, *, mutate=None, all_engine=False, repository_commit=None):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        files = set(PROOF_FILES)
        if all_engine:
            files.update(str(path.relative_to(root)) for path in (root / "backend/design").glob("*.py"))
        for filename in sorted(files):
            contents = (root / filename).read_bytes()
            if filename == mutate:
                contents += b"\n# Older site version\n"
            archive.writestr(filename, contents)
    payload = buffer.getvalue()
    metadata = json.dumps({"engine_version": "review", "engine_sha256": hashlib.sha256(payload).hexdigest(),
                           "repository_commit": repository_commit}).encode()
    return payload, metadata


def test_all_engine_files_match_with_actual_zip_contents():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO)
    def fake_get(url, timeout, limit):
        return info if url.endswith("client-source.json") else payload
    proof = verify("https://example.invalid", expected_commit="1234567", fetch=fake_get)
    assert proof["status"] == "MATCH"
    assert proof["verified_same_engine"]
    assert len(proof["measured_files"]) == len(PROOF_FILES)


def test_changed_engine_is_detected_even_when_site_metadata_matches_its_old_zip():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO, mutate=PROOF_FILES[0])
    proof = verify("https://example.invalid", fetch=lambda url, *_: info if url.endswith(".json") else payload)
    assert proof["status"] == "MISMATCH"
    assert not proof["verified_same_engine"]
    assert proof["manifest_matches_download"]
    assert next(x for x in proof["measured_files"] if x["file"] == PROOF_FILES[0])["status"] == "DIFFERENT"


def test_tampered_engine_zip_is_detected_by_site_manifest():
    from ops.release.verify_live import REPO
    payload, info = make_bundle(REPO)
    data = json.loads(info)
    data["engine_sha256"] = "0" * 64
    proof = verify("https://example.invalid", fetch=lambda url, *_: json.dumps(data).encode() if url.endswith(".json") else payload)
    assert not proof["manifest_matches_download"]
    assert proof["status"] == "MISMATCH"


def test_unreachable_site_never_claimed_published():
    def unavailable(*args):
        raise OSError("not reachable")
    proof = verify("https://example.invalid", fetch=unavailable)
    assert proof["status"] == "UNREACHABLE"
    assert not proof["live_site_published"]
    assert not proof["verified_same_engine"]
