"""Validate content-addressed TWINKLE Stage 5 H2 evidence bundles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile


class EvidenceBundleError(ValueError):
    """Raised when an H2 evidence receipt or bundle is invalid."""


_SHA256 = re.compile(r"[0-9A-F]{64}")
_SCHEMA = "twinkle-stage5-h2-evidence-receipt-v1"


def _validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceBundleError(f"unsafe evidence path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
        part in {"", ".", ".."} or ":" in part for part in path.parts
    ):
        raise EvidenceBundleError(f"unsafe evidence path: {value!r}")
    return value


def _normalize_inventory(inventory: object) -> list[dict]:
    if not isinstance(inventory, list) or not inventory:
        raise EvidenceBundleError("evidence inventory must be a non-empty list")
    normalized = []
    seen = set()
    for value in inventory:
        if not isinstance(value, dict):
            raise EvidenceBundleError("invalid evidence inventory record")
        kind = value.get("kind", "file")
        allowed = (
            {"kind", "path", "bytes", "sha256"}
            if kind == "file"
            else {"kind", "path", "fileCount", "bytes", "treeSha256"}
        )
        keys = set(value)
        if kind not in {"file", "tree"} or (
            keys != allowed and keys != allowed - {"kind"}
        ):
            raise EvidenceBundleError("invalid evidence inventory record")
        relative = _validate_relative_path(value["path"])
        size = value["bytes"]
        if relative in seen:
            raise EvidenceBundleError(f"duplicate evidence path: {relative}")
        if type(size) is not int or size < 0:
            raise EvidenceBundleError(f"invalid evidence byte count: {relative}")
        seen.add(relative)
        if kind == "file":
            digest = value["sha256"]
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise EvidenceBundleError(f"invalid evidence sha256: {relative}")
            normalized.append(
                {"kind": "file", "path": relative, "bytes": size, "sha256": digest}
            )
        else:
            count = value["fileCount"]
            digest = value["treeSha256"]
            if type(count) is not int or count < 1:
                raise EvidenceBundleError(f"invalid evidence file count: {relative}")
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                raise EvidenceBundleError(f"invalid evidence tree sha256: {relative}")
            normalized.append(
                {
                    "kind": "tree",
                    "path": relative,
                    "fileCount": count,
                    "bytes": size,
                    "treeSha256": digest,
                }
            )
    paths = [PurePosixPath(record["path"]) for record in normalized]
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            if left in right.parents or right in left.parents:
                raise EvidenceBundleError("overlapping evidence inventory paths")
    return sorted(normalized, key=lambda record: record["path"])


def compute_bundle_sha256(inventory: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in _normalize_inventory(inventory):
        digest.update(record["kind"].encode("ascii"))
        digest.update(b"\0")
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        if record["kind"] == "tree":
            digest.update(str(record["fileCount"]).encode("ascii"))
            digest.update(b"\0")
        digest.update(str(record["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(
            record.get("sha256", record.get("treeSha256")).encode("ascii")
        )
        digest.update(b"\n")
    return digest.hexdigest().upper()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _tree_record(root: Path) -> tuple[int, int, str]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    total = 0
    for path in files:
        if path.is_symlink():
            raise EvidenceBundleError(f"unsafe evidence link: {path}")
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_sha256(path).encode("ascii"))
        digest.update(b"\n")
        total += path.stat().st_size
    return len(files), total, digest.hexdigest().upper()


@dataclass(frozen=True)
class EvidenceBundle:
    root: Path
    bundle_sha256: str
    inventory: tuple[dict, ...]
    validated_paths: frozenset[str]

    @property
    def inventory_paths(self) -> set[str]:
        return set(self.validated_paths) | {
            record["path"] for record in self.inventory
        }

    def resolve(self, relative: str | Path) -> Path:
        key = _validate_relative_path(PurePosixPath(relative).as_posix())
        target = self.root / "files" / Path(*PurePosixPath(key).parts)
        validated_directory = target.is_dir() and any(
            path.startswith(key + "/") for path in self.validated_paths
        )
        if key not in self.inventory_paths and not validated_directory:
            raise EvidenceBundleError(f"evidence path is not listed: {key}")
        return target


def validate_evidence_bundle(receipt_path: Path, bundle_root: Path) -> EvidenceBundle:
    receipt_path = Path(receipt_path).resolve(strict=True)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceBundleError(f"invalid evidence receipt: {receipt_path}") from error
    if not isinstance(receipt, dict) or receipt.get("schema") != _SCHEMA:
        raise EvidenceBundleError("unsupported evidence receipt schema")
    if receipt.get("milestone") != "stage5-h2":
        raise EvidenceBundleError("unexpected evidence milestone")
    inventory = _normalize_inventory(receipt.get("inventory"))
    expected_bundle_sha = compute_bundle_sha256(inventory)
    if receipt.get("bundleSha256") != expected_bundle_sha:
        raise EvidenceBundleError("evidence bundle SHA drift")
    declared_count = receipt.get("bundleFileCount")
    declared_bytes = receipt.get("bundleBytes")
    actual_count = sum(record.get("fileCount", 1) for record in inventory)
    actual_bytes = sum(record["bytes"] for record in inventory)
    if (
        declared_count is not None
        and (type(declared_count) is not int or declared_count != actual_count)
    ) or (
        declared_bytes is not None
        and (type(declared_bytes) is not int or declared_bytes != actual_bytes)
    ):
        raise EvidenceBundleError("declared evidence bundle totals drift")

    bundle_root = Path(bundle_root).resolve(strict=True)
    if bundle_root.name.upper() != expected_bundle_sha:
        raise EvidenceBundleError("evidence bundle directory name must equal bundle SHA")
    files_root = bundle_root / "files"
    if not files_root.is_dir() or files_root.is_symlink():
        raise EvidenceBundleError("evidence bundle files root is missing or unsafe")
    actual_paths = {
        path.relative_to(files_root).as_posix()
        for path in files_root.rglob("*")
        if path.is_file()
    }
    expected_paths = set()
    for record in inventory:
        relative = Path(*PurePosixPath(record["path"]).parts)
        if record["kind"] == "file":
            expected_paths.add(record["path"])
            continue
        tree_root = files_root / relative
        if not tree_root.is_dir() or tree_root.is_symlink():
            raise EvidenceBundleError(f"evidence files missing: {record['path']}")
        tree_files = sorted(path for path in tree_root.rglob("*") if path.is_file())
        tree_count, tree_bytes, tree_sha = _tree_record(tree_root)
        for path in tree_files:
            expected_paths.add(path.relative_to(files_root).as_posix())
        if (
            tree_count != record["fileCount"]
            or tree_bytes != record["bytes"]
            or tree_sha != record["treeSha256"]
        ):
            raise EvidenceBundleError(f"evidence tree drift: {record['path']}")
    missing = expected_paths - actual_paths
    unexpected = actual_paths - expected_paths
    if missing:
        raise EvidenceBundleError(f"evidence files missing: {sorted(missing)}")
    if unexpected:
        raise EvidenceBundleError(f"unexpected evidence files: {sorted(unexpected)}")
    for record in inventory:
        if record["kind"] == "tree":
            continue
        path = files_root / Path(*PurePosixPath(record["path"]).parts)
        if path.is_symlink() or path.stat().st_size != record["bytes"]:
            raise EvidenceBundleError(f"evidence file drift: {record['path']}")
        if _file_sha256(path) != record["sha256"]:
            raise EvidenceBundleError(f"evidence file drift: {record['path']}")
    return EvidenceBundle(
        bundle_root,
        expected_bundle_sha,
        tuple(inventory),
        frozenset(expected_paths),
    )


def build_evidence_bundle(
    source_root: Path, destination_parent: Path, receipt_path: Path
) -> EvidenceBundle:
    source_root = Path(source_root).resolve(strict=True)
    receipt_path = Path(receipt_path).resolve(strict=True)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    inventory = _normalize_inventory(receipt.get("inventory"))
    bundle_sha = compute_bundle_sha256(inventory)
    if receipt.get("schema") != _SCHEMA or receipt.get("milestone") != "stage5-h2":
        raise EvidenceBundleError("unsupported evidence receipt")
    if receipt.get("bundleSha256") != bundle_sha:
        raise EvidenceBundleError("evidence bundle SHA drift")
    destination_parent = Path(destination_parent).resolve()
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination = destination_parent / bundle_sha
    if destination.exists():
        raise EvidenceBundleError(f"evidence bundle already exists: {destination}")

    stage = Path(tempfile.mkdtemp(prefix=f".{bundle_sha}.", dir=destination_parent))
    try:
        files_root = stage / "files"
        for record in inventory:
            relative = Path(*PurePosixPath(record["path"]).parts)
            source = source_root / relative
            target = files_root / relative
            if record["kind"] == "tree":
                if not source.is_dir() or source.is_symlink():
                    raise EvidenceBundleError(f"evidence tree missing: {record['path']}")
                if _tree_record(source) != (
                    record["fileCount"],
                    record["bytes"],
                    record["treeSha256"],
                ):
                    raise EvidenceBundleError(f"evidence tree drift: {record['path']}")
                shutil.copytree(source, target)
            else:
                if (
                    not source.is_file()
                    or source.is_symlink()
                    or source.stat().st_size != record["bytes"]
                    or _file_sha256(source) != record["sha256"]
                ):
                    raise EvidenceBundleError(f"evidence file drift: {record['path']}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return validate_evidence_bundle(receipt_path, destination)
