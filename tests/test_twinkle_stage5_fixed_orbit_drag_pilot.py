import json
import hashlib
from pathlib import Path
import re

import pytest

from scripts import build_twinkle_stage5_fixed_orbit_drag_pilot as pilot


REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts" / "build_twinkle_stage5_fixed_orbit_drag_pilot.py"
INTERPOLATION_PROTECTION = {
    "scripts/build_twinkle_stage5_png_interpolation_pilot.py": (
        57_587,
        "A3DE3330B1B4F6CA1C00E3EA588564DACA03DD2582CC57C4CAF67C59BBE6D7BE",
    ),
    "tests/test_twinkle_stage5_png_interpolation_pilot.py": (
        11_634,
        "1CF460D2939BC2A412FF101373E39AD21F6E3FB59B589CBD54219B4EFC0EF6A4",
    ),
}


def css_rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match, f"missing CSS rule: {selector}"
    return match.group(1).replace(" ", "")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_contract_reuses_the_approved_closed_c360_track():
    assert BUILDER.is_file()
    assert pilot.FRAME_COUNT == 96
    assert pilot.ORBIT_DURATION_MS == 8_000
    assert pilot.ANGLE_STEP_DEGREES == 3.75
    assert pilot.PLAYBACK_DIRECTION == "forward"
    assert pilot.CLICK_DRAG_THRESHOLD_PX == 6
    assert pilot.HOTSPOT_SPEED_FACTOR == pytest.approx(0.30)
    assert pilot.HOTSPOT_LEAVE_GRACE_MS <= 120
    assert pilot.SPEED_RECOVERY_MS == 180


def test_output_root_is_exactly_the_new_isolated_pilot_directory(tmp_path):
    expected = REPO / "output" / "twinkle-stage5-fixed-orbit-drag-pilot"
    assert pilot.validate_output_root(REPO, expected) == expected.resolve()

    for forbidden in (
        REPO / "showcase" / "homepage",
        REPO / "showcase" / "homepage" / "assets" / "twinkle",
        REPO / "output" / "twinkle-stage5-rgba-hover-pilot",
        tmp_path / "fixed-orbit-drag-pilot",
    ):
        with pytest.raises(pilot.PilotValidationError, match="fixed-orbit pilot output"):
            pilot.validate_output_root(REPO, forbidden)


def test_authority_binds_registry_profile_frames_and_frame_local_hotspots():
    authority = pilot.load_authority(REPO)

    assert authority["registrySha256"] == pilot.APPROVED_REGISTRY_SHA256
    assert authority["c360ManifestSha256"] == pilot.APPROVED_C360_MANIFEST_SHA256
    assert authority["orbitProfile"] == {
        "id": "C360-F96",
        "topology": "cyclic",
        "azimuthDegrees": [0.0, 360.0],
        "endExclusive": True,
        "elevationMode": "fixed",
        "durationMs": 8_000,
        "physicalFrameCount": 96,
        "logicalIndexCount": 96,
        "angleStepDegrees": 3.75,
        "maximumTurnDurationMs": 2_000,
        "maximumAngularSpeedDegreesPerSecond": 90.0,
        "accelerationRampMs": 250,
        "decelerationRampMs": 250,
        "settledHoldMs": 100,
        "maximumEntryFramesPerUnit": 2,
    }
    assert tuple(authority["frames"]) == tuple(range(96))
    assert all(record["path"].is_file() for record in authority["frames"].values())
    assert all(
        set(record["hotspots"]) == set(pilot.HOTSPOT_UNITS)
        for record in authority["frames"].values()
    )
    assert all(
        record["hotspots"][unit]["status"]
        in {"visible", "back-facing", "occluded", "out-of-safe"}
        for record in authority["frames"].values()
        for unit in pilot.HOTSPOT_UNITS
    )


def test_unapproved_registry_or_c360_manifest_is_rejected(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text("{}\n", encoding="utf-8")
    with pytest.raises(pilot.PilotValidationError, match="approved registry SHA"):
        pilot.validate_approved_registry(registry)

    manifest = tmp_path / "c360.json"
    manifest.write_text("{}\n", encoding="utf-8")
    with pytest.raises(pilot.PilotValidationError, match="approved C360 manifest SHA"):
        pilot.validate_approved_c360_manifest(manifest)


def test_assemble_pilot_copies_only_the_96_manifest_frames_with_exact_hashes(tmp_path):
    staging = tmp_path / "pilot"
    authority = pilot.load_authority(REPO)

    report = pilot.assemble_pilot(staging, authority)

    copied = sorted((staging / "frames").glob("frame-*.png"))
    assert len(copied) == 96
    assert [path.name for path in copied] == [f"frame-{index:03d}.png" for index in range(96)]
    for index, path in enumerate(copied):
        assert pilot.sha256(path) == authority["frames"][index]["sha256"]
        assert path.stat().st_size == authority["frames"][index]["bytes"]
    assert report["frameCount"] == 96
    assert report["trackStateCount"] == 96
    assert report["outsideTrackStateCount"] == 0
    assert report["formalAssetWrites"] == 0
    assert report["thirdPartyRuntimeDependencies"] == []


def test_generated_manifest_contains_only_authoritative_frame_and_hotspot_data(tmp_path):
    staging = tmp_path / "pilot"
    authority = pilot.load_authority(REPO)
    pilot.assemble_pilot(staging, authority)
    manifest = json.loads((staging / "pilot-manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema"] == "twinkle-stage5-fixed-orbit-drag-pilot-v1"
    assert manifest["frameCount"] == 96
    assert manifest["durationMs"] == 8_000
    assert manifest["direction"] == "forward"
    assert len(manifest["frames"]) == 96
    for index, record in enumerate(manifest["frames"]):
        source = authority["frames"][index]
        assert record["index"] == index
        assert record["angleDegrees"] == source["angleDegrees"]
        assert record["src"] == f"frames/frame-{index:03d}.png"
        assert record["sha256"] == source["sha256"]
        assert record["bytes"] == source["bytes"]
        assert record["hotspots"] == source["hotspots"]


def test_interaction_kernel_has_one_clock_pointer_capture_and_safe_release_paths(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "requestAnimationFrame(animationLoop)" in source
    assert source.count("requestAnimationFrame(animationLoop)") == 2
    assert "setInterval(" not in source
    assert "orbitPositionFrames" in source
    assert "setPointerCapture(event.pointerId)" in source
    assert "releasePointerCapture" in source
    assert "pointerdown" in source and "pointermove" in source and "pointerup" in source
    assert "pointercancel" in source and "lostpointercapture" in source
    assert "event.button !== 0" in source
    assert "event.isPrimary === false" in source
    assert "CLICK_DRAG_THRESHOLD_PX = 6" in source
    assert "viewportWidth" in source and "FRAME_COUNT" in source
    assert "suppressNextClick" in source


def test_speed_priority_hotspot_grace_recovery_and_visibility_safety_are_explicit(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "HOTSPOT_SPEED_FACTOR = 0.3" in source
    assert "HOTSPOT_LEAVE_GRACE_MS = 100" in source
    assert "SPEED_RECOVERY_MS = 180" in source
    assert "state.safePaused" in source
    assert "state.pointer.held" in source
    assert "state.hotspotIntent.hovered.size" in source
    assert "state.hotspotIntent.focused.size" in source
    assert "prefers-reduced-motion: reduce" in source
    assert "document.visibilityState" in source
    assert "IntersectionObserver" in source
    assert "pagehide" in source
    assert "resource-error" in source
    assert "clearHotspotIntent" in source


def test_page_preserves_hotspot_visual_contract_and_vertical_touch_scroll(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    html = (staging / "index.html").read_text(encoding="utf-8")
    css = (staging / "pilot.css").read_text(encoding="utf-8")

    assert html.count("<button") == 2
    assert "play-pause" not in html and "replay" not in html and "scrubber" not in html
    assert "hotspot-ring" in html and "hotspot-pulse" in html and "hotspot-label" in html
    assert "touch-action:pan-y" in css.replace(" ", "")
    assert ".hotspot{position:absolute;width:30px;height:30px" in css.replace("\n", "")
    assert ".hotspot-label" in css
    assert "pointer-events:none" in css.replace(" ", "")
    assert '<link rel="icon" href="data:,">' in html


def test_eligible_hotspot_labels_are_visible_without_hover_focus_or_pressed_state(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    css = (staging / "pilot.css").read_text(encoding="utf-8")

    label_rule = css_rule(css, ".hotspot-label")
    assert "opacity:1" in label_rule
    assert "transform:translate(0,-50%)" in label_rule
    assert "pointer-events:none" in label_rule
    assert ".hotspot:hover .hotspot-label" not in css
    assert ".hotspot:focus-visible .hotspot-label" not in css
    assert '.hotspot[aria-pressed="true"] .hotspot-label' not in css


def test_pixel_10_dual_visible_labels_use_only_the_approved_mobile_offsets(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    css = (staging / "pilot.css").read_text(encoding="utf-8").replace(" ", "")

    dual_visible = ".orbit-viewport:has(.chamber.is-visible):has(.condenser.is-visible)"
    assert "@media(max-width:480px)" in css
    assert (
        f"{dual_visible}.chamber.hotspot-label"
        "{transform:translate(0,calc(-50%-15px))}"
    ) in css
    assert (
        f"{dual_visible}.condenser.hotspot-label"
        "{transform:translate(0,calc(-50%+5px))}"
    ) in css
    assert css.count(dual_visible) == 2
    assert ".hotspot-label{position:absolute;left:27px" in css
    assert "font-size:12px" in css and "white-space:nowrap" in css


def test_png_interpolation_pilot_key_files_remain_read_only():
    for relative, (expected_bytes, expected_sha256) in INTERPOLATION_PROTECTION.items():
        path = REPO / relative
        assert path.stat().st_size == expected_bytes
        assert file_sha256(path) == expected_sha256


def test_frame_qualification_hides_the_whole_hotspot_and_supports_two_labels(tmp_path):
    staging = tmp_path / "pilot"
    authority = pilot.load_authority(REPO)
    pilot.assemble_pilot(staging, authority)
    source = (staging / "pilot.js").read_text(encoding="utf-8")
    html = (staging / "index.html").read_text(encoding="utf-8")

    assert "record.status==='visible'&&record.eligible===true" in source
    assert "element.hidden=false" in source and "element.disabled=false" in source
    assert "element.disabled=true" in source and "element.hidden=true" in source
    assert "clearHotspotIntent(unit)" in source
    assert "if(document.activeElement===element)element.blur()" in source
    assert html.count('class="hotspot-label"') == 2
    assert any(
        all(frame["hotspots"][unit]["eligible"] for unit in pilot.HOTSPOT_UNITS)
        for frame in authority["frames"].values()
    )


def test_slowdown_hold_drag_and_reduced_motion_contract_remains_independent_of_labels(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")
    css = (staging / "pilot.css").read_text(encoding="utf-8")
    html = (staging / "index.html").read_text(encoding="utf-8")

    assert "if(state.pointer.held)return 0" in source
    assert "state.hotspotIntent.hovered.size||state.hotspotIntent.focused.size" in source
    assert "return HOTSPOT_SPEED_FACTOR" in source
    assert "Math.hypot(dx,dy)>CLICK_DRAG_THRESHOLD_PX" in source
    assert "setPointerCapture(event.pointerId)" in source
    assert "prefers-reduced-motion: reduce" in source
    assert "if(event.matches)state.orbitPositionFrames=0" in source
    assert css_rule(css, ".hotspot-label").count("pointer-events:none") == 1
    assert html.count('<button class="hotspot') == 2


def test_checked_in_pilot_markup_styles_and_runtime_are_builder_generated():
    output = REPO / "output" / "twinkle-stage5-fixed-orbit-drag-pilot"

    assert (output / "index.html").read_text(encoding="utf-8") == pilot.PILOT_HTML
    assert (output / "pilot.css").read_text(encoding="utf-8") == pilot.PILOT_CSS + "\n"
    assert (output / "pilot.js").read_text(encoding="utf-8") == pilot.PILOT_JS + "\n"


def test_pointer_capture_preserves_sub_threshold_hotspot_activation(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "pressHotspotUnit" in source
    assert "commitHotspotSelection" in source
    assert "if(!wasDragging&&pressHotspotUnit&&reason==='pointerup')" in source
    assert "skipCapturedHotspotClick" in source


def test_window_blur_is_an_additional_background_safety_signal(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "windowFocused:true" in source
    assert "reasons.push('window-blurred')" in source
    assert "addEventListener('blur'" in source
    assert "addEventListener('focus'" in source


def test_audit_status_tracks_speed_even_while_the_frame_is_held(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "function updateStatus()" in source
    assert "renderFrame();}updateStatus();viewport.dataset.held" in source


def test_speed_recovery_progress_cannot_go_negative_between_clock_samples(tmp_path):
    staging = tmp_path / "pilot"
    pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    source = (staging / "pilot.js").read_text(encoding="utf-8")

    assert "Math.min(1,Math.max(0,(now-transition.started)/SPEED_RECOVERY_MS))" in source


def test_machine_report_declares_the_acceptance_and_stop_boundary(tmp_path):
    staging = tmp_path / "pilot"
    report = pilot.assemble_pilot(staging, pilot.load_authority(REPO))
    persisted = json.loads((staging / "machine-results.json").read_text(encoding="utf-8"))

    assert persisted == report
    assert report["machinePassed"] is True
    assert report["singleTimelineAuthority"] is True
    assert report["pointerEvents"] is True
    assert report["pointerCapture"] is True
    assert report["touchAction"] == "pan-y"
    assert report["normalSpeedFactor"] == 1.0
    assert report["hotspotSpeedFactor"] == 0.3
    assert report["heldSpeedFactor"] == 0.0
    assert report["clickDragThresholdCssPx"] == 6
    assert report["hotspotLeaveGraceMs"] <= 120
    assert report["speedRecoveryMs"] == 180
    assert report["formalIntegrationAuthorized"] is False
    assert report["focusViewportImplemented"] is False
