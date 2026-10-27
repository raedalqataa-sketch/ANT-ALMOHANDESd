"""Security and case-contract checks for the manually dispatched live experiment."""
import ast
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/'.github/workflows/gemini-live-proof.yml'


def python_blocks():
    lines=WORKFLOW.read_text().splitlines();blocks=[];index=0
    while index<len(lines):
        if lines[index].strip()=="python - <<'PY'":
            body=[];index+=1
            while lines[index].strip()!='PY':
                body.append(lines[index][10:]);index+=1
            blocks.append('\n'.join(body))
        index+=1
    return blocks


def test_workflow_is_manual_only_read_only_and_not_a_deployment():
    text=WORKFLOW.read_text()
    assert 'name: Gemini Architectural Live Test' in text
    assert 'workflow_dispatch:' in text
    assert '\n  push:' not in text and '\n  pull_request' not in text
    assert 'contents: read' in text and 'write-all' not in text
    assert '${{ secrets.GEMINI_API_KEY }}' in text
    assert 'allow_engine_fallback=False' in text
    assert "live['origin']!='LIVE_API'" in text
    assert 'actions/upload-artifact@v4' in text
    assert 'connection_only:' in text and 'default: true' in text
    assert 'echo "$GEMINI_API_KEY"' not in text and 'printenv' not in text
    for body in python_blocks():ast.parse(body)


def test_live_case_is_saudi_600m2_with_disclosed_assumptions():
    document=json.loads((ROOT/'quality_review/gemini_sa600_case.json').read_text())
    intent=document['intent']
    assert intent['country']=='SA'
    assert intent['width']==20 and intent['depth']==30 and intent['floors']=='two'
    assert intent['main_street']=='top' and intent['north_edge']=='top'
    assert document['assumptions']['family_size_not_supplied']
    assert not intent.get('street_widths')
    assert "gemini_sa600_case.json" in WORKFLOW.read_text()
    assert "'ye-medium'" not in WORKFLOW.read_text()


def test_missing_secret_stops_before_any_api_request():
    env=os.environ.copy();env.pop('GEMINI_API_KEY',None)
    result=subprocess.run(['python','-c',python_blocks()[0]],env=env,capture_output=True,text=True)
    assert result.returncode!=0
    assert 'MISSING_CREDENTIAL' in result.stderr


def test_registered_launcher_is_opt_in_and_experimental_branch_only():
    text=(ROOT/'.github/workflows/live-engine-proof.yml').read_text()
    assert 'gemini_live:' in text and 'default: false' in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "github.ref_name == 'feature/ai-auto-keys-002'" in text
    assert 'uses: ./.github/workflows/gemini-live-proof.yml' in text
    assert 'workflow_call:' in WORKFLOW.read_text()
