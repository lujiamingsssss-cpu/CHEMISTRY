import hashlib
import json
from pathlib import Path

import pytest

from scripts import twinkle_stage5_h2_evidence as evidence


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _write_bundle(tmp_path: Path) -> tuple[Path, Path, dict]:
    payloads = {
        "output/frames/frame-000.png": b"synthetic-frame-000",
        "output/review/index.html": b"<title>synthetic H2 review</title>\n",
    }
    inventory = [
        {"path": path, "bytes": len(payload), "sha256": _sha256(payload)}
        for path, payload in sorted(payloads.items())
    ]
    bundle_sha = evidence.compute_bundle_sha256(inventory)
    bundle_root = tmp_path / bundle_sha
    for relative, payload in payloads.items():
        target = bundle_root / "files" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    receipt = {
        "schema": "twinkle-stage5-h2-evidence-receipt-v1",
        "milestone": "stage5-h2",
        "bundleSha256": bundle_sha,
        "inventory": inventory,
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return receipt_path, bundle_root, receipt


def test_bundle_validation_requires_content_addressed_root_and_exact_inventory(tmp_path):
    receipt_path, bundle_root, receipt = _write_bundle(tmp_path)

    bundle = evidence.validate_evidence_bundle(receipt_path, bundle_root)

    assert bundle.bundle_sha256 == receipt["bundleSha256"]
    assert bundle.resolve("output/frames/frame-000.png").read_bytes() == b"synthetic-frame-000"
    assert bundle.inventory_paths == {
        "output/frames/frame-000.png",
        "output/review/index.html",
    }


def test_bundle_validation_rejects_missing_drift_extra_and_wrong_root_name(tmp_path):
    receipt_path, bundle_root, receipt = _write_bundle(tmp_path)
    frame = bundle_root / "files/output/frames/frame-000.png"

    frame.unlink()
    with pytest.raises(evidence.EvidenceBundleError, match="missing"):
        evidence.validate_evidence_bundle(receipt_path, bundle_root)
    frame.write_bytes(b"synthetic-frame-000")

    frame.write_bytes(b"drift")
    with pytest.raises(evidence.EvidenceBundleError, match="drift"):
        evidence.validate_evidence_bundle(receipt_path, bundle_root)
    frame.write_bytes(b"synthetic-frame-000")

    extra = bundle_root / "files/output/unlisted.log"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("not in inventory", encoding="utf-8")
    with pytest.raises(evidence.EvidenceBundleError, match="unexpected"):
        evidence.validate_evidence_bundle(receipt_path, bundle_root)
    extra.unlink()

    wrong_root = tmp_path / "not-content-addressed"
    bundle_root.rename(wrong_root)
    with pytest.raises(evidence.EvidenceBundleError, match="directory name"):
        evidence.validate_evidence_bundle(receipt_path, wrong_root)


@pytest.mark.parametrize(
    "unsafe",
    [
        "../escape",
        "/absolute",
        "C:" + "/absolute",
        "output/../escape",
        "files\\escape",
    ],
)
def test_receipt_rejects_unsafe_or_noncanonical_paths(tmp_path, unsafe):
    inventory = [{"path": unsafe, "bytes": 1, "sha256": _sha256(b"x")}]
    receipt = {
        "schema": "twinkle-stage5-h2-evidence-receipt-v1",
        "milestone": "stage5-h2",
        "bundleSha256": "0" * 64,
        "inventory": inventory,
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(evidence.EvidenceBundleError, match="path"):
        evidence.validate_evidence_bundle(receipt_path, tmp_path / ("0" * 64))


def test_resolver_never_falls_back_to_an_unlisted_external_file(tmp_path):
    receipt_path, bundle_root, _ = _write_bundle(tmp_path)
    bundle = evidence.validate_evidence_bundle(receipt_path, bundle_root)

    with pytest.raises(evidence.EvidenceBundleError, match="not listed"):
        bundle.resolve("output/secret-unlisted.bin")


def test_tree_inventory_compacts_many_files_without_weakening_exact_validation(tmp_path):
    files = {
        "frame-000.png": b"frame-zero",
        "nested/frame-001.png": b"frame-one",
    }
    tree_digest = hashlib.sha256()
    for relative, payload in sorted(files.items()):
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(_sha256(payload).encode("ascii"))
        tree_digest.update(b"\n")
    inventory = [
        {
            "kind": "tree",
            "path": "output/frames",
            "fileCount": len(files),
            "bytes": sum(map(len, files.values())),
            "treeSha256": tree_digest.hexdigest().upper(),
        }
    ]
    bundle_sha = evidence.compute_bundle_sha256(inventory)
    bundle_root = tmp_path / bundle_sha / "files/output/frames"
    for relative, payload in files.items():
        target = bundle_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    receipt = {
        "schema": "twinkle-stage5-h2-evidence-receipt-v1",
        "milestone": "stage5-h2",
        "bundleSha256": bundle_sha,
        "inventory": inventory,
    }
    receipt_path = tmp_path / "tree-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    bundle = evidence.validate_evidence_bundle(receipt_path, bundle_root.parents[2])

    assert bundle.resolve("output/frames").is_dir()
    assert bundle.resolve("output/frames/nested").is_dir()
    assert bundle.resolve("output/frames/frame-000.png").read_bytes() == b"frame-zero"
    assert bundle.resolve("output/frames/nested/frame-001.png").read_bytes() == b"frame-one"
    with pytest.raises(evidence.EvidenceBundleError, match="not listed"):
        bundle.resolve("output/frames/missing.png")


def test_bundle_builder_copies_only_receipted_files_and_refuses_overwrite(tmp_path):
    source = tmp_path / "source"
    (source / "output/frames").mkdir(parents=True)
    (source / "output/frames/frame-000.png").write_bytes(b"frame")
    (source / "output/review.json").write_bytes(b"{}\n")
    frame_sha = _sha256(b"frame")
    tree_hash = hashlib.sha256(
        b"frame-000.png\0" + frame_sha.encode("ascii") + b"\n"
    ).hexdigest().upper()
    inventory = [
        {
            "kind": "tree",
            "path": "output/frames",
            "fileCount": 1,
            "bytes": 5,
            "treeSha256": tree_hash,
        },
        {
            "kind": "file",
            "path": "output/review.json",
            "bytes": 3,
            "sha256": _sha256(b"{}\n"),
        },
    ]
    bundle_sha = evidence.compute_bundle_sha256(inventory)
    receipt = {
        "schema": "twinkle-stage5-h2-evidence-receipt-v1",
        "milestone": "stage5-h2",
        "bundleSha256": bundle_sha,
        "inventory": inventory,
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    bundle = evidence.build_evidence_bundle(source, tmp_path / "bundles", receipt_path)

    assert bundle.root.name == bundle_sha
    assert bundle.resolve("output/review.json").read_bytes() == b"{}\n"
    with pytest.raises(evidence.EvidenceBundleError, match="already exists"):
        evidence.build_evidence_bundle(source, tmp_path / "bundles", receipt_path)


def test_declared_bundle_totals_must_match_the_inventory(tmp_path):
    receipt_path, bundle_root, receipt = _write_bundle(tmp_path)
    receipt["bundleFileCount"] = 99
    receipt["bundleBytes"] = 99
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(evidence.EvidenceBundleError, match="totals"):
        evidence.validate_evidence_bundle(receipt_path, bundle_root)
