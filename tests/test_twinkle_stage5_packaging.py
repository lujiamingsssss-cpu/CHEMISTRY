import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import package_twinkle_stage5 as packaging
from scripts.package_twinkle_stage5 import (
    PackagingError,
    load_runtime_contract,
    migrate_runtime_assets,
    publish_asset_authority,
)


PNG = b"\x89PNG\r\n\x1a\nfixture"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _write_contract(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    manifest = source / "output" / "authority" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest_bytes = b'{"schema":"fixture-authority-v1"}\n'
    manifest.write_bytes(manifest_bytes)
    asset = source / "output" / "authority" / "frame-000.png"
    asset.write_bytes(PNG)

    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema": "twinkle-stage5-m0-dry-run-v1",
                "authorities": [
                    {
                        "id": "fixture-authority",
                        "sourcePath": "output/authority/manifest.json",
                        "schema": "fixture-authority-v1",
                        "sha256": _sha256(manifest_bytes),
                        "bytes": len(manifest_bytes),
                    }
                ],
                "selectedRoutes": [],
                "runtimeInventory": {
                    "fileCount": 1,
                    "totalBytes": len(PNG),
                    "byRole": [
                        {"role": "c360", "fileCount": 1, "totalBytes": len(PNG)}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "role",
                "routeId",
                "sourceManifest",
                "sourcePath",
                "targetPath",
                "sha256",
                "bytes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "role": "c360",
                "routeId": "",
                "sourceManifest": "fixture-authority",
                "sourcePath": "output/authority/frame-000.png",
                "targetPath": "showcase/homepage/assets/twinkle/c360/frame-000.png",
                "sha256": _sha256(PNG),
                "bytes": len(PNG),
            }
        )
    return source, summary, inventory


def test_load_runtime_contract_validates_authority_and_materialized_png(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)

    contract = load_runtime_contract(source, summary, inventory)

    assert contract.file_count == 1
    assert contract.total_bytes == len(PNG)
    assert contract.files[0].target_path == Path(
        "showcase/homepage/assets/twinkle/c360/frame-000.png"
    )
    assert contract.authorities[0].sha256 == _sha256(
        (source / "output/authority/manifest.json").read_bytes()
    )


def _rewrite_inventory(inventory: Path, **changes: str) -> None:
    with inventory.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(changes)
    with inventory.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _rewrite_summary_counts(summary: Path, byte_count: int) -> None:
    value = json.loads(summary.read_text(encoding="utf-8"))
    value["runtimeInventory"]["totalBytes"] = byte_count
    value["runtimeInventory"]["byRole"][0]["totalBytes"] = byte_count
    summary.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sourcePath", "../escape.png", "unsafe repository-relative path"),
        ("targetPath", "../escape.png", "unsafe repository-relative path"),
        ("targetPath", "C:" "/escape.png", "unsafe repository-relative path"),
        ("targetPath", "showcase\\homepage\\escape.png", "unsafe repository-relative path"),
    ],
)
def test_load_runtime_contract_rejects_path_escape(
    tmp_path, field, value, message
):
    source, summary, inventory = _write_contract(tmp_path)
    _rewrite_inventory(inventory, **{field: value})

    with pytest.raises(PackagingError, match=message):
        load_runtime_contract(source, summary, inventory)


def test_load_runtime_contract_rejects_missing_source(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    (source / "output/authority/frame-000.png").unlink()

    with pytest.raises(PackagingError, match="required source is missing"):
        load_runtime_contract(source, summary, inventory)


def test_load_runtime_contract_rejects_sha_drift(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    (source / "output/authority/frame-000.png").write_bytes(
        b"\x89PNG\r\n\x1a\nFIxture"
    )

    with pytest.raises(PackagingError, match="asset SHA drift"):
        load_runtime_contract(source, summary, inventory)


def test_load_runtime_contract_rejects_byte_drift(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    _rewrite_inventory(inventory, bytes=str(len(PNG) + 1))

    with pytest.raises(PackagingError, match="asset byte drift"):
        load_runtime_contract(source, summary, inventory)


def test_load_runtime_contract_rejects_unmaterialized_lfs_pointer(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
        b"size 1\n"
    )
    (source / "output/authority/frame-000.png").write_bytes(pointer)
    _rewrite_inventory(
        inventory, sha256=_sha256(pointer), bytes=str(len(pointer))
    )
    _rewrite_summary_counts(summary, len(pointer))

    with pytest.raises(PackagingError, match="not a materialized PNG"):
        load_runtime_contract(source, summary, inventory)


def test_load_runtime_contract_accepts_composite_provenance_when_every_id_exists(
    tmp_path,
):
    source, summary, inventory = _write_contract(tmp_path)
    second = source / "output/second/manifest.json"
    second.parent.mkdir(parents=True)
    second_bytes = b'{"schema":"fixture-second-v1"}\n'
    second.write_bytes(second_bytes)
    value = json.loads(summary.read_text(encoding="utf-8"))
    value["authorities"].append(
        {
            "id": "fixture-second",
            "sourcePath": "output/second/manifest.json",
            "schema": "fixture-second-v1",
            "sha256": _sha256(second_bytes),
            "bytes": len(second_bytes),
        }
    )
    summary.write_text(json.dumps(value), encoding="utf-8")
    _rewrite_inventory(
        inventory, sourceManifest="fixture-authority+fixture-second"
    )

    contract = load_runtime_contract(source, summary, inventory)

    assert contract.files[0].source_manifest == (
        "fixture-authority+fixture-second"
    )


def test_migrate_runtime_assets_publishes_exact_inventory_by_atomic_directory_rename(
    tmp_path,
):
    source, summary, inventory = _write_contract(tmp_path)
    contract = load_runtime_contract(source, summary, inventory)
    target = tmp_path / "target"
    (target / "showcase/homepage/assets").mkdir(parents=True)

    destination = migrate_runtime_assets(source, target, contract)

    assert destination == target / "showcase/homepage/assets/twinkle"
    assert [path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()] == [
        "c360/frame-000.png"
    ]
    assert (destination / "c360/frame-000.png").read_bytes() == PNG
    assert not list((target / "showcase/homepage/assets").glob(".twinkle-stage5-*.staging"))


def test_migrate_runtime_assets_rejects_existing_target_without_writing(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    contract = load_runtime_contract(source, summary, inventory)
    target = tmp_path / "target"
    destination = target / "showcase/homepage/assets/twinkle"
    destination.mkdir(parents=True)
    sentinel = destination / "sentinel.txt"
    sentinel.write_text("existing", encoding="utf-8")

    with pytest.raises(PackagingError, match="destination already exists"):
        migrate_runtime_assets(source, target, contract)

    assert sentinel.read_text(encoding="utf-8") == "existing"


def test_migrate_runtime_assets_removes_only_own_staging_after_injected_copy_failure(
    tmp_path, monkeypatch
):
    source, summary, inventory = _write_contract(tmp_path)
    contract = load_runtime_contract(source, summary, inventory)
    target = tmp_path / "target"
    assets = target / "showcase/homepage/assets"
    assets.mkdir(parents=True)
    unrelated = assets / ".twinkle-stage5-unrelated.staging"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep", encoding="utf-8")

    def fail_copy(*_args, **_kwargs):
        raise OSError("injected copy failure")

    monkeypatch.setattr(packaging.shutil, "copyfile", fail_copy)

    with pytest.raises(PackagingError, match="runtime migration failed"):
        migrate_runtime_assets(source, target, contract)

    assert (unrelated / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (assets / "twinkle").exists()
    assert [path.name for path in assets.glob(".twinkle-stage5-*.staging")] == [
        unrelated.name
    ]


def test_load_runtime_contract_rejects_reparse_point_in_source_path(tmp_path):
    source, summary, inventory = _write_contract(tmp_path)
    link = source / "output/linked-authority"
    try:
        link.symlink_to(source / "output/authority", target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"directory symlinks unavailable: {error}")
        result = subprocess.run(
            [
                "cmd",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(source / "output/authority"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            pytest.fail(f"could not create test junction: {result.stderr or result.stdout}")
    _rewrite_inventory(
        inventory, sourcePath="output/linked-authority/frame-000.png"
    )

    try:
        with pytest.raises(PackagingError, match="reparse point is not allowed"):
            load_runtime_contract(source, summary, inventory)
    finally:
        link.rmdir()


def test_migrate_runtime_assets_rejects_extra_staged_file_and_rolls_back(
    tmp_path, monkeypatch
):
    source, summary, inventory = _write_contract(tmp_path)
    contract = load_runtime_contract(source, summary, inventory)
    target = tmp_path / "target"
    assets = target / "showcase/homepage/assets"
    assets.mkdir(parents=True)
    real_copy = packaging.shutil.copyfile

    def inject_extra(source_path, target_path):
        result = real_copy(source_path, target_path)
        Path(target_path).with_name("unexpected.png").write_bytes(PNG)
        return result

    monkeypatch.setattr(packaging.shutil, "copyfile", inject_extra)

    with pytest.raises(PackagingError, match="missing or extra files"):
        migrate_runtime_assets(source, target, contract)

    assert not (assets / "twinkle").exists()
    assert not list(assets.glob(".twinkle-stage5-*.staging"))


def test_publish_asset_authority_copies_manifest_bytes_and_generates_only_inventory(
    tmp_path,
):
    source, summary, inventory = _write_contract(tmp_path)
    contract = load_runtime_contract(source, summary, inventory)
    target = tmp_path / "target"
    target.mkdir()

    authority_path = publish_asset_authority(
        source,
        target,
        contract,
        summary,
        inventory,
        source_branch="codex/source",
        source_head="a" * 40,
    )

    assert authority_path == target / "registry/twinkle/stage5-runtime-assets.json"
    manifest_copy = target / "registry/twinkle/stage5-source-manifests/fixture-authority.json"
    assert manifest_copy.read_bytes() == (
        source / "output/authority/manifest.json"
    ).read_bytes()
    value = json.loads(authority_path.read_text(encoding="utf-8"))
    assert value["schema"] == "twinkle-stage5-runtime-assets-v1"
    assert value["sourceRevision"] == {
        "branch": "codex/source",
        "head": "a" * 40,
    }
    assert value["dryRunContract"]["summarySha256"] == _sha256(
        summary.read_bytes()
    )
    assert value["dryRunContract"]["inventorySha256"] == _sha256(
        inventory.read_bytes()
    )
    assert value["runtimeInventory"]["fileCount"] == 1
    assert value["runtimeInventory"]["totalBytes"] == len(PNG)
    assert len(value["runtimeInventory"]["files"]) == 1
    assert value["runtimeInventory"]["files"][0]["targetPath"] == (
        "showcase/homepage/assets/twinkle/c360/frame-000.png"
    )
