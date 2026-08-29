import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "twinkle_camera_projection.py"
GENERATOR_PATH = ROOT / "scripts" / "build_twinkle_route1_camera_board.py"


def load_module():
    assert MODULE_PATH.is_file(), "pure Python camera projection module is missing"
    spec = importlib.util.spec_from_file_location("twinkle_camera_projection", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_module_has_no_blender_runtime_or_process_dependency():
    module = load_module()
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "import bpy" not in source
    assert "subprocess" not in source
    assert module.SUPPORTED_SENSOR_FITS == {"AUTO", "HORIZONTAL"}


def test_camera_board_generator_reuses_the_pure_projection_module():
    source = GENERATOR_PATH.read_text(encoding="utf-8")
    assert "from twinkle_camera_projection import" in source
    assert "def projection_record" not in source
    assert "world_to_camera_view" not in source


def test_historical_camera_target_matches_blender_5_2_shift_and_aspect():
    module = load_module()
    camera = module.CameraSpec(
        location=(0.47813308, 0.45754248, 0.62989557),
        target=(0.38404316, 0.58584690, 0.57002020),
        lens_mm=58.0,
        sensor_width_mm=36.0,
        shift_x=0.125,
        shift_y=0.0085,
        resolution_x=1280,
        resolution_y=900,
        sensor_fit="AUTO",
    )
    projected = module.project_world_point(camera.target, camera)
    assert math.isclose(projected.x, 0.375, abs_tol=1e-8)
    assert math.isclose(projected.y, 0.51208889, abs_tol=1e-8)
    assert math.isclose(projected.depth, 0.16999999, abs_tol=1e-8)


def test_perspective_width_scales_with_focal_length_and_inverse_distance():
    module = load_module()
    near = module.CameraSpec(
        location=(0.0, -1.0, 0.0),
        target=(0.0, 0.0, 0.0),
        lens_mm=50.0,
        sensor_width_mm=36.0,
        shift_x=0.0,
        shift_y=0.0,
        resolution_x=1280,
        resolution_y=900,
        sensor_fit="HORIZONTAL",
    )
    far = module.CameraSpec(**{**near.as_dict(), "location": (0.0, -2.0, 0.0)})
    points = ((-0.18, 0.0, 0.0), (0.18, 0.0, 0.0))
    near_bounds = module.project_bounds(points, near)
    far_bounds = module.project_bounds(points, far)
    assert math.isclose(near_bounds.width, 0.5, abs_tol=1e-8)
    assert math.isclose(far_bounds.width, 0.25, abs_tol=1e-8)


def test_composition_evaluation_reports_soft_layout_diagnostics_without_rejecting():
    module = load_module()
    camera = module.CameraSpec(
        location=(0.0, -1.0, 0.0),
        target=(0.0, 0.0, 0.0),
        lens_mm=50.0,
        sensor_width_mm=36.0,
        shift_x=0.13,
        shift_y=0.0,
        resolution_x=1280,
        resolution_y=900,
        sensor_fit="HORIZONTAL",
    )
    settled = ((-0.40, 0.0, -0.30), (0.40, 0.0, 0.30))
    mid = tuple((x + 0.20, y, z) for x, y, z in settled)
    end = tuple((x + 0.40, y, z) for x, y, z in settled)
    result = module.evaluate_composition(
        {
            "focused-settled": settled,
            "extract-mid": mid,
            "extract-end": end,
        },
        camera,
        reserved_right=0.26,
        minimum_target_width=0.45,
        maximum_target_width=0.60,
        maximum_sweep_width=0.65,
    )
    assert result.left_stage_bounds.as_list() == [0.0, 0.0, 0.74, 1.0]
    assert set(result.by_state) == {
        "focused-settled",
        "extract-mid",
        "extract-end",
    }
    assert result.sweep_bounds.width > 0
    assert result.sweep_width_of_left_stage > 0
    assert all(record.depth_positive for record in result.by_state.values())
    assert result.reject_reasons == ()
    assert any("target-width-above" in item for item in result.diagnostics)
    assert any("target-clipped" in item for item in result.diagnostics)
    assert any("panel-intrusion" in item for item in result.diagnostics)
    assert any("sweep-width-above" in item for item in result.diagnostics)


def test_panel_overlap_is_not_mislabeled_as_canvas_clipping():
    module = load_module()
    camera = module.CameraSpec(
        location=(0.0, -1.0, 0.0),
        target=(0.0, 0.0, 0.0),
        lens_mm=50.0,
        sensor_width_mm=36.0,
        shift_x=0.13,
        shift_y=0.0,
        resolution_x=1280,
        resolution_y=900,
        sensor_fit="HORIZONTAL",
    )
    points = ((0.25, 0.0, -0.05), (0.35, 0.0, 0.05))
    result = module.evaluate_composition(
        {"focused-settled": points},
        camera,
        reserved_right=0.26,
        minimum_target_width=0.45,
        maximum_target_width=0.60,
        maximum_sweep_width=0.65,
    )
    record = result.by_state["focused-settled"]
    assert record.panel_intrusion is True
    assert record.target_clipped is False
    assert "focused-settled-panel-intrusion" in result.diagnostics
    assert "focused-settled-target-clipped" not in result.diagnostics


def test_invalid_or_unsupported_camera_inputs_are_rejected():
    module = load_module()
    base = {
        "location": (0.0, -1.0, 0.0),
        "target": (0.0, 0.0, 0.0),
        "lens_mm": 50.0,
        "sensor_width_mm": 36.0,
        "shift_x": 0.0,
        "shift_y": 0.0,
        "resolution_x": 1280,
        "resolution_y": 900,
    }
    for overrides in (
        {"lens_mm": 0.0},
        {"sensor_width_mm": 0.0},
        {"resolution_x": 0},
        {"sensor_fit": "VERTICAL"},
        {"lens_mm": math.nan},
        {"lens_mm": math.inf},
        {"sensor_width_mm": math.nan},
        {"sensor_width_mm": math.inf},
        {"shift_x": math.nan},
        {"shift_x": math.inf},
        {"shift_y": math.nan},
        {"shift_y": math.inf},
    ):
        try:
            module.CameraSpec(**{**base, **overrides})
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid camera input accepted: {overrides}")
