from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DRIVE_RE = re.compile(r"^[A-Za-z]:")
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
STABLE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PackagingError(ValueError):
    pass


@dataclass(frozen=True)
class AuthorityRecord:
    id: str
    source_path: Path
    schema: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class RuntimeFile:
    role: str
    route_id: str
    source_manifest: str
    source_path: Path
    target_path: Path
    sha256: str
    bytes: int


@dataclass(frozen=True)
class RuntimeContract:
    authorities: tuple[AuthorityRecord, ...]
    files: tuple[RuntimeFile, ...]
    file_count: int
    total_bytes: int
    selected_routes: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _relative_parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise PackagingError(f"unsafe repository-relative path: {value!r}")
    if value.startswith(("/", "//")) or DRIVE_RE.match(value):
        raise PackagingError(f"unsafe repository-relative path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise PackagingError(f"unsafe repository-relative path: {value!r}")
    return pure.parts


def _is_reparse(path: Path) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _resolve_source(root: Path, value: str) -> Path:
    current = root
    for part in _relative_parts(value):
        current /= part
        if not current.exists() and not current.is_symlink():
            raise PackagingError(f"required source is missing: {value}")
        if _is_reparse(current):
            raise PackagingError(f"reparse point is not allowed: {value}")
    resolved = current.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PackagingError(f"source path escapes repository: {value}") from error
    if not resolved.is_file():
        raise PackagingError(f"source must be a regular file: {value}")
    return resolved


def _read_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackagingError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise PackagingError(f"{label} must be a JSON object")
    return value


def _validated_hash(value: object, label: str) -> str:
    normalized = str(value).upper()
    if not SHA256_RE.fullmatch(normalized):
        raise PackagingError(f"invalid SHA-256 for {label}")
    return normalized


def load_runtime_contract(
    source_repo: Path, summary_path: Path, inventory_path: Path
) -> RuntimeContract:
    source_root = Path(source_repo).resolve(strict=True)
    summary = _read_json(Path(summary_path), "dry-run summary")
    if summary.get("schema") != "twinkle-stage5-m0-dry-run-v1":
        raise PackagingError("dry-run summary schema mismatch")

    authorities = []
    authority_ids = set()
    for record in summary.get("authorities", []):
        if not isinstance(record, dict):
            raise PackagingError("authority record must be an object")
        authority_id = record.get("id")
        if not isinstance(authority_id, str) or not authority_id or authority_id in authority_ids:
            raise PackagingError("authority ids must be unique non-empty strings")
        authority_ids.add(authority_id)
        source_value = record.get("sourcePath")
        path = _resolve_source(source_root, source_value)
        expected_hash = _validated_hash(record.get("sha256"), authority_id)
        expected_bytes = record.get("bytes")
        if path.stat().st_size != expected_bytes or _sha256(path) != expected_hash:
            raise PackagingError(f"authority drift: {authority_id}")
        authorities.append(
            AuthorityRecord(
                id=authority_id,
                source_path=Path(source_value),
                schema=str(record.get("schema")),
                sha256=expected_hash,
                bytes=expected_bytes,
            )
        )
    if not authorities:
        raise PackagingError("dry-run summary has no authorities")

    expected_fields = {
        "role",
        "routeId",
        "sourceManifest",
        "sourcePath",
        "targetPath",
        "sha256",
        "bytes",
    }
    try:
        with Path(inventory_path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if set(reader.fieldnames or ()) != expected_fields:
                raise PackagingError("dry-run CSV columns mismatch")
            rows = list(reader)
    except OSError as error:
        raise PackagingError(f"cannot read dry-run CSV: {inventory_path}") from error

    files = []
    source_paths = set()
    target_paths = set()
    role_counts = Counter()
    role_bytes = Counter()
    total_bytes = 0
    for row in rows:
        provenance_ids = row["sourceManifest"].split("+")
        if (
            not all(provenance_ids)
            or len(set(provenance_ids)) != len(provenance_ids)
            or any(value not in authority_ids for value in provenance_ids)
        ):
            raise PackagingError(f"unknown source manifest: {row['sourceManifest']}")
        source_value = row["sourcePath"]
        target_value = row["targetPath"]
        source_path = _resolve_source(source_root, source_value)
        target_parts = _relative_parts(target_value)
        if target_value in target_paths or source_value in source_paths:
            raise PackagingError("dry-run paths must be unique")
        source_paths.add(source_value)
        target_paths.add(target_value)
        expected_hash = _validated_hash(row["sha256"], source_value)
        try:
            expected_bytes = int(row["bytes"])
        except (TypeError, ValueError) as error:
            raise PackagingError(f"invalid byte count: {source_value}") from error
        if source_path.stat().st_size != expected_bytes:
            raise PackagingError(f"asset byte drift: {source_value}")
        if _sha256(source_path) != expected_hash:
            raise PackagingError(f"asset SHA drift: {source_value}")
        with source_path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise PackagingError(f"asset is not a materialized PNG: {source_value}")
        role = row["role"]
        if not role:
            raise PackagingError("runtime role must not be empty")
        role_counts[role] += 1
        role_bytes[role] += expected_bytes
        total_bytes += expected_bytes
        files.append(
            RuntimeFile(
                role=role,
                route_id=row["routeId"],
                source_manifest=row["sourceManifest"],
                source_path=Path(source_value),
                target_path=Path(*target_parts),
                sha256=expected_hash,
                bytes=expected_bytes,
            )
        )

    runtime_inventory = summary.get("runtimeInventory")
    if not isinstance(runtime_inventory, dict):
        raise PackagingError("runtime inventory summary is missing")
    if runtime_inventory.get("fileCount") != len(files):
        raise PackagingError("runtime file count drift")
    if runtime_inventory.get("totalBytes") != total_bytes:
        raise PackagingError("runtime byte count drift")
    expected_roles = {
        item["role"]: (item["fileCount"], item["totalBytes"])
        for item in runtime_inventory.get("byRole", [])
    }
    actual_roles = {
        role: (role_counts[role], role_bytes[role]) for role in role_counts
    }
    if actual_roles != expected_roles:
        raise PackagingError("runtime role inventory drift")
    selected_routes = summary.get("selectedRoutes")
    if not isinstance(selected_routes, list) or not all(
        isinstance(route, str) and route for route in selected_routes
    ):
        raise PackagingError("selected routes are invalid")
    actual_routes = {runtime_file.route_id for runtime_file in files if runtime_file.route_id}
    if actual_routes != set(selected_routes):
        raise PackagingError("selected route inventory drift")

    return RuntimeContract(
        authorities=tuple(authorities),
        files=tuple(files),
        file_count=len(files),
        total_bytes=total_bytes,
        selected_routes=tuple(selected_routes),
    )


def _runtime_relative_path(target_path: Path) -> Path:
    prefix = ("showcase", "homepage", "assets", "twinkle")
    if target_path.parts[: len(prefix)] != prefix or len(target_path.parts) == len(prefix):
        raise PackagingError(f"runtime target is outside the approved root: {target_path}")
    return Path(*target_path.parts[len(prefix) :])


def _validate_staged_runtime(stage: Path, contract: RuntimeContract) -> None:
    expected = {_runtime_relative_path(item.target_path).as_posix(): item for item in contract.files}
    actual = {}
    for path in stage.rglob("*"):
        if _is_reparse(path):
            raise PackagingError(f"reparse point in runtime staging: {path.name}")
        if path.is_file():
            actual[path.relative_to(stage).as_posix()] = path
        elif not path.is_dir():
            raise PackagingError(f"non-regular runtime staging entry: {path.name}")
    if set(actual) != set(expected):
        raise PackagingError("runtime staging has missing or extra files")
    total_bytes = 0
    for relative, item in expected.items():
        path = actual[relative]
        size = path.stat().st_size
        if size != item.bytes:
            raise PackagingError(f"staged runtime byte drift: {relative}")
        if _sha256(path) != item.sha256:
            raise PackagingError(f"staged runtime SHA drift: {relative}")
        with path.open("rb") as stream:
            if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise PackagingError(f"staged runtime is not a materialized PNG: {relative}")
        total_bytes += size
    if len(actual) != contract.file_count or total_bytes != contract.total_bytes:
        raise PackagingError("staged runtime aggregate inventory drift")


def migrate_runtime_assets(
    source_repo: Path, target_repo: Path, contract: RuntimeContract
) -> Path:
    source_root = Path(source_repo).resolve(strict=True)
    target_root = Path(target_repo).resolve(strict=True)
    assets_parent = target_root / "showcase" / "homepage" / "assets"
    if not assets_parent.is_dir():
        raise PackagingError("controlled homepage assets directory is missing")
    current = target_root
    for part in ("showcase", "homepage", "assets"):
        current /= part
        if _is_reparse(current):
            raise PackagingError("reparse point is not allowed in the target path")
    destination = assets_parent / "twinkle"
    if destination.exists() or destination.is_symlink():
        raise PackagingError("runtime destination already exists")

    stage = assets_parent / f".twinkle-stage5-{uuid.uuid4().hex}.staging"
    stage.mkdir()
    try:
        for item in contract.files:
            source = _resolve_source(source_root, item.source_path.as_posix())
            if source.stat().st_size != item.bytes or _sha256(source) != item.sha256:
                raise PackagingError(f"source drift during migration: {item.source_path}")
            with source.open("rb") as stream:
                if stream.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                    raise PackagingError(
                        f"source is not a materialized PNG: {item.source_path}"
                    )
            target = stage / _runtime_relative_path(item.target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        _validate_staged_runtime(stage, contract)
        os.replace(stage, destination)
    except (OSError, PackagingError) as error:
        if stage.exists() or stage.is_symlink():
            shutil.rmtree(stage)
        raise PackagingError(f"runtime migration failed: {error}") from error
    return destination


def _authority_document(
    contract: RuntimeContract,
    summary_path: Path,
    inventory_path: Path,
    source_branch: str,
    source_head: str,
) -> dict:
    return {
        "schema": "twinkle-stage5-runtime-assets-v1",
        "sourceRevision": {"branch": source_branch, "head": source_head},
        "dryRunContract": {
            "summarySha256": _sha256(Path(summary_path)),
            "inventorySha256": _sha256(Path(inventory_path)),
        },
        "authorities": [
            {
                "id": item.id,
                "schema": item.schema,
                "sourcePath": item.source_path.as_posix(),
                "copyPath": (
                    f"registry/twinkle/stage5-source-manifests/{item.id}.json"
                ),
                "sha256": item.sha256,
                "bytes": item.bytes,
            }
            for item in contract.authorities
        ],
        "runtimeInventory": {
            "root": "showcase/homepage/assets/twinkle",
            "fileCount": contract.file_count,
            "totalBytes": contract.total_bytes,
            "selectedRoutes": list(contract.selected_routes),
            "files": [
                {
                    "role": item.role,
                    "routeId": item.route_id,
                    "sourceManifest": item.source_manifest,
                    "sourcePath": item.source_path.as_posix(),
                    "targetPath": item.target_path.as_posix(),
                    "sha256": item.sha256,
                    "bytes": item.bytes,
                }
                for item in contract.files
            ],
        },
    }


def _validate_staged_authority(
    stage_twinkle: Path, document: dict, contract: RuntimeContract
) -> None:
    authority_path = stage_twinkle / "stage5-runtime-assets.json"
    loaded = _read_json(authority_path, "stage-five asset authority")
    if loaded != document:
        raise PackagingError("staged asset authority content drift")
    inventory = loaded.get("runtimeInventory", {})
    if (
        inventory.get("fileCount") != contract.file_count
        or inventory.get("totalBytes") != contract.total_bytes
        or len(inventory.get("files", [])) != contract.file_count
    ):
        raise PackagingError("staged asset authority inventory drift")
    expected_files = {"stage5-runtime-assets.json"}
    for item in contract.authorities:
        relative = f"stage5-source-manifests/{item.id}.json"
        expected_files.add(relative)
        copy = stage_twinkle / relative
        if copy.stat().st_size != item.bytes or _sha256(copy) != item.sha256:
            raise PackagingError(f"staged manifest copy drift: {item.id}")
    actual_files = {
        path.relative_to(stage_twinkle).as_posix()
        for path in stage_twinkle.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise PackagingError("staged authority has missing or extra files")


def publish_asset_authority(
    source_repo: Path,
    target_repo: Path,
    contract: RuntimeContract,
    summary_path: Path,
    inventory_path: Path,
    *,
    source_branch: str,
    source_head: str,
) -> Path:
    if not isinstance(source_branch, str) or not source_branch:
        raise PackagingError("source branch is required")
    if not HEAD_RE.fullmatch(source_head):
        raise PackagingError("source HEAD must be a 40-character lowercase SHA")
    for item in contract.authorities:
        if not STABLE_ID_RE.fullmatch(item.id):
            raise PackagingError(f"unsafe authority id: {item.id}")

    source_root = Path(source_repo).resolve(strict=True)
    target_root = Path(target_repo).resolve(strict=True)
    registry_parent = target_root / "registry"
    created_parent = False
    if not registry_parent.exists():
        registry_parent.mkdir()
        created_parent = True
    if _is_reparse(registry_parent) or not registry_parent.is_dir():
        raise PackagingError("registry parent must be a regular directory")
    destination = registry_parent / "twinkle"
    if destination.exists() or destination.is_symlink():
        raise PackagingError("asset authority destination already exists")

    stage = registry_parent / f".twinkle-stage5-{uuid.uuid4().hex}.staging"
    stage_twinkle = stage / "twinkle"
    stage_twinkle.mkdir(parents=True)
    try:
        manifest_dir = stage_twinkle / "stage5-source-manifests"
        manifest_dir.mkdir()
        for item in contract.authorities:
            source = _resolve_source(source_root, item.source_path.as_posix())
            if source.stat().st_size != item.bytes or _sha256(source) != item.sha256:
                raise PackagingError(f"authority drift during publish: {item.id}")
            shutil.copyfile(source, manifest_dir / f"{item.id}.json")
        document = _authority_document(
            contract,
            Path(summary_path),
            Path(inventory_path),
            source_branch,
            source_head,
        )
        (stage_twinkle / "stage5-runtime-assets.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _validate_staged_authority(stage_twinkle, document, contract)
        os.replace(stage_twinkle, destination)
        stage.rmdir()
    except (OSError, PackagingError) as error:
        if stage.exists() or stage.is_symlink():
            shutil.rmtree(stage)
        if created_parent and registry_parent.exists() and not any(registry_parent.iterdir()):
            registry_parent.rmdir()
        raise PackagingError(f"asset authority publish failed: {error}") from error
    return destination / "stage5-runtime-assets.json"
