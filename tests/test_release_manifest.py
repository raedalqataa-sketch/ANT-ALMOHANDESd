import hashlib
import json

from ops.release.manifest import write_release_manifest


def test_release_manifest_binds_commit_and_actual_engine_bundle(tmp_path):
    client = tmp_path / "client"
    engine = client / "villa-engine"
    engine.mkdir(parents=True)
    (engine / "engine.zip").write_bytes(b"actual-engine-bundle")
    (client / "client-source.json").write_bytes(b'{"engine_version":"0.6.2-general"}')
    (client / "index.html").write_bytes(b"<html>client</html>")
    (engine / "generate").mkdir()
    (engine / "generate" / "automatic-runtime.js").write_bytes(b"real-runtime")

    result = write_release_manifest(client, git_commit="a" * 40,
                                    build_number="test-42", built_at="2026-10-23T00:00:00Z")
    saved = json.loads((client / "release-manifest.json").read_text())

    assert result == saved
    assert saved["git_commit"] == "a" * 40
    assert saved["build_number"] == "test-42"
    assert saved["files"]["client/villa-engine/engine.zip"] == hashlib.sha256(b"actual-engine-bundle").hexdigest()
    assert saved["bundle_sha256"] == saved["files"]["client/villa-engine/engine.zip"]
    assert saved["files"]["client/client-source.json"] == hashlib.sha256(b'{"engine_version":"0.6.2-general"}').hexdigest()
    assert saved["files"]["client/villa-engine/generate/automatic-runtime.js"] == hashlib.sha256(b"real-runtime").hexdigest()
    assert "client/release-manifest.json" not in saved["files"]
