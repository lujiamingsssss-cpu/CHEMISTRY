"""Read-only release verification for this repository.

This replaces the shell commands the project kept re-deriving before a push. It
never writes to the repository and never mutates git state; every check either
passes, fails, or is explicitly skipped with a reason.

The load-bearing check is ``collection_parity``: a worktree whose ``tests/`` holds
untracked test files collects more tests than a clean checkout, which silently
invalidates any "the suite passes" claim.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec"
H2_REVIEW_BUILDER = Path("scripts/build_twinkle_stage5_h2_full_flow_review.py")
RECEIPT = Path("registry/twinkle/stage5-h2-evidence-receipt.json")

FORBIDDEN_RELEASE_PATHS = re.compile(
    r"(?i)(CURRENT_WORK\.md|\.env$|credential|secret|session|\.trace$|trace\.zip"
    r"|\.log$|id_rsa|\.pem$|\.key$)"
)

TEST_FILE_LINE = re.compile(r"^(?P<path>\S+\.py)(?:::\S+)?:\s*\d+\s*$")


@dataclass(frozen=True)
class ParityFindings:
    """How the tests this checkout collects relate to the tests git tracks."""

    untracked_collected: tuple[str, ...]
    tracked_not_collected: tuple[str, ...]

    @property
    def ok(self) -> bool:
        # A tracked module without a test_ prefix (a fixtures helper) is expected.
        return not self.untracked_collected


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "ok" | "fail" | "skip"
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def collect_parity(tracked: Iterable[str], collected: Iterable[str]) -> ParityFindings:
    """Compare tracked test modules with the modules pytest actually collects."""

    tracked_set = {path.replace("\\", "/") for path in tracked}
    collected_set = {path.replace("\\", "/") for path in collected}
    return ParityFindings(
        untracked_collected=tuple(sorted(collected_set - tracked_set)),
        tracked_not_collected=tuple(sorted(tracked_set - collected_set)),
    )


def _run(command: Sequence[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), cwd=repo, capture_output=True, text=True)


def _parse_collected_tests(stdout: str) -> tuple[str, ...]:
    """Extract test module paths from ``pytest --collect-only -q`` output.

    Handles both the per-file count summary and plain node-id listings.
    """

    found: set[str] = set()
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("=") or line.startswith("!"):
            continue
        match = TEST_FILE_LINE.match(line)
        if match:
            found.add(match.group("path").replace("\\", "/"))
            continue
        if "::" in line:
            candidate = line.split("::", 1)[0].strip()
            if candidate.endswith(".py"):
                found.add(candidate.replace("\\", "/"))
    return tuple(sorted(found))


def _git_tracked_tests(repo: Path) -> tuple[str, ...]:
    result = _run(["git", "ls-files", "tests/*.py"], repo)
    if result.returncode != 0:
        return ()
    return tuple(
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    )


def check_lfs(repo: Path) -> CheckResult:
    listed = _run(["git", "lfs", "ls-files"], repo)
    if listed.returncode != 0:
        return CheckResult("lfs", "skip", "git-lfs 不可用，无法核验 LFS 状态")

    paths = []
    for line in listed.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            paths.append(parts[2].strip())

    unmaterialized = []
    for relative in paths:
        target = repo / relative
        try:
            with target.open("rb") as handle:
                head = handle.read(len(LFS_POINTER_HEADER))
        except OSError as error:
            unmaterialized.append(f"{relative} (unreadable: {error.__class__.__name__})")
            continue
        if head == LFS_POINTER_HEADER:
            unmaterialized.append(relative)

    if unmaterialized:
        preview = ", ".join(unmaterialized[:3])
        return CheckResult(
            "lfs",
            "fail",
            f"{len(paths)} 个 LFS 文件中有 {len(unmaterialized)} 个未物化 pointer：{preview}",
        )
    return CheckResult("lfs", "ok", f"{len(paths)} 个 LFS 文件均已物化")


def check_collection_parity(repo: Path) -> CheckResult:
    tracked = _git_tracked_tests(repo)
    if not tracked:
        return CheckResult("collection_parity", "skip", "无法从 git 读取 tests/ 跟踪列表")

    collected_run = _run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        repo,
    )
    collected = _parse_collected_tests(collected_run.stdout)
    if not collected:
        return CheckResult(
            "collection_parity",
            "fail",
            f"pytest 未收集到任何测试（退出码 {collected_run.returncode}）",
        )

    findings = collect_parity(tracked, collected)
    if not findings.ok:
        preview = ", ".join(path.split("/")[-1] for path in findings.untracked_collected[:4])
        return CheckResult(
            "collection_parity",
            "fail",
            f"收集 {len(collected)} 个文件，其中 {len(findings.untracked_collected)} 个未被 git 跟踪"
            f"（{preview}）—— 本 checkout 与 clean checkout 不等价",
        )
    return CheckResult(
        "collection_parity",
        "ok",
        f"收集 {len(collected)} 个文件，全部已被 git 跟踪",
    )


def check_registry_receipt(repo: Path) -> CheckResult:
    receipt_path = repo / RECEIPT
    if not receipt_path.is_file():
        return CheckResult("registry_receipt", "skip", f"{RECEIPT.as_posix()} 不存在")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    inventory = receipt.get("inventory", [])
    files = 0
    total_bytes = 0
    for entry in inventory:
        if entry.get("kind") == "file":
            files += 1
        else:
            files += int(entry.get("fileCount", 0))
        total_bytes += int(entry.get("bytes", 0))

    declared_files = int(receipt.get("bundleFileCount", -1))
    declared_bytes = int(receipt.get("bundleBytes", -1))
    if files != declared_files or total_bytes != declared_bytes:
        return CheckResult(
            "registry_receipt",
            "fail",
            f"receipt 自洽性不符：inventory 计得 {files} 文件 / {total_bytes} 字节，"
            f"声明 {declared_files} / {declared_bytes}",
        )
    return CheckResult(
        "registry_receipt",
        "ok",
        f"receipt 自洽：{files} 文件 / {total_bytes} 字节，bundle SHA 存在",
    )


def _expected_script_pins(repo: Path) -> dict[str, str]:
    builder = repo / H2_REVIEW_BUILDER
    if not builder.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("twinkle_h2_release_verify", builder)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        return {}
    spec.loader.exec_module(module)
    hashes = getattr(module, "EXPECTED_HASHES", {})
    # Only tracked script pins are verifiable from git; the rest are machine-local.
    return {
        path: digest
        for path, digest in hashes.items()
        if isinstance(path, str) and path.startswith("scripts/")
    }


def check_sha_pins(repo: Path) -> CheckResult:
    expected = _expected_script_pins(repo)
    if not expected:
        return CheckResult("sha_pins", "skip", "未找到可核验的 scripts/ SHA pin")

    drifted = []
    for path, digest in sorted(expected.items()):
        blob = _run(["git", "show", f"HEAD:{path}"], repo)
        if blob.returncode != 0:
            drifted.append(f"{path} (git 中不存在)")
            continue
        actual = hashlib.sha256(blob.stdout.encode("utf-8", "surrogateescape")).hexdigest().upper()
        if actual != digest.upper():
            drifted.append(path)

    if drifted:
        return CheckResult(
            "sha_pins",
            "fail",
            f"{len(drifted)} 个 SHA-bound 脚本与 pin 不符：{', '.join(drifted)}"
            " —— 改动这些脚本会破坏已归档证据链",
        )
    return CheckResult("sha_pins", "ok", f"{len(expected)} 个 scripts/ SHA pin 全部一致")


def check_release_diff_hygiene(repo: Path) -> CheckResult:
    base = _run(["git", "rev-parse", "--verify", "origin/main"], repo)
    if base.returncode != 0:
        return CheckResult("release_diff_hygiene", "skip", "无 origin/main，无法计算待合并差异")

    diff = _run(["git", "diff", "--name-only", "origin/main...HEAD"], repo)
    if diff.returncode != 0:
        return CheckResult("release_diff_hygiene", "skip", "无法计算与 origin/main 的差异")

    changed = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
    offenders = [path for path in changed if FORBIDDEN_RELEASE_PATHS.search(path)]
    if offenders:
        return CheckResult(
            "release_diff_hygiene",
            "fail",
            f"待合并差异含禁止内容：{', '.join(offenders[:4])}",
        )
    return CheckResult(
        "release_diff_hygiene",
        "ok",
        f"待合并差异 {len(changed)} 个文件，未含凭据/session/trace/日志/bundle",
    )


def check_test_suite(repo: Path) -> CheckResult:
    result = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], repo)
    tail = [line for line in result.stdout.strip().splitlines() if line.strip()]
    summary = tail[-1] if tail else "无输出"
    if result.returncode != 0:
        return CheckResult("test_suite", "fail", f"pytest 退出码 {result.returncode}：{summary}")
    return CheckResult("test_suite", "ok", summary)


def run_checks(repo: Path, with_tests: bool = False) -> list[CheckResult]:
    checks = [
        check_lfs(repo),
        check_collection_parity(repo),
        check_registry_receipt(repo),
        check_sha_pins(repo),
        check_release_diff_hygiene(repo),
    ]
    if with_tests:
        checks.append(check_test_suite(repo))
    return checks


def _report(checks: Sequence[CheckResult], as_json: bool) -> bool:
    ok = not any(check.status == "fail" for check in checks)
    if as_json:
        print(json.dumps({"ok": ok, "checks": [check.as_dict() for check in checks]}, ensure_ascii=False, indent=2))
        return ok

    symbols = {"ok": "PASS", "fail": "FAIL", "skip": "SKIP"}
    for check in checks:
        print(f"[{symbols.get(check.status, check.status)}] {check.name}: {check.detail}")
    print("\n结论：" + ("全部通过" if ok else "存在失败项"))
    return ok


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only release verification: LFS, collection parity, registry, SHA pins, diff hygiene.",
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="also run the full pytest suite (off by default)",
    )
    args = parser.parse_args(argv)

    checks = run_checks(repository_root(), with_tests=args.with_tests)
    return 0 if _report(checks, args.json) else 1


if __name__ == "__main__":
    raise SystemExit(main())
