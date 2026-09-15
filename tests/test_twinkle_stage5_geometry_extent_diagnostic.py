import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "diagnose_twinkle_stage5_geometry_extents.py"


def _module():
    assert SCRIPT.is_file(), "geometry extent diagnostic is missing"
    spec = importlib.util.spec_from_file_location("twinkle_geometry_extents", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostic_source_is_read_only_and_never_renders() -> None:
    assert SCRIPT.is_file(), "geometry extent diagnostic is missing"
    source = SCRIPT.read_text(encoding="utf-8")

    assert "bpy.ops.render" not in source
    assert "bpy.ops.wm.save" not in source
    assert ".save_as_mainfile" not in source
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source


def test_visibility_classification_separates_model_background_and_auxiliary() -> None:
    module = _module()

    assert module.classify_object("MESH", False, False, False) == "modelForeground"
    assert module.classify_object("MESH", False, True, False) == "fixedBackgroundExcluded"
    assert module.classify_object("MESH", True, False, False) == "hiddenGeometry"
    assert module.classify_object("MESH", False, False, True) == "hiddenGeometry"
    assert module.classify_object("LIGHT", False, False, False) == "lightingOrCamera"
    assert module.classify_object("CAMERA", False, False, False) == "lightingOrCamera"
    assert module.classify_object("EMPTY", False, False, False) == "auxiliaryNonRenderable"


def test_minimum_centered_carrier_uses_geometry_and_four_edge_viewport_guards() -> None:
    module = _module()
    state_ranges = {
        "condenser.mechanicalExpanded": {"minX": -100.0, "minY": -50.0, "maxX": 800.0, "maxY": 500.0},
        "chamber.mechanicalExpanded": {"minX": 0.0, "minY": 0.0, "maxX": 640.0, "maxY": 450.0},
        "chamber.inspectionStable": {"minX": 0.0, "minY": 0.0, "maxX": 640.0, "maxY": 450.0},
    }

    result = module.minimum_centered_carrier(
        state_ranges,
        reference=(640, 450),
        viewports=((1280, 800), (900, 700)),
        translate_x=240,
        scale=0.97,
        transparent_guard=1,
    )

    assert result["resolutionMultiplier"] == 1.8
    assert result["lowResolutionCanvas"] == [1152, 810]
    assert result["lowResolutionReferenceWindow"] == {"x": 256, "y": 180, "width": 640, "height": 450}
    assert result["fullQualityCanvas"] == [2304, 1620]
    assert result["fullQualityReferenceWindow"] == {"x": 512, "y": 360, "width": 1280, "height": 900}
    assert result["lensShiftCoefficient"] == 0.5555555556
    assert all(edge["passed"] for viewport in result["viewportSafety"] for edge in viewport["edges"].values())
    assert result["runtimeVisualOffsetChangeRequired"] is False
    assert result["runtimeCarrierMappingScaleChangeRequired"] is True


def test_minimum_carrier_expands_from_measured_union_without_changing_reference() -> None:
    module = _module()
    state_ranges = {
        "one": {"minX": -500.0, "minY": -200.0, "maxX": 1050.0, "maxY": 700.0},
        "two": {"minX": -20.0, "minY": -10.0, "maxX": 660.0, "maxY": 460.0},
    }

    result = module.minimum_centered_carrier(
        state_ranges,
        reference=(640, 450),
        viewports=((1280, 800), (900, 700)),
        translate_x=240,
        scale=0.97,
        transparent_guard=1,
    )

    assert result["resolutionMultiplier"] > 1.8
    assert result["lowResolutionReferenceWindow"]["width"] == 640
    assert result["lowResolutionReferenceWindow"]["height"] == 450
    assert result["fullQualityReferenceWindow"]["width"] == 1280
    assert result["fullQualityReferenceWindow"]["height"] == 900


def test_blender_argument_boundary_only_accepts_repo_after_separator(tmp_path: Path) -> None:
    module = _module()

    args = module.parse_args(["blender.exe", "--background", "source.blend", "--", "--repo", str(tmp_path)])

    assert args.repo == tmp_path
