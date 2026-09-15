"""Acceptance tests for the double-click batch wrappers in ``scripts/``.

The wrappers exist so the two repository tools can be started by double-clicking
without opening a terminal. They must stay thin: resolve the repository from
their own location, use the project virtual environment explicitly, and contain
no machine-specific absolute paths.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
DEV_PREVIEW_BAT = REPO / "scripts/dev_preview.bat"
RELEASE_VERIFY_BAT = REPO / "scripts/release_verify.bat"
WRAPPERS = (DEV_PREVIEW_BAT, RELEASE_VERIFY_BAT)
MISSING_VENV_MARKER = "Virtual environment interpreter not found"

pytestmark = pytest.mark.skipif(os.name != "nt", reason="batch wrappers are Windows-only")


def _run_wrapper(bat: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # Empty stdin lets the trailing ``pause`` return instead of blocking.
    return subprocess.run(
        ["cmd", "/c", str(bat), *args],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        input="",
        timeout=300,
    )


def test_both_wrappers_exist_beside_the_scripts_they_launch():
    assert [path.name for path in WRAPPERS if path.is_file()] == [
        "dev_preview.bat",
        "release_verify.bat",
    ]


def test_wrappers_contain_no_absolute_or_machine_specific_paths():
    for bat in WRAPPERS:
        text = bat.read_text(encoding="utf-8", errors="replace")
        assert not re.search(r"[A-Za-z]:\\", text), f"{bat.name} hard-codes a drive path"
        assert "你的名字" not in text


def test_wrappers_select_the_project_virtual_environment():
    for bat in WRAPPERS:
        text = bat.read_text(encoding="utf-8", errors="replace").lower()
        assert ".venv" in text
        assert "python.exe" in text


def test_dev_preview_wrapper_prints_targets_and_exits_zero():
    result = _run_wrapper(DEV_PREVIEW_BAT, "--print-only")

    assert result.returncode == 0
    assert "/showcase/homepage/index.html" in result.stdout


def test_release_verify_wrapper_propagates_the_underlying_exit_code():
    direct = subprocess.run(
        [sys.executable, str(REPO / "scripts/release_verify.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )

    wrapped = _run_wrapper(RELEASE_VERIFY_BAT)

    # Guard against a vacuous pass: prove the wrapper really ran the verifier.
    assert "collection_parity" in wrapped.stdout
    assert "collection_parity" in direct.stdout
    assert wrapped.returncode == direct.returncode


def test_wrappers_resolve_the_repository_from_any_working_directory(tmp_path):
    result = _run_wrapper(DEV_PREVIEW_BAT, "--print-only", cwd=tmp_path)

    assert result.returncode == 0
    assert "/showcase/homepage/index.html" in result.stdout


def test_missing_virtualenv_is_reported_clearly(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / DEV_PREVIEW_BAT.name).write_bytes(DEV_PREVIEW_BAT.read_bytes())

    result = _run_wrapper(scripts / DEV_PREVIEW_BAT.name, cwd=tmp_path)

    assert result.returncode != 0
    assert MISSING_VENV_MARKER in result.stdout


def test_running_a_wrapper_never_changes_the_working_tree():
    before = subprocess.run(
        ["git", "status", "--short"], cwd=str(REPO), check=True, capture_output=True, text=True
    ).stdout

    result = _run_wrapper(DEV_PREVIEW_BAT, "--print-only")

    after = subprocess.run(
        ["git", "status", "--short"], cwd=str(REPO), check=True, capture_output=True, text=True
    ).stdout

    # Guard against a vacuous pass: the wrapper must actually have run.
    assert result.returncode == 0
    assert "/showcase/homepage/index.html" in result.stdout
    assert before == after
