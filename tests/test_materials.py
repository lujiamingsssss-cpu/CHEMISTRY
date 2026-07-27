from pathlib import Path

import pytest

from chemical_trade_copilot.materials import discover_documents


def test_discover_documents_only_uses_explicit_product_folders(tmp_path: Path) -> None:
    root = tmp_path / "materials"
    der = root / "D.E.R. 331"
    epon = root / "EPON Resin 8280"
    excluded = root / "_excluded" / "D.E.N. 438__pending_TDS"
    der.mkdir(parents=True)
    epon.mkdir()
    excluded.mkdir(parents=True)

    (der / "TDS - D.E.R. 331.pdf").write_bytes(b"pdf")
    (der / "SDS - D.E.R. 331.pdf").write_bytes(b"pdf")
    (epon / "TDS - EPON Resin 8280.pdf").write_bytes(b"pdf")
    (epon / "SDS - EPON Resin 8280.pdf").write_bytes(b"pdf")
    (excluded / "SDS - D.E.N. 438.pdf").write_bytes(b"pdf")

    documents = discover_documents(root, ["D.E.R. 331", "EPON Resin 8280"])

    assert [(doc.product, doc.doc_type) for doc in documents] == [
        ("D.E.R. 331", "SDS"),
        ("D.E.R. 331", "TDS"),
        ("EPON Resin 8280", "SDS"),
        ("EPON Resin 8280", "TDS"),
    ]
    assert all("_excluded" not in str(doc.path) for doc in documents)


def test_discover_documents_rejects_missing_product_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing product folder"):
        discover_documents(tmp_path, ["D.E.R. 331"])


def test_discover_documents_rejects_unknown_document_type(tmp_path: Path) -> None:
    folder = tmp_path / "D.E.R. 331"
    folder.mkdir()
    (folder / "brochure.pdf").write_bytes(b"pdf")

    with pytest.raises(ValueError, match="TDS or SDS"):
        discover_documents(tmp_path, ["D.E.R. 331"])


def test_discover_documents_requires_one_tds_and_sds_per_product(tmp_path: Path) -> None:
    folder = tmp_path / "D.E.R. 331"
    folder.mkdir()
    (folder / "TDS - D.E.R. 331.pdf").write_bytes(b"pdf")

    with pytest.raises(ValueError, match="exactly one TDS and one SDS"):
        discover_documents(tmp_path, ["D.E.R. 331"])


def test_discover_documents_rejects_product_outside_approved_list(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "TDS - Outside.pdf").write_bytes(b"pdf")
    (outside / "SDS - Outside.pdf").write_bytes(b"pdf")

    with pytest.raises(ValueError, match="not approved"):
        discover_documents(tmp_path, [str(outside)])
