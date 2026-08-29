from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
CHECKER = ROOT / "scripts" / "check_current_work_hygiene.py"

REQUIRED_HEADINGS = (
    "## Active Scope",
    "## Non-goals",
    "## Authoritative State",
    "## Approval and Rollback",
    "## Complexity Budget",
    "## Temporary Artifacts",
    "## Unique Next Action",
)

VALID_CURRENT_WORK = """# Current Work

Status: active

## Active Scope
- One current task.

## Non-goals
- No deployment.

## Authoritative State
- Git and tests are authoritative.

## Approval and Rollback
- Approval: user-approved local work.
- Rollback: revert this task's files.

## Complexity Budget
- User-visible acceptance: one verified outcome.
- New dependencies: none.

## Temporary Artifacts
- None

## Unique Next Action
- Run the current acceptance check.
"""


def run_checker(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--repo", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_repo(tmp_path: Path, current_work: str = VALID_CURRENT_WORK) -> Path:
    (tmp_path / "CURRENT_WORK.md").write_text(current_work, encoding="utf-8")
    return tmp_path


def test_valid_single_control_file_passes(tmp_path: Path) -> None:
    result = run_checker(write_repo(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_completed_task_without_current_work_passes(tmp_path: Path) -> None:
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_current_work_over_12_kib_warns_without_failing(tmp_path: Path) -> None:
    result = run_checker(write_repo(tmp_path, VALID_CURRENT_WORK + ("x" * 13_000)))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING" in result.stdout
    assert "12 KiB" in result.stdout


def test_current_work_over_16_kib_is_rejected(tmp_path: Path) -> None:
    result = run_checker(write_repo(tmp_path, VALID_CURRENT_WORK + ("x" * 17_000)))
    assert result.returncode == 1
    assert "16 KiB" in result.stdout


def test_current_work_over_120_lines_is_rejected(tmp_path: Path) -> None:
    oversized = VALID_CURRENT_WORK + ("\n- evidence" * 121)
    result = run_checker(write_repo(tmp_path, oversized))
    assert result.returncode == 1
    assert "120 lines" in result.stdout


@pytest.mark.parametrize("heading", REQUIRED_HEADINGS)
def test_each_required_heading_is_mandatory(tmp_path: Path, heading: str) -> None:
    result = run_checker(write_repo(tmp_path, VALID_CURRENT_WORK.replace(heading, "", 1)))
    assert result.returncode == 1
    assert heading in result.stdout


def test_duplicate_required_heading_is_rejected(tmp_path: Path) -> None:
    duplicate = VALID_CURRENT_WORK + "\n## Active Scope\n- Duplicate.\n"
    result = run_checker(write_repo(tmp_path, duplicate))
    assert result.returncode == 1
    assert "required heading must occur exactly once: ## Active Scope" in result.stdout


def test_history_and_runtime_state_are_rejected(tmp_path: Path) -> None:
    invalid = VALID_CURRENT_WORK.replace(
        "## Unique Next Action",
        "## Verification Log\n- PID 21856 passed.\n\n## Unique Next Action",
    )
    result = run_checker(write_repo(tmp_path, invalid))
    assert result.returncode == 1
    assert "history-style heading" in result.stdout
    assert "runtime PID" in result.stdout


def test_secondary_state_documents_are_rejected(tmp_path: Path) -> None:
    repo = write_repo(tmp_path)
    secondary = repo / "docs" / "superpowers" / "reviews" / "old-review.md"
    secondary.parent.mkdir(parents=True)
    secondary.write_text("# Second control surface\n", encoding="utf-8")
    result = run_checker(repo)
    assert result.returncode == 1
    assert "secondary task-state document" in result.stdout


def test_temporary_artifacts_require_lifecycle_fields(tmp_path: Path) -> None:
    invalid = VALID_CURRENT_WORK.replace(
        "- None\n\n## Unique Next Action",
        "- path=C:\\temp\\thing | owner=task\n\n## Unique Next Action",
    )
    result = run_checker(write_repo(tmp_path, invalid))
    assert result.returncode == 1
    for field in ("purpose=", "recovery=", "cleanup="):
        assert field in result.stdout


def test_repository_startup_rules_invoke_the_gate_unconditionally() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "只要存在 `CURRENT_WORK.md`" in agents
    assert "python scripts/check_current_work_hygiene.py --repo ." in agents
    assert "不得主观判断" in agents
    assert "不得新增“继承但不属于当前 checkout”" in agents


def test_repository_rules_define_current_checkout_authority() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required_rules = (
        "git rev-parse --show-toplevel",
        "当前 checkout 根目录的 `AGENTS.md`",
        "不得把主仓、另一个 Worktree 或其他 checkout 的 `AGENTS.md`",
        "git worktree list --porcelain",
        "目录分隔符、斜杠方向或大小写差异",
        "纯路径格式差异",
        "分支、HEAD、任务状态或实际目录",
        "main 中提交的 `AGENTS.md` 是未来新 Worktree 的长期基线",
        "现有 Worktree 仍读取自己的 checkout 副本",
    )
    for rule in required_rules:
        assert rule in agents


def test_playbook_template_matches_checker_contract(tmp_path: Path) -> None:
    playbook = (ROOT / "docs" / "ENGINEERING_PLAYBOOK.md").read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert heading in playbook
    for field in ("path=", "owner=", "purpose=", "recovery=", "cleanup="):
        assert field in playbook
    assert "12 KiB" in playbook
    assert "16 KiB" in playbook
    assert "120 行" in playbook

    template = re.search(r"```markdown\n(# Current Work:.*)\n```", playbook, re.DOTALL)
    assert template is not None
    result = run_checker(write_repo(tmp_path, template.group(1)))
    assert result.returncode == 0, result.stdout + result.stderr
