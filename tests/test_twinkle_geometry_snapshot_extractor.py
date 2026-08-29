import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_twinkle_geometry_snapshot.py"


def test_stage1_3_sources_do_not_embed_private_absolute_paths():
    paths = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-08-20-twinkle-page-coordinated-render-design.md",
        *sorted((ROOT / "scripts").glob("*twinkle*.py")),
        ROOT / "scripts" / "twinkle_geometry_snapshot_v1.json",
        *sorted((ROOT / "tests").glob("*twinkle*.py")),
        ROOT / "tests" / "test_streamlit_app.py",
    )
    private_literal = re.compile(
        r"(?:r)?[\"'][A-Za-z]:[\\/]"
        r"|[rR][\"']\\\\"
        r"|[\"']\\\\\\\\"
        r"|(?:r)?[\"']/(?:Users|home)/",
        re.IGNORECASE,
    )
    offenders = {
        path.relative_to(ROOT).as_posix(): private_literal.findall(
            path.read_text(encoding="utf-8")
        )
        for path in paths
        if private_literal.search(path.read_text(encoding="utf-8"))
    }
    assert offenders == {}


def test_geometry_extractor_is_stdout_only_and_has_no_visual_or_save_path():
    assert SCRIPT.is_file(), "read-only geometry snapshot extractor is missing"
    source = SCRIPT.read_text(encoding="utf-8")
    assert "GEOMETRY_SNAPSHOT=" in source
    assert "bmesh.ops.convex_hull" in source
    assert "evaluated_get" in source
    assert "authorityStateOffsets" in source
    for forbidden in (
        "bpy.ops.render",
        "write_still",
        "save_as_mainfile",
        "save_mainfile",
        "write_text",
        "write_bytes",
        "mkdir",
        "output-root",
        "set_camera",
    ):
        assert forbidden not in source


def test_geometry_extractor_locks_authority_hashes_and_exact_units():
    assert SCRIPT.is_file(), "read-only geometry snapshot extractor is missing"
    source = SCRIPT.read_text(encoding="utf-8")
    assert "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81" in source
    assert "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6" in source
    assert '"unit": "dual_channel_collection_optics_chamber"' in source
    assert '"rootObjects": (' in source
    assert '"DetectBox_Bottom_Mala2020:1"' in source
    assert '"Side2_optics:1"' in source
    assert '"authorityStateOffsets": (' in source
    assert '(0.0, 0.0, -0.14)' in source
    assert '(0.0, -0.10, 0.0)' in source
    assert '"unit": "dual_channel_condenser_lens_assembly"' in source
    assert '"legacySourceObjectId": "SHOWCASE_GROUP__f_dual_acl_housing"' in source
