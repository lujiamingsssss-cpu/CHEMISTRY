import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = REPO / "registry/twinkle/stage5-runtime-assets.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def test_stage5_asset_authority_has_exact_manifest_copies_and_runtime_inventory():
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    assert authority["schema"] == "twinkle-stage5-runtime-assets-v1"
    assert authority["sourceRevision"] == {
        "branch": "codex/twinkle-hotspot-page-revision",
        "head": "4b8f43e4ca5cf636432392d330c51e1faa8d2d78",
    }
    assert len(authority["authorities"]) == 7
    for record in authority["authorities"]:
        copy = REPO / record["copyPath"]
        assert copy.is_file()
        assert copy.stat().st_size == record["bytes"]
        assert _sha256(copy) == record["sha256"]

    inventory = authority["runtimeInventory"]
    files = inventory["files"]
    assert inventory["root"] == "showcase/homepage/assets/twinkle"
    assert inventory["fileCount"] == len(files) == 248
    assert inventory["totalBytes"] == sum(item["bytes"] for item in files) == 130_156_891
    assert set(inventory["selectedRoutes"]) == {
        "dual_channel_collection_optics_chamber--entry-006--A",
        "dual_channel_collection_optics_chamber--entry-065--B",
        "dual_channel_condenser_lens_assembly--entry-087--A",
        "dual_channel_condenser_lens_assembly--entry-008--A",
    }
    assert Counter(item["role"] for item in files) == {
        "c360": 96,
        "focus": 100,
        "mechanical-chamber": 25,
        "mechanical-condenser": 25,
        "inspection-chamber-lit": 1,
        "inspection-chamber-unlit": 1,
    }

    expected_paths = {item["targetPath"] for item in files}
    actual_paths = {
        path.relative_to(REPO).as_posix()
        for path in (REPO / inventory["root"]).rglob("*")
        if path.is_file()
    }
    assert actual_paths == expected_paths
    for item in files:
        path = REPO / item["targetPath"]
        assert path.stat().st_size == item["bytes"]
        assert _sha256(path) == item["sha256"]
        with path.open("rb") as stream:
            assert stream.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE


def test_every_runtime_png_is_lfs_targeted_while_worktree_content_is_materialized():
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    paths = [item["targetPath"] for item in authority["runtimeInventory"]["files"]]
    result = subprocess.run(
        ["git", "check-attr", "filter", "diff", "merge", "text", "--stdin"],
        cwd=REPO,
        input=("\n".join(paths) + "\n").encode(),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    lines = result.stdout.decode().splitlines()
    assert len(lines) == len(paths) * 4
    for path in paths:
        assert f"{path}: filter: lfs" in lines
        assert f"{path}: diff: lfs" in lines
        assert f"{path}: merge: lfs" in lines
        assert f"{path}: text: unset" in lines
        with (REPO / path).open("rb") as stream:
            assert stream.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE
