from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


WARN_BYTES = 12 * 1024
MAX_BYTES = 16 * 1024
MAX_LINES = 120
REQUIRED_HEADINGS = (
    "## Active Scope",
    "## Non-goals",
    "## Authoritative State",
    "## Approval and Rollback",
    "## Complexity Budget",
    "## Temporary Artifacts",
    "## Unique Next Action",
)
HISTORY_HEADINGS = re.compile(
    r"^##\s+.*(?:history|log|completed|archive|milestone|checkpoint).*$",
    re.IGNORECASE | re.MULTILINE,
)
TEMP_FIELDS = ("path=", "owner=", "purpose=", "recovery=", "cleanup=")


def section_body(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    following = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + following.start() if following else len(text)
    return text[start:end]


def check_repo(repo: Path) -> list[str]:
    errors: list[str] = []
    current_work = repo / "CURRENT_WORK.md"
    if not current_work.is_file():
        return []

    raw = current_work.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if len(raw) > MAX_BYTES:
        errors.append(f"CURRENT_WORK.md exceeds 16 KiB ({len(raw)} bytes)")
    line_count = len(text.splitlines())
    if line_count > MAX_LINES:
        errors.append(f"CURRENT_WORK.md exceeds {MAX_LINES} lines ({line_count} lines)")

    for heading in REQUIRED_HEADINGS:
        count = len(re.findall(rf"^{re.escape(heading)}$", text, re.MULTILINE))
        if count != 1:
            errors.append(f"required heading must occur exactly once: {heading}")

    status_count = len(re.findall(r"^Status:\s*\S.*$", text, re.MULTILINE))
    if status_count != 1:
        errors.append("exactly one non-empty Status: line is required")
    if HISTORY_HEADINGS.search(text):
        errors.append("history-style heading is forbidden in CURRENT_WORK.md")
    if re.search(r"\bPID\s*[:=#]?\s*\d+\b", text, re.IGNORECASE):
        errors.append("runtime PID snapshots are forbidden in CURRENT_WORK.md")

    complexity = section_body(text, "## Complexity Budget")
    for label in ("User-visible acceptance:", "New dependencies:"):
        if label not in complexity:
            errors.append(f"Complexity Budget is missing: {label}")

    temporary = section_body(text, "## Temporary Artifacts")
    bullets = [line.strip() for line in temporary.splitlines() if line.strip().startswith("-")]
    if not bullets:
        errors.append("Temporary Artifacts must contain '- None' or lifecycle entries")
    elif bullets != ["- None"]:
        for bullet in bullets:
            missing = [field for field in TEMP_FIELDS if field not in bullet]
            if missing:
                errors.append(
                    "temporary artifact entry is missing " + ", ".join(missing) + f": {bullet}"
                )

    for area in (repo / "docs" / "superpowers" / "plans", repo / "docs" / "superpowers" / "reviews"):
        if area.is_dir():
            for document in sorted(area.rglob("*.md")):
                errors.append(f"secondary task-state document is forbidden: {document.relative_to(repo)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce CURRENT_WORK.md lifecycle hygiene")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    current_work = repo / "CURRENT_WORK.md"
    if current_work.is_file() and current_work.stat().st_size > WARN_BYTES:
        print(
            "CURRENT_WORK hygiene: WARNING - "
            f"CURRENT_WORK.md exceeds 12 KiB ({current_work.stat().st_size} bytes)"
        )
    errors = check_repo(repo)
    if errors:
        print("CURRENT_WORK hygiene: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("CURRENT_WORK hygiene: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
