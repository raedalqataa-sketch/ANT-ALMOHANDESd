"""Run offline source and selected behavioural checks on pinned branch snapshots."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
KEY_TESTS = {
    "relationship-milp": "test_assl_stage012_gate_fail_closed.py",
    "relational-first": "test_assl_stage012_window_clearance.py",
    "structural-replanning": "test_assl_structural_011.py",
    "functional-groups": "test_assl_functional_groups_012.py",
    "feedback-replan": "test_assl_replan_010.py",
    "door-circulation": "test_assl_openings_009.py",
    "diverse-topology": "test_assl_topology_options.py",
    "diversity-qa": "test_assl_topology_options.py",
    "constraint-packing": "test_assl_free_layout_solver.py",
    "functional-graph": "test_assl_free_layout_audit.py",
    "compact-hub": "test_assl_architectural_composer.py",
    "composition-first": "test_assl_architectural_composer.py",
    "assl-geometry": "test_assl_free_layout_audit.py",
    "assl-regulatory": "test_assl_integration_gate.py",
    "space-efficiency": "test_space_efficiency_cells.py",
    "architectural-intelligence": "test_architectural_intelligence.py",
    "massing": "test_massing_quality.py",
    "municipal": "test_saudi_2024_geometry.py",
    "overlays": "test_saudi_2024_overlay.py",
    "plot-evidence": "test_plot_intake.py",
    "rear-corner": "test_site_placement.py",
    "guest-distributor": "test_guest_distributor_contract.py",
    "privacy-repair": "test_v3_repair_diagnosis.py",
    "v4-relayout": "test_layout_mutations_v4.py",
    "v4-integrated": "test_engineering_integration_v4.py",
    "v4-functional": "test_v4_engine.py",
    "worker-lifecycle": "worker_session.test.cjs",
    "lovable-browser": "lovable_bridge.test.cjs",
    "customer-generation": "test_browser_runtime_dependencies.py",
    "release-proof": "test_live_release_provenance.py",
    "live-engine": "test_release_manifest.py",
    "logtura": "telemetry.test.cjs",
    "gemini": "test_gemini_provider.py",
    "ai-auto": "test_ai_lab_credentials.py",
    "features-v1": "test_automatic_features.py",
    "reference-informed": "test_reference_patterns.py",
    "architecture-constitution": "test_constitution_v2.py",
    "adaptive-residential": "test_multi_country_design.py",
}
BASELINES = ("test_general.py", "test_design.py", "test_engine.py")


def execute(command, cwd, timeout, env):
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)
        output = proc.stdout + proc.stderr
        return {"status": "pass" if proc.returncode == 0 else "fail",
                "exit_code": proc.returncode, "output": output[-6000:]}
    except subprocess.TimeoutExpired as error:
        def decode(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
        return {"status": "timeout", "output": (decode(error.stdout) + decode(error.stderr))[-6000:]}


def inspect(ref, sha, timeout):
    start = time.monotonic()
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL"}}
    env.update(PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    with tempfile.TemporaryDirectory(prefix="ant-branch-") as folder:
        source = Path(folder)
        with subprocess.Popen(["git", "archive", sha], cwd=ROOT, stdout=subprocess.PIPE) as archive:
            with tarfile.open(fileobj=archive.stdout, mode="r|") as files:
                files.extractall(source, filter="data")
            if archive.wait() != 0:
                raise RuntimeError(f"Cannot extract {ref}")
        env["HOME"] = folder
        features = [name for name in ("assl", "client_web", "backend/design/general_engine.py",
                                      "backend/design/architect_planner.py", "backend/design/functional_program.py",
                                      "backend/design/layout_rebuild.py", "backend/design/independent_audit.py")
                    if (source / name).exists()]
        syntax = execute([sys.executable, "-m", "compileall", "-q",
                          *[name for name in ("backend", "assl") if (source / name).exists()]], source, 25, env)
        tests = source / "tests"
        requested = next((test for marker, test in KEY_TESTS.items() if marker in ref and (tests / test).exists()), None)
        name = requested or next((test for test in BASELINES if (tests / test).exists()), None)
        if not name:
            check = {"status": "missing", "output": "No supported test entry point"}
        else:
            cmd = ["node", "--test", f"tests/{name}"] if name.endswith(".cjs") else [
                sys.executable, "-m", "pytest", "-q", f"tests/{name}"]
            if not requested and name == "test_general.py":
                cmd.extend(["-k", "input_validation_and_reference_migration or independent_recheck"])
            check = execute(cmd, source, timeout, env)
    return {"branch": ref, "commit": sha, "features": features, "syntax": syntax,
            "test": name, "check": check, "seconds": round(time.monotonic() - start, 2)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--refs", type=Path, required=True, help="Saved git ls-remote --heads output")
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--timeout", type=int, default=60)
    cli.add_argument("--workers", type=int, default=3)
    opts = cli.parse_args()
    refs = [(ref.removeprefix("refs/heads/"), sha) for sha, ref in
            (line.split() for line in opts.refs.read_text().splitlines() if line.strip())]
    if any(not re.fullmatch("[a-f0-9]{40}", sha) for _, sha in refs):
        raise ValueError("Invalid commit")
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=opts.workers) as pool:
        results = []
        for row in pool.map(lambda item: inspect(*item, opts.timeout), refs):
            results.append(row)
            print(row["branch"], row["test"], row["check"]["status"], flush=True)
    opts.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
