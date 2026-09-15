import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts/build_twinkle_stage5_h2_full_flow_review.py"
RECEIPT = REPO / "registry/twinkle/stage5-h2-evidence-receipt.json"


def _builder():
    spec = importlib.util.spec_from_file_location("twinkle_h2_portability", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_real_review_never_falls_back_to_large_files_in_the_dirty_repository():
    module = _builder()

    with pytest.raises(module.ReviewValidationError, match="explicit evidence root"):
        module.plan_review(REPO)
    with pytest.raises(module.ReviewValidationError, match="explicit evidence root"):
        module.validate_milestone_evidence(REPO, None)


def test_builder_cli_exposes_explicit_evidence_validation_mode():
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--help"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--evidence-root" in result.stdout
    assert "--validate-evidence" in result.stdout


def test_committed_receipt_binds_current_formal_results_and_compact_tree_inventory():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["schema"] == "twinkle-stage5-h2-evidence-receipt-v1"
    assert receipt["milestone"] == "stage5-h2"
    assert receipt["outcomeSummary"] == {
        "pass": 18,
        "fail": 0,
        "blocked": 0,
        "error": 0,
    }
    assert receipt["formalEvidence"] == {
        "browserResultsSha256": "FD8000AB655F88B743C2CBB80F926C1FD747E7BECFF7B899D5D4DD5E2CC4E026",
        "machineResultsSha256": "2E95D6A241373F8CFEBB24734FB3FAB92EAFF4A9710F0EB0EF0258D1879823B6",
        "reviewPageSha256": "B5E693D91312AB1D1B153418D53F08E9FBBEE07B1E1E897E06CC007B4AA6F9D7",
        "reviewManifestSha256": "F6965D48C261FD4608177D380D75270D18F3D9DA6CF439F3057FB518CC2DCD4D",
        "condenserScreenshotSha256": "79DFF7411B33C0A338CB63EB42EFB433972AD77F81298EF343ED3F5CED443F63",
        "chamberScreenshotSha256": "7394FFDC7267605F8DF4CBCB22ECB71BA0FE3F6B2BA792036B23DE5BC64039F3",
    }
    tree_paths = {
        record["path"]
        for record in receipt["inventory"]
        if record.get("kind") == "tree"
    }
    assert "output/twinkle-stage5-a192-full-sequence/frames" in tree_paths
    assert "showcase/homepage/assets/twinkle-condenser-unified-v1" in tree_paths
    assert any("full-quality-focus-candidates/routes" in path for path in tree_paths)
    serialized = json.dumps(receipt, ensure_ascii=False).lower()
    for excluded in ("session", "trace", "http-stderr", "failed-attempt"):
        assert excluded not in serialized


def test_builder_hard_codes_formal_evidence_and_never_falls_back_for_output(tmp_path):
    module = _builder()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert module.EXPECTED_FORMAL_EVIDENCE == receipt["formalEvidence"]
    local_only = tmp_path / "output/local-only.bin"
    local_only.parent.mkdir(parents=True)
    local_only.write_bytes(b"must not be accepted")

    class EmptyBundle:
        inventory_paths = set()

        @staticmethod
        def resolve(relative):
            raise module.EvidenceBundleError(f"evidence path is not listed: {relative}")

    with pytest.raises(module.EvidenceBundleError, match="not listed"):
        module._resolve(tmp_path, EmptyBundle(), "output/local-only.bin")


def test_sha_bound_core_authorities_disable_checkout_eol_conversion():
    paths = [
        "registry/twinkle/stage5-source-manifests/stage4-c2.json",
        "registry/twinkle/stage5-source-manifests/stage4-c360.json",
        "registry/twinkle/stage5-source-manifests/stage3-r2.json",
        "registry/twinkle/stage5-condenser-homepage-v1.json",
        "registry/twinkle/stage5-runtime-assets.json",
        "scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py",
        "scripts/build_twinkle_stage5_a192_full_sequence.py",
        "scripts/build_twinkle_stage5_entry_count_pilot.py",
        "showcase/homepage/catalog/ring-gallery-core.mjs",
        "showcase/homepage/catalog/product-items.mjs",
    ]
    result = subprocess.run(
        ["git", "check-attr", "text", "--stdin"],
        cwd=REPO,
        input=("\n".join(paths) + "\n").encode(),
        check=True,
        capture_output=True,
    )

    assert result.stdout.decode().splitlines() == [
        f"{path}: text: unset" for path in paths
    ]


def test_sha_bound_authorities_are_stored_verbatim_in_git():
    module = _builder()
    runtime = json.loads(
        (REPO / "registry/twinkle/stage5-runtime-assets.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        record["copyPath"]: record["sha256"]
        for record in runtime["authorities"]
    }
    expected.update(
        {
            path: digest
            for path, digest in module.EXPECTED_HASHES.items()
            if path.startswith("scripts/")
        }
    )

    actual = {
        path: hashlib.sha256(
            subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=REPO)
        ).hexdigest().upper()
        for path in expected
    }

    assert actual == expected
