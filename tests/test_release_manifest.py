"""The release manifest must describe actual, byte-matched bundle contents."""
import hashlib
from pathlib import Path
from zipfile import ZipFile

from ops.release.build_manifest import create_manifest


def test_manifest_contains_source_and_bundle_hashes(tmp_path):
    source=tmp_path/'source'
    (source/'backend/design').mkdir(parents=True)
    path=source/'backend/design/engine.py'
    path.write_bytes(b'current-engine\n')
    bundle=tmp_path/'engine.zip'
    with ZipFile(bundle,'w') as archive:
        archive.write(path,'backend/design/engine.py')
    result=create_manifest(source,bundle,source_paths=('backend/design/engine.py',),
        git_sha='a'*40,engine_version='v4',build_number='42',rules_version='rules-1',
        built_at='2026-10-23T00:00:00Z')
    assert result['git_sha']=='a'*40
    assert result['build_number']=='42'
    assert result['bundle']['sha256']==hashlib.sha256(bundle.read_bytes()).hexdigest()
    assert result['files']['backend/design/engine.py']==hashlib.sha256(b'current-engine\n').hexdigest()


def test_manifest_rejects_stale_engine_bytes(tmp_path):
    source=tmp_path/'source'
    (source/'backend/design').mkdir(parents=True)
    (source/'backend/design/engine.py').write_bytes(b'new')
    bundle=tmp_path/'engine.zip'
    with ZipFile(bundle,'w') as archive:
        archive.writestr('backend/design/engine.py',b'old')
    try:
        create_manifest(source,bundle,source_paths=('backend/design/engine.py',),
            git_sha='a'*40,engine_version='v4',build_number='42',rules_version='rules-1',
            built_at='2026-10-23T00:00:00Z')
    except ValueError as error:
        assert 'backend/design/engine.py' in str(error)
    else:
        raise AssertionError('stale engine bundle was accepted')
