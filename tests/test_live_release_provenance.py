"""Deterministic mocks for publication proof; no external site or secrets needed."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from ops.release.verify_live import PROOF_FILES, inspect_archive, verify


def make_bundle(root, *, mutate=None):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for filename in PROOF_FILES:
            contents = (root / filename).read_bytes()
            if filename == mutate:
                contents += b"\n# Older site version\n"
            archive.writestr(filename, contents)
    payload = buffer.getvalue()
    metadata = json.dumps({"engine_version": "review", "engine_sha256": hashlib.sha256(payload).hexdigest()}).encode()
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
    assert proof["measured_files"][0]["status"] == "DIFFERENT"


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
