"""Create a source-verified manifest for a browser engine ZIP release."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from .verify_live import PROOF_FILES, REPO


def create_manifest(repository, bundle, *, source_paths=PROOF_FILES, git_sha,
                    engine_version, build_number, rules_version, built_at):
    """Refuse an engine ZIP if any required source file is absent or stale."""
    repository=Path(repository)
    bundle=Path(bundle)
    files={}
    with ZipFile(bundle) as archive:
        names=archive.namelist()
        for name in source_paths:
            if names.count(name)!=1:
                raise ValueError(f"expected exactly one bundle entry: {name}")
            expected=(repository/name).read_bytes()
            actual=archive.read(name)
            if actual!=expected:
                raise ValueError(f"bundle differs from checked-out source: {name}")
            files[name]=hashlib.sha256(expected).hexdigest()
    return {
        'git_sha':git_sha,
        'engine_version':engine_version,
        'build_number':str(build_number),
        'built_at':built_at,
        'rules_version':rules_version,
        'files':files,
        'bundle':{'name':bundle.name,'sha256':hashlib.sha256(bundle.read_bytes()).hexdigest()},
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--engine-version',required=True)
    parser.add_argument('--build-number',required=True)
    parser.add_argument('--rules-version',required=True)
    args=parser.parse_args()
    git_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if git_sha!=args.expected_commit:
        parser.error('checked-out commit does not match --expected-commit')
    subprocess.run(['git','diff','--exit-code','HEAD','--',*PROOF_FILES],cwd=REPO,check=True)
    manifest=create_manifest(REPO,args.bundle,git_sha=git_sha,
        engine_version=args.engine_version,build_number=args.build_number,
        rules_version=args.rules_version,
        built_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(args.output)


if __name__=='__main__':
    main()
