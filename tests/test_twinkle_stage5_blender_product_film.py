import math
from pathlib import Path

import pytest

from scripts import build_twinkle_stage5_blender_product_film as film


def test_v2_static_storyboard_is_from_scratch_and_bounded():
    assert film.PREVIEW_REVISION == "v2-from-scratch"
    assert [candidate.name for candidate in film.STORYBOARD_CANDIDATES] == [
        "shell-contour",
        "front-cover-seam",
        "top-optic-conditional",
        "underside-optic-conditional",
        "dual-channel-interface",
        "loop-bridge",
    ]
    rejected_locations = {
        (0.11082844478906573, 0.47487522148149974, 0.7),
        (0.07, 0.425, 0.665),
        (0.365, 0.395, 0.382),
        (0.625, 0.445, 0.66),
    }
    for candidate in film.STORYBOARD_CANDIDATES:
        assert len(candidate.keyframes) == 3
        assert candidate.value
        assert candidate.match_to_next
        assert math.dist(candidate.keyframes[0].location, candidate.keyframes[-1].location) <= 0.055
        assert all(state.location not in rejected_locations for state in candidate.keyframes)


def test_v2_dual_channel_candidate_is_contextual_not_interface_filling():
    candidate = next(x for x in film.STORYBOARD_CANDIDATES if x.name == "dual-channel-interface")

    assert all(state.lens_mm == 55.0 for state in candidate.keyframes)
    assert all(math.dist(state.location, state.target) >= 0.52 for state in candidate.keyframes)


def test_v2_underside_arc_finishes_on_brighter_match_cut_endpoint():
    candidate = next(x for x in film.STORYBOARD_CANDIDATES if x.name == "underside-optic-conditional")

    assert candidate.keyframes[0].location == pytest.approx((0.390, 0.300, 0.360))
    assert candidate.keyframes[-1].location == pytest.approx((0.360, 0.270, 0.340))


def test_v2_hero_candidates_are_exact_a192_poses_and_crop_safe():
    assert tuple(film.HERO_CANDIDATES) == (144, 148, 152)
    for frame, candidate in film.HERO_CANDIDATES.items():
        assert candidate.state.lens_mm == 58.0
        assert candidate.visible_subject_fraction == 1.0
        assert film.crop_safe(candidate.subject_bounds, 64 / 45, 1280 / 800)
        assert film.crop_safe(candidate.subject_bounds, 64 / 45, 900 / 700)


def test_v2_bridge_starts_at_selected_hero_and_ends_at_opening_state():
    shell = next(x for x in film.STORYBOARD_CANDIDATES if x.name == "shell-contour")
    bridge = next(x for x in film.STORYBOARD_CANDIDATES if x.name == "loop-bridge")
    hero = film.HERO_CANDIDATES[152].state

    assert bridge.keyframes[0] == hero
    assert bridge.keyframes[-1] == shell.keyframes[0]
    assert all(state.lens_mm == 58.0 for state in bridge.keyframes + shell.keyframes)
    bridge_direction = tuple(b - a for a, b in zip(bridge.keyframes[0].location, bridge.keyframes[-1].location))
    shell_direction = tuple(b - a for a, b in zip(shell.keyframes[0].location, shell.keyframes[-1].location))
    cosine = sum(a * b for a, b in zip(bridge_direction, shell_direction)) / (
        math.dist((0, 0, 0), bridge_direction) * math.dist((0, 0, 0), shell_direction)
    )
    assert cosine >= 0.999


def test_v2_selected_hero_reveal_has_static_gate_and_exact_exit():
    reveal = film.SELECTED_HERO_REVEAL

    assert len(reveal.keyframes) == 3
    assert reveal.keyframes[-1] == film.HERO_CANDIDATES[152].state
    assert all(state.lens_mm == 58.0 for state in reveal.keyframes)
    assert math.dist(reveal.keyframes[0].location, reveal.keyframes[-1].location) <= 0.070


def test_v2_timeline_has_three_local_shots_hero_and_one_bridge():
    assert film.V2_FPS == 30
    assert film.V2_FRAME_COUNT == 324
    assert film.V2_DURATION_SECONDS == pytest.approx(10.8)
    assert [(shot.name, shot.start, shot.end_exclusive) for shot in film.V2_SHOTS] == [
        ("shell-contour", 0, 72),
        ("underside-optic", 72, 144),
        ("dual-channel-interface", 144, 207),
        ("hero-reveal", 207, 288),
        ("loop-bridge", 288, 324),
    ]


def test_v2_camera_timeline_has_nonrepeating_speed_continuous_loop():
    frame_zero = film.v2_camera_state(0)
    frame_one = film.v2_camera_state(1)
    last_frame = film.v2_camera_state(film.V2_FRAME_COUNT - 1)
    virtual_end = film.v2_camera_state(film.V2_FRAME_COUNT)

    assert virtual_end == frame_zero
    assert last_frame != frame_zero
    assert film.v2_camera_state(288) == film.HERO_CANDIDATES[152].state
    boundary_step = math.dist(last_frame.location, frame_zero.location)
    opening_step = math.dist(frame_zero.location, frame_one.location)
    assert boundary_step == pytest.approx(opening_step, rel=0.12)
    for shot in film.V2_SHOTS:
        states = [film.v2_camera_state(frame) for frame in range(shot.start, shot.end_exclusive)]
        assert max(math.dist(a.location, b.location) for a, b in zip(states, states[1:])) < 0.004


def test_storyboard_items_include_selected_hero_start_mid_end():
    items = film.storyboard_items()
    hero = [item for item in items if item[0] == "hero-reveal-selected"]

    assert [item[1] for item in hero] == ["start", "mid", "end"]
    assert [item[2] for item in hero] == list(film.SELECTED_HERO_REVEAL.keyframes)


def test_frame_metrics_records_black_ratio_mean_and_low_percentiles(tmp_path):
    from PIL import Image

    pixels = [(0, 0, 0)] * 8 + [(40, 40, 40)] * 4 + [(100, 100, 100)] * 4
    path = tmp_path / "frame.png"
    image = Image.new("RGB", (4, 4))
    image.putdata(pixels)
    image.save(path)

    result = film.frame_metrics(path, near_black_threshold=20)

    assert result["nearBlackFraction"] == pytest.approx(0.5)
    assert result["meanLuma"] == pytest.approx(35.0)
    assert result["p10Luma"] == pytest.approx(0.0)
    assert result["p25Luma"] == pytest.approx(0.0)


def test_preview_contract_is_complete_end_exclusive_30_fps():
    assert film.PREVIEW_FPS == 30
    assert film.PREVIEW_RESOLUTION == (640, 450)
    assert film.PREVIEW_FRAME_COUNT == 360
    assert film.PREVIEW_DURATION_SECONDS == 12.0
    assert [shot.name for shot in film.SHOTS] == [
        "dark-shell-loop",
        "machined-seam",
        "blue-optic",
        "dual-channel-interface",
        "hero-reveal",
        "dark-bridge-loop",
    ]
    assert [shot.start for shot in film.SHOTS] == [0, 60, 120, 192, 246, 324]
    assert [shot.end_exclusive for shot in film.SHOTS] == [60, 120, 192, 246, 324, 360]


def test_virtual_loop_frame_matches_frame_zero_with_continuous_step():
    frame_zero = film.camera_state(0)
    last_frame = film.camera_state(film.PREVIEW_FRAME_COUNT - 1)
    virtual_end = film.camera_state(film.PREVIEW_FRAME_COUNT)
    frame_one = film.camera_state(1)

    assert virtual_end == frame_zero
    assert last_frame != frame_zero
    boundary_step = math.dist(last_frame.location, frame_zero.location)
    opening_step = math.dist(frame_zero.location, frame_one.location)
    assert boundary_step == pytest.approx(opening_step, rel=0.08)
    assert last_frame.target == frame_zero.target == frame_one.target
    assert last_frame.lens_mm == frame_zero.lens_mm == frame_one.lens_mm


def test_blue_optic_shot_reuses_proven_chamber_underside_camera_family():
    opening = film.camera_state(120)
    closing = film.camera_state(191)

    assert opening.target == closing.target == pytest.approx((0.285227, 0.622304, 0.585193))
    assert opening.location == pytest.approx((0.365, 0.395, 0.382))
    assert closing.location == pytest.approx((0.452, 0.455, 0.405))
    assert opening.lens_mm == closing.lens_mm == pytest.approx(72.0)


def test_dark_studio_has_fixed_neutral_optic_strip_and_low_specular_floor():
    optic = film.STUDIO_LIGHTING["TEMP__TWINKLE_OPTIC_STRIP"]
    underside = film.STUDIO_LIGHTING["TEMP__TWINKLE_UNDERSIDE_STRIP"]

    assert optic[0] == pytest.approx(26.0)
    assert optic[1] == pytest.approx((0.78, 0.88, 1.0))
    assert optic[2] == "RECTANGLE"
    assert optic[5] == pytest.approx((0.055, 0.762, 0.712))
    assert underside[0] == pytest.approx(48.0)
    assert underside[1] == pytest.approx((0.78, 0.86, 1.0))
    assert underside[2] == "RECTANGLE"
    assert underside[5] == pytest.approx((0.300, 0.500, 0.300))
    assert film.FLOOR_BASE_COLOR == pytest.approx((0.002, 0.003, 0.005, 1.0))
    assert film.FLOOR_ROUGHNESS >= 0.72
    assert film.FLOOR_IOR_LEVEL <= 0.12
    assert film.HIDE_STUDIO_FLOOR is True


def test_v2_studio_uses_real_graphite_backdrop_instead_of_black_void():
    assert film.V2_EXPOSURE == pytest.approx(-0.90)
    assert film.V2_BACKDROP["location"] == pytest.approx((0.383, 0.920, 0.650))
    assert film.V2_BACKDROP["dimensions"] == pytest.approx((3.00, 2.00))
    assert film.V2_BACKDROP["baseColor"] == pytest.approx((0.0012, 0.0018, 0.0026, 1.0))
    assert film.V2_BACKDROP["emissionOnly"] is True
    assert film.V2_BACKDROP["emissionColor"] == pytest.approx((0.008, 0.012, 0.018, 1.0))
    wash = film.V2_STUDIO_LIGHTING["TEMP__TWINKLE_V2_BACKDROP_WASH"]
    assert wash[0] == pytest.approx(0.5)
    assert wash[5] == pytest.approx((0.383, 0.730, 0.880))


def test_v2_lighting_is_low_key_with_specular_strips_not_broad_flat_fill():
    key = film.V2_STUDIO_LIGHTING["WS_Key_Softbox"][0]
    fill = film.V2_STUDIO_LIGHTING["WS_Fill_Softbox"][0]
    front = film.V2_STUDIO_LIGHTING["WS_Front_Bounce"][0]
    rim = film.V2_STUDIO_LIGHTING["WS_Rim_Light"][0]
    edge = film.V2_STUDIO_LIGHTING["TEMP__TWINKLE_V2_EDGE_STRIP"][0]
    wash = film.V2_STUDIO_LIGHTING["TEMP__TWINKLE_V2_BACKDROP_WASH"][0]

    assert key <= 10.0
    assert fill <= 4.0
    assert front <= 1.5
    assert wash <= 0.6
    assert rim >= 52.0
    assert edge >= 56.0
    assert rim / fill >= 13.0
    assert film.V2_STUDIO_LIGHTING["WS_Rim_Light"][6] <= 0.05
    assert film.V2_STUDIO_LIGHTING["TEMP__TWINKLE_V2_EDGE_STRIP"][6] == 0.0
    assert film.V2_STUDIO_LIGHTING["TEMP__TWINKLE_V2_UNDERSIDE"][6] == 0.0


def test_hero_reveal_finishes_at_a192_frame_148_authority_pose():
    state = film.camera_state(323)
    assert state.location == pytest.approx((-0.096428074, 0.067317277, 0.881142139))
    assert state.target == pytest.approx((0.383089125, 0.618871093, 0.554803014))
    assert state.lens_mm == 58.0
    assert film.HERO_A192_CANDIDATES == (144, 148, 152)
    assert film.HERO_A192_SELECTED == 148


def test_representative_blender_command_uses_boolean_flag_without_value():
    command = film.blender_command(
        Path("blender.exe"),
        Path("authority.blend"),
        Path("output"),
        representative_only=True,
    )

    assert command[-1] == "--representative-only"
    assert "true" not in command[command.index("--representative-only") :]


def test_storyboard_command_is_isolated_from_rejected_preview_worker():
    command = film.storyboard_blender_command(
        Path("blender.exe"), Path("authority.blend"), Path("output")
    )

    assert command[:3] == ["blender.exe", "--background", "authority.blend"]
    assert command[-3:] == ["--worker-output", "output", "--storyboard-only"]
    assert "--preview" not in command


def test_blender_zero_exit_without_worker_result_is_failure(tmp_path):
    class Completed:
        returncode = 0
        stderr = "Python exception"

    with pytest.raises(film.FilmValidationError, match="missing worker result"):
        film.require_blender_result(Completed(), tmp_path / "missing.json")


def test_v2_blender_command_isolated_from_rejected_preview():
    command = film.v2_blender_command(
        Path("blender.exe"), Path("authority.blend"), Path("output")
    )

    assert command[:3] == ["blender.exe", "--background", "authority.blend"]
    assert command[-3:] == ["--worker-output", "output", "--v2-preview"]
    assert "--preview" not in command


def test_sequence_metrics_records_frame_cut_and_loop_deltas(tmp_path):
    from PIL import Image

    paths = []
    for index, value in enumerate((0, 10, 100)):
        path = tmp_path / f"frame-{index:03d}.png"
        Image.new("RGB", (4, 4), (value, value, value)).save(path)
        paths.append(path)

    result = film.sequence_metrics(paths, cut_indices=(2,), near_black_threshold=20)

    assert [row["nearBlackFraction"] for row in result["frames"]] == [1.0, 1.0, 0.0]
    assert result["frames"][1]["adjacentMeanAbsDiff"] == pytest.approx(10.0)
    assert result["cuts"][0]["meanLumaDelta"] == pytest.approx(90.0)
    assert result["cuts"][0]["nearBlackDelta"] == pytest.approx(-1.0)
    assert result["loop"]["meanAbsDiff"] == pytest.approx(100.0)


def test_blender_command_uses_authority_read_only_and_preview_worker(tmp_path):
    blender = Path("blender.exe")
    source = Path("authority") / "twinkle.blend"
    output = tmp_path / "preview"
    command = film.blender_command(blender, source, output)

    assert command[:3] == [str(blender), "--background", str(source)]
    assert "--python" in command
    assert command[-4:] == ["--worker-output", str(output), "--preview", "true"]
    assert "--save" not in command


def test_output_root_must_be_dedicated_product_film_directory(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    accepted = repo / "output" / "twinkle-stage5-blender-product-film"
    assert film.validate_output_root(repo, accepted) == accepted.resolve()

    with pytest.raises(film.FilmValidationError):
        film.validate_output_root(repo, repo / "output")


def test_dip_to_black_loop_fades_locked_shot_one_directly_and_has_no_pre_roll_splice():
    contract = film.DIP_TO_BLACK_LOOP

    assert contract["fadeInFrames"] == 12
    assert contract["fadeOutFrames"] == 18
    assert contract["heroFrameCount"] == 150
    assert contract["fadeOutStartFrame"] + contract["fadeOutFrames"] == contract["heroFrameCount"]
    assert "preRollFrames" not in contract


def test_dip_to_black_loop_command_fades_while_motion_continues_and_concatenates_locked_shots():
    command = film.dip_to_black_loop_ffmpeg_command(
        "ffmpeg",
        Path("shot-1.mp4"),
        Path("shot-2.mp4"),
        Path("shot-3.mp4"),
        Path("shot-4.mp4"),
        Path("loop-review.mp4"),
    )
    graph = command[command.index("-filter_complex") + 1]

    assert "[0:v]fade=t=in:s=0:n=12" in graph
    assert "[3:v]fade=t=out:s=132:n=18" in graph
    assert "concat=n=4:v=1:a=0" in graph
    assert "pre-roll" not in " ".join(command)
    assert command[-1] == "loop-review.mp4"
    assert "-r" in command and command[command.index("-r") + 1] == "30"


def test_dip_to_black_review_root_is_created_before_ffmpeg_writes(tmp_path):
    review_root = film.prepare_dip_to_black_review_root(tmp_path)

    assert review_root == tmp_path / film.DIP_TO_BLACK_OUTPUT_DIR
    assert review_root.is_dir()


def test_quality_preflight_contract_is_fixed_to_three_candidates_and_four_problem_frames():
    assert film.QUALITY_PREFLIGHT_CANDIDATES == (
        ("A", (640, 450), 64),
        ("B1", (1280, 900), 128),
        ("B2", (1280, 900), 256),
    )
    assert film.QUALITY_PREFLIGHT_FRAMES == (
        ("edge-aperture", 30, "micro"),
        ("rolled-side-panel-surface-skimming-correction", 30, "motion"),
        ("underside-ring", 24, "micro"),
        ("dual-interface-to-hero-continuous-correction", 60, "motion"),
    )


def test_quality_preflight_command_is_read_only_and_uses_isolated_worker_mode(tmp_path):
    command = film.quality_preflight_blender_command(
        Path("blender.exe"), Path("authority.blend"), tmp_path / "candidate"
    )

    assert command[:3] == ["blender.exe", "--background", "authority.blend"]
    assert command[-3:] == ["--worker-output", str(tmp_path / "candidate"), "--quality-preflight"]
    assert "--save" not in command


def test_quality_b2_full_render_contract_is_fixed_to_approved_four_clips():
    assert film.QUALITY_B2_RESOLUTION == (1280, 900)
    assert film.QUALITY_B2_SAMPLES == 256
    assert film.QUALITY_B2_FULL_CLIPS == (
        ("edge-aperture", 45, "micro"),
        ("rolled-side-panel-surface-skimming-correction", 60, "motion"),
        ("underside-ring", 48, "micro"),
        ("dual-interface-to-hero-continuous-correction", 150, "motion"),
    )
    assert sum(frame_count for _, frame_count, _ in film.QUALITY_B2_FULL_CLIPS) == 303


def test_quality_b2_full_command_is_read_only_and_uses_isolated_worker_mode(tmp_path):
    command = film.quality_b2_full_blender_command(
        Path("blender.exe"), Path("authority.blend"), tmp_path / "candidate"
    )

    assert command[:3] == ["blender.exe", "--background", "authority.blend"]
    assert command[-3:] == ["--worker-output", str(tmp_path / "candidate"), "--quality-b2-full-render"]
    assert "--save" not in command


def test_quality_b2_review_contract_locks_sequence_boundaries_and_fades(tmp_path):
    contract = film.quality_b2_review_contract(tmp_path)

    assert [item["name"] for item in contract["clips"]] == [
        "edge-aperture",
        "rolled-side-panel-surface-skimming-correction",
        "underside-ring",
        "dual-interface-to-hero-continuous-correction",
    ]
    assert [item["startFrame"] for item in contract["clips"]] == [0, 45, 105, 153]
    assert [item["frameCount"] for item in contract["clips"]] == [45, 60, 48, 150]
    assert contract["combinedFrameCount"] == 303
    assert contract["fadeIn"] == {"startFrame": 0, "frameCount": 12, "firstFullFrame": 12}
    assert contract["fadeOut"] == {"startFrame": 285, "frameCount": 18, "lastFrame": 302}


def test_quality_b2_review_probe_validation_rejects_wrong_combined_frame_count(tmp_path):
    contract = film.quality_b2_review_contract(tmp_path)
    probes = {
        item["video"].name: {
            "codec_name": "h264",
            "width": 1280,
            "height": 900,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "30/1",
            "avg_frame_rate": "30/1",
            "nb_frames": item["frameCount"],
            "duration": item["frameCount"] / 30,
        }
        for item in contract["clips"]
    }
    probes[contract["combinedVideo"].name] = {
        "codec_name": "h264",
        "width": 1280,
        "height": 900,
        "pix_fmt": "yuv420p",
        "r_frame_rate": "30/1",
        "avg_frame_rate": "30/1",
        "nb_frames": 302,
        "duration": 302 / 30,
    }

    with pytest.raises(film.FilmValidationError, match="combined frame count"):
        film.validate_quality_b2_review_probes(contract, probes)


def test_quality_b2_review_sampling_contract_covers_sequence_and_fade_boundaries(tmp_path):
    contract = film.quality_b2_review_contract(tmp_path)

    assert film.quality_b2_review_sequence_checks(contract) == (
        ("edge-aperture", 30, 30),
        ("rolled-side-panel-surface-skimming-correction", 30, 75),
        ("underside-ring", 24, 129),
        ("dual-interface-to-hero-continuous-correction", 60, 213),
        ("fade-in-complete", 12, 12),
        ("fade-out-start", 132, 285),
    )
    assert film.QUALITY_B2_REVIEW_CONTACT_FRAMES == (
        0, 6, 11, 12, 30, 44,
        45, 75, 104, 105, 129, 152,
        153, 200, 240, 284, 294, 302,
    )


def test_quality_b2_review_tool_output_parsers_are_strict():
    probe = film.parse_quality_b2_video_probe("""
    {"streams":[{"codec_name":"h264","width":1280,"height":900,"pix_fmt":"yuv420p",
    "r_frame_rate":"30/1","avg_frame_rate":"30/1","nb_frames":"45"}],
    "format":{"duration":"1.500000","size":"1234"}}
    """)
    assert probe == {
        "codec_name": "h264",
        "width": 1280,
        "height": 900,
        "pix_fmt": "yuv420p",
        "r_frame_rate": "30/1",
        "avg_frame_rate": "30/1",
        "nb_frames": 45,
        "duration": 1.5,
        "bytes": 1234,
    }
    assert film.parse_quality_b2_ssim("SSIM Y:0.997 U:0.998 V:0.999 All:0.998324 (27.7)") == pytest.approx(0.998324)
    assert film.parse_quality_b2_signalstats(
        "frame:0 pts:0 pts_time:0\nlavfi.signalstats.YAVG=16\n"
        "frame:1 pts:6144 pts_time:0.4\nlavfi.signalstats.YAVG=32.6901\n"
    ) == {0: 16.0, 12: 32.6901}


def test_quality_b2_review_audit_cli_is_explicit_and_does_not_require_blender():
    args = film.parse_args([
        "--repo", ".",
        "--output-root", "candidate",
        "--quality-b2-review-audit",
        "--ffmpeg", "ffmpeg",
        "--ffprobe", "ffprobe",
    ])

    assert args.quality_b2_review_audit is True
    assert args.blender is None
    assert args.source_blend is None
    assert args.ffprobe == "ffprobe"
