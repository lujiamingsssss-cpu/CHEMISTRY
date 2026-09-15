"""Acceptance tests for scripts/release_verify.py.

The verifier replaces the ad-hoc shell commands this project kept re-deriving
before every push. Its load-bearing rule is the collection-parity check: a
worktree whose ``tests/`` holds untracked test files collects more tests than a
clean checkout, which silently invalidates any "the suite passes" claim.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/release_verify.py"


def _module():
    spec = importlib.util.spec_from_file_location("release_verify", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec so dataclasses can resolve the module by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collect_parity_flags_tests_that_are_collected_but_not_tracked():
    module = _module()

    findings = module.collect_parity(
        tracked={"tests/test_a.py"},
        collected={"tests/test_a.py", "tests/test_b.py"},
    )

    assert findings.untracked_collected == ("tests/test_b.py",)
    assert findings.ok is False


def test_collect_parity_accepts_matching_sets():
    module = _module()

    findings = module.collect_parity(
        tracked={"tests/test_a.py"},
        collected={"tests/test_a.py"},
    )

    assert findings.untracked_collected == ()
    assert findings.ok is True


def test_collect_parity_reports_tracked_modules_that_are_not_collected():
    module = _module()

    findings = module.collect_parity(
        tracked={"tests/test_a.py", "tests/twinkle_fixtures.py"},
        collected={"tests/test_a.py"},
    )

    # A tracked helper module with no test_ prefix is expected, not a failure.
    assert findings.tracked_not_collected == ("tests/twinkle_fixtures.py",)
    assert findings.ok is True


def test_cli_exposes_json_and_opt_in_test_flags():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--json" in result.stdout
    assert "--with-tests" in result.stdout


def test_cli_emits_json_report_and_never_writes_to_the_repository():
    before = subprocess.run(
        ["git", "status", "--short"], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    after = subprocess.run(
        ["git", "status", "--short"], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout

    report = json.loads(result.stdout)
    assert {"checks", "ok"} <= set(report)
    assert isinstance(report["checks"], list)
    assert {check["name"] for check in report["checks"]} >= {"lfs", "collection_parity"}
    assert before == after


def test_cli_exit_code_matches_reported_ok():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    report = json.loads(result.stdout)
    assert (result.returncode == 0) is report["ok"]
