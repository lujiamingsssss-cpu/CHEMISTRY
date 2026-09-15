import importlib.util
import json
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts" / "build_twinkle_stage5_png_interpolation_pilot.py"
OUTPUT = REPO / "output" / "twinkle-stage5-png-interpolation-pilot"


def pilot():
    assert BUILDER.is_file(), "PNG interpolation pilot builder is missing"
    spec = importlib.util.spec_from_file_location("twinkle_png_interpolation", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def generated():
    module = pilot()
    assert OUTPUT.is_dir(), "PNG interpolation pilot output is missing"
    manifest = json.loads((OUTPUT / "pilot-manifest.json").read_text(encoding="utf-8"))
    results = json.loads((OUTPUT / "machine-results.json").read_text(encoding="utf-8"))
    return module, manifest, results


def test_only_real_render_and_ffmpeg_candidates_exist():
    module = pilot()
    assert module.CANDIDATES == ("A", "B")
    source = BUILDER.read_text(encoding="utf-8").lower()
    for forbidden in ("rife", "neural", "crossfade", "<canvas", "webgl"):
        assert forbidden not in source


def test_representative_intervals_are_minimal_shared_and_cover_seam():
    module = pilot()
    pairs = [(record["startFrame"], record["endFrame"]) for record in module.REPRESENTATIVE_INTERVALS]
    assert pairs == [(7, 8), (8, 9), (64, 65), (78, 79), (95, 0)]
    assert pairs.count((95, 0)) == 1
    assert len(pairs) == 5


def test_a_and_b_use_identical_192_288_times_and_angles():
    module = pilot()
    authority = module.load_authority(REPO)
    points = module.sample_points(authority)
    assert len(points) == 15
    assert {point["density"] for point in points} == {192, 288}
    assert {point["fraction"] for point in points} == {"1/2", "1/3", "2/3"}
    assert all(point["candidateIds"] == ["A", "B"] for point in points)
    seam = [point for point in points if point["startFrame"] == 95]
    assert [point["angleDegrees"] for point in seam] == pytest.approx([358.125, 357.5, 358.75])


def test_authoritative_96_frame_hashes_and_bytes_are_bound():
    module = pilot()
    authority = module.load_authority(REPO)
    assert tuple(authority["frames"]) == tuple(range(96))
    for record in authority["frames"].values():
        assert module.sha256(record["path"]) == record["sha256"]
        assert record["path"].stat().st_size == record["bytes"]


def test_stage4_sources_are_read_only_authorities():
    module = pilot()
    stage4 = module.registered_worktree_for_branch(REPO, module.STAGE4_BRANCH)
    paths = module.stage4_source_paths(REPO, stage4)
    assert paths["repo"] == stage4.resolve()
    assert paths["script"].is_file() and paths["manifest"].is_file()
    assert paths["candidateBlend"].is_file()
    assert module.sha256(paths["candidateBlend"]) == module.EXPECTED_BLEND_SHA256


def test_output_is_exactly_task_exclusive_directory(tmp_path):
    module = pilot()
    assert module.validate_output_root(REPO, OUTPUT) == OUTPUT.resolve()
    for forbidden in (REPO / "showcase/homepage", REPO / "registry", tmp_path / "pilot"):
        with pytest.raises(module.PilotValidationError):
            module.validate_output_root(REPO, forbidden)


def test_pilot_never_builds_complete_sequences():
    module = pilot()
    points = module.sample_points(module.load_authority(REPO))
    assert sum(point["density"] == 192 for point in points) == 5
    assert sum(point["density"] == 288 for point in points) == 10
    assert len(points) < 96
    assert 480 not in module.DENSITIES


def test_formal_homepage_registry_and_248_assets_are_protected():
    _, _, results = generated()
    protection = results["formalProtection"]
    assert protection["registryBefore"] == protection["registryAfter"]
    assert protection["formalInventoryBefore"] == protection["formalInventoryAfter"]
    assert protection["formalFileCount"] == 248
    assert protection["formalWrites"] == 0


def test_real_render_records_angle_hash_bytes_time_and_settings():
    _, manifest, results = generated()
    candidate = results["candidates"]["A"]
    assert candidate["method"] == "authoritative-blender-real-render"
    assert candidate["controlSceneCompositionPassed"] is True
    assert candidate["controlCameraExact"] is True
    assert candidate["controlPixelComparison"]["maximumChannelDelta"] <= 1
    assert candidate["controlPixelComparison"]["differentPixelFraction"] <= 0.0002
    assert candidate["renderSettings"]["resolution"] == [640, 450]
    assert candidate["renderSettings"]["samples"] == 64
    if candidate["status"] == "passed":
        assert len(manifest["candidates"]["A"]["frames"]) == 15
        assert all(record["angleDegrees"] >= 0 for record in manifest["candidates"]["A"]["frames"])
        assert all(record["sha256"] and record["bytes"] > 0 and record["elapsedSeconds"] > 0 for record in manifest["candidates"]["A"]["frames"])


def test_ffmpeg_records_version_parameters_and_source_frames():
    _, manifest, results = generated()
    candidate = results["candidates"]["B"]
    assert candidate["method"] == "ffmpeg-minterpolate-mci"
    assert candidate["ffmpegVersion"].startswith("ffmpeg version ")
    assert "minterpolate" in " ".join(candidate["parameters"])
    if candidate["status"] == "passed":
        frames = manifest["candidates"]["B"]["frames"]
        assert len(frames) == 15
        assert all(len(record["sourceFrames"]) == 2 for record in frames)


def test_ffmpeg_cannot_silently_change_size_alpha_or_color_contract():
    _, manifest, results = generated()
    candidate = results["candidates"]["B"]
    if candidate["status"] == "passed":
        assert candidate["pixelContract"] == {
            "format": "PNG",
            "mode": "RGBA",
            "size": [640, 450],
            "alphaExtrema": [255, 255],
            "srgb": True,
            "gamma": pytest.approx(0.45455),
        }
        assert all(record["pixelContractPassed"] is True for record in manifest["candidates"]["B"]["frames"])
    else:
        assert candidate["failureEvidence"]


def test_intermediate_hotspots_hold_previous_authority_without_interpolation():
    _, manifest, _ = generated()
    baseline = {record["index"]: record for record in manifest["baselineFrames"]}
    for candidate in ("A", "B"):
        for record in manifest["candidates"][candidate]["frames"]:
            assert record["hotspots"] == baseline[record["startFrame"]]["hotspots"]


def test_label_visibility_does_not_regress():
    module = pilot()
    fixed = module.load_fixed_pilot_module(REPO)
    css = fixed.PILOT_CSS.replace(" ", "")
    assert ".hotspot-label{" in css and "opacity:1" in css
    assert ".hotspot:hover.hotspot-label" not in css


def test_interaction_invariants_do_not_regress():
    module = pilot()
    fixed = module.load_fixed_pilot_module(REPO)
    assert fixed.HOTSPOT_SPEED_FACTOR == pytest.approx(0.30)
    assert fixed.CLICK_DRAG_THRESHOLD_PX == 6
    assert "setPointerCapture(event.pointerId)" in fixed.PILOT_JS
    assert "if(state.pointer.held)return 0" in fixed.PILOT_JS


def test_reduced_motion_keeps_static_authoritative_frame():
    _, _, _ = generated()
    source = (OUTPUT / "pilot.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in source
    assert "static-authoritative" in source


def test_builder_page_manifest_and_results_are_consistent():
    _, manifest, results = generated()
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    assert manifest["schema"] == "twinkle-stage5-png-interpolation-pilot-v1"
    assert results["schema"] == "twinkle-stage5-png-interpolation-machine-results-v1"
    assert results["representativeIntervalIds"] == [record["id"] for record in manifest["representativeIntervals"]]
    assert html.count('data-variant="') == 5
    assert (OUTPUT / "pilot.css").is_file() and (OUTPUT / "pilot.js").is_file()


def test_generated_counts_are_bounded_to_fixed_samples():
    _, manifest, results = generated()
    for candidate in ("A", "B"):
        frames = manifest["candidates"][candidate]["frames"]
        if results["candidates"][candidate]["status"] == "passed":
            assert len(frames) == 15
            assert sum(record["density"] == 192 for record in frames) == 5
            assert sum(record["density"] == 288 for record in frames) == 10
        else:
            assert len(frames) <= 15


def test_failed_candidate_is_never_marked_formal_or_recommended():
    _, _, results = generated()
    assert results["formalIntegrationAuthorized"] is False
    assert results["formalSelectionMade"] is False
    for candidate in results["candidates"].values():
        if candidate["status"] == "failed":
            assert candidate["formalUsable"] is False
            assert candidate["recommended"] is False


def test_same_time_comparisons_and_visual_metrics_cover_all_fixed_samples():
    _, manifest, _ = generated()
    metrics_path = OUTPUT / "visual-metrics.json"
    assert metrics_path.is_file()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert len(metrics["samples"]) == 15
    assert {record["sampleId"] for record in metrics["samples"]} == {
        record["id"] for record in manifest["samplePoints"]
    }
    assert len(list((OUTPUT / "comparisons").glob("*.png"))) == 15
    assert all(record["comparison"] and record["difference"] for record in metrics["samples"])


def test_fixed_visual_artifacts_fail_ffmpeg_without_making_formal_selection():
    _, manifest, results = generated()
    candidate = results["candidates"]["B"]
    assert candidate["status"] == "failed"
    assert candidate["formalUsable"] is False
    assert candidate["recommended"] is False
    assert results["formalSelectionMade"] is False
    assert len(manifest["candidates"]["B"]["frames"]) == 15
    assert {"ghosting", "edge-tearing", "reflection-drift"}.issubset(
        set(candidate["detectedArtifacts"])
    )


def test_browser_timeline_places_authoritative_end_at_fraction_one():
    module = pilot()
    assert "{...start,fractionValue:0}" in module.PILOT_JS
    assert "{...end,fractionValue:1}" in module.PILOT_JS


def test_browser_interaction_kernel_keeps_hover_hold_capture_and_six_px_threshold():
    module = pilot()
    source = module.PILOT_JS
    assert "pointerover" in source and "pointerout" in source
    assert "state.speed=.3" in source
    assert "state.speed=0" in source
    assert "setPointerCapture(event.pointerId)" in source
    assert "Math.hypot(dx,dy)>6" in source


def test_browser_results_persist_desktop_touch_motion_and_error_gates():
    results_path = OUTPUT / "browser-results.json"
    assert results_path.is_file()
    results = json.loads(results_path.read_text(encoding="utf-8"))
    assert results["machinePassed"] is True
    assert results["desktop"]["errors"] == {"console": [], "page": [], "request": [], "http": []}
    assert results["touchEquivalent"]["errors"] == {"console": [], "page": [], "request": [], "http": []}
    assert results["desktop"]["intervalPlaybackCount"] == 5
    assert results["desktop"]["sourceUpdates"] == {"96": 2, "192": 3, "288": 4}
    assert results["touchEquivalent"]["pointerDragPassed"] is True
    assert results["reducedMotion"]["mode"] == "static-authoritative"
    assert results["mobileLabelOverlapDeferred"] is True
    assert results["formalSelectionMade"] is False
    machine = json.loads((OUTPUT / "machine-results.json").read_text(encoding="utf-8"))
    assert machine["browserAcceptancePending"] is False
    assert machine["browserPassed"] is True
