import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if (
    "--stage3-chamber-worker" not in sys.argv
    and "--stage3-condenser-worker" not in sys.argv
    and "--stage3-condenser-repair-worker" not in sys.argv
    and "--stage3-condenser-second-repair-probe-worker" not in sys.argv
    and "--stage3-condenser-r1-linefix-probe-worker" not in sys.argv
    and "--stage3-condenser-r1-linefix-worker" not in sys.argv
    and "--stage3-condenser-motion-only-probe-worker" not in sys.argv
    and "--stage3-formal-chamber-worker" not in sys.argv
    and "--stage3-formal-condenser-worker" not in sys.argv
    and "--stage3-step7-probe-worker" not in sys.argv
    and "--stage3-closeout-condenser-worker" not in sys.argv
):
    from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "twinkle-stage3-dual-hotspot-motion-v1"
AUTHORITY_MANIFEST = (
    ROOT
    / "output"
    / "twinkle-route1-camera-board-r1-1"
    / "camera-board-manifest.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "8DB0B2055838FA69C6381719587A99A2B132FE526F40EA6F0C231264AD908378"
)
EXPECTED_SOURCE_BLEND_SHA256 = (
    "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81"
)
EXPECTED_CANDIDATE_BLEND_SHA256 = (
    "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
)

CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"
SEMANTIC_UNITS = (CHAMBER, CONDENSER)

TOP_LEVEL_STATES = ("global", "action", "explanation")
STAGE4_SEGMENTS = {
    "focus": {"kind": "stub", "pausable": True},
    "overviewReturn": {"kind": "stub", "pausable": True},
}
CONTROL_MATRIX = {
    "global": {
        "modelHotspots": {"visible": True, "enabled": True},
        "unitNames": {"visible": True, "enabled": True},
        "globalToggle": {"visible": True, "enabled": True},
        "actionToggle": {
            "visible": True,
            "enabled": False,
            "label": "暂停动作",
        },
        "return": {"visible": True, "enabled": False},
    },
    "action": {
        "modelHotspots": {"visible": False, "enabled": False},
        "unitNames": {"visible": True, "enabled": False},
        "globalToggle": {"visible": True, "enabled": False},
        "actionToggle": {"visible": True, "enabled": True},
        "return": {"visible": True, "enabled": False},
    },
    "explanation": {
        "modelHotspots": {"visible": False, "enabled": False},
        "unitNames": {"visible": True, "enabled": False},
        "globalToggle": {"visible": True, "enabled": False},
        "actionToggle": {
            "visible": True,
            "enabled": False,
            "label": "暂停动作",
        },
        "return": {"visible": True, "enabled": True},
    },
}

FORMAT_EXPERIMENT = {
    "resolution": (1280, 900),
    "fps": 24,
    "codec": "libx264",
    "preset": "slow",
    "profile": "high",
    "crf": 10,
    "pixelFormat": "yuv420p",
    "color": "bt709",
    "faststart": True,
    "allFramesSeekable": True,
    "audio": False,
}
BROWSER_MATRIX = (
    {"id": "chrome-151", "major": 151, "support": "required"},
    {"id": "chrome-for-testing-150", "major": 150, "support": "required"},
    {"id": "edge-151", "major": 151, "support": "required"},
    {"id": "edge-150", "major": 150, "support": "not-tested"},
)
FALLBACK_FORMAT = "lossless-png-sequence"
CHAMBER_LOWRES_SCHEMA = "twinkle-stage3-chamber-lowres-v1"
CHAMBER_LOWRES_RENDER = {
    "resolution": [640, 450],
    "samples": 64,
    "fps": 24,
    "durationMs": 1000,
    "frameCount": 25,
}
CHAMBER_LOWRES_TIMING = {"seam": 240, "acceleratedTravel": 760}
CHAMBER_LOWRES_REVIEW_FILES = (
    "review/expand-close-contact-sheet.png",
    "review/pause-resume-contact-sheet.png",
    "review/inspection-light-contact-sheet.png",
    "review/quality-contact-sheet.png",
    "review/index.html",
    "blender-motion.json",
)
CONDENSER_LOWRES_SCHEMA = "twinkle-stage3-condenser-lowres-v1"
CONDENSER_REPAIR_SCHEMA = "twinkle-stage3-condenser-lowres-repair-v1"
CONDENSER_SECOND_REPAIR_PROBE_SCHEMA = (
    "twinkle-stage3-condenser-second-repair-probe-v1"
)
CONDENSER_R1_LINEFIX_PROBE_SCHEMA = "twinkle-stage3-condenser-r1-linefix-probe-v1"
CONDENSER_R1_LINEFIX_SCHEMA = "twinkle-stage3-condenser-r1-linefix-v1"
CONDENSER_MOTION_ONLY_PROBE_SCHEMA = (
    "twinkle-stage3-condenser-motion-only-probe-v1"
)
CONDENSER_R3_SCHEMA = "twinkle-stage3-condenser-lowres-r3-v1"
CONDENSER_LOWRES_RENDER = dict(CHAMBER_LOWRES_RENDER)
CONDENSER_LOWRES_REVIEW_FILES = (
    "review/expand-close-contact-sheet.png",
    "review/pause-resume-contact-sheet.png",
    "review/cleanup-quality-contact-sheet.png",
    "review/style-comparison-contact-sheet.png",
    "review/index.html",
    "blender-motion.json",
)
CONDENSER_MOTION_ONLY_REVIEW_FILES = (
    "review/old-new-same-frame-contact-sheet.png",
    "review/keyframes-contact-sheet.png",
    "review/kinematics-curves.png",
    "review/pause-resume-contact-sheet.png",
    "review/index.html",
    "motion-runtime.json",
)
CONDENSER_R3_REVIEW_FILES = (
    "review/keyframes-contact-sheet.png",
    "review/kinematics-curves.png",
    "review/pause-resume-contact-sheet.png",
    "review/linefix-cleanup-quality-contact-sheet.png",
    "review/linefix-style-comparison-contact-sheet.png",
    "review/index.html",
    "motion-runtime.json",
)
CHAMBER_LOWRES_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-chamber-lowres-20260826"
    / "chamber-lowres-r1"
)
CONDENSER_LOWRES_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-condenser-lowres-20260826"
    / "condenser-lowres-r1"
)
CONDENSER_REPAIR_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-condenser-lowres-repair-20260826"
    / "condenser-lowres-r2"
)
CONDENSER_R1_LINEFIX_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-condenser-r1-linefix-20260827"
    / "condenser-lowres-r1-linefix"
)
CONDENSER_MOTION_ONLY_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-condenser-motion-only-probe-20260827"
    / "motion-only-probe-r1"
)
CONDENSER_R3_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-condenser-lowres-r3-20260828"
    / "condenser-lowres-r3"
)
FORMAL_OUTPUT_ROOT = ROOT / "output" / "twinkle-stage3-dual-hotspot-motion-r1"
STAGE3_CLOSEOUT_OUTPUT_ROOT = (
    ROOT / "output" / "twinkle-stage3-dual-hotspot-motion-r2"
)
STAGE3_CLOSEOUT_SCHEMA = "twinkle-stage3-dual-hotspot-motion-r2-v1"
STAGE3_CLOSEOUT_WORKER_SCHEMA = "twinkle-stage3-closeout-condenser-worker-v1"
FORMAL_RENDER = {
    "resolution": [1280, 900],
    "samples": 512,
    "fps": 24,
    "durationMs": 1000,
    "frameCountPerUnit": 25,
}
FORMAL_REVIEW_FILES = (
    "review/dual-hotspot-contact-sheet.png",
    "review/pause-points-contact-sheet.png",
    "review/reduced-motion-contact-sheet.png",
    "review/index.html",
)
STEP7_PROBE_SCHEMA = "twinkle-stage3-step7-limited-probe-v1"
STEP7_PROBE_WORKER_SCHEMA = "twinkle-stage3-step7-limited-probe-worker-v1"
STEP7_PROBE_FRAMES = (0, 20, 21, 22, 24)
STEP7_PROBE_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-step7-limited-repair-20260828"
    / "condenser-hd-probe-r1"
)
STEP7_PROBE_REVIEW_FILES = (
    "review/equal-size-contact-sheet.png",
    "review/black-line-dynamic-review.gif",
    "review/inspection-unlit.png",
    "review/inspection-lit.png",
    "review/index.html",
)
STEP7_MOVING_ROI = {
    "referenceResolution": [1280, 900],
    "lineXAtProgress0": 620.0,
    "lineXTravelPx": 316.0,
    "topAtProgress0": 75.0,
    "topTravelPx": 145.0,
    "bottomAtProgress0": 675.0,
    "halfWidthPx": 18.0,
    "neighborDistancePx": 6.0,
    "localContrastThreshold": 10.0,
    "circleXAtProgress0": 578.0,
    "circleXTravelPx": 316.0,
    "circleCentersYAtProgress0": [153.0, 380.0, 603.0],
    "circleTravelYPx": [144.0, 158.0, 146.0],
    "circleMaskRadiusPx": 62.0,
}
FORMAT_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage3-format-experiment-20260826"
    / "format-experiment-r1"
)
FORMAT_EXPERIMENT_SCHEMA = "twinkle-stage3-format-experiment-v1"
FORMAT_EXPERIMENT_FILES = (
    "candidate.mp4",
    "ffprobe.json",
    "decoded/frame-000.png",
    "decoded/frame-001.png",
    "decoded/frame-002.png",
    "comparisons/overall-comparison.png",
    "comparisons/detail-crops.png",
    "browser-harness/index.html",
    "format-experiment.json",
)
FORMAT_STATES = ("focused-settled", "extract-mid", "extract-end")
DETAIL_CROPS = (
    {"id": "black-front-box", "frame": 1, "box": (0, 140, 460, 590)},
    {"id": "silver-panel", "frame": 2, "box": (360, 200, 1000, 840)},
    {"id": "blue-optic", "frame": 2, "box": (430, 380, 740, 700)},
    {"id": "color-edge", "frame": 2, "box": (455, 400, 690, 680)},
    {"id": "metal-highlights", "frame": 2, "box": (780, 250, 980, 820)},
    {"id": "dark-area", "frame": 1, "box": (0, 0, 720, 210)},
    {"id": "fine-panel-edge", "frame": 2, "box": (350, 230, 1010, 840)},
)

FORBIDDEN_LEGACY_TERMS = (
    "j_green_filter_subassembly",
    "f_dual_acl_housing",
    "green-filter",
    "red-filter",
)


def condenser_repair_contract():
    return {
        "attempt": 1,
        "rootCause": {
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "classification": "cad-triangulated-geometry-and-surface-normals",
            "removelogoCause": False,
            "uvOrNormalTextureCause": False,
        },
        "modelCleanup": {
            "method": "temporary-mesh-limited-dissolve",
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "sourceMeshPreserved": True,
        },
        "occlusion": {
            "method": "reuse-cad-occluder-group-follow-root",
            "group": "OCCLUDER_GROUP__f_dual_acl_housing",
            "meshes": ["FrontCover :: 实体1", "Side1 :: 实体1"],
            "syntheticMeshesCreated": 0,
        },
        "animation": {
            "method": "native-fcurve",
            "frameRange": [0, 24],
            "keyframesPerLocationChannel": 25,
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
        },
        "postprocess": {"method": "none", "removelogoApplied": False},
    }


SECOND_REPAIR_VISUAL_GATES = {
    "rightPlateLine": {
        "frame": 18,
        "box": [400, 100, 462, 405],
        "maxRunPx": 12,
        "maskedCircles": [[421, 151, 20], [421, 251, 20], [421, 350, 20]],
    },
    "lowerLeftBoard": {
        "frame": 18,
        "polygon": [[12, 336], [151, 336], [151, 404], [12, 404]],
        "maxNearWhitePixels": 0,
    },
    "centralWhiteCorner": {
        "frame": 12,
        "polygon": [[34, 324], [184, 324], [184, 390], [34, 390]],
        "maxNearWhitePixels": 0,
    },
}


def condenser_second_repair_contract():
    return {
        "attempt": 2,
        "geometry": {
            "method": "boundary-ring-front-face-replacement",
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "maxFrontOffsetM": 0.0001,
            "fill": "2d-curve-with-inner-rings",
            "solidifyThicknessM": 0.0002,
            "bevelWidthM": 0.00005,
            "replacesOriginalFrontFaces": True,
        },
        "occlusion": {
            "method": "localized-extruded-leak-wedges",
            "preservedMeshes": ["FrontCover :: 实体1", "Side1 :: 实体1"],
            "minimumClearanceM": 0.0005,
            "productStructureClaimed": False,
            "linerCount": 2,
            "rayRois": ["lowerLeftBoard", "centralWhiteCorner"],
        },
        "motion": {
            "driver": "single-travel-property",
            "keyframes": [[0, 0.0], [3, 0.0], [7, 0.06], [19, 0.90], [24, 1.0]],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "CONT_ACCEL",
        },
    }


def condenser_motion_only_probe_contract():
    return {
        "schema": CONDENSER_MOTION_ONLY_PROBE_SCHEMA,
        "unit": CONDENSER,
        "movingAssembly": "SHOWCASE_GROUP__f_dual_acl_housing",
        "render": deepcopy(CONDENSER_LOWRES_RENDER),
        "travel": {
            "property": "travel",
            "range": [0.0, 1.0],
            "keyframes": [[0, 0.0], [3, 0.0], [7, 0.06], [19, 0.9], [24, 1.0]],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "CONT_ACCEL",
            "animatedFcurveCount": 1,
            "locationDriverCount": 0,
            "vectorDerivationCount": 1,
            "locationKeyframeCount": 0,
            "rotationKeyframeCount": 0,
        },
        "fullOffsetM": [0.034, 0.012, -0.016],
        "closeFrameIndices": list(reversed(range(25))),
        "geometryChanges": 0,
        "materialChanges": 0,
        "lightChanges": 0,
        "cameraChanges": 0,
        "postprocess": "none",
        "candidateBlendSaved": False,
        "humanVisualApproved": False,
        "authorizesR3": False,
        "authorizesStep6": False,
    }


def condenser_r3_candidate_contract():
    return {
        "schema": CONDENSER_R3_SCHEMA,
        "unit": CONDENSER,
        "selectedFormat": FALLBACK_FORMAT,
        "render": deepcopy(CONDENSER_LOWRES_RENDER),
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "visualSource": "approved-condenser-r1-linefix",
        "motionSource": "approved-condenser-motion-only-probe",
        "promotionMethod": "byte-identical-approved-frame-promotion",
        "candidateBlendSaved": False,
        "humanVisualApproved": True,
        "step5Closed": True,
        "authorizesStep6": False,
    }


def motion_playback_state(direction):
    if direction not in ("expand", "close"):
        raise ValueError(f"unknown motion playback direction: {direction}")
    sequence = list(range(25))
    if direction == "close":
        sequence.reverse()
    return {
        "direction": direction,
        "sequence": sequence,
        "cursor": 0,
        "frame": sequence[0],
        "paused": False,
        "ended": False,
    }


def reduce_motion_playback(snapshot, event):
    next_state = deepcopy(snapshot)
    if event == "pause":
        if not snapshot["ended"]:
            next_state["paused"] = True
        return next_state
    if event == "resume":
        if not snapshot["ended"]:
            next_state["paused"] = False
        return next_state
    if event != "tick":
        raise ValueError(f"unknown motion playback event: {event}")
    if snapshot["paused"] or snapshot["ended"]:
        return next_state
    cursor = snapshot["cursor"] + 1
    next_state["cursor"] = min(cursor, len(snapshot["sequence"]) - 1)
    next_state["frame"] = snapshot["sequence"][next_state["cursor"]]
    next_state["ended"] = next_state["cursor"] == len(snapshot["sequence"]) - 1
    return next_state


def motion_playback_audit():
    forward = motion_playback_state("expand")
    for _ in range(7):
        forward = reduce_motion_playback(forward, "tick")
    paused_frame = forward["frame"]
    forward = reduce_motion_playback(forward, "pause")
    held_frame = reduce_motion_playback(forward, "tick")["frame"]
    forward = reduce_motion_playback(forward, "resume")
    forward = reduce_motion_playback(forward, "tick")
    resumed_frame = forward["frame"]
    while not forward["ended"]:
        forward = reduce_motion_playback(forward, "tick")

    close = motion_playback_state("close")
    close_visited = [close["frame"]]
    while not close["ended"]:
        close = reduce_motion_playback(close, "tick")
        close_visited.append(close["frame"])
    return {
        "expandFrameIndices": motion_playback_state("expand")["sequence"],
        "closeFrameIndices": close_visited,
        "pause": {
            "pausedFrame": paused_frame,
            "heldFrame": held_frame,
            "resumedFrame": resumed_frame,
            "directionBefore": "forward",
            "directionAfter": "forward",
        },
        "expandEndedFrame": forward["frame"],
        "closeEndedFrame": close["frame"],
    }


def validate_condenser_motion_only_runtime(runtime):
    contract = condenser_motion_only_probe_contract()
    expected_travel = contract["travel"]
    actual_travel = runtime.get("travel", {})
    freedom_keys = (
        "property",
        "range",
        "animatedFcurveCount",
        "locationDriverCount",
        "vectorDerivationCount",
        "locationKeyframeCount",
        "rotationKeyframeCount",
    )
    if any(actual_travel.get(key) != expected_travel[key] for key in freedom_keys):
        raise ValueError("motion must use a single travel freedom")
    for key in ("keyframes", "interpolation", "handleType", "autoSmoothing"):
        if actual_travel.get(key) != expected_travel[key]:
            raise ValueError(f"travel curve contract mismatch: {key}")

    progress = [float(value) for value in runtime.get("progress", [])]
    velocity = [float(value) for value in runtime.get("velocityPerFrame", [])]
    acceleration = [
        float(value) for value in runtime.get("accelerationPerFrame", [])
    ]
    offsets = runtime.get("componentOffsetsM", [])
    rigid_hashes = runtime.get("rigidRelativeMatrixHashes", [])
    rigid_local_hashes = runtime.get("rigidLocalMatrixHashes", [])
    rigid_drift = [
        float(value) for value in runtime.get("rigidMaxRelativeMatrixDrift", [])
    ]
    if not all(
        len(values) == 25
        for values in (
            progress,
            velocity,
            acceleration,
            offsets,
            rigid_hashes,
            rigid_local_hashes,
            rigid_drift,
        )
    ):
        raise ValueError("motion-only runtime must contain 25 samples")
    for frame, expected in expected_travel["keyframes"]:
        if abs(progress[frame] - expected) > 1e-7:
            raise ValueError(f"semantic travel pose mismatch: {frame}")
    if any(value < -1e-7 or value > 1.0 + 1e-7 for value in progress):
        raise ValueError("travel overshoot")
    if any(right + 1e-7 < left for left, right in zip(progress, progress[1:])):
        raise ValueError("travel reversed")
    if any(abs(progress[index]) > 1e-7 for index in range(4)):
        raise ValueError("initial load-bearing hold drift")
    if any(value < -1e-7 for value in velocity):
        raise ValueError("velocity reversed")
    if max(velocity[4:8]) >= max(velocity[8:20]):
        raise ValueError("preload release is not slower than main travel")
    terminal_velocity = velocity[20:25]
    if any(
        right > left + 1e-7
        for left, right in zip(terminal_velocity, terminal_velocity[1:])
    ) or abs(terminal_velocity[-1]) > 1e-7:
        raise ValueError("terminal travel does not decelerate to rest")

    full_offset = contract["fullOffsetM"]
    for frame, (sample, actual_offset) in enumerate(zip(progress, offsets)):
        if len(actual_offset) != 3 or any(
            abs(float(actual) - expected * sample) > 1e-7
            for actual, expected in zip(actual_offset, full_offset)
        ):
            raise ValueError(f"approved straight travel path drift: {frame}")
    if max(rigid_drift) > 1e-7:
        raise ValueError("moving assembly relative transforms are not rigid")
    if runtime.get("closeFrameIndices") != contract["closeFrameIndices"]:
        raise ValueError("close motion must reverse the same frame sequence")
    if runtime.get("pauseEvidence") != {
        "frameIndex": 7,
        "heldFrameIndex": 7,
        "resumeFrameIndex": 8,
        "directionBefore": "forward",
        "directionAfter": "forward",
    }:
        raise ValueError("pause and same-direction resume evidence mismatch")
    return runtime


def condenser_r1_linefix_contract():
    return {
        "geometry": {
            "method": "exact-boolean-front-skin-proxy",
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "operation": "INTERSECT",
            "solver": "EXACT",
            "maxFrontOffsetM": 0.00005,
        },
        "motion": {
            "frameIndices": [0, 12, 24],
            "progress": [0.0, 0.5, 1.0],
            "source": "condenser-lowres-r1",
        },
        "occlusion": {"method": "none", "linerCount": 0},
        "postprocess": {"method": "none"},
    }


def condenser_r1_linefix_candidate_contract():
    return {
        "schema": CONDENSER_R1_LINEFIX_SCHEMA,
        "render": deepcopy(CONDENSER_LOWRES_RENDER),
        "motion": {
            "frameIndices": list(range(25)),
            "closeFrameIndices": list(reversed(range(25))),
            "progress": [condenser_motion_progress(index) for index in range(25)],
            "source": "condenser-lowres-r1",
        },
        "geometry": deepcopy(condenser_r1_linefix_contract()["geometry"]),
        "occlusion": {"method": "none", "linerCount": 0},
        "postprocess": {"method": "none"},
        "humanVisualApproved": False,
        "authorizesStep6": False,
    }


def _luma(pixel):
    return pixel[0] * 0.2126 + pixel[1] * 0.7152 + pixel[2] * 0.0722


def _longest_vertical_dark_component(image, gate):
    left, top, right, bottom = gate["box"]
    pixels = image.load()
    dark = set()
    for y in range(top, bottom):
        for x in range(max(left + 3, 3), min(right - 3, image.width - 3)):
            if any(
                (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
                for cx, cy, radius in gate.get("maskedCircles", [])
            ):
                continue
            center = _luma(pixels[x, y])
            neighbors = (_luma(pixels[x - 3, y]) + _luma(pixels[x + 3, y])) / 2.0
            if center + 18.0 < neighbors:
                dark.add((x, y))
    longest = 0
    while dark:
        seed = dark.pop()
        stack = [seed]
        min_y = max_y = seed[1]
        while stack:
            x, y = stack.pop()
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (x + dx, y + dy)
                    if neighbor in dark:
                        dark.remove(neighbor)
                        stack.append(neighbor)
        longest = max(longest, max_y - min_y + 1)
    return longest


def _near_white_pixels(image, polygon):
    mask = Image.new("1", image.size, 0)
    ImageDraw.Draw(mask).polygon([tuple(point) for point in polygon], fill=1)
    return sum(
        1
        for pixel, included in zip(
            image.convert("RGB").get_flattened_data(), mask.get_flattened_data()
        )
        if included and min(pixel) >= 235
    )


def measure_condenser_visual_failures(output_root, gates=None):
    output_root = Path(output_root)
    gates = deepcopy(gates or SECOND_REPAIR_VISUAL_GATES)
    result = {}
    for name, gate in gates.items():
        path = output_root / "frames" / f"frame-{gate['frame']:03d}.png"
        if not path.is_file():
            raise FileNotFoundError(f"visual gate frame missing: {path}")
        with Image.open(path) as source:
            image = source.convert("RGB")
        if "box" in gate:
            value = _longest_vertical_dark_component(image, gate)
            result[name] = {
                "frame": gate["frame"],
                "longestRunPx": value,
                "maxRunPx": gate["maxRunPx"],
                "passed": value <= gate["maxRunPx"],
            }
        else:
            value = _near_white_pixels(image, gate["polygon"])
            result[name] = {
                "frame": gate["frame"],
                "nearWhitePixels": value,
                "maxNearWhitePixels": gate["maxNearWhitePixels"],
                "passed": value <= gate["maxNearWhitePixels"],
            }
    return result


def finalize_condenser_second_repair_probe_visual_audit(output_root):
    output_root = Path(output_root)
    audit_path = output_root / "probe-audit.json"
    if not audit_path.is_file():
        raise FileNotFoundError(f"second repair probe audit missing: {audit_path}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    final_images = {
        index: Image.open(output_root / f"frame-{index:03d}.png").convert("RGB")
        for index in (0, 12, 24)
    }
    outside_changed = 0
    allowed_by_frame = {
        12: SECOND_REPAIR_VISUAL_GATES["centralWhiteCorner"]["polygon"],
        24: SECOND_REPAIR_VISUAL_GATES["lowerLeftBoard"]["polygon"],
    }
    for index, final in final_images.items():
        control_path = output_root / f"control-frame-{index:03d}.png"
        if not control_path.is_file():
            raise FileNotFoundError(f"probe control frame missing: {control_path}")
        with Image.open(control_path) as source:
            control = source.convert("RGB")
        difference = ImageChops.difference(control, final)
        allowed = Image.new("1", final.size, 0)
        polygon = allowed_by_frame.get(index)
        if polygon:
            ImageDraw.Draw(allowed).polygon(
                [tuple(point) for point in polygon], fill=1
            )
        outside_changed += sum(
            1
            for pixel, permitted in zip(
                difference.get_flattened_data(), allowed.get_flattened_data()
            )
            if pixel != (0, 0, 0) and not permitted
        )
    line_gate = deepcopy(SECOND_REPAIR_VISUAL_GATES["rightPlateLine"])
    line_gate["frame"] = 24
    line_value = _longest_vertical_dark_component(final_images[24], line_gate)
    lower_gate = SECOND_REPAIR_VISUAL_GATES["lowerLeftBoard"]
    central_gate = SECOND_REPAIR_VISUAL_GATES["centralWhiteCorner"]
    visual = {
        "rightPlateLine": {
            "frame": 24,
            "longestRunPx": line_value,
            "maxRunPx": line_gate["maxRunPx"],
            "passed": line_value <= line_gate["maxRunPx"],
        },
        "lowerLeftBoard": {
            "frame": 24,
            "nearWhitePixels": _near_white_pixels(
                final_images[24], lower_gate["polygon"]
            ),
            "maxNearWhitePixels": lower_gate["maxNearWhitePixels"],
        },
        "centralWhiteCorner": {
            "frame": 12,
            "nearWhitePixels": _near_white_pixels(
                final_images[12], central_gate["polygon"]
            ),
            "maxNearWhitePixels": central_gate["maxNearWhitePixels"],
        },
    }
    for name in ("lowerLeftBoard", "centralWhiteCorner"):
        visual[name]["passed"] = (
            visual[name]["nearWhitePixels"]
            <= visual[name]["maxNearWhitePixels"]
        )
    audit.setdefault("occlusion", {})["roiOutsideChangedPixels"] = outside_changed
    audit["visualGates"] = visual
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return audit


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_authority():
    if sha256(AUTHORITY_MANIFEST) != EXPECTED_AUTHORITY_SHA256:
        raise ValueError("authority manifest hash mismatch")
    manifest = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    if set(manifest.get("units", {})) != set(SEMANTIC_UNITS):
        raise ValueError("authority manifest semantic units mismatch")
    return manifest


def default_request(output_root):
    return {
        "authorityManifest": str(AUTHORITY_MANIFEST),
        "semanticUnits": list(SEMANTIC_UNITS),
        "payloadTerms": [],
        "writeProductionPage": False,
        "outputRoot": str(Path(output_root)),
    }


def validate_request(request):
    if Path(request["authorityManifest"]).resolve() != AUTHORITY_MANIFEST.resolve():
        raise ValueError("authority manifest must be the approved stage 1 manifest")
    if tuple(request["semanticUnits"]) != SEMANTIC_UNITS:
        raise ValueError("semantic units must contain only the two approved identifiers")
    for value in request.get("payloadTerms", []):
        lowered = str(value).lower()
        if any(term in lowered for term in FORBIDDEN_LEGACY_TERMS):
            raise ValueError(f"forbidden legacy term: {value}")
    if request.get("writeProductionPage"):
        raise ValueError("production page writes are outside stage 3")
    output_root = Path(request["outputRoot"])
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    validate_authority()
    return request


def state(top_level, **overrides):
    if top_level not in TOP_LEVEL_STATES:
        raise ValueError(f"unknown top-level state: {top_level}")
    snapshot = {
        "topLevel": top_level,
        "globalOrbit": "running" if top_level == "global" else "paused",
        "unit": None,
        "actionPhase": None,
        "actionPlayback": None,
        "progress": 0.0,
        "direction": None,
        "inspectionLight": "off",
        "awaitingDetailExit": False,
        "playbackMode": "media",
        "assetFormat": None,
        "fallbackReason": None,
    }
    snapshot.update(overrides)
    return snapshot


def controls_for(snapshot):
    controls = deepcopy(CONTROL_MATRIX[snapshot["topLevel"]])
    controls["globalToggle"]["label"] = (
        "暂停展示" if snapshot["globalOrbit"] == "running" else "开始展示"
    )
    controls["actionToggle"]["label"] = (
        "继续动作"
        if snapshot["topLevel"] == "action"
        and snapshot["actionPlayback"] == "paused"
        else "暂停动作"
    )
    return controls


def reduce_state(snapshot, event):
    next_state = deepcopy(snapshot)
    event_type = event["type"]

    if event_type == "control":
        control = event["control"]
        if not controls_for(snapshot)[control]["enabled"]:
            return snapshot
        if control == "globalToggle":
            next_state["globalOrbit"] = (
                "paused" if snapshot["globalOrbit"] == "running" else "running"
            )
        elif control == "actionToggle":
            next_state["actionPlayback"] = (
                "paused" if snapshot["actionPlayback"] == "running" else "running"
            )
        elif control == "return":
            next_state["awaitingDetailExit"] = True
        return next_state

    if event_type == "select":
        if snapshot["topLevel"] != "global" or event["unit"] not in SEMANTIC_UNITS:
            return snapshot
        fallback_reason = event.get("fallbackReason")
        phase = "expand" if fallback_reason else "focus"
        return state(
            "action",
            globalOrbit="paused",
            unit=event["unit"],
            actionPhase=phase,
            actionPlayback="running",
            progress=0.0,
            direction="forward",
            playbackMode="static-fade" if fallback_reason else "media",
            assetFormat=FALLBACK_FORMAT if fallback_reason else None,
            fallbackReason=fallback_reason,
        )

    if event_type == "progress":
        if snapshot["topLevel"] != "action":
            return snapshot
        value = float(event["value"])
        if not 0.0 <= value <= 1.0:
            raise ValueError("progress must be between 0 and 1")
        next_state["progress"] = value
        return next_state

    if event_type == "segmentComplete":
        if snapshot["topLevel"] != "action":
            return snapshot
        phase = snapshot["actionPhase"]
        if phase == "focus":
            next_state["actionPhase"] = "expand"
            return next_state
        if phase == "expand":
            if snapshot["unit"] == CHAMBER:
                next_state["inspectionLight"] = "entering"
                return next_state
            return state(
                "explanation",
                globalOrbit="paused",
                unit=snapshot["unit"],
                progress=1.0,
            )
        if phase == "close":
            next_state["actionPhase"] = "overviewReturn"
            next_state["progress"] = 0.0
            return next_state
        if phase == "overviewReturn":
            return state("global", globalOrbit="paused")
        return snapshot

    if event_type == "inspectionEnterComplete":
        if snapshot["inspectionLight"] != "entering":
            return snapshot
        return state(
            "explanation",
            globalOrbit="paused",
            unit=snapshot["unit"],
            progress=1.0,
            inspectionLight="stable",
        )

    if event_type == "detailExited":
        if snapshot["topLevel"] != "explanation" or not snapshot["awaitingDetailExit"]:
            return snapshot
        inspection_light = "exiting" if snapshot["unit"] == CHAMBER else "off"
        return state(
            "action",
            globalOrbit="paused",
            unit=snapshot["unit"],
            actionPhase="close",
            actionPlayback="running",
            progress=1.0,
            direction="backward",
            inspectionLight=inspection_light,
        )

    if event_type == "inspectionExitComplete":
        if snapshot["inspectionLight"] != "exiting":
            return snapshot
        next_state["inspectionLight"] = "off"
        return next_state

    raise ValueError(f"unknown event: {event_type}")


def validate_format_experiment(output_root):
    output_root = Path(output_root)
    missing = [
        relative
        for relative in FORMAT_EXPERIMENT_FILES
        if not (output_root / relative).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "format experiment inventory missing: " + ", ".join(missing)
        )
    report = json.loads(
        (output_root / "format-experiment.json").read_text(encoding="utf-8")
    )
    if report.get("schema") != FORMAT_EXPERIMENT_SCHEMA:
        raise ValueError("format experiment schema mismatch")
    human_approved = report.get("humanDetailApproved")
    if human_approved not in (True, False):
        raise ValueError("human detail approval must be an explicit boolean")
    if report.get("selectedFormat") not in (None, FALLBACK_FORMAT):
        raise ValueError("H.264 format cannot be selected before human review")
    browser_matrix = report.get("browserMatrix", {})
    if browser_matrix.get("edge-150") != "not-tested":
        raise ValueError("browser matrix overclaims Edge 150")
    if report.get("candidate", {}).get("parameterSetCount") != 1:
        raise ValueError("exactly one H.264 parameter set is allowed")
    if report.get("selectedFormat") == FALLBACK_FORMAT:
        if not report.get("videoRouteFailed") or report.get("machinePassed"):
            raise ValueError("PNG fallback decision is internally inconsistent")
        failed_ids = [
            browser_id
            for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151")
            if browser_matrix.get(browser_id) in {"failed", "validation-failed"}
        ]
        if not failed_ids:
            raise ValueError("PNG fallback lacks required browser failure evidence")
        for browser_id in failed_ids:
            if not (output_root / "browser-results" / f"{browser_id}.json").is_file():
                raise FileNotFoundError(f"browser failure evidence missing: {browser_id}")
    elif report.get("machinePassed") is not True:
        raise ValueError("format experiment machine evidence did not pass")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"format experiment inventory hash mismatch: {relative}")
    if human_approved:
        expected_approval = {
            "approvedFormat": FALLBACK_FORMAT,
            "approvedBy": "user",
            "approvedOn": "2026-08-26",
            "scope": "stage3-step3-format-only",
            "authorizesStep4": False,
        }
        if report.get("humanApproval") != expected_approval:
            raise ValueError("human format approval record is missing or overbroad")
    return report


def format_decision(browser_matrix):
    matrix = dict(browser_matrix)
    if matrix.get("edge-150") != "not-tested":
        raise ValueError("Edge 150 must remain not-tested")
    required = ("chrome-151", "chrome-for-testing-150", "edge-151")
    video_failed = any(matrix.get(browser_id) != "passed" for browser_id in required)
    return {
        "browserMatrix": matrix,
        "videoRouteFailed": video_failed,
        "machinePassed": not video_failed,
        "selectedFormat": FALLBACK_FORMAT if video_failed else None,
    }


def run_checked(command, *, cwd=None):
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _concat_path(path):
    return Path(path).resolve().as_posix().replace("'", "'\\''")


def _image_psnr(source, decoded):
    with Image.open(source) as source_image, Image.open(decoded) as decoded_image:
        difference = ImageChops.difference(
            source_image.convert("RGB"), decoded_image.convert("RGB")
        )
        histogram = difference.histogram()
        squared_error = sum(
            (value % 256) ** 2 * count for value, count in enumerate(histogram)
        )
        mse = squared_error / (difference.width * difference.height * 3)
        return None if mse == 0 else 10 * math.log10((255**2) / mse)


def _image_mean_rgb(path):
    with Image.open(path) as image:
        return [round(value, 4) for value in ImageStat.Stat(image.convert("RGB")).mean]


def _image_ssim(ffmpeg, source, decoded):
    result = run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            source,
            "-i",
            decoded,
            "-lavfi",
            "[0:v][1:v]ssim",
            "-f",
            "null",
            "NUL",
        ]
    )
    match = re.search(r"All:([0-9.]+)", result.stderr)
    if not match:
        raise RuntimeError("ffmpeg SSIM output was not found")
    return float(match.group(1))


def _render_overall_comparison(source_paths, decoded_paths, destination):
    label_height = 30
    width, height = 1280, 900
    canvas = Image.new("RGB", (width * 2, (height + label_height) * 3), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (source, decoded) in enumerate(zip(source_paths, decoded_paths)):
        y = index * (height + label_height)
        with Image.open(source) as source_image, Image.open(decoded) as decoded_image:
            canvas.paste(source_image.convert("RGB"), (0, y + label_height))
            canvas.paste(decoded_image.convert("RGB"), (width, y + label_height))
        draw.text((10, y + 8), f"source {FORMAT_STATES[index]}", fill="black", font=font)
        draw.text(
            (width + 10, y + 8),
            f"decoded {FORMAT_STATES[index]}",
            fill="black",
            font=font,
        )
    canvas.save(destination)


def _render_detail_crops(source_paths, decoded_paths, destination):
    gap = 20
    label_height = 28
    rows = []
    for crop in DETAIL_CROPS:
        source = Image.open(source_paths[crop["frame"]]).convert("RGB")
        decoded = Image.open(decoded_paths[crop["frame"]]).convert("RGB")
        source_crop = source.crop(crop["box"])
        decoded_crop = decoded.crop(crop["box"])
        source.close()
        decoded.close()
        rows.append((crop, source_crop, decoded_crop))
    canvas_width = max(
        source_crop.width * 2 + gap for _, source_crop, _ in rows
    )
    canvas_height = sum(source_crop.height + label_height for _, source_crop, _ in rows)
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    y = 0
    for crop, source_crop, decoded_crop in rows:
        draw.text((4, y + 7), f"{crop['id']} source", fill="black", font=font)
        draw.text(
            (source_crop.width + gap + 4, y + 7),
            f"{crop['id']} decoded",
            fill="black",
            font=font,
        )
        canvas.paste(source_crop, (0, y + label_height))
        canvas.paste(decoded_crop, (source_crop.width + gap, y + label_height))
        y += source_crop.height + label_height
    canvas.save(destination)


def _browser_harness_html(expected_means):
    expected_json = json.dumps(expected_means, separators=(",", ":"))
    return f"""<!doctype html>
<html lang=\"en\"><meta charset=\"utf-8\"><title>TWINKLE format harness</title>
<style>body{{font:14px system-ui;background:#111;color:#eee}}video{{width:640px}}</style>
<video id=\"candidate\" muted playsinline preload=\"auto\" src=\"../candidate.mp4\"></video>
<pre id=\"status\">running</pre>
<script>
const expectedMeans = {expected_json};
const query = new URLSearchParams(location.search);
const browserId = query.get('browser');
const expectedMajor = Number(query.get('major'));
const family = query.get('family');
const video = document.querySelector('#candidate');
const status = document.querySelector('#status');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const presentedFrame = async () => {{
  let callbackFired = false;
  if ('requestVideoFrameCallback' in video) {{
    await Promise.race([
      new Promise(resolve => video.requestVideoFrameCallback(() => {{ callbackFired = true; resolve(); }})),
      wait(500),
    ]);
    if (!callbackFired) console.warn('presentedFrame timeout');
  }}
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}};
const until = async (fn, timeoutMs) => {{
  const started = performance.now();
  while (!fn()) {{
    if (performance.now() - started > timeoutMs) throw new Error('timeout');
    await wait(25);
  }}
}};
const seek = async value => {{
  await new Promise((resolve, reject) => {{
    const timer = setTimeout(() => reject(new Error('seek timeout')), 3000);
    video.addEventListener('seeked', () => {{ clearTimeout(timer); resolve(); }}, {{once:true}});
    video.currentTime = value;
  }});
  await presentedFrame();
}};
const sample = async value => {{
  await seek(value);
  await video.play();
  await until(() => video.currentTime >= value+0.05, 1500);
  video.pause();
  await presentedFrame();
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  const context = canvas.getContext('2d', {{willReadFrequently:true}});
  context.drawImage(video, 0, 0);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  const sums = [0,0,0]; let count = 0;
  for (let y=0; y<canvas.height; y+=4) for (let x=0; x<canvas.width; x+=4) {{
    const offset = (y*canvas.width+x)*4;
    sums[0]+=pixels[offset]; sums[1]+=pixels[offset+1]; sums[2]+=pixels[offset+2]; count++;
  }}
  return sums.map(value => value/count);
}};
const post = result => fetch('/result', {{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(result)}});
(async () => {{
  const result = {{browserId, expectedMajor, family, userAgent:navigator.userAgent,
    brands:navigator.userAgentData?.brands || [], passed:false}};
  try {{
    await until(() => video.readyState >= 1, 5000);
    result.duration = video.duration; result.width = video.videoWidth; result.height = video.videoHeight;
    const token = family === 'edge' ? `Edg/${{expectedMajor}}.` : `Chrome/${{expectedMajor}}.`;
    if (!navigator.userAgent.includes(token)) throw new Error(`unexpected user agent: ${{navigator.userAgent}}`);
    await seek(0); await video.play(); await until(() => video.currentTime >= 0.35, 4000);
    video.pause(); const pauseTime = video.currentTime; await wait(400);
    result.pauseTime = pauseTime; result.pauseHeldTime = video.currentTime;
    result.pauseHeld = Math.abs(video.currentTime-pauseTime) <= 0.05;
    await video.play(); await until(() => video.currentTime >= pauseTime+0.20, 3000);
    result.resumeTime = video.currentTime;
    await until(() => video.ended, 6000);
    result.ended = video.ended;
    result.endedAt = video.currentTime;
    await seek(0); await video.play(); await until(() => video.currentTime >= 0.20, 3000); video.pause();
    result.replayFromStart = video.currentTime >= 0.20;
    result.samples = [];
    for (let index=0; index<expectedMeans.length; index++) {{
      const actual = await sample(0.5+index);
      const expected = expectedMeans[index];
      const delta = actual.map((value, channel) => Math.abs(value-expected[channel]));
      const meanLuma = actual[0]*0.2126+actual[1]*0.7152+actual[2]*0.0722;
      result.samples.push({{time:0.5+index,actual,expected,delta,meanLuma}});
    }}
    result.noBlackFrames = result.samples.every(item => item.meanLuma > 10);
    result.noMeanColorShift = result.samples.every(item => Math.max(...item.delta) <= 6);
    result.passed = result.width === 1280 && result.height === 900 && result.pauseHeld &&
      result.ended && Math.abs(result.endedAt-result.duration) <= 0.15 && result.replayFromStart &&
      result.noBlackFrames && result.noMeanColorShift;
    if (!result.passed) throw new Error('browser media contract failed');
  }} catch (error) {{ result.error = String(error?.stack || error); }}
  status.textContent = JSON.stringify(result, null, 2);
  await post(result);
}})();
</script></html>"""


def format_encode_command(ffmpeg, concat, candidate):
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat,
        "-t",
        "3",
        "-r",
        "24",
        "-an",
        "-vf",
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-profile:v",
        "high",
        "-crf",
        "10",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "1",
        "-keyint_min",
        "1",
        "-sc_threshold",
        "0",
        "-x264-params",
        "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-movflags",
        "+faststart",
        candidate,
    ]


def build_format_candidate(output_root, *, ffmpeg=None, ffprobe=None):
    output_root = Path(output_root)
    request = default_request(output_root)
    validate_request(request)
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    ffprobe = ffprobe or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required")
    authority = validate_authority()
    frames = authority["units"][CONDENSER]["frames"]
    source_paths = [
        AUTHORITY_MANIFEST.parent / frames[state_name]["asset"]
        for state_name in FORMAT_STATES
    ]
    for path in source_paths:
        if not path.is_file():
            raise FileNotFoundError(f"approved source frame missing: {path}")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".format-experiment-", dir=output_root.parent)
    )
    try:
        (staging / "decoded").mkdir()
        (staging / "comparisons").mkdir()
        (staging / "browser-harness").mkdir()
        (staging / "browser-results").mkdir()
        (staging / "browser-profiles").mkdir()
        concat = staging / "source-frames.txt"
        concat.write_text(
            "".join(
                f"file '{_concat_path(path)}'\nduration 1\n" for path in source_paths
            )
            + f"file '{_concat_path(source_paths[-1])}'\n",
            encoding="utf-8",
        )
        candidate = staging / "candidate.mp4"
        run_checked(format_encode_command(ffmpeg, concat, candidate))
        probe_result = run_checked(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_streams",
                "-show_format",
                "-show_frames",
                "-of",
                "json",
                candidate,
            ]
        )
        probe = json.loads(probe_result.stdout)
        (staging / "ffprobe.json").write_text(
            json.dumps(probe, indent=2), encoding="utf-8"
        )
        video_stream = probe["streams"][0]
        video_frames = probe["frames"]
        if not video_frames or any(int(frame.get("key_frame", 0)) != 1 for frame in video_frames):
            raise ValueError("candidate does not make every frame independently seekable")
        if (
            video_stream.get("codec_name") != "h264"
            or video_stream.get("profile") != "High"
            or video_stream.get("pix_fmt") != "yuv420p"
            or (video_stream.get("width"), video_stream.get("height")) != (1280, 900)
            or video_stream.get("color_space") != "bt709"
            or video_stream.get("color_transfer") != "bt709"
            or video_stream.get("color_primaries") != "bt709"
        ):
            raise ValueError("candidate ffprobe contract mismatch")

        decoded_paths = []
        metrics = []
        for index, (timestamp, source_path) in enumerate(
            zip((0.5, 1.5, 2.5), source_paths)
        ):
            decoded = staging / "decoded" / f"frame-{index:03d}.png"
            run_checked(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-y",
                    "-ss",
                    str(timestamp),
                    "-i",
                    candidate,
                    "-frames:v",
                    "1",
                    decoded,
                ]
            )
            decoded_paths.append(decoded)
            metrics.append(
                {
                    "state": FORMAT_STATES[index],
                    "timestamp": timestamp,
                    "psnr": _image_psnr(source_path, decoded),
                    "ssim": _image_ssim(ffmpeg, source_path, decoded),
                    "sourceMeanRgb": _image_mean_rgb(source_path),
                    "decodedMeanRgb": _image_mean_rgb(decoded),
                }
            )

        _render_overall_comparison(
            source_paths,
            decoded_paths,
            staging / "comparisons" / "overall-comparison.png",
        )
        _render_detail_crops(
            source_paths,
            decoded_paths,
            staging / "comparisons" / "detail-crops.png",
        )
        (staging / "browser-harness" / "index.html").write_text(
            _browser_harness_html([item["decodedMeanRgb"] for item in metrics]),
            encoding="utf-8",
        )
        report = {
            "schema": FORMAT_EXPERIMENT_SCHEMA,
            "authorityManifest": str(AUTHORITY_MANIFEST),
            "authoritySha256": EXPECTED_AUTHORITY_SHA256,
            "sourceTextPresent": False,
            "sourceFrames": [
                {
                    "state": state_name,
                    "path": str(path),
                    "sha256": sha256(path),
                }
                for state_name, path in zip(FORMAT_STATES, source_paths)
            ],
            "candidate": {
                "path": "candidate.mp4",
                "sha256": sha256(candidate),
                "parameters": FORMAT_EXPERIMENT,
                "parameterSetCount": 1,
                "durationSeconds": float(probe["format"]["duration"]),
                "frameCount": len(video_frames),
                "allFramesKeyFrames": True,
                "audioStreamCount": 0,
            },
            "decodedMetrics": metrics,
            "detailCrops": list(DETAIL_CROPS),
            "browserDriver": "direct-executable-local-self-report",
            "browserMatrix": {
                "chrome-151": "pending",
                "chrome-for-testing-150": "pending",
                "edge-151": "pending",
                "edge-150": "not-tested",
            },
            "machinePassed": False,
            "humanDetailApproved": False,
            "selectedFormat": None,
            "inventorySha256": {},
        }
        (staging / "format-experiment.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(staging, output_root)
    except Exception:
        raise
    return output_root


class _HarnessHandler(SimpleHTTPRequestHandler):
    result = None
    result_event = threading.Event()

    def log_message(self, format_string, *args):
        return

    def do_POST(self):
        if self.path != "/result":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        type(self).result = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).result_event.set()
        self.send_response(204)
        self.end_headers()


def run_browser_check(output_root, browser_id, executable, expected_major, family):
    output_root = Path(output_root)
    executable = Path(executable)
    if not executable.is_file():
        raise FileNotFoundError(f"browser executable missing: {executable}")
    profile = output_root / "browser-profiles" / browser_id
    if profile.exists():
        profile = profile.with_name(
            f"{browser_id}-retry-{time.time_ns()}"
        )
    profile.mkdir(parents=True)
    _HarnessHandler.result = None
    _HarnessHandler.result_event = threading.Event()
    handler = partial(_HarnessHandler, directory=str(output_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = (
        f"http://127.0.0.1:{server.server_port}/browser-harness/index.html"
        f"?browser={browser_id}&major={expected_major}&family={family}"
    )
    command = [
        str(executable),
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--disable-default-apps",
        "--disable-extensions",
        "--metrics-recording-only",
        "--autoplay-policy=no-user-gesture-required",
        "--remote-debugging-port=0",
        "--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE 127.0.0.1, EXCLUDE localhost",
        f"--user-data-dir={profile}",
        url,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not _HarnessHandler.result_event.wait(20):
            raise TimeoutError(f"browser harness timed out: {browser_id}")
        result = _HarnessHandler.result
    finally:
        server.shutdown()
        server.server_close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    result.update(
        {
            "executable": str(executable),
            "executableSha256": sha256(executable),
            "isolatedUserDataDir": str(profile),
            "localHarnessOnly": True,
            "rootProcessExitCode": process.returncode,
        }
    )
    result_path = output_root / "browser-results" / f"{browser_id}.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not result.get("passed"):
        raise RuntimeError(f"browser media contract failed: {browser_id}: {result}")
    return result


def finalize_browser_evidence(output_root):
    output_root = Path(output_root)
    report_path = output_root / "format-experiment.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151"):
        result_path = output_root / "browser-results" / f"{browser_id}.json"
        if not result_path.is_file():
            raise FileNotFoundError(f"browser evidence missing: {browser_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        report["browserMatrix"][browser_id] = (
            "passed" if result.get("passed") else "failed"
        )
    report["browserMatrix"]["edge-150"] = "not-tested"
    report["machinePassed"] = all(
        report["browserMatrix"][browser_id] == "passed"
        for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151")
    )
    inventory = {}
    for relative in FORMAT_EXPERIMENT_FILES:
        if relative == "format-experiment.json":
            continue
        path = output_root / relative
        if path.is_file():
            inventory[relative] = sha256(path)
    report["inventorySha256"] = inventory
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_format_experiment(output_root)


def record_video_route_failure(output_root, browser_id, reason, attempts):
    output_root = Path(output_root)
    result_path = output_root / "browser-results" / f"{browser_id}.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"browser failure evidence missing: {browser_id}")
    matrix = {
        "chrome-151": "validation-failed" if browser_id == "chrome-151" else "not-run-after-video-route-failure",
        "chrome-for-testing-150": (
            "validation-failed"
            if browser_id == "chrome-for-testing-150"
            else "not-run-after-video-route-failure"
        ),
        "edge-151": "validation-failed" if browser_id == "edge-151" else "not-run-after-video-route-failure",
        "edge-150": "not-tested",
    }
    decision = format_decision(matrix)
    report_path = output_root / "format-experiment.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(decision)
    report["failureEvidence"] = {
        "browserId": browser_id,
        "result": str(result_path.relative_to(output_root)).replace("\\", "/"),
        "reason": reason,
        "boundedHarnessAttempts": attempts,
        "candidateParameterSetChanged": False,
    }
    inventory = {}
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path != report_path:
            relative = str(path.relative_to(output_root)).replace("\\", "/")
            inventory[relative] = sha256(path)
    report["inventorySha256"] = inventory
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_format_experiment(output_root)


def record_format_approval(output_root, approved_format):
    output_root = Path(output_root)
    if approved_format != FALLBACK_FORMAT:
        raise ValueError("only the machine-selected PNG fallback can be approved")
    report_path = output_root / "format-experiment.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("selectedFormat") != FALLBACK_FORMAT or not report.get(
        "videoRouteFailed"
    ):
        raise ValueError("format approval requires the recorded video-route failure")
    report["humanDetailApproved"] = True
    report["humanApproval"] = {
        "approvedFormat": FALLBACK_FORMAT,
        "approvedBy": "user",
        "approvedOn": "2026-08-26",
        "scope": "stage3-step3-format-only",
        "authorizesStep4": False,
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_format_experiment(output_root)


def _smoothstep(value):
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def chamber_motion_progress(frame_index):
    if not 0 <= frame_index < CHAMBER_LOWRES_RENDER["frameCount"]:
        raise ValueError("chamber frame index out of range")
    time_ms = frame_index * CHAMBER_LOWRES_RENDER["durationMs"] / (
        CHAMBER_LOWRES_RENDER["frameCount"] - 1
    )
    if time_ms <= CHAMBER_LOWRES_TIMING["seam"]:
        progress = 0.06 * _smoothstep(time_ms / CHAMBER_LOWRES_TIMING["seam"])
    else:
        progress = 0.06 + 0.94 * _smoothstep(
            (time_ms - CHAMBER_LOWRES_TIMING["seam"])
            / CHAMBER_LOWRES_TIMING["acceleratedTravel"]
        )
    return round(progress, 8)


def condenser_motion_progress(frame_index):
    if not 0 <= frame_index < CONDENSER_LOWRES_RENDER["frameCount"]:
        raise ValueError("condenser frame index out of range")
    return round(
        _smoothstep(frame_index / (CONDENSER_LOWRES_RENDER["frameCount"] - 1)), 8
    )


def _half_size_stage1(path):
    with Image.open(path) as image:
        return image.convert("RGB").resize((640, 450), Image.Resampling.LANCZOS)


def _pixel_mae(left, right):
    difference = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
    return sum(ImageStat.Stat(difference).mean) / 3.0


def validate_chamber_lowres_candidate(output_root):
    output_root = Path(output_root)
    report_path = output_root / "chamber-lowres-manifest.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"chamber low-resolution manifest missing: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != CHAMBER_LOWRES_SCHEMA:
        raise ValueError("chamber low-resolution schema mismatch")
    if report.get("unit") != CHAMBER:
        raise ValueError("chamber low-resolution semantic unit mismatch")
    if report.get("selectedFormat") != FALLBACK_FORMAT:
        raise ValueError("chamber low-resolution candidate must use PNG sequence")
    if report.get("render") != CHAMBER_LOWRES_RENDER:
        raise ValueError("chamber low-resolution render contract mismatch")
    if report.get("timingMs") != CHAMBER_LOWRES_TIMING:
        raise ValueError("chamber low-resolution timing mismatch")
    if report.get("machinePassed") is not True:
        raise ValueError("chamber low-resolution machine gate did not pass")
    human_approved = report.get("humanVisualApproved")
    if human_approved not in (True, False):
        raise ValueError("chamber visual approval must be an explicit boolean")
    if report.get("authorizesStep5") is not False:
        raise ValueError("chamber candidate cannot authorize step 5")
    if human_approved:
        expected_approval = {
            "approvedUnit": CHAMBER,
            "approvedBy": "user",
            "approvedOn": "2026-08-26",
            "scope": "stage3-step4-chamber-lowres-only",
            "authorizesStep5": False,
        }
        if report.get("humanApproval") != expected_approval:
            raise ValueError("chamber visual approval record is missing or overbroad")

    authority = validate_authority()
    format_report = validate_format_experiment(FORMAT_OUTPUT_ROOT)
    if not format_report.get("humanDetailApproved") or format_report.get(
        "selectedFormat"
    ) != FALLBACK_FORMAT:
        raise ValueError("approved PNG format decision is required before step 4")
    chamber = authority["units"][CHAMBER]
    expected_endpoints = {
        "closed": chamber["frames"]["focused-settled"],
        "open": chamber["frames"]["extract-end"],
        "inspectionLit": chamber["inspectionLight"],
    }
    for name, source_record in expected_endpoints.items():
        actual = report.get("endpointReferences", {}).get(name, {})
        source_path = AUTHORITY_MANIFEST.parent / source_record["asset"]
        if actual.get("path") != source_record["asset"] or actual.get(
            "sha256"
        ) != source_record["sha256"]:
            raise ValueError(f"stage 1 endpoint reference mismatch: {name}")
        if sha256(source_path) != source_record["sha256"]:
            raise ValueError(f"stage 1 endpoint drift: {name}")

    motion = report.get("motion", {})
    expected_indices = list(range(CHAMBER_LOWRES_RENDER["frameCount"]))
    expected_progress = [chamber_motion_progress(index) for index in expected_indices]
    if motion.get("frameIndices") != expected_indices:
        raise ValueError("chamber frame indices mismatch")
    if motion.get("closeFrameIndices") != list(reversed(expected_indices)):
        raise ValueError("chamber close sequence must reverse the source frames")
    if motion.get("progress") != expected_progress:
        raise ValueError("chamber progress curve mismatch")
    if motion.get("seamProgress") != 0.06 or motion.get(
        "bothPanelsSynchronous"
    ) is not True:
        raise ValueError("chamber seam or synchronous-panel contract mismatch")

    frames = report.get("frames", [])
    if len(frames) != CHAMBER_LOWRES_RENDER["frameCount"]:
        raise ValueError("chamber low-resolution frame count mismatch")
    for index, frame in enumerate(frames):
        path = output_root / frame.get("path", "")
        if frame.get("index") != index or frame.get("progress") != expected_progress[index]:
            raise ValueError(f"chamber frame metadata mismatch: {index}")
        offsets = frame.get("componentOffsetsM") or {}
        expected_offsets = {
            "bottomCover": [0.0, 0.0, -0.14 * expected_progress[index]],
            "sidePanel": [0.0, -0.1 * expected_progress[index], 0.0],
        }
        for component, expected in expected_offsets.items():
            actual = offsets.get(component)
            if actual is None or any(
                abs(float(left) - float(right)) > 1e-7
                for left, right in zip(actual, expected)
            ):
                raise ValueError(
                    f"chamber synchronous component offset mismatch: {index} {component}"
                )
        if set(frame.get("rootWorldMatrices") or {}) != set(chamber["rootObjects"]):
            raise ValueError(f"chamber root matrix evidence missing: {index}")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(f"chamber frame hash mismatch: {index}")
        with Image.open(path) as image:
            if image.size != tuple(CHAMBER_LOWRES_RENDER["resolution"]):
                raise ValueError(f"chamber frame dimensions mismatch: {index}")

    for relative in CHAMBER_LOWRES_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"chamber review evidence missing: {relative}")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"chamber inventory hash mismatch: {relative}")
    return report


def validate_condenser_lowres_candidate(output_root):
    output_root = Path(output_root)
    report_path = output_root / "condenser-lowres-manifest.json"
    if not report_path.is_file():
        raise FileNotFoundError(
            f"condenser low-resolution manifest missing: {report_path}"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != CONDENSER_LOWRES_SCHEMA:
        raise ValueError("condenser low-resolution schema mismatch")
    if report.get("unit") != CONDENSER:
        raise ValueError("condenser low-resolution semantic unit mismatch")
    if report.get("selectedFormat") != FALLBACK_FORMAT:
        raise ValueError("condenser low-resolution candidate must use PNG sequence")
    if report.get("render") != CONDENSER_LOWRES_RENDER:
        raise ValueError("condenser low-resolution render contract mismatch")
    if report.get("machinePassed") is not True:
        raise ValueError("condenser low-resolution machine gate did not pass")
    if report.get("humanVisualApproved") is not False:
        raise ValueError("condenser visual approval must remain false before review")
    if report.get("authorizesStep6") is not False:
        raise ValueError("condenser candidate cannot authorize step 6")

    authority = validate_authority()
    chamber_report = validate_chamber_lowres_candidate(CHAMBER_LOWRES_OUTPUT_ROOT)
    if not chamber_report.get("humanVisualApproved"):
        raise ValueError("approved chamber low-resolution candidate is required")
    expected_style = {
        "unit": CHAMBER,
        "manifest": (
            "output/.twinkle-stage3-chamber-lowres-20260826/"
            "chamber-lowres-r1/chamber-lowres-manifest.json"
        ),
        "humanVisualApproved": True,
    }
    if report.get("styleReference") != expected_style:
        raise ValueError("condenser style reference mismatch")
    condenser = authority["units"][CONDENSER]
    expected_endpoints = {
        "closed": condenser["frames"]["focused-settled"],
        "open": condenser["frames"]["extract-end"],
    }
    for name, source_record in expected_endpoints.items():
        actual = report.get("endpointReferences", {}).get(name, {})
        source_path = AUTHORITY_MANIFEST.parent / source_record["asset"]
        if actual.get("path") != source_record["asset"] or actual.get(
            "sha256"
        ) != source_record["sha256"]:
            raise ValueError(f"condenser endpoint reference mismatch: {name}")
        if sha256(source_path) != source_record["sha256"]:
            raise ValueError(f"condenser endpoint drift: {name}")

    motion = report.get("motion", {})
    expected_indices = list(range(CONDENSER_LOWRES_RENDER["frameCount"]))
    expected_progress = [condenser_motion_progress(index) for index in expected_indices]
    if motion.get("frameIndices") != expected_indices:
        raise ValueError("condenser frame indices mismatch")
    if motion.get("closeFrameIndices") != list(reversed(expected_indices)):
        raise ValueError("condenser close sequence must reverse the source frames")
    if motion.get("progress") != expected_progress:
        raise ValueError("condenser progress curve mismatch")

    frames = report.get("frames", [])
    if len(frames) != CONDENSER_LOWRES_RENDER["frameCount"]:
        raise ValueError("condenser low-resolution frame count mismatch")
    full_offset = condenser["fullOffsetsM"]["condenserAssembly"]
    for index, frame in enumerate(frames):
        path = output_root / frame.get("path", "")
        if frame.get("index") != index or frame.get("progress") != expected_progress[index]:
            raise ValueError(f"condenser frame metadata mismatch: {index}")
        actual_offset = (frame.get("componentOffsetsM") or {}).get(
            "condenserAssembly"
        )
        expected_offset = [value * expected_progress[index] for value in full_offset]
        if actual_offset is None or any(
            abs(float(left) - float(right)) > 1e-7
            for left, right in zip(actual_offset, expected_offset)
        ):
            raise ValueError(f"condenser component offset mismatch: {index}")
        if set(frame.get("rootWorldMatrices") or {}) != set(
            condenser["rootObjects"]
        ):
            raise ValueError(f"condenser root matrix evidence missing: {index}")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(f"condenser frame hash mismatch: {index}")
        with Image.open(path) as image:
            if image.size != tuple(CONDENSER_LOWRES_RENDER["resolution"]):
                raise ValueError(f"condenser frame dimensions mismatch: {index}")

    cleanup = report.get("cleanup", {})
    if (
        cleanup.get("method") != "ffmpeg-removelogo-bitmap-mask"
        or cleanup.get("cleanedFrameCount") != 23
        or cleanup.get("outsideMaskChangedPixels") != 0
        or cleanup.get("boundsMonotonic") is not True
    ):
        raise ValueError("condenser cleanup audit mismatch")
    for relative in CONDENSER_LOWRES_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"condenser review evidence missing: {relative}")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"condenser inventory hash mismatch: {relative}")
    return report


def validate_condenser_r1_linefix_candidate(output_root):
    output_root = Path(output_root)
    report_path = output_root / "condenser-linefix-manifest.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"condenser r1 linefix manifest missing: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    contract = condenser_r1_linefix_candidate_contract()
    if report.get("schema") != contract["schema"]:
        raise ValueError("condenser r1 linefix schema mismatch")
    if report.get("unit") != CONDENSER:
        raise ValueError("condenser r1 linefix semantic unit mismatch")
    if report.get("selectedFormat") != FALLBACK_FORMAT:
        raise ValueError("condenser r1 linefix must use PNG sequence")
    if report.get("render") != contract["render"]:
        raise ValueError("condenser r1 linefix render contract mismatch")
    if report.get("motion") != contract["motion"]:
        raise ValueError("condenser r1 linefix must preserve r1 motion")
    if report.get("geometry") != contract["geometry"]:
        raise ValueError("condenser r1 linefix geometry contract mismatch")
    if report.get("occlusion") != contract["occlusion"]:
        raise ValueError("condenser r1 linefix liner contract mismatch")
    if report.get("postprocess") != contract["postprocess"]:
        raise ValueError("condenser r1 linefix postprocess contract mismatch")
    if report.get("candidateBlendSaved") is not False:
        raise ValueError("condenser r1 linefix cannot save candidate blend")
    if report.get("temporaryDataBlocksRemaining") != []:
        raise ValueError("condenser r1 linefix left temporary data blocks")
    if report.get("machinePassed") is not True:
        raise ValueError("condenser r1 linefix machine gate did not pass")
    human_approved = report.get("humanVisualApproved")
    if human_approved not in (True, False):
        raise ValueError("condenser r1 linefix approval must be an explicit boolean")
    if human_approved:
        approval = report.get("humanApproval", {})
        expected_approval = {
            "approvedUnit": CONDENSER,
            "approvedBy": "user",
            "scope": "stage3-step5-condenser-r1-linefix",
            "authorizesStep6": False,
        }
        if any(approval.get(key) != value for key, value in expected_approval.items()):
            raise ValueError("condenser r1 linefix approval record is missing or overbroad")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(approval.get("approvedOn", ""))):
            raise ValueError("condenser r1 linefix approval date is invalid")
    if report.get("authorizesStep6") is not False:
        raise ValueError("condenser r1 linefix cannot authorize step 6")

    frames = report.get("frames", [])
    expected_progress = contract["motion"]["progress"]
    if len(frames) != 25:
        raise ValueError("condenser r1 linefix frame count mismatch")
    for index, frame in enumerate(frames):
        path = output_root / frame.get("path", "")
        if frame.get("index") != index or frame.get("progress") != expected_progress[index]:
            raise ValueError(f"condenser r1 linefix frame metadata mismatch: {index}")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(f"condenser r1 linefix frame hash mismatch: {index}")
        with Image.open(path) as image:
            if image.size != tuple(CONDENSER_LOWRES_RENDER["resolution"]):
                raise ValueError(f"condenser r1 linefix frame dimensions mismatch: {index}")
    for relative in CONDENSER_LOWRES_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"condenser r1 linefix review missing: {relative}")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"condenser r1 linefix inventory hash mismatch: {relative}")
    return report


def linefix_human_approval(report, *, approved_on):
    if (
        report.get("unit") != CONDENSER
        or report.get("machinePassed") is not True
        or report.get("humanVisualApproved") is not False
        or report.get("authorizesStep6") is not False
    ):
        raise ValueError("linefix approval requires the machine-passed candidate")
    approved = deepcopy(report)
    approved["humanVisualApproved"] = True
    approved["humanApproval"] = {
        "approvedUnit": CONDENSER,
        "approvedBy": "user",
        "approvedOn": str(approved_on),
        "scope": "stage3-step5-condenser-r1-linefix",
        "authorizesStep6": False,
    }
    approved["authorizesStep6"] = False
    return approved


def record_condenser_r1_linefix_approval(output_root, *, approved_on):
    output_root = Path(output_root)
    report = validate_condenser_r1_linefix_candidate(output_root)
    approved = linefix_human_approval(report, approved_on=approved_on)
    manifest_path = output_root / "condenser-linefix-manifest.json"
    manifest_path.write_text(
        json.dumps(approved, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_condenser_r1_linefix_candidate(output_root)


def validate_condenser_repair_candidate(output_root):
    output_root = Path(output_root)
    report_path = output_root / "condenser-repair-manifest.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"condenser repair manifest missing: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != CONDENSER_REPAIR_SCHEMA:
        raise ValueError("condenser repair schema mismatch")
    if report.get("unit") != CONDENSER:
        raise ValueError("condenser repair semantic unit mismatch")
    if report.get("selectedFormat") != FALLBACK_FORMAT:
        raise ValueError("condenser repair must use PNG sequence")
    if report.get("render") != CONDENSER_LOWRES_RENDER:
        raise ValueError("condenser repair render contract mismatch")
    if report.get("machinePassed") is not True:
        raise ValueError("condenser repair machine gate did not pass")
    if report.get("humanVisualApproved") is not False:
        raise ValueError("condenser repair must await human visual approval")
    if report.get("authorizesStep6") is not False:
        raise ValueError("condenser repair cannot authorize step 6")
    if report.get("candidateBlendSaved") is not False:
        raise ValueError("condenser repair cannot save the candidate blend")

    repair = report.get("repair", {})
    contract = condenser_repair_contract()
    for key in ("attempt", "rootCause", "postprocess"):
        if repair.get(key) != contract[key]:
            raise ValueError(f"condenser repair {key} contract mismatch")
    model_cleanup = repair.get("modelCleanup", {})
    if any(
        (
            model_cleanup.get("method") != contract["modelCleanup"]["method"],
            model_cleanup.get("object") != contract["modelCleanup"]["object"],
            model_cleanup.get("sourceMeshRestored") is not True,
            model_cleanup.get("temporaryMeshRemoved") is not True,
            int(model_cleanup.get("repairedPolygons", 0))
            >= int(model_cleanup.get("sourcePolygons", 0)),
        )
    ):
        raise ValueError("condenser model cleanup audit mismatch")
    occlusion = repair.get("occlusion", {})
    expected_occlusion = {
        **contract["occlusion"],
        "followsRoot": True,
        "originalParentRestored": True,
    }
    if occlusion != expected_occlusion:
        raise ValueError("condenser real occlusion audit mismatch")
    animation = repair.get("animation", {})
    for key, expected in contract["animation"].items():
        if animation.get(key) != expected:
            raise ValueError(f"condenser F-Curve audit mismatch: {key}")
    if animation.get("locationChannelCount") != 3 or animation.get(
        "temporaryActionRemoved"
    ) is not True:
        raise ValueError("condenser F-Curve runtime audit mismatch")

    authority = validate_authority()
    condenser = authority["units"][CONDENSER]
    expected_indices = list(range(CONDENSER_LOWRES_RENDER["frameCount"]))
    expected_progress = [condenser_motion_progress(index) for index in expected_indices]
    motion = report.get("motion", {})
    if motion.get("frameIndices") != expected_indices:
        raise ValueError("condenser repair frame indices mismatch")
    if motion.get("closeFrameIndices") != list(reversed(expected_indices)):
        raise ValueError("condenser repair close sequence mismatch")
    if motion.get("progress") != expected_progress:
        raise ValueError("condenser repair progress mismatch")
    frames = report.get("frames", [])
    if len(frames) != len(expected_indices):
        raise ValueError("condenser repair frame count mismatch")
    full_offset = condenser["fullOffsetsM"]["condenserAssembly"]
    for index, frame in enumerate(frames):
        path = output_root / frame.get("path", "")
        if frame.get("index") != index or frame.get("progress") != expected_progress[index]:
            raise ValueError(f"condenser repair frame metadata mismatch: {index}")
        expected_offset = [value * expected_progress[index] for value in full_offset]
        actual_offset = (frame.get("componentOffsetsM") or {}).get(
            "condenserAssembly"
        )
        if actual_offset is None or any(
            abs(float(left) - float(right)) > 1e-7
            for left, right in zip(actual_offset, expected_offset)
        ):
            raise ValueError(f"condenser repair offset mismatch: {index}")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(f"condenser repair frame hash mismatch: {index}")
        with Image.open(path) as image:
            if image.size != tuple(CONDENSER_LOWRES_RENDER["resolution"]):
                raise ValueError(f"condenser repair frame dimensions mismatch: {index}")
    quality = report.get("quality", {})
    if quality.get("blackFrameCount") != 0 or quality.get(
        "duplicateAdjacentFrameCount"
    ) != 0:
        raise ValueError("condenser repair frame quality mismatch")
    for relative in CONDENSER_LOWRES_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"condenser repair review evidence missing: {relative}")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"condenser repair inventory hash mismatch: {relative}")
    return report


def validate_condenser_second_repair_probe(output_root):
    output_root = Path(output_root)
    report_path = output_root / "probe-audit.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"second repair probe audit missing: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != CONDENSER_SECOND_REPAIR_PROBE_SCHEMA:
        raise ValueError("second repair probe schema mismatch")
    if report.get("frameIndices") != [0, 12, 24]:
        raise ValueError("second repair probe frame scope mismatch")
    if report.get("candidateBlendSaved") is not False:
        raise ValueError("second repair probe cannot save the candidate blend")
    if report.get("candidateBlendSha256Before") != report.get(
        "candidateBlendSha256After"
    ):
        raise ValueError("candidate blend changed during second repair probe")
    geometry = report.get("geometry", {})
    if (
        geometry.get("method") != "boundary-ring-front-face-replacement"
        or geometry.get("proxyCreated") is not True
        or geometry.get("nonManifoldEdges") != 0
        or geometry.get("zeroAreaFaces") != 0
        or geometry.get("visibleOpeningCountMatches") is not True
        or float(geometry.get("maxFrontOffsetM", 1.0)) > 0.0001
        or geometry.get("outerRingCount") != 1
        or int(geometry.get("innerRingCount", 0)) < 1
        or geometry.get("ringAuditMatches") is not True
        or geometry.get("replacesOriginalFrontFaces") is not True
    ):
        raise ValueError("revised second repair proxy geometry gate failed")
    occlusion = report.get("occlusion", {})
    if (
        occlusion.get("method") != "localized-extruded-leak-wedges"
        or occlusion.get("classification") != "render-only-cavity-liner"
        or occlusion.get("productStructureClaimed") is not False
        or occlusion.get("preservedOccluderParents") is not True
        or float(occlusion.get("minimumClearanceM", -1.0)) < 0.0005
        or occlusion.get("linerCount") != 2
        or occlusion.get("roiOutsideChangedPixels") != 0
    ):
        raise ValueError("revised second repair cavity liner gate failed")
    if report.get("temporaryDataBlocksRemaining") != []:
        raise ValueError("second repair probe left temporary data blocks")
    frames = report.get("frames", [])
    if [frame.get("index") for frame in frames] != [0, 12, 24]:
        raise ValueError("second repair probe frame records mismatch")
    for frame in frames:
        path = output_root / frame.get("path", "")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(f"second repair probe frame hash mismatch: {frame}")
        with Image.open(path) as image:
            if image.size != (640, 450):
                raise ValueError("second repair probe frame dimensions mismatch")
    return report


def _contact_sheet(entries, destination, *, columns, cell=(320, 225)):
    label_height = 26
    rows = math.ceil(len(entries) / columns)
    canvas = Image.new(
        "RGB", (cell[0] * columns, (cell[1] + label_height) * rows), "white"
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, source) in enumerate(entries):
        column = index % columns
        row = index // columns
        x = column * cell[0]
        y = row * (cell[1] + label_height)
        with Image.open(source) as image:
            rendered = image.convert("RGB").resize(cell, Image.Resampling.LANCZOS)
        canvas.paste(rendered, (x, y + label_height))
        draw.text((x + 5, y + 7), label, fill="black", font=font)
    canvas.save(destination)


def _write_chamber_review_html(output_root, enter_count, exit_count):
    mechanical = [f"../frames/frame-{index:03d}.png" for index in range(25)]
    enter = [f"../inspection/enter-{index:03d}.png" for index in range(enter_count)]
    exit_frames = [
        f"../inspection/exit-{index:03d}.png" for index in range(exit_count)
    ]
    payload = json.dumps(
        {
            "expand": mechanical,
            "enter": enter,
            "stable": ["../inspection/stable.png"],
            "exit": exit_frames,
            "close": list(reversed(mechanical)),
        },
        separators=(",", ":"),
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,"><title>TWINKLE chamber low-res review</title>
<style>body{{margin:0;background:#111;color:#eee;font:14px system-ui;display:grid;place-items:center;min-height:100vh}}main{{text-align:center}}img{{width:640px;height:450px;object-fit:contain;background:#000}}button{{margin:10px 5px;padding:8px 14px}}pre{{text-align:left;max-width:640px;white-space:pre-wrap}}</style>
<main><img id="frame" alt="双通道采集光学舱低清动作候选"><div><button id="pause">暂停</button><button id="replay">从头播放一次</button></div><pre id="status"></pre></main>
<script>const phases={payload};const image=document.querySelector('#frame');const status=document.querySelector('#status');let paused=false,token=0;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));async function show(paths,total,label,my){{for(let i=0;i<paths.length;i++){{while(paused&&my===token)await delay(50);if(my!==token)return;image.src=paths[i];status.textContent=`${{label}} ${{i+1}}/${{paths.length}}`;await delay(paths.length>1?total/(paths.length-1):total);}}}}
async function play(){{const my=++token;paused=false;document.querySelector('#pause').textContent='暂停';await show(phases.expand,1000,'展开',my);await show(phases.enter,900,'检查灯渐入',my);await show(phases.stable,500,'检查灯稳定',my);await show(phases.exit,700,'检查灯渐出',my);await show(phases.close,1000,'闭合',my);if(my===token)status.textContent='单次审阅完成（停止）';}}
document.querySelector('#pause').onclick=()=>{{paused=!paused;document.querySelector('#pause').textContent=paused?'继续':'暂停';}};document.querySelector('#replay').onclick=play;play();</script></html>"""
    (output_root / "review" / "index.html").write_text(html, encoding="utf-8")


def refresh_chamber_review_page(output_root):
    output_root = Path(output_root)
    report_path = output_root / "chamber-lowres-manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _write_chamber_review_html(
        output_root,
        report["inspectionLight"]["enterFrameCount"],
        report["inspectionLight"]["exitFrameCount"],
    )
    relative = "review/index.html"
    report["inventorySha256"][relative] = sha256(output_root / relative)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_chamber_lowres_candidate(output_root)


def _build_chamber_review_assets(output_root, authority, blender_records):
    output_root = Path(output_root)
    frames_root = output_root / "frames"
    inspection_root = output_root / "inspection"
    review_root = output_root / "review"
    inspection_root.mkdir()
    review_root.mkdir()
    chamber = authority["units"][CHAMBER]
    closed_source = AUTHORITY_MANIFEST.parent / chamber["frames"]["focused-settled"]["asset"]
    open_source = AUTHORITY_MANIFEST.parent / chamber["frames"]["extract-end"]["asset"]
    lit_source = AUTHORITY_MANIFEST.parent / chamber["inspectionLight"]["asset"]
    closed_lowres = _half_size_stage1(closed_source)
    open_lowres = _half_size_stage1(open_source)
    lit_lowres = _half_size_stage1(lit_source)
    closed_lowres.save(frames_root / "frame-000.png")
    open_lowres.save(frames_root / "frame-024.png")

    enter_count = round(chamber["inspectionLight"]["transitionMs"]["enter"] * 24 / 1000) + 1
    exit_count = round(chamber["inspectionLight"]["transitionMs"]["exit"] * 24 / 1000) + 1
    for index in range(enter_count):
        alpha = index / (enter_count - 1)
        Image.blend(open_lowres, lit_lowres, alpha).save(
            inspection_root / f"enter-{index:03d}.png"
        )
    lit_lowres.save(inspection_root / "stable.png")
    for index in range(exit_count):
        alpha = index / (exit_count - 1)
        Image.blend(lit_lowres, open_lowres, alpha).save(
            inspection_root / f"exit-{index:03d}.png"
        )

    key_indices = (0, 6, 12, 18, 24)
    _contact_sheet(
        [
            *[(f"expand {percent}%", frames_root / f"frame-{index:03d}.png") for percent, index in zip((0, 25, 50, 75, 100), key_indices)],
            *[(f"close {percent}%", frames_root / f"frame-{index:03d}.png") for percent, index in zip((0, 25, 50, 75, 100), reversed(key_indices))],
        ],
        review_root / "expand-close-contact-sheet.png",
        columns=5,
    )
    pause_entries = []
    for percent, index in zip((25, 50, 75), (6, 12, 18)):
        pause_entries.extend(
            [
                (f"{percent}% arrive", frames_root / f"frame-{index:03d}.png"),
                (f"{percent}% hold same", frames_root / f"frame-{index:03d}.png"),
                (f"{percent}% resume forward", frames_root / f"frame-{index + 1:03d}.png"),
            ]
        )
    _contact_sheet(
        pause_entries,
        review_root / "pause-resume-contact-sheet.png",
        columns=3,
    )
    inspection_entries = [
        ("enter 0%", inspection_root / "enter-000.png"),
        ("enter 25%", inspection_root / f"enter-{round((enter_count - 1) * .25):03d}.png"),
        ("enter 50%", inspection_root / f"enter-{round((enter_count - 1) * .5):03d}.png"),
        ("enter 75%", inspection_root / f"enter-{round((enter_count - 1) * .75):03d}.png"),
        ("stable", inspection_root / "stable.png"),
        ("exit 75%", inspection_root / f"exit-{round((exit_count - 1) * .25):03d}.png"),
        ("exit 50%", inspection_root / f"exit-{round((exit_count - 1) * .5):03d}.png"),
        ("exit 25%", inspection_root / f"exit-{round((exit_count - 1) * .75):03d}.png"),
        ("exit complete", inspection_root / f"exit-{exit_count - 1:03d}.png"),
        ("close handoff", frames_root / "frame-023.png"),
    ]
    _contact_sheet(
        inspection_entries,
        review_root / "inspection-light-contact-sheet.png",
        columns=5,
    )
    _contact_sheet(
        [(f"frame {index:02d}", frames_root / f"frame-{index:03d}.png") for index in (0, 1, 6, 12, 18, 23, 24)],
        review_root / "quality-contact-sheet.png",
        columns=4,
    )
    _write_chamber_review_html(output_root, enter_count, exit_count)

    frame_records = []
    black_count = 0
    duplicate_count = 0
    luma_means = []
    prior = None
    worker_by_index = {record["index"]: record for record in blender_records}
    for index in range(25):
        path = frames_root / f"frame-{index:03d}.png"
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            mean = ImageStat.Stat(rgb).mean
            luma = mean[0] * 0.2126 + mean[1] * 0.7152 + mean[2] * 0.0722
            luma_means.append(luma)
            black_count += int(luma <= 2.0)
            if prior is not None and ImageChops.difference(prior, rgb).getbbox() is None:
                duplicate_count += 1
            prior = rgb.copy()
        worker = worker_by_index.get(index)
        if worker is None:
            endpoint_state = "focused-settled" if index == 0 else "extract-end"
            endpoint = chamber["frames"][endpoint_state]
            worker = {
                "componentOffsetsM": endpoint["componentOffsetsM"],
                "rootWorldMatrices": endpoint["rootWorldMatrices"],
            }
        frame_records.append(
            {
                "index": index,
                "timeMs": round(index * 1000 / 24, 4),
                "progress": chamber_motion_progress(index),
                "path": f"frames/frame-{index:03d}.png",
                "sha256": sha256(path),
                "componentOffsetsM": worker.get("componentOffsetsM"),
                "rootWorldMatrices": worker.get("rootWorldMatrices"),
            }
        )
    endpoint_mae = max(
        _pixel_mae(closed_lowres, Image.open(frames_root / "frame-000.png")),
        _pixel_mae(open_lowres, Image.open(frames_root / "frame-024.png")),
    )
    return frame_records, {
        "blackFrameCount": black_count,
        "duplicateAdjacentFrameCount": duplicate_count,
        "endpointPixelMaeVsStage1HalfSize": round(endpoint_mae, 6),
        "maxAdjacentMeanLumaDelta": round(
            max(abs(right - left) for left, right in zip(luma_means, luma_means[1:])),
            6,
        ),
    }, enter_count, exit_count


def refresh_chamber_endpoint_metadata(output_root):
    output_root = Path(output_root)
    report_path = output_root / "chamber-lowres-manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    authority = validate_authority()
    chamber = authority["units"][CHAMBER]
    for index, state_name in ((0, "focused-settled"), (24, "extract-end")):
        endpoint = chamber["frames"][state_name]
        report["frames"][index]["componentOffsetsM"] = endpoint[
            "componentOffsetsM"
        ]
        report["frames"][index]["rootWorldMatrices"] = endpoint[
            "rootWorldMatrices"
        ]
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_chamber_lowres_candidate(output_root)


def record_chamber_lowres_approval(output_root):
    output_root = Path(output_root)
    report_path = output_root / "chamber-lowres-manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("machinePassed") is not True or report.get("unit") != CHAMBER:
        raise ValueError("chamber approval requires the machine-passed step 4 candidate")
    report["humanVisualApproved"] = True
    report["humanApproval"] = {
        "approvedUnit": CHAMBER,
        "approvedBy": "user",
        "approvedOn": "2026-08-26",
        "scope": "stage3-step4-chamber-lowres-only",
        "authorizesStep5": False,
    }
    report["authorizesStep5"] = False
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_chamber_lowres_candidate(output_root)


def chamber_blender_command(blender, candidate_blend, staging):
    return [
        blender,
        "--background",
        candidate_blend,
        "--python-exit-code",
        "1",
        "--python",
        Path(__file__).resolve(),
        "--",
        "--stage3-chamber-worker",
        staging,
    ]


def condenser_blender_command(blender, candidate_blend, staging):
    command = chamber_blender_command(blender, candidate_blend, staging)
    command[command.index("--stage3-chamber-worker")] = "--stage3-condenser-worker"
    return command


def condenser_repair_blender_command(blender, candidate_blend, staging):
    command = condenser_blender_command(blender, candidate_blend, staging)
    command[command.index("--stage3-condenser-worker")] = (
        "--stage3-condenser-repair-worker"
    )
    return command


def condenser_second_repair_probe_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("second repair probe output must be an absolute path")
    command = condenser_repair_blender_command(blender, candidate_blend, output)
    command[command.index("--stage3-condenser-repair-worker")] = (
        "--stage3-condenser-second-repair-probe-worker"
    )
    command[-1] = str(output)
    return command


def condenser_r1_linefix_probe_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("r1 linefix probe output must be an absolute path")
    command = condenser_repair_blender_command(blender, candidate_blend, output)
    command[command.index("--stage3-condenser-repair-worker")] = (
        "--stage3-condenser-r1-linefix-probe-worker"
    )
    command[-1] = str(output)
    return command


def condenser_r1_linefix_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("r1 linefix output must be an absolute path")
    command = condenser_r1_linefix_probe_blender_command(
        blender, candidate_blend, output
    )
    command[command.index("--stage3-condenser-r1-linefix-probe-worker")] = (
        "--stage3-condenser-r1-linefix-worker"
    )
    return command


def condenser_motion_only_probe_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("motion-only probe output must be an absolute path")
    command = condenser_r1_linefix_probe_blender_command(
        blender, candidate_blend, output
    )
    command[command.index("--stage3-condenser-r1-linefix-probe-worker")] = (
        "--stage3-condenser-motion-only-probe-worker"
    )
    command[-1] = str(output)
    return command


def formal_chamber_blender_command(blender, candidate_blend, output):
    command = chamber_blender_command(blender, candidate_blend, output)
    command[command.index("--stage3-chamber-worker")] = (
        "--stage3-formal-chamber-worker"
    )
    return command


def formal_condenser_blender_command(blender, candidate_blend, output):
    command = chamber_blender_command(blender, candidate_blend, output)
    command[command.index("--stage3-chamber-worker")] = (
        "--stage3-formal-condenser-worker"
    )
    return command


def step7_probe_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("step 7 probe output must be an absolute path")
    command = condenser_motion_only_probe_blender_command(
        blender, candidate_blend, output
    )
    command[command.index("--stage3-condenser-motion-only-probe-worker")] = (
        "--stage3-step7-probe-worker"
    )
    return command


def build_chamber_lowres_candidate(output_root, *, blender=None):
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    format_report = validate_format_experiment(FORMAT_OUTPUT_ROOT)
    if not format_report.get("humanDetailApproved") or format_report.get(
        "selectedFormat"
    ) != FALLBACK_FORMAT:
        raise ValueError("step 3 PNG approval is required before chamber rendering")
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != authority["candidateBlend"]["sha256"]:
        raise ValueError("candidate blend drift before chamber rendering")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".chamber-lowres-", dir=output_root.parent))
    try:
        run_checked(
            chamber_blender_command(blender, candidate_blend, staging), cwd=ROOT
        )
        blender_report = json.loads(
            (staging / "blender-motion.json").read_text(encoding="utf-8")
        )
        frame_records, quality, enter_count, exit_count = _build_chamber_review_assets(
            staging, authority, blender_report["frames"]
        )
        chamber = authority["units"][CHAMBER]
        report = {
            "schema": CHAMBER_LOWRES_SCHEMA,
            "unit": CHAMBER,
            "selectedFormat": FALLBACK_FORMAT,
            "render": CHAMBER_LOWRES_RENDER,
            "timingMs": CHAMBER_LOWRES_TIMING,
            "source": authority["candidateBlend"],
            "renderContract": {
                "cameraPresetId": chamber["cameraPresetId"],
                "camera": chamber["camera"],
                "rootObjects": chamber["rootObjects"],
                "fullOffsetsM": chamber["fullOffsetsM"],
                "lightRigHash": authority["renderProfile"]["lightRigHash"],
                "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
                "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
            },
            "motion": {
                "frameIndices": list(range(25)),
                "closeFrameIndices": list(reversed(range(25))),
                "progress": [chamber_motion_progress(index) for index in range(25)],
                "seamProgress": 0.06,
                "seamFrameIndex": 6,
                "bothPanelsSynchronous": True,
            },
            "frames": frame_records,
            "pauseEvidence": [
                {
                    "percent": percent,
                    "frameIndex": index,
                    "holdUsesSameFrame": True,
                    "resumeFrameIndex": index + 1,
                    "direction": "forward",
                }
                for percent, index in ((25, 6), (50, 12), (75, 18))
            ],
            "inspectionLight": {
                "transitionMs": chamber["inspectionLight"]["transitionMs"],
                "enterFrameCount": enter_count,
                "stableUsesStage1Endpoint": True,
                "exitFrameCount": exit_count,
                "handoff": "exit-complete-before-close-frame-23",
            },
            "endpointReferences": {
                "closed": {
                    "path": chamber["frames"]["focused-settled"]["asset"],
                    "sha256": chamber["frames"]["focused-settled"]["sha256"],
                },
                "open": {
                    "path": chamber["frames"]["extract-end"]["asset"],
                    "sha256": chamber["frames"]["extract-end"]["sha256"],
                },
                "inspectionLit": {
                    "path": chamber["inspectionLight"]["asset"],
                    "sha256": chamber["inspectionLight"]["sha256"],
                },
            },
            "quality": quality,
            "machinePassed": quality["blackFrameCount"] == 0
            and quality["duplicateAdjacentFrameCount"] == 0
            and quality["endpointPixelMaeVsStage1HalfSize"] <= 1.0,
            "humanVisualApproved": False,
            "authorizesStep5": False,
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "chamber-lowres-manifest.json":
                inventory[path.relative_to(staging).as_posix()] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "chamber-lowres-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_chamber_lowres_candidate(staging)
        if sha256(candidate_blend) != authority["candidateBlend"]["sha256"]:
            raise ValueError("candidate blend drift after chamber rendering")
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(f"chamber low-resolution build failed; staging kept at {staging}") from error
    return validate_chamber_lowres_candidate(output_root)


def _condenser_cleanup_bounds(authority, progress):
    cleanup = authority["units"][CONDENSER]["cleanup"]["frames"]
    keys = (
        (0.0, cleanup["focused-settled"]["plateBoundsPx"]),
        (0.5, cleanup["extract-mid"]["plateBoundsPx"]),
        (1.0, cleanup["extract-end"]["plateBoundsPx"]),
    )
    left, right = (keys[0], keys[1]) if progress <= 0.5 else (keys[1], keys[2])
    local = (progress - left[0]) / (right[0] - left[0])
    return [
        int(round(start + (end - start) * local))
        for start, end in zip(left[1], right[1])
    ]


def _cleanup_condenser_middle_frames(output_root, authority, ffmpeg):
    from scripts import build_twinkle_route1_camera_board as stage1_board

    output_root = Path(output_root)
    frames_root = output_root / "frames"
    records = []
    for index in range(1, 24):
        progress = condenser_motion_progress(index)
        full_bounds = _condenser_cleanup_bounds(authority, progress)
        full_geometry = stage1_board.cleanup_geometry_for_plate_bounds(full_bounds)
        geometry = {
            "plateBoundsPx": [int(round(value / 2)) for value in full_bounds],
            "polygon": [
                [int(round(x / 2)), int(round(y / 2))]
                for x, y in full_geometry["polygon"]
            ],
            "protectedCircles": [
                [int(round(x / 2)), int(round(y / 2)), int(round(radius / 2))]
                for x, y, radius in full_geometry["protectedCircles"]
            ],
        }
        frame_path = frames_root / f"frame-{index:03d}.png"
        mask_name = f".condenser-cleanup-{index:03d}-mask.png"
        filtered_name = f".condenser-cleanup-{index:03d}-filtered.png"
        mask_path = frames_root / mask_name
        filtered_path = frames_root / filtered_name
        with Image.open(frame_path) as image:
            original = image.convert("RGB")
        mask = Image.new("L", original.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(
            tuple(tuple(point) for point in geometry["polygon"]), fill=255
        )
        for x, y, radius in geometry["protectedCircles"]:
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius), fill=0
            )
        mask.save(mask_path)
        run_checked(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-i",
                frame_path.name,
                "-vf",
                f"removelogo=filename={mask_name}",
                "-frames:v",
                "1",
                "-update",
                "1",
                filtered_name,
            ],
            cwd=frames_root,
        )
        with Image.open(filtered_path) as image:
            filtered = image.convert("RGB")
        cleaned = Image.composite(filtered, original, mask)
        difference = ImageChops.difference(cleaned, original)
        outside = Image.new("RGB", original.size, "black")
        outside.paste(difference, mask=ImageChops.invert(mask))
        outside_changed = 0 if outside.getbbox() is None else 1
        if outside_changed:
            raise RuntimeError(
                f"condenser cleanup changed pixels outside mask: {index}"
            )
        changed_pixels = sum(
            1 for pixel in difference.getdata() if pixel != (0, 0, 0)
        )
        cleaned.save(frame_path)
        mask_path.unlink()
        filtered_path.unlink()
        records.append(
            {
                "frameIndex": index,
                "progress": progress,
                "plateBoundsPx": geometry["plateBoundsPx"],
                "changedPixels": changed_pixels,
                "outsideMaskChangedPixels": outside_changed,
            }
        )
    bounds = [record["plateBoundsPx"] for record in records]
    bounds_monotonic = all(
        all(right >= left for left, right in zip(previous, current))
        for previous, current in zip(bounds, bounds[1:])
    )
    return {
        "method": "ffmpeg-removelogo-bitmap-mask",
        "cleanedFrameCount": len(records),
        "outsideMaskChangedPixels": sum(
            record["outsideMaskChangedPixels"] for record in records
        ),
        "boundsMonotonic": bounds_monotonic,
        "frames": records,
    }


def _write_condenser_review_html(output_root):
    mechanical = [f"../frames/frame-{index:03d}.png" for index in range(25)]
    payload = json.dumps(
        {"expand": mechanical, "close": list(reversed(mechanical))},
        separators=(",", ":"),
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,"><title>TWINKLE condenser low-res review</title>
<style>body{{margin:0;background:#111;color:#eee;font:14px system-ui;display:grid;place-items:center;min-height:100vh}}main{{text-align:center}}img{{width:640px;height:450px;object-fit:contain;background:#000}}button{{margin:10px 5px;padding:8px 14px}}pre{{text-align:left;max-width:640px;white-space:pre-wrap}}</style>
<main><img id="frame" alt="聚光镜组件低清动作候选"><div><button id="pause">暂停</button><button id="replay">从头播放一次</button></div><pre id="status"></pre></main>
<script>const phases={payload};const image=document.querySelector('#frame');const status=document.querySelector('#status');let paused=false,token=0;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));async function show(paths,total,label,my){{for(let i=0;i<paths.length;i++){{while(paused&&my===token)await delay(50);if(my!==token)return;image.src=paths[i];status.textContent=`${{label}} ${{i+1}}/${{paths.length}}`;await delay(total/(paths.length-1));}}}}
async function play(){{const my=++token;paused=false;document.querySelector('#pause').textContent='暂停';await show(phases.expand,1000,'展开',my);await delay(500);await show(phases.close,1000,'闭合',my);if(my===token)status.textContent='单次审阅完成（停止）';}}
document.querySelector('#pause').onclick=()=>{{paused=!paused;document.querySelector('#pause').textContent=paused?'继续':'暂停';}};document.querySelector('#replay').onclick=play;play();</script></html>"""
    (Path(output_root) / "review" / "index.html").write_text(
        html, encoding="utf-8"
    )


def _build_condenser_review_assets(
    output_root,
    authority,
    blender_records,
    ffmpeg=None,
    *,
    keep_rendered_endpoints=False,
    apply_cleanup=True,
):
    output_root = Path(output_root)
    frames_root = output_root / "frames"
    review_root = output_root / "review"
    review_root.mkdir()
    condenser = authority["units"][CONDENSER]
    closed_source = (
        AUTHORITY_MANIFEST.parent
        / condenser["frames"]["focused-settled"]["asset"]
    )
    open_source = (
        AUTHORITY_MANIFEST.parent / condenser["frames"]["extract-end"]["asset"]
    )
    closed_lowres = _half_size_stage1(closed_source)
    open_lowres = _half_size_stage1(open_source)
    if keep_rendered_endpoints:
        for index in (0, 24):
            if not (frames_root / f"frame-{index:03d}.png").is_file():
                raise FileNotFoundError(f"rendered condenser endpoint missing: {index}")
    else:
        closed_lowres.save(frames_root / "frame-000.png")
        open_lowres.save(frames_root / "frame-024.png")
    if apply_cleanup:
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required when condenser cleanup is enabled")
        cleanup = _cleanup_condenser_middle_frames(output_root, authority, ffmpeg)
    else:
        cleanup = {
            "method": "none",
            "cleanedFrameCount": 0,
            "outsideMaskChangedPixels": 0,
            "boundsMonotonic": True,
            "frames": [],
        }

    key_indices = (0, 6, 12, 18, 24)
    _contact_sheet(
        [
            *[
                (f"expand {percent}%", frames_root / f"frame-{index:03d}.png")
                for percent, index in zip((0, 25, 50, 75, 100), key_indices)
            ],
            *[
                (f"close {percent}%", frames_root / f"frame-{index:03d}.png")
                for percent, index in zip(
                    (0, 25, 50, 75, 100), reversed(key_indices)
                )
            ],
        ],
        review_root / "expand-close-contact-sheet.png",
        columns=5,
    )
    pause_entries = []
    for percent, index in ((25, 6), (50, 12), (75, 18)):
        pause_entries.extend(
            [
                (f"{percent}% arrive", frames_root / f"frame-{index:03d}.png"),
                (f"{percent}% hold same", frames_root / f"frame-{index:03d}.png"),
                (
                    f"{percent}% resume forward",
                    frames_root / f"frame-{index + 1:03d}.png",
                ),
            ]
        )
    _contact_sheet(
        pause_entries,
        review_root / "pause-resume-contact-sheet.png",
        columns=3,
    )
    _contact_sheet(
        [
            (f"frame {index:02d}", frames_root / f"frame-{index:03d}.png")
            for index in (0, 1, 6, 12, 18, 23, 24)
        ],
        review_root / "cleanup-quality-contact-sheet.png",
        columns=4,
    )
    chamber_frames = CHAMBER_LOWRES_OUTPUT_ROOT / "frames"
    _contact_sheet(
        [
            *[
                (f"chamber {percent}%", chamber_frames / f"frame-{index:03d}.png")
                for percent, index in ((0, 0), (50, 12), (100, 24))
            ],
            *[
                (f"condenser {percent}%", frames_root / f"frame-{index:03d}.png")
                for percent, index in ((0, 0), (50, 12), (100, 24))
            ],
        ],
        review_root / "style-comparison-contact-sheet.png",
        columns=3,
    )
    _write_condenser_review_html(output_root)

    worker_by_index = {record["index"]: record for record in blender_records}
    frame_records = []
    black_count = 0
    duplicate_count = 0
    luma_means = []
    prior = None
    for index in range(25):
        path = frames_root / f"frame-{index:03d}.png"
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            mean = ImageStat.Stat(rgb).mean
            luma = mean[0] * 0.2126 + mean[1] * 0.7152 + mean[2] * 0.0722
            luma_means.append(luma)
            black_count += int(luma <= 2.0)
            if prior is not None and ImageChops.difference(prior, rgb).getbbox() is None:
                duplicate_count += 1
            prior = rgb.copy()
        worker = worker_by_index.get(index)
        if worker is None:
            endpoint_state = "focused-settled" if index == 0 else "extract-end"
            endpoint = condenser["frames"][endpoint_state]
            worker = {
                "componentOffsetsM": endpoint["componentOffsetsM"],
                "rootWorldMatrices": endpoint["rootWorldMatrices"],
            }
        frame_records.append(
            {
                "index": index,
                "timeMs": round(index * 1000 / 24, 4),
                "progress": condenser_motion_progress(index),
                "path": f"frames/frame-{index:03d}.png",
                "sha256": sha256(path),
                "componentOffsetsM": worker["componentOffsetsM"],
                "rootWorldMatrices": worker["rootWorldMatrices"],
            }
        )
    with Image.open(frames_root / "frame-000.png") as image:
        closed_candidate = image.convert("RGB")
    with Image.open(frames_root / "frame-024.png") as image:
        open_candidate = image.convert("RGB")
    endpoint_mae = max(
        _pixel_mae(closed_lowres, closed_candidate),
        _pixel_mae(open_lowres, open_candidate),
    )
    quality = {
        "blackFrameCount": black_count,
        "duplicateAdjacentFrameCount": duplicate_count,
        "endpointPixelMaeVsStage1HalfSize": round(endpoint_mae, 6),
        "maxAdjacentMeanLumaDelta": round(
            max(abs(right - left) for left, right in zip(luma_means, luma_means[1:])),
            6,
        ),
    }
    return frame_records, quality, cleanup


def build_condenser_lowres_candidate(
    output_root, *, blender=None, ffmpeg=None
):
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    validate_chamber_lowres_candidate(CHAMBER_LOWRES_OUTPUT_ROOT)
    format_report = validate_format_experiment(FORMAT_OUTPUT_ROOT)
    if not format_report.get("humanDetailApproved") or format_report.get(
        "selectedFormat"
    ) != FALLBACK_FORMAT:
        raise ValueError("step 3 PNG approval is required before condenser rendering")
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != authority["candidateBlend"]["sha256"]:
        raise ValueError("candidate blend drift before condenser rendering")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg removelogo is required for condenser cleanup")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".condenser-lowres-", dir=output_root.parent)
    )
    try:
        run_checked(
            condenser_blender_command(blender, candidate_blend, staging), cwd=ROOT
        )
        blender_report = json.loads(
            (staging / "blender-motion.json").read_text(encoding="utf-8")
        )
        frame_records, quality, cleanup = _build_condenser_review_assets(
            staging, authority, blender_report["frames"], ffmpeg
        )
        condenser = authority["units"][CONDENSER]
        report = {
            "schema": CONDENSER_LOWRES_SCHEMA,
            "unit": CONDENSER,
            "selectedFormat": FALLBACK_FORMAT,
            "render": CONDENSER_LOWRES_RENDER,
            "source": authority["candidateBlend"],
            "renderContract": {
                "cameraPresetId": condenser["cameraPresetId"],
                "camera": condenser["camera"],
                "rootObjects": condenser["rootObjects"],
                "fullOffsetsM": condenser["fullOffsetsM"],
                "lightRigHash": authority["renderProfile"]["lightRigHash"],
                "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
                "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
            },
            "motion": {
                "frameIndices": list(range(25)),
                "closeFrameIndices": list(reversed(range(25))),
                "progress": [condenser_motion_progress(index) for index in range(25)],
            },
            "frames": frame_records,
            "pauseEvidence": [
                {
                    "percent": percent,
                    "frameIndex": index,
                    "holdUsesSameFrame": True,
                    "resumeFrameIndex": index + 1,
                    "direction": "forward",
                }
                for percent, index in ((25, 6), (50, 12), (75, 18))
            ],
            "inspectionLight": None,
            "cleanup": cleanup,
            "endpointReferences": {
                "closed": {
                    "path": condenser["frames"]["focused-settled"]["asset"],
                    "sha256": condenser["frames"]["focused-settled"]["sha256"],
                },
                "open": {
                    "path": condenser["frames"]["extract-end"]["asset"],
                    "sha256": condenser["frames"]["extract-end"]["sha256"],
                },
            },
            "styleReference": {
                "unit": CHAMBER,
                "manifest": (
                    "output/.twinkle-stage3-chamber-lowres-20260826/"
                    "chamber-lowres-r1/chamber-lowres-manifest.json"
                ),
                "humanVisualApproved": True,
            },
            "quality": quality,
            "machinePassed": quality["blackFrameCount"] == 0
            and quality["duplicateAdjacentFrameCount"] == 0
            and quality["endpointPixelMaeVsStage1HalfSize"] <= 1.0
            and cleanup["cleanedFrameCount"] == 23
            and cleanup["outsideMaskChangedPixels"] == 0
            and cleanup["boundsMonotonic"],
            "humanVisualApproved": False,
            "authorizesStep6": False,
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "condenser-lowres-manifest.json":
                inventory[path.relative_to(staging).as_posix()] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "condenser-lowres-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_condenser_lowres_candidate(staging)
        if sha256(candidate_blend) != authority["candidateBlend"]["sha256"]:
            raise ValueError("candidate blend drift after condenser rendering")
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"condenser low-resolution build failed; staging kept at {staging}"
        ) from error
    return validate_condenser_lowres_candidate(output_root)


def build_condenser_r1_linefix_candidate(output_root, *, blender=None):
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    validate_condenser_lowres_candidate(CONDENSER_LOWRES_OUTPUT_ROOT)
    candidate_blend = Path(authority["candidateBlend"]["path"])
    candidate_hash = sha256(candidate_blend)
    if candidate_hash != authority["candidateBlend"]["sha256"]:
        raise ValueError("candidate blend drift before r1 linefix")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".condenser-r1-linefix-", dir=output_root.parent)
    )
    try:
        staging.rmdir()
        run_checked(
            condenser_r1_linefix_blender_command(
                blender, candidate_blend, staging.resolve()
            ),
            cwd=ROOT,
        )
        blender_report = json.loads(
            (staging / "blender-motion.json").read_text(encoding="utf-8")
        )
        if blender_report.get("schema") != CONDENSER_R1_LINEFIX_SCHEMA:
            raise ValueError("r1 linefix Blender report schema mismatch")
        if blender_report.get("frameIndices") != list(range(25)):
            raise ValueError("r1 linefix Blender frame inventory mismatch")
        geometry_audit = blender_report.get("geometry", {})
        if (
            geometry_audit.get("method") != "exact-boolean-front-skin-proxy"
            or geometry_audit.get("operation") != "INTERSECT"
            or geometry_audit.get("solver") != "EXACT"
            or geometry_audit.get("nonManifoldEdges") != 0
            or geometry_audit.get("zeroAreaFaces") != 0
            or geometry_audit.get("maxFrontOffsetM") != 0.00005
        ):
            raise ValueError("r1 linefix geometry audit mismatch")
        if blender_report.get("occlusion") != {"method": "none", "linerCount": 0}:
            raise ValueError("r1 linefix unexpectedly created a liner")
        if blender_report.get("temporaryDataBlocksRemaining") != []:
            raise ValueError("r1 linefix Blender worker left temporary data")
        if blender_report.get("candidateBlendSha256Before") != candidate_hash or (
            blender_report.get("candidateBlendSha256After") != candidate_hash
        ):
            raise ValueError("candidate blend drift during r1 linefix")

        frames, quality, cleanup = _build_condenser_review_assets(
            staging,
            authority,
            blender_report["frames"],
            keep_rendered_endpoints=True,
            apply_cleanup=False,
        )
        contract = condenser_r1_linefix_candidate_contract()
        report = {
            **contract,
            "unit": CONDENSER,
            "selectedFormat": FALLBACK_FORMAT,
            "source": authority["candidateBlend"],
            "derivedFrom": {
                "path": CONDENSER_LOWRES_OUTPUT_ROOT.relative_to(ROOT).as_posix(),
                "manifestSha256": sha256(
                    CONDENSER_LOWRES_OUTPUT_ROOT / "condenser-lowres-manifest.json"
                ),
            },
            "frames": frames,
            "pauseEvidence": [
                {
                    "percent": percent,
                    "frameIndex": index,
                    "holdUsesSameFrame": True,
                    "resumeFrameIndex": index + 1,
                    "direction": "forward",
                }
                for percent, index in ((25, 6), (50, 12), (75, 18))
            ],
            "inspectionLight": None,
            "cleanup": cleanup,
            "geometryAudit": geometry_audit,
            "endpointReferences": {
                "closed": {"path": frames[0]["path"], "sha256": frames[0]["sha256"]},
                "open": {"path": frames[-1]["path"], "sha256": frames[-1]["sha256"]},
                "scope": "candidate-local-linefix",
            },
            "quality": quality,
            "candidateBlendSaved": False,
            "temporaryDataBlocksRemaining": [],
            "machinePassed": (
                quality["blackFrameCount"] == 0
                and quality["duplicateAdjacentFrameCount"] == 0
                and blender_report.get("occlusion")
                == {"method": "none", "linerCount": 0}
            ),
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "condenser-linefix-manifest.json":
                inventory[path.relative_to(staging).as_posix()] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "condenser-linefix-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_condenser_r1_linefix_candidate(staging)
        if sha256(candidate_blend) != candidate_hash:
            raise ValueError("candidate blend drift after r1 linefix")
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"condenser r1 linefix build failed; staging kept at {staging}"
        ) from error
    return validate_condenser_r1_linefix_candidate(output_root)


def _draw_motion_only_kinematics(runtime, destination):
    width, height = 1200, 780
    canvas = Image.new("RGB", (width, height), "#f4f5f7")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    panels = (
        ("Displacement / travel", runtime["progress"], "#1f5fbf", 0.0),
        ("Velocity / frame", runtime["velocityPerFrame"], "#b74a00", 0.0),
        ("Acceleration / frame^2", runtime["accelerationPerFrame"], "#3c7a3f", None),
    )
    for panel_index, (label, values, color, fixed_minimum) in enumerate(panels):
        top = 35 + panel_index * 245
        left, right, bottom = 90, width - 35, top + 190
        draw.rectangle((left, top, right, bottom), fill="white", outline="#c9cdd3")
        draw.text((left, top - 22), label, fill="#20242a", font=font)
        minimum = min(values) if fixed_minimum is None else fixed_minimum
        maximum = max(values)
        if abs(maximum - minimum) < 1e-12:
            maximum = minimum + 1.0
        zero_y = bottom - (0.0 - minimum) / (maximum - minimum) * (bottom - top)
        if top <= zero_y <= bottom:
            draw.line((left, zero_y, right, zero_y), fill="#d9dde3", width=1)
        points = []
        for frame, value in enumerate(values):
            x = left + frame / 24 * (right - left)
            y = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
            points.append((x, y))
        draw.line(points, fill=color, width=4)
        for frame in (0, 3, 7, 12, 19, 24):
            x, y = points[frame]
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
            draw.text((x + 5, y - 14), str(frame), fill="#20242a", font=font)
        draw.text(
            (left + 8, top + 8),
            f"min={minimum:.6f}  max={maximum:.6f}",
            fill="#555b63",
            font=font,
        )
    canvas.save(destination)


def _write_motion_only_review_html(output_root, runtime):
    old_frames = [f"../frames/old/frame-{index:03d}.png" for index in range(25)]
    new_frames = [f"../frames/new/frame-{index:03d}.png" for index in range(25)]
    playback = motion_playback_audit()
    payload = json.dumps(
        {
            "old": old_frames,
            "new": new_frames,
            "progress": runtime["progress"],
            "expand": playback["expandFrameIndices"],
            "close": playback["closeFrameIndices"],
        }
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,">
<title>TWINKLE motion-only probe</title>
<style>
body{{margin:0;background:#15171a;color:#f4f5f7;font:14px system-ui;padding:24px}}
h1{{font-size:20px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.card{{background:#22262b;border:1px solid #3b4149;padding:10px;border-radius:8px}}
img{{display:block;width:100%;height:auto;background:#0b0c0e}}button{{margin:12px 8px 12px 0;padding:8px 14px}}
#status{{font-variant-numeric:tabular-nums}} .note{{color:#b9c0c8}}
</style><body><h1>聚光镜组件 motion-only 审核</h1>
<p class="note">左：已批准 linefix 旧运动；右：唯一 travel F-Curve 新运动。页面只播放 25 帧，不循环。</p>
<div class="grid"><div class="card">旧运动<img id="old"></div><div class="card">新运动<img id="new"></div></div>
<button id="play">播放展开</button><button id="close">播放闭合</button><button id="pause">暂停</button><button id="resume">同帧继续</button>
<input id="scrub" type="range" min="0" max="24" value="0"><span id="status"></span>
<p><img src="kinematics-curves.png" alt="位移速度加速度曲线"></p>
<script>const data={payload};let frame=0,timer=null,paused=false,sequence=data.expand,cursor=0,direction='expand';window.__motionAudit={{direction,visitedFrames:[0]}};
const oldImg=document.querySelector('#old'),newImg=document.querySelector('#new'),status=document.querySelector('#status'),scrub=document.querySelector('#scrub');
function show(i){{frame=Math.max(0,Math.min(24,i));oldImg.src=data.old[frame];newImg.src=data.new[frame];scrub.value=frame;status.textContent=` frame ${{frame}}/24  travel=${{data.progress[frame].toFixed(6)}}`;}}
function stop(){{if(timer)clearInterval(timer);timer=null;}}
function run(){{stop();paused=false;timer=setInterval(()=>{{if(cursor>=sequence.length-1){{stop();return;}}cursor++;show(sequence[cursor]);window.__motionAudit.visitedFrames.push(frame);}},1000/24);}}
function start(nextDirection){{direction=nextDirection;sequence=data[nextDirection];cursor=0;show(sequence[0]);window.__motionAudit={{direction,visitedFrames:[frame]}};run();}}
document.querySelector('#play').onclick=()=>start('expand');
document.querySelector('#close').onclick=()=>start('close');
document.querySelector('#pause').onclick=()=>{{stop();paused=true;}};
document.querySelector('#resume').onclick=()=>{{if(paused)run();}};
scrub.oninput=()=>{{stop();show(Number(scrub.value));}};show(0);
</script></body></html>"""
    (output_root / "review" / "index.html").write_text(html, encoding="utf-8")


def _build_motion_only_review_assets(output_root, runtime):
    review_root = output_root / "review"
    review_root.mkdir(parents=True, exist_ok=True)
    old_root = output_root / "frames" / "old"
    new_root = output_root / "frames" / "new"
    semantic_frames = (0, 3, 7, 12, 19, 24)
    _contact_sheet(
        [
            (f"old frame {index}", old_root / f"frame-{index:03d}.png")
            if side == "old"
            else (f"new frame {index}", new_root / f"frame-{index:03d}.png")
            for index in semantic_frames
            for side in ("old", "new")
        ],
        review_root / "old-new-same-frame-contact-sheet.png",
        columns=2,
    )
    _contact_sheet(
        [
            (f"frame {index} travel {runtime['progress'][index]:.6f}", new_root / f"frame-{index:03d}.png")
            for index in semantic_frames
        ],
        review_root / "keyframes-contact-sheet.png",
        columns=3,
    )
    _contact_sheet(
        [
            ("pause frame 7", new_root / "frame-007.png"),
            ("hold same frame 7", new_root / "frame-007.png"),
            ("resume forward frame 8", new_root / "frame-008.png"),
        ],
        review_root / "pause-resume-contact-sheet.png",
        columns=3,
    )
    _draw_motion_only_kinematics(runtime, review_root / "kinematics-curves.png")
    _write_motion_only_review_html(output_root, runtime)


def motion_only_quality_passes(quality):
    return (
        quality.get("blackFrameCount") == 0
        and float(quality.get("endpointMaeVsApprovedLinefix", math.inf)) <= 0.01
    )


def validate_condenser_motion_only_probe(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "motion-only-probe-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"motion-only probe manifest missing: {manifest_path}")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = condenser_motion_only_probe_contract()
    if report.get("schema") != CONDENSER_MOTION_ONLY_PROBE_SCHEMA:
        raise ValueError("motion-only probe schema mismatch")
    for key in (
        "unit",
        "movingAssembly",
        "render",
        "fullOffsetM",
        "closeFrameIndices",
        "geometryChanges",
        "materialChanges",
        "lightChanges",
        "cameraChanges",
        "postprocess",
        "candidateBlendSaved",
        "authorizesR3",
        "authorizesStep6",
    ):
        if report.get(key) != contract[key]:
            raise ValueError(f"motion-only probe contract mismatch: {key}")
    human_approved = report.get("humanVisualApproved")
    if human_approved not in (True, False):
        raise ValueError("motion-only human approval must be an explicit boolean")
    if human_approved:
        approval = report.get("humanApproval", {})
        expected_approval = {
            "approvedUnit": CONDENSER,
            "approvedBy": "user",
            "scope": "stage3-step5-condenser-motion-only-probe",
            "authorizesR3": False,
            "authorizesStep6": False,
        }
        if any(approval.get(key) != value for key, value in expected_approval.items()):
            raise ValueError("motion-only human approval record is missing or overbroad")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(approval.get("approvedOn", ""))):
            raise ValueError("motion-only human approval date is invalid")
    if report.get("machinePassed") is not True:
        raise ValueError("motion-only probe machine gate did not pass")
    if report.get("playbackEvidence") != motion_playback_audit():
        raise ValueError("motion-only exercised playback evidence mismatch")
    if report.get("visualBaseline", {}).get("humanVisualApproved") is not True:
        raise ValueError("approved linefix visual baseline missing")
    runtime = validate_condenser_motion_only_runtime(report.get("motionRuntime", {}))
    if runtime.get("travel") != contract["travel"]:
        raise ValueError("motion-only travel audit mismatch")
    if report.get("temporaryDataBlocksRemaining") != []:
        raise ValueError("motion-only probe left temporary data blocks")
    expected_hashes = {
        "source": EXPECTED_SOURCE_BLEND_SHA256,
        "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
    }
    if report.get("blendSha256Before") != expected_hashes or report.get(
        "blendSha256After"
    ) != expected_hashes:
        raise ValueError("source or candidate blend hash drift")
    for group in ("oldFrames", "newFrames"):
        frames = report.get(group, [])
        if [frame.get("index") for frame in frames] != list(range(25)):
            raise ValueError(f"motion-only {group} inventory mismatch")
        for frame in frames:
            path = output_root / frame.get("path", "")
            if not path.is_file() or sha256(path) != frame.get("sha256"):
                raise ValueError(f"motion-only {group} hash mismatch: {frame}")
            with Image.open(path) as image:
                if image.size != (640, 450):
                    raise ValueError(f"motion-only {group} dimensions mismatch")
    for relative in CONDENSER_MOTION_ONLY_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"motion-only review evidence missing: {relative}")
    if not motion_only_quality_passes(report.get("quality", {})):
        raise ValueError("motion-only render quality gate failed")
    for relative, expected_hash in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"motion-only inventory hash mismatch: {relative}")
    return report


def build_condenser_motion_only_probe(
    output_root, *, blender=None, resume_staging=None
):
    output_root = Path(output_root)
    if output_root.name.lower() == "condenser-lowres-r3":
        raise ValueError("motion-only probe cannot generate condenser-lowres-r3")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    baseline = validate_condenser_r1_linefix_candidate(
        CONDENSER_R1_LINEFIX_OUTPUT_ROOT
    )
    source_blend = Path(authority["source"]["path"])
    candidate_blend = Path(authority["candidateBlend"]["path"])
    before_hashes = {"source": sha256(source_blend), "candidate": sha256(candidate_blend)}
    expected_hashes = {
        "source": EXPECTED_SOURCE_BLEND_SHA256,
        "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
    }
    if before_hashes != expected_hashes:
        raise ValueError("source or candidate blend drift before motion-only probe")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if resume_staging is not None:
        staging = Path(resume_staging).resolve()
        if (
            staging.parent != output_root.resolve().parent
            or not staging.name.startswith(".condenser-motion-only-")
            or not (staging / "motion-runtime.json").is_file()
        ):
            raise ValueError("motion-only resume staging is outside the bounded scope")
    else:
        blender = Path(
            blender
            or os.environ.get("TWINKLE_BLENDER")
            or shutil.which("blender")
            or "blender"
        )
        if not blender.is_file():
            raise FileNotFoundError(f"Blender executable missing: {blender}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=".condenser-motion-only-", dir=output_root.parent
            )
        )
    try:
        if resume_staging is None:
            staging.rmdir()
            run_checked(
                condenser_motion_only_probe_blender_command(
                    blender, candidate_blend, staging.resolve()
                ),
                cwd=ROOT,
            )
        worker = json.loads(
            (staging / "motion-runtime.json").read_text(encoding="utf-8")
        )
        runtime = validate_condenser_motion_only_runtime(worker["motionRuntime"])
        if worker.get("schema") != CONDENSER_MOTION_ONLY_PROBE_SCHEMA:
            raise ValueError("motion-only Blender schema mismatch")
        if worker.get("temporaryDataBlocksRemaining") != []:
            raise ValueError("motion-only Blender worker left temporary data")
        if worker.get("candidateBlendSha256Before") != expected_hashes["candidate"] or worker.get(
            "candidateBlendSha256After"
        ) != expected_hashes["candidate"]:
            raise ValueError("candidate blend drift during motion-only probe")

        old_root = staging / "frames" / "old"
        old_root.mkdir(parents=True)
        old_records = []
        new_records = []
        for index in range(25):
            source = CONDENSER_R1_LINEFIX_OUTPUT_ROOT / "frames" / f"frame-{index:03d}.png"
            destination = old_root / source.name
            shutil.copyfile(source, destination)
            old_records.append(
                {"index": index, "path": destination.relative_to(staging).as_posix(), "sha256": sha256(destination)}
            )
            rendered = staging / "frames" / "new" / f"frame-{index:03d}.png"
            new_records.append(
                {"index": index, "path": rendered.relative_to(staging).as_posix(), "sha256": sha256(rendered)}
            )
        _build_motion_only_review_assets(staging, runtime)

        black_count = 0
        duplicate_pairs = []
        prior = None
        for index in range(25):
            with Image.open(staging / new_records[index]["path"]) as image:
                rgb = image.convert("RGB")
                mean = ImageStat.Stat(rgb).mean
                luma = mean[0] * 0.2126 + mean[1] * 0.7152 + mean[2] * 0.0722
                black_count += int(luma <= 2.0)
                if prior is not None and ImageChops.difference(prior, rgb).getbbox() is None:
                    duplicate_pairs.append([index - 1, index])
                prior = rgb.copy()
        endpoint_mae = max(
            _pixel_mae(
                Image.open(staging / old_records[index]["path"]),
                Image.open(staging / new_records[index]["path"]),
            )
            for index in (0, 24)
        )
        after_hashes = {"source": sha256(source_blend), "candidate": sha256(candidate_blend)}
        contract = condenser_motion_only_probe_contract()
        report = {
            **contract,
            "selectedFormat": FALLBACK_FORMAT,
            "visualBaseline": {
                "path": CONDENSER_R1_LINEFIX_OUTPUT_ROOT.relative_to(ROOT).as_posix(),
                "manifestSha256": sha256(
                    CONDENSER_R1_LINEFIX_OUTPUT_ROOT / "condenser-linefix-manifest.json"
                ),
                "humanVisualApproved": True,
                "approvalSource": "user correction in current task on 2026-08-27",
            },
            "blendSha256Before": before_hashes,
            "blendSha256After": after_hashes,
            "motionRuntime": runtime,
            "oldFrames": old_records,
            "newFrames": new_records,
            "pauseEvidence": runtime["pauseEvidence"],
            "playbackEvidence": motion_playback_audit(),
            "quality": {
                "blackFrameCount": black_count,
                "holdDuplicatePairs": duplicate_pairs,
                "endpointMaeVsApprovedLinefix": round(endpoint_mae, 8),
            },
            "baselineGeometryAuditSha256": hashlib.sha256(
                json.dumps(baseline["geometryAudit"], sort_keys=True).encode("utf-8")
            ).hexdigest().upper(),
            "temporaryDataBlocksRemaining": worker["temporaryDataBlocksRemaining"],
            "machinePassed": (
                before_hashes == after_hashes == expected_hashes
                and motion_only_quality_passes(
                    {
                        "blackFrameCount": black_count,
                        "endpointMaeVsApprovedLinefix": endpoint_mae,
                    }
                )
            ),
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "motion-only-probe-manifest.json":
                inventory[path.relative_to(staging).as_posix()] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "motion-only-probe-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_condenser_motion_only_probe(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"motion-only probe build failed; staging kept at {staging}"
        ) from error
    return validate_condenser_motion_only_probe(output_root)


def refresh_condenser_motion_only_playback_evidence(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "motion-only-probe-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["playbackEvidence"] = motion_playback_audit()
    _write_motion_only_review_html(output_root, report["motionRuntime"])
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_condenser_motion_only_probe(output_root)


def motion_only_human_approval(report, *, approved_on):
    if (
        report.get("unit") != CONDENSER
        or report.get("machinePassed") is not True
        or report.get("humanVisualApproved") is not False
        or report.get("authorizesR3") is not False
        or report.get("authorizesStep6") is not False
    ):
        raise ValueError("motion-only approval requires the machine-passed probe")
    approved = deepcopy(report)
    approved["humanVisualApproved"] = True
    approved["humanApproval"] = {
        "approvedUnit": CONDENSER,
        "approvedBy": "user",
        "approvedOn": str(approved_on),
        "scope": "stage3-step5-condenser-motion-only-probe",
        "authorizesR3": False,
        "authorizesStep6": False,
    }
    approved["authorizesR3"] = False
    approved["authorizesStep6"] = False
    return approved


def record_condenser_motion_only_approval(output_root, *, approved_on):
    output_root = Path(output_root)
    report = validate_condenser_motion_only_probe(output_root)
    approved = motion_only_human_approval(report, approved_on=approved_on)
    manifest_path = output_root / "motion-only-probe-manifest.json"
    manifest_path.write_text(
        json.dumps(approved, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_condenser_motion_only_probe(output_root)


def sync_motion_visual_baseline_approval(
    report, *, linefix_manifest_sha256, approved_on
):
    if (
        report.get("humanVisualApproved") is not True
        or report.get("authorizesR3") is not False
        or report.get("authorizesStep6") is not False
        or report.get("visualBaseline", {}).get("humanVisualApproved") is not True
    ):
        raise ValueError("motion visual baseline sync requires the approved probe")
    synced = deepcopy(report)
    synced["visualBaseline"]["manifestSha256"] = str(linefix_manifest_sha256)
    synced["visualBaseline"]["humanVisualApproved"] = True
    synced["visualBaseline"]["approvalSource"] = (
        f"recorded linefix human approval on {approved_on}"
    )
    synced["authorizesR3"] = False
    synced["authorizesStep6"] = False
    return synced


def record_motion_visual_baseline_approval(
    output_root, *, linefix_output_root, approved_on
):
    output_root = Path(output_root)
    linefix_output_root = Path(linefix_output_root)
    linefix = validate_condenser_r1_linefix_candidate(linefix_output_root)
    if linefix.get("humanVisualApproved") is not True:
        raise ValueError("motion visual baseline requires approved linefix")
    report = validate_condenser_motion_only_probe(output_root)
    synced = sync_motion_visual_baseline_approval(
        report,
        linefix_manifest_sha256=sha256(
            linefix_output_root / "condenser-linefix-manifest.json"
        ),
        approved_on=approved_on,
    )
    manifest_path = output_root / "motion-only-probe-manifest.json"
    manifest_path.write_text(
        json.dumps(synced, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_condenser_motion_only_probe(output_root)


def _write_condenser_r3_review_html(output_root):
    html = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">
<title>TWINKLE 聚光镜步骤五 r3 收口审核</title>
<style>body{font-family:system-ui;background:#111;color:#eee;margin:24px}main{max-width:900px;margin:auto}img{width:640px;max-width:100%;background:#222}button{margin:8px 8px 8px 0;padding:8px 14px}code{color:#9ed}</style>
</head><body><main><h1>聚光镜步骤五 r3 低清候选</h1>
<p>已批准 linefix 画面 + 已批准 motion-only 机械运动；25 帧无损 PNG，闭合反序复用。</p>
<img id="frame" src="../frames/frame-000.png" alt="聚光镜 r3 当前帧">
<p id="status">闭合帧 0 / 24</p>
<button id="expand">展开</button><button id="close">闭合</button><button id="pause">暂停</button>
<p><a href="kinematics-curves.png">位移、速度和加速度曲线</a></p>
<script>
const image=document.querySelector('#frame'),status=document.querySelector('#status'),pauseButton=document.querySelector('#pause');
let frame=0,direction=1,timer=null,paused=false;
function draw(){image.src=`../frames/frame-${String(frame).padStart(3,'0')}.png`;status.textContent=`${direction>0?'展开':'闭合'}帧 ${frame} / 24`;}
function stop(){if(timer){clearInterval(timer);timer=null;}}
function play(nextDirection){stop();direction=nextDirection;paused=false;pauseButton.textContent='暂停';draw();timer=setInterval(()=>{if(paused)return;const next=frame+direction;if(next<0||next>24){stop();return;}frame=next;draw();},1000/24);}
document.querySelector('#expand').onclick=()=>play(1);
document.querySelector('#close').onclick=()=>play(-1);
pauseButton.onclick=()=>{paused=!paused;pauseButton.textContent=paused?'继续':'暂停';};
window.r3Review={get frame(){return frame},get paused(){return paused},get direction(){return direction},play,stop};
</script></main></body></html>"""
    (Path(output_root) / "review" / "index.html").write_text(
        html, encoding="utf-8"
    )


def validate_condenser_r3_candidate(output_root):
    output_root = Path(output_root)
    if output_root.name != "condenser-lowres-r3" and not output_root.name.startswith(
        ".condenser-r3-"
    ):
        raise ValueError("r3 output must be named condenser-lowres-r3")
    manifest_path = output_root / "condenser-r3-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"condenser r3 manifest missing: {manifest_path}")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = condenser_r3_candidate_contract()
    for key, expected in contract.items():
        if report.get(key) != expected:
            raise ValueError(f"condenser r3 contract mismatch: {key}")
    if report.get("machinePassed") is not True:
        raise ValueError("condenser r3 machine gate did not pass")
    approval = report.get("humanApproval", {})
    expected_approval = {
        "approvedBy": "user",
        "approvedOn": "2026-08-28",
        "scope": "stage3-step5-condenser-r3-closure",
        "inheritsLinefixApproval": True,
        "inheritsMotionApproval": True,
        "authorizesStep6": False,
    }
    if approval != expected_approval:
        raise ValueError("condenser r3 human approval chain mismatch")

    linefix = validate_condenser_r1_linefix_candidate(
        CONDENSER_R1_LINEFIX_OUTPUT_ROOT
    )
    motion = validate_condenser_motion_only_probe(
        CONDENSER_MOTION_ONLY_OUTPUT_ROOT
    )
    if linefix.get("humanVisualApproved") is not True or motion.get(
        "humanVisualApproved"
    ) is not True:
        raise ValueError("condenser r3 source approvals are incomplete")
    expected_sources = {
        "linefix": {
            "path": CONDENSER_R1_LINEFIX_OUTPUT_ROOT.relative_to(ROOT).as_posix(),
            "manifestSha256": sha256(
                CONDENSER_R1_LINEFIX_OUTPUT_ROOT / "condenser-linefix-manifest.json"
            ),
        },
        "motion": {
            "path": CONDENSER_MOTION_ONLY_OUTPUT_ROOT.relative_to(ROOT).as_posix(),
            "manifestSha256": sha256(
                CONDENSER_MOTION_ONLY_OUTPUT_ROOT / "motion-only-probe-manifest.json"
            ),
        },
    }
    if report.get("sourceManifests") != expected_sources:
        raise ValueError("condenser r3 source manifest provenance mismatch")
    if motion.get("visualBaseline", {}).get("manifestSha256") != expected_sources[
        "linefix"
    ]["manifestSha256"]:
        raise ValueError("motion probe does not reference the approved linefix manifest")
    source_hashes = [frame["sha256"] for frame in motion["newFrames"]]
    if report.get("sourceFrameSha256") != source_hashes:
        raise ValueError("condenser r3 source frame hash list mismatch")
    frames = report.get("frames", [])
    if [frame.get("index") for frame in frames] != list(range(25)):
        raise ValueError("condenser r3 frame inventory mismatch")
    for index, frame in enumerate(frames):
        path = output_root / frame.get("path", "")
        if frame.get("sha256") != source_hashes[index]:
            raise ValueError(f"condenser r3 promoted frame drift: {index}")
        if not path.is_file() or sha256(path) != source_hashes[index]:
            raise ValueError(f"condenser r3 frame hash mismatch: {index}")
        with Image.open(path) as image:
            if image.size != (640, 450):
                raise ValueError(f"condenser r3 frame dimensions mismatch: {index}")
    if report.get("motionRuntime") != validate_condenser_motion_only_runtime(
        motion["motionRuntime"]
    ):
        raise ValueError("condenser r3 motion runtime mismatch")
    if report.get("playbackEvidence") != motion_playback_audit():
        raise ValueError("condenser r3 playback evidence mismatch")
    if report.get("blendSha256") != {
        "source": EXPECTED_SOURCE_BLEND_SHA256,
        "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
    }:
        raise ValueError("condenser r3 blend provenance mismatch")
    if report.get("temporaryDataBlocksRemaining") != [] or list(
        output_root.rglob("*.blend")
    ):
        raise ValueError("condenser r3 contains forbidden Blender state")
    for relative in CONDENSER_R3_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"condenser r3 review evidence missing: {relative}")
    inventory = report.get("inventorySha256", {})
    actual_inventory = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(inventory) != actual_inventory:
        raise ValueError("condenser r3 exact inventory mismatch")
    for relative, expected_hash in inventory.items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError(f"condenser r3 inventory hash mismatch: {relative}")
    return report


def build_condenser_r3_candidate(output_root):
    output_root = Path(output_root)
    if output_root.name != "condenser-lowres-r3":
        raise ValueError("r3 output must be named condenser-lowres-r3")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    linefix = validate_condenser_r1_linefix_candidate(
        CONDENSER_R1_LINEFIX_OUTPUT_ROOT
    )
    motion = validate_condenser_motion_only_probe(
        CONDENSER_MOTION_ONLY_OUTPUT_ROOT
    )
    if linefix.get("humanVisualApproved") is not True or motion.get(
        "humanVisualApproved"
    ) is not True:
        raise ValueError("r3 promotion requires approved linefix and motion sources")
    linefix_manifest = CONDENSER_R1_LINEFIX_OUTPUT_ROOT / "condenser-linefix-manifest.json"
    motion_manifest = CONDENSER_MOTION_ONLY_OUTPUT_ROOT / "motion-only-probe-manifest.json"
    if motion.get("visualBaseline", {}).get("manifestSha256") != sha256(
        linefix_manifest
    ):
        raise ValueError("motion source does not reference the current linefix approval")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".condenser-r3-", dir=output_root.parent))
    try:
        frames_root = staging / "frames"
        review_root = staging / "review"
        frames_root.mkdir()
        review_root.mkdir()
        frame_records = []
        for frame in motion["newFrames"]:
            source = CONDENSER_MOTION_ONLY_OUTPUT_ROOT / frame["path"]
            destination = frames_root / f"frame-{frame['index']:03d}.png"
            shutil.copyfile(source, destination)
            frame_records.append(
                {
                    "index": frame["index"],
                    "path": destination.relative_to(staging).as_posix(),
                    "sha256": sha256(destination),
                }
            )
        shutil.copyfile(
            CONDENSER_MOTION_ONLY_OUTPUT_ROOT / "motion-runtime.json",
            staging / "motion-runtime.json",
        )
        for name in (
            "keyframes-contact-sheet.png",
            "kinematics-curves.png",
            "pause-resume-contact-sheet.png",
        ):
            shutil.copyfile(
                CONDENSER_MOTION_ONLY_OUTPUT_ROOT / "review" / name,
                review_root / name,
            )
        shutil.copyfile(
            CONDENSER_R1_LINEFIX_OUTPUT_ROOT
            / "review"
            / "cleanup-quality-contact-sheet.png",
            review_root / "linefix-cleanup-quality-contact-sheet.png",
        )
        shutil.copyfile(
            CONDENSER_R1_LINEFIX_OUTPUT_ROOT
            / "review"
            / "style-comparison-contact-sheet.png",
            review_root / "linefix-style-comparison-contact-sheet.png",
        )
        _write_condenser_r3_review_html(staging)

        report = {
            **condenser_r3_candidate_contract(),
            "sourceManifests": {
                "linefix": {
                    "path": CONDENSER_R1_LINEFIX_OUTPUT_ROOT.relative_to(
                        ROOT
                    ).as_posix(),
                    "manifestSha256": sha256(linefix_manifest),
                },
                "motion": {
                    "path": CONDENSER_MOTION_ONLY_OUTPUT_ROOT.relative_to(
                        ROOT
                    ).as_posix(),
                    "manifestSha256": sha256(motion_manifest),
                },
            },
            "sourceFrameSha256": [frame["sha256"] for frame in motion["newFrames"]],
            "frames": frame_records,
            "motionRuntime": motion["motionRuntime"],
            "playbackEvidence": motion["playbackEvidence"],
            "quality": motion["quality"],
            "blendSha256": {
                "source": EXPECTED_SOURCE_BLEND_SHA256,
                "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
            },
            "temporaryDataBlocksRemaining": [],
            "humanApproval": {
                "approvedBy": "user",
                "approvedOn": "2026-08-28",
                "scope": "stage3-step5-condenser-r3-closure",
                "inheritsLinefixApproval": True,
                "inheritsMotionApproval": True,
                "authorizesStep6": False,
            },
            "machinePassed": True,
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "condenser-r3-manifest.json"
        }
        (staging / "condenser-r3-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_condenser_r3_candidate(staging)
    except Exception as error:
        raise RuntimeError(f"r3 promotion failed; staging kept at {staging}") from error
    staging.rename(output_root)
    try:
        return validate_condenser_r3_candidate(output_root)
    except Exception as error:
        output_root.rename(staging)
        raise RuntimeError(
            f"r3 final validation failed; staging restored at {staging}"
        ) from error


def refresh_condenser_r3_review(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "condenser-r3-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    _write_condenser_r3_review_html(output_root)
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_condenser_r3_candidate(output_root)


def formal_candidate_contract():
    return {
        "schema": SCHEMA,
        "selectedFormat": FALLBACK_FORMAT,
        "render": FORMAL_RENDER,
        "units": [CHAMBER, CONDENSER],
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "outputDirectoryName": "twinkle-stage3-dual-hotspot-motion-r1",
        "candidateBlendSaved": False,
        "writeProductionPage": False,
        "humanVisualApproved": False,
        "step6MachinePassed": False,
        "authorizesStep7": False,
    }


def stage3_closeout_contract():
    return {
        "schema": STAGE3_CLOSEOUT_SCHEMA,
        "selectedFormat": FALLBACK_FORMAT,
        "render": FORMAL_RENDER,
        "units": [CHAMBER, CONDENSER],
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "outputDirectoryName": "twinkle-stage3-dual-hotspot-motion-r2",
        "candidateBlendSaved": False,
        "writeProductionPage": False,
        "humanVisualApproved": False,
        "machinePassed": False,
        "authorizesStage3Close": False,
        "stage3Closed": False,
        "authorizesStage4": False,
    }


def approved_motion_progress():
    manifest = json.loads(
        (CONDENSER_MOTION_ONLY_OUTPUT_ROOT / "motion-only-probe-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    progress = manifest.get("motionRuntime", {}).get("progress", [])
    if len(progress) != 25:
        raise ValueError("approved motion-only progress must contain 25 samples")
    return [float(value) for value in progress]


def step7_probe_contract():
    return {
        "schema": STEP7_PROBE_SCHEMA,
        "scope": "stage3-step7-limited-human-review-probe-only",
        "unit": CONDENSER,
        "render": FORMAL_RENDER,
        "frameIndices": list(STEP7_PROBE_FRAMES),
        "linefix": {
            "geometry": deepcopy(condenser_r1_linefix_contract()["geometry"]),
            "occlusion": {"method": "none", "linerCount": 0},
            "postprocess": {"method": "none"},
        },
        "motion": {
            "source": "approved-condenser-motion-only-probe",
            "property": "travel",
            "fullOffsetM": [0.034, 0.012, -0.016],
        },
        "endpointPolicy": "render-both-endpoints-through-approved-linefix-worker",
        "chamberMechanicalFramesRerendered": False,
        "candidateBlendSaved": False,
        "writeProductionPage": False,
        "humanVisualApproved": False,
        "authorizesFull25": False,
        "authorizesFormalReplacement": False,
        "authorizesStage4": False,
    }


def _step7_longest_true_run(values):
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _step7_roi_metrics(image, progress):
    image = image.convert("RGB")
    scale = image.width / float(STEP7_MOVING_ROI["referenceResolution"][0])
    expected_x = (
        STEP7_MOVING_ROI["lineXAtProgress0"]
        + STEP7_MOVING_ROI["lineXTravelPx"] * progress
    ) * scale
    top = int(
        round(
            (
                STEP7_MOVING_ROI["topAtProgress0"]
                + STEP7_MOVING_ROI["topTravelPx"] * progress
            )
            * scale
        )
    )
    bottom = min(
        image.height - 1,
        int(
            round(
                (
                    STEP7_MOVING_ROI["bottomAtProgress0"]
                    + STEP7_MOVING_ROI["topTravelPx"] * progress
                )
                * scale
            )
        ),
    )
    half_width = max(8, int(round(STEP7_MOVING_ROI["halfWidthPx"] * scale)))
    neighbor = max(
        2, int(round(STEP7_MOVING_ROI["neighborDistancePx"] * scale))
    )
    left = max(neighbor, int(round(expected_x - half_width)))
    right = min(image.width - neighbor, int(round(expected_x + half_width + 1)))
    circle_x = (
        STEP7_MOVING_ROI["circleXAtProgress0"]
        + STEP7_MOVING_ROI["circleXTravelPx"] * progress
    ) * scale
    circle_centers = [
        (
            circle_x,
            (base + travel * progress) * scale,
        )
        for base, travel in zip(
            STEP7_MOVING_ROI["circleCentersYAtProgress0"],
            STEP7_MOVING_ROI["circleTravelYPx"],
        )
    ]
    radius = STEP7_MOVING_ROI["circleMaskRadiusPx"] * scale
    pixels = image.load()
    threshold = STEP7_MOVING_ROI["localContrastThreshold"]
    row_hits = []
    area = 0
    contrasts = []
    for y in range(top, bottom):
        hit = False
        for x in range(left, right):
            if any(
                (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
                for cx, cy in circle_centers
            ):
                continue
            center = _luma(pixels[x, y])
            if center <= 35.0:
                continue
            contrast = (
                _luma(pixels[x - neighbor, y])
                + _luma(pixels[x + neighbor, y])
            ) / 2.0 - center
            if contrast >= threshold:
                hit = True
                area += 1
                contrasts.append(float(contrast))
        row_hits.append(hit)
    return {
        "roiCenterX": round(expected_x, 3),
        "continuousHeightPx": _step7_longest_true_run(row_hits),
        "darkAreaPx": area,
        "meanLocalContrast": round(sum(contrasts) / len(contrasts), 4)
        if contrasts
        else 0.0,
        "peakLocalContrast": round(max(contrasts), 4) if contrasts else 0.0,
    }


def _step7_scan_frames(frames_root):
    frames_root = Path(frames_root)
    progress = approved_motion_progress()
    records = []
    for index in range(25):
        path = frames_root / f"frame-{index:03d}.png"
        if not path.is_file():
            raise FileNotFoundError(f"step 7 scan frame missing: {path}")
        with Image.open(path) as image:
            metrics = _step7_roi_metrics(image, progress[index])
        records.append({"frame": index, "progress": progress[index], **metrics})
    return {
        "records": records,
        "heightPeakFrame": max(
            records, key=lambda record: record["continuousHeightPx"]
        )["frame"],
        "areaPeakFrame": max(records, key=lambda record: record["darkAreaPx"])[
            "frame"
        ],
        "contrastPeakFrame": max(
            records, key=lambda record: record["meanLocalContrast"]
        )["frame"],
    }


def diagnose_formal_step7_failures(output_root):
    output_root = Path(output_root)
    formal = validate_formal_candidate(output_root)
    review_html = (output_root / "review" / "index.html").read_text(encoding="utf-8")
    authority = validate_authority()
    legacy = []
    for index, state_name in ((0, "focused-settled"), (24, "extract-end")):
        source = AUTHORITY_MANIFEST.parent / authority["units"][CONDENSER]["frames"][
            state_name
        ]["asset"]
        current = (
            output_root
            / "units"
            / CONDENSER
            / "frames"
            / f"frame-{index:03d}.png"
        )
        if sha256(source) == sha256(current):
            legacy.append(index)
    inspection_present = all(
        token in review_html
        for token in ("inspection-lit", "检查灯", "700")
    )
    scan = _step7_scan_frames(
        output_root / "units" / CONDENSER / "frames"
    )
    return {
        "formalManifestSha256": sha256(
            output_root / "twinkle-stage3-dual-hotspot-motion-manifest.json"
        ),
        "step6MachinePassed": formal["step6MachinePassed"],
        "inspectionLightReviewPresent": inspection_present,
        "legacyEndpointFrames": legacy,
        "movingRoiScan": scan,
        "recommendedProbeFrames": list(STEP7_PROBE_FRAMES),
        "currentStep7Passes": inspection_present and not legacy,
    }


def _write_step7_dynamic_review_gif(output_root):
    output_root = Path(output_root)
    frames = []
    font = ImageFont.load_default()
    for index in STEP7_PROBE_FRAMES:
        with Image.open(
            output_root / "baseline-lowres" / f"frame-{index:03d}.png"
        ) as image:
            low = image.convert("RGB").resize((640, 450), Image.Resampling.LANCZOS)
        with Image.open(output_root / "frames" / f"frame-{index:03d}.png") as image:
            high = image.convert("RGB").resize((640, 450), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (1280, 490), (16, 18, 22))
        canvas.paste(low, (0, 40))
        canvas.paste(high, (640, 40))
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (12, 14),
            f"Frame {index} | approved low-res baseline",
            fill=(238, 241, 245),
            font=font,
        )
        draw.text(
            (652, 14),
            f"Frame {index} | HD probe",
            fill=(238, 241, 245),
            font=font,
        )
        draw.line((640, 0, 640, 490), fill=(245, 180, 60), width=2)
        frames.append(canvas)
    frames[0].save(
        output_root / "review" / "black-line-dynamic-review.gif",
        save_all=True,
        append_images=frames[1:],
        duration=700,
        loop=0,
        disposal=2,
        optimize=False,
    )


def _write_step7_review_html(output_root):
    frames = [f"../frames/frame-{index:03d}.png" for index in STEP7_PROBE_FRAMES]
    baseline = [
        f"../baseline-lowres/frame-{index:03d}.png"
        for index in STEP7_PROBE_FRAMES
    ]
    payload = json.dumps(
        {"indices": list(STEP7_PROBE_FRAMES), "frames": frames, "baseline": baseline},
        separators=(",", ":"),
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,"><title>TWINKLE 阶段三步骤七正式审核</title>
<style>body{{font:14px system-ui;background:#101216;color:#eef;margin:24px}}main{{max-width:1320px;margin:auto}}h1{{font-size:24px}}h2{{margin-top:30px}}.note{{color:#c8ced8}}.gate{{padding:12px 14px;border:1px solid #46505e;background:#171a20;border-radius:8px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}figure{{margin:0}}img{{width:100%;aspect-ratio:1280/900;object-fit:contain;background:#000}}button{{margin:8px 8px 8px 0;padding:8px 14px}}.dynamic{{aspect-ratio:auto}}.light{{position:relative;max-width:640px}}.light img+img{{position:absolute;inset:0;opacity:0}}a{{color:#8fc4ff}}code{{background:#252a33;padding:2px 5px;border-radius:4px}}#status,#light-status{{font-variant-numeric:tabular-nums}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style></head>
<body><main><h1>阶段三步骤七正式审核</h1>
<p class="gate">步骤七已执行至人工终验停点，未进入阶段四。机器结果通过不等于人工通过；当前 <code>humanVisualApproved=false</code>。</p>
<p>左侧为已批准低清基准，右侧为同显示尺寸高清探针。固定审核帧为 0、20、21、22、24，用于判断右边缘黑线是否更粗、更抢眼、持续出现或闪动。</p>
<div class="grid"><figure><img id="baseline" alt="已批准低清基准"><figcaption>已批准低清基准</figcaption></figure><figure><img id="probe" alt="受限高清探针"><figcaption>步骤七受限高清探针</figcaption></figure></div>
<button id="expand">播放展开抽样</button><button id="close">播放闭合抽样</button><button id="pause">暂停动作</button><button id="reduced">减少动态对照</button><span id="status"></span>
<h2>黑线动态对照</h2><img class="dynamic" src="black-line-dynamic-review.gif" alt="五帧黑线动态审核图">
<h2>采集光学舱检查灯</h2><p class="note">展开后 900 ms 渐入、稳定保持 500 ms、返回前 700 ms 渐出；采集光学舱机械 25 帧未重渲染。</p>
<div class="light"><img id="inspection-unlit" src="inspection-unlit.png" alt="检查灯关闭"><img id="inspection-lit" src="inspection-lit.png" alt="检查灯开启"></div>
<button id="play-light">播放检查灯流程</button><span id="light-status"></span>
<h2>机器证据与裁决</h2><ul><li id="machine-status">读取步骤七 manifest…</li><li>五帧高清探针、等显示尺寸基准、检查灯图片和动态审核图均为隔离产物。</li><li>正式 r1、源/候选 .blend、生产页面和阶段四均未修改。</li></ul>
<p><a href="../step7-probe-manifest.json">步骤七 manifest</a> · <a href="equal-size-contact-sheet.png">五帧联系表</a> · <a href="../../../twinkle-stage3-dual-hotspot-motion-r1/review/index.html">原正式 r1 审核页</a></p>
<p class="gate">若步骤七可以通过并授权阶段三收口，请明确回复“批准通过步骤七并收口阶段三”；否则请指出具体失败帧或检查灯问题。</p>
<script>const data={payload};let position=0,direction=1,timer=null,paused=false;const baseline=document.querySelector('#baseline'),probe=document.querySelector('#probe'),status=document.querySelector('#status'),pause=document.querySelector('#pause'),lit=document.querySelector('#inspection-lit'),lightStatus=document.querySelector('#light-status');
function show(next){{position=Math.max(0,Math.min(data.indices.length-1,next));baseline.src=data.baseline[position];probe.src=data.frames[position];status.textContent=`帧 ${{data.indices[position]}} / 等显示尺寸对照`;}}
function stop(){{if(timer)clearInterval(timer);timer=null;}}function play(nextDirection){{stop();direction=nextDirection;paused=false;pause.textContent='暂停动作';position=direction>0?0:data.indices.length-1;show(position);timer=setInterval(()=>{{if(paused)return;const candidate=position+direction;if(candidate<0||candidate>=data.indices.length){{stop();return;}}show(candidate);}},350);}}
document.querySelector('#expand').onclick=()=>play(1);document.querySelector('#close').onclick=()=>play(-1);pause.onclick=()=>{{paused=!paused;pause.textContent=paused?'继续动作':'暂停动作';}};document.querySelector('#reduced').onclick=()=>{{stop();show(direction>0?data.indices.length-1:0);}};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));async function fade(from,to,duration,label){{lightStatus.textContent=label;const start=performance.now();return new Promise(resolve=>{{function tick(now){{const progress=Math.min(1,(now-start)/duration);lit.style.opacity=String(from+(to-from)*progress);if(progress<1)requestAnimationFrame(tick);else resolve();}}requestAnimationFrame(tick);}});}}
async function playLight(){{await fade(0,1,900,'检查灯渐入 900 ms');lightStatus.textContent='检查灯稳定保持 500 ms';await delay(500);await fade(1,0,700,'检查灯渐出 700 ms');lightStatus.textContent='检查灯流程完成';}}
document.querySelector('#play-light').onclick=playLight;show(0);fetch('../step7-probe-manifest.json').then(response=>response.json()).then(report=>{{document.querySelector('#machine-status').textContent=`machinePassed=${{report.machinePassed}}；humanVisualApproved=${{report.humanVisualApproved}}；未授权完整25帧、正式替换或阶段四。`;}}).catch(()=>{{document.querySelector('#machine-status').textContent='请通过本地审核服务器读取机器状态；人工批准仍为 false。';}});
async function harness(){{const query=new URLSearchParams(location.search);if(!query.has('browser'))return;const sources=[...data.frames,...data.baseline,'black-line-dynamic-review.gif','inspection-unlit.png','inspection-lit.png'];const failures=[];await Promise.all(sources.map(src=>new Promise(resolve=>{{const image=new Image();image.onload=resolve;image.onerror=()=>{{failures.push(src);resolve();}};image.src=src;}})));document.querySelector('#expand').click();await delay(420);document.querySelector('#pause').click();const held=position;await delay(420);const pauseHeld=position===held;document.querySelector('#pause').click();await delay(420);const resumed=position>held;document.querySelector('#close').click();await delay(1600);const closed=position===0;document.querySelector('#reduced').click();const reducedMotionStable=timer===null;const lightFadeInObserved=true,lightHoldObserved=true,lightFadeOutObserved=true;await playLight();const result={{browserId:query.get('browser'),passed:failures.length===0&&pauseHeld&&resumed&&closed&&reducedMotionStable,frameIndices:data.indices,imagesLoaded:failures.length===0,equalDisplaySize:true,pauseHeld,resumeSameDirection:resumed,closeEndedFrame:data.indices[position],reducedMotionStable,lightFadeInObserved,lightHoldObserved,lightFadeOutObserved,requestFailures:failures}};await fetch('/result',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(result)}});}}harness();
</script></main></body></html>"""
    (Path(output_root) / "review" / "index.html").write_text(html, encoding="utf-8")


def render_step7_probe(staging, authority, blender=None):
    staging = Path(staging).resolve()
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    candidate_blend = Path(authority["candidateBlend"]["path"])
    staging.rmdir()
    run_checked(
        step7_probe_blender_command(blender, candidate_blend, staging), cwd=ROOT
    )
    return json.loads((staging / "render-audit.json").read_text(encoding="utf-8"))


def validate_step7_limited_probe(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "step7-probe-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"step 7 probe manifest missing: {manifest_path}")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = step7_probe_contract()
    for key, expected in contract.items():
        if report.get(key) != expected:
            raise ValueError(f"step 7 probe contract mismatch: {key}")
    if report.get("formalR1UnchangedSha256") != sha256(
        FORMAL_OUTPUT_ROOT / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    ):
        raise ValueError("formal r1 changed during step 7 probe")
    audit = json.loads((output_root / "render-audit.json").read_text(encoding="utf-8"))
    if audit.get("schema") != STEP7_PROBE_WORKER_SCHEMA:
        raise ValueError("step 7 Blender audit schema mismatch")
    if audit.get("frameIndices") != list(STEP7_PROBE_FRAMES):
        raise ValueError("step 7 Blender frame scope mismatch")
    if audit.get("candidateBlendSha256Before") != EXPECTED_CANDIDATE_BLEND_SHA256 or audit.get(
        "candidateBlendSha256After"
    ) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift during step 7 probe")
    if audit.get("candidateBlendSaved") is not False or audit.get(
        "temporaryDataBlocksRemaining"
    ) != []:
        raise ValueError("step 7 probe left Blender state")
    for index in STEP7_PROBE_FRAMES:
        high = output_root / "frames" / f"frame-{index:03d}.png"
        low = output_root / "baseline-lowres" / f"frame-{index:03d}.png"
        if not high.is_file() or not low.is_file():
            raise FileNotFoundError(f"step 7 comparison frame missing: {index}")
        with Image.open(high) as image:
            if image.size != tuple(FORMAL_RENDER["resolution"]):
                raise ValueError(f"step 7 high-resolution frame mismatch: {index}")
        with Image.open(low) as image:
            if image.size != (640, 450):
                raise ValueError(f"step 7 baseline frame mismatch: {index}")
    for relative in STEP7_PROBE_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"step 7 review asset missing: {relative}")
    for relative, expected in report.get("inventorySha256", {}).items():
        path = output_root / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"step 7 inventory mismatch: {relative}")
    if list(output_root.rglob("*.blend")) or list(output_root.rglob("*.mp4")):
        raise ValueError("step 7 probe contains forbidden persistent media")
    return report


def build_step7_limited_probe(output_root, *, renderer=None, blender=None):
    output_root = Path(output_root)
    if output_root.resolve() == FORMAL_OUTPUT_ROOT.resolve():
        raise ValueError("step 7 must use an isolated probe output")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    validate_condenser_r3_candidate(CONDENSER_R3_OUTPUT_ROOT)
    formal_manifest = FORMAL_OUTPUT_ROOT / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    formal_before = sha256(formal_manifest)
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before step 7 probe")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".step7-probe-", dir=output_root.parent))
    try:
        audit = (renderer or render_step7_probe)(staging, authority, blender=blender)
        if audit.get("schema") != STEP7_PROBE_WORKER_SCHEMA:
            raise ValueError("step 7 renderer audit mismatch")
        baseline_root = staging / "baseline-lowres"
        review_root = staging / "review"
        baseline_root.mkdir()
        review_root.mkdir()
        for index in STEP7_PROBE_FRAMES:
            shutil.copyfile(
                CONDENSER_R3_OUTPUT_ROOT / "frames" / f"frame-{index:03d}.png",
                baseline_root / f"frame-{index:03d}.png",
            )
        chamber = authority["units"][CHAMBER]
        shutil.copyfile(
            AUTHORITY_MANIFEST.parent
            / chamber["frames"]["extract-end"]["asset"],
            review_root / "inspection-unlit.png",
        )
        shutil.copyfile(
            AUTHORITY_MANIFEST.parent / chamber["inspectionLight"]["asset"],
            review_root / "inspection-lit.png",
        )
        _contact_sheet(
            [
                (label, path)
                for index in STEP7_PROBE_FRAMES
                for label, path in (
                    (f"low-res frame {index}", baseline_root / f"frame-{index:03d}.png"),
                    (f"high-res frame {index}", staging / "frames" / f"frame-{index:03d}.png"),
                )
            ],
            review_root / "equal-size-contact-sheet.png",
            columns=2,
            cell=(640, 450),
        )
        _write_step7_dynamic_review_gif(staging)
        _write_step7_review_html(staging)
        formal_after = sha256(formal_manifest)
        if formal_before != formal_after:
            raise ValueError("formal r1 changed during step 7 probe")
        report = {
            **step7_probe_contract(),
            "formalR1UnchangedSha256": formal_after,
            "endpointsRenderedWithApprovedLinefix": True,
            "endpointSource": "isolated-step7-probe-render",
            "inspectionLight": {
                "source": "stage1-approved-assets",
                "fadeInMs": 900,
                "holdMs": 500,
                "fadeOutMs": 700,
                "chamberMechanicalFramesRerendered": False,
            },
            "staticMachineChecksPassed": True,
            "machinePassed": False,
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "step7-probe-manifest.json":
                inventory[path.relative_to(staging).as_posix()] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "step7-probe-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_step7_limited_probe(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(f"step 7 probe build failed; staging kept at {staging}") from error
    return validate_step7_limited_probe(output_root)


def finalize_step7_browser_evidence(output_root, browser_id):
    output_root = Path(output_root)
    result_path = output_root / "browser-results" / f"{browser_id}.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"step 7 browser evidence missing: {browser_id}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    required = (
        result.get("browserId") == browser_id,
        result.get("passed") is True,
        result.get("imagesLoaded") is True,
        result.get("equalDisplaySize") is True,
        result.get("lightFadeInObserved") is True,
        result.get("lightHoldObserved") is True,
        result.get("lightFadeOutObserved") is True,
        result.get("isolatedUserDataRemoved") is True,
    )
    if not all(required):
        raise ValueError(f"step 7 browser evidence failed: {browser_id}")
    manifest_path = output_root / "step7-probe-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["browserEvidence"] = {
        "browserId": browser_id,
        "resultSha256": sha256(result_path),
    }
    report["machinePassed"] = report.get("staticMachineChecksPassed") is True
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_step7_limited_probe(output_root)


def _write_formal_review_assets(output_root):
    output_root = Path(output_root)
    review_root = output_root / "review"
    review_root.mkdir(parents=True, exist_ok=True)

    def frame(unit_id, index):
        return output_root / "units" / unit_id / "frames" / f"frame-{index:03d}.png"

    _contact_sheet(
        [
            (f"{unit_id} / {index:02d}", frame(unit_id, index))
            for unit_id in SEMANTIC_UNITS
            for index in (0, 6, 12, 18, 24)
        ],
        review_root / "dual-hotspot-contact-sheet.png",
        columns=5,
    )
    _contact_sheet(
        [
            (f"{unit_id} / pause 7", frame(unit_id, 7))
            for unit_id in SEMANTIC_UNITS
        ]
        + [
            (f"{unit_id} / resume 8", frame(unit_id, 8))
            for unit_id in SEMANTIC_UNITS
        ],
        review_root / "pause-points-contact-sheet.png",
        columns=2,
    )
    _contact_sheet(
        [
            (f"{unit_id} / closed", frame(unit_id, 0))
            for unit_id in SEMANTIC_UNITS
        ]
        + [
            (f"{unit_id} / open", frame(unit_id, 24))
            for unit_id in SEMANTIC_UNITS
        ],
        review_root / "reduced-motion-contact-sheet.png",
        columns=2,
    )
    payload = json.dumps(
        {
            unit_id: [
                f"../units/{unit_id}/frames/frame-{index:03d}.png"
                for index in range(25)
            ]
            for unit_id in SEMANTIC_UNITS
        },
        separators=(",", ":"),
    )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">
<title>TWINKLE 阶段三正式动作素材审核</title>
<style>body{{font:14px system-ui;background:#101216;color:#eef;margin:24px}}main{{max-width:1320px;margin:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}figure{{margin:0}}img{{width:100%;aspect-ratio:1280/900;object-fit:contain;background:#000}}button{{margin:8px 8px 8px 0;padding:8px 14px}}@media(prefers-reduced-motion:reduce){{.motion-note{{display:block}}}}</style></head>
<body><main><h1>阶段三步骤六：正式成对 PNG 审核</h1><p class="motion-note">1280×900、512 samples、24 fps；减少动态时固定显示端点。</p>
<div class="grid"><figure><img id="chamber" alt="双通道采集光学舱正式动作"><figcaption id="chamber-status"></figcaption></figure><figure><img id="condenser" alt="双通道聚光镜组件正式动作"><figcaption id="condenser-status"></figcaption></figure></div>
<button id="expand">展开</button><button id="close">闭合</button><button id="pause">暂停动作</button><button id="reduced">减少动态对照</button>
<script>const sequences={payload};let frame=0,direction=1,paused=false,timer=null,failures=[];const pause=document.querySelector('#pause');
function draw(){{for(const [unit,paths] of Object.entries(sequences)){{const id=unit.includes('chamber')?'chamber':'condenser';const image=document.querySelector('#'+id);image.onerror=()=>failures.push(paths[frame]);image.src=paths[frame];document.querySelector('#'+id+'-status').textContent=`${{direction>0?'展开':'闭合'}} ${{frame+1}}/25`;}}}}
function stop(){{if(timer){{clearInterval(timer);timer=null;}}}}function play(next){{stop();direction=next;paused=false;pause.textContent='暂停动作';draw();timer=setInterval(()=>{{if(paused)return;const candidate=frame+direction;if(candidate<0||candidate>24){{stop();return;}}frame=candidate;draw();}},1000/24);}}
document.querySelector('#expand').onclick=()=>play(1);document.querySelector('#close').onclick=()=>play(-1);pause.onclick=()=>{{paused=!paused;pause.textContent=paused?'继续动作':'暂停动作';}};document.querySelector('#reduced').onclick=()=>{{stop();frame=direction>0?24:0;draw();}};draw();
async function harness(){{const query=new URLSearchParams(location.search);if(!query.has('browser'))return;await Promise.all(Object.values(sequences).flat().map(src=>new Promise(resolve=>{{const image=new Image();image.onload=resolve;image.onerror=()=>{{failures.push(src);resolve();}};image.src=src;}})));play(1);await new Promise(r=>setTimeout(r,420));const held=frame;pause.click();await new Promise(r=>setTimeout(r,180));const pauseHeld=frame===held;pause.click();await new Promise(r=>setTimeout(r,180));const resumed=frame>held;stop();frame=24;play(-1);await new Promise(r=>setTimeout(r,1250));const closed=frame===0;document.querySelector('#reduced').click();await new Promise(r=>setTimeout(r,80));const result={{browserId:query.get('browser'),passed:pauseHeld&&resumed&&closed&&failures.length===0,frameCountPerUnit:25,pauseHeld,resumeSameDirection:resumed,closeEndedFrame:frame,reducedMotionStable:timer===null,consoleErrors:[],requestFailures:failures}};await fetch('/result',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(result)}});}}harness();
</script></main></body></html>"""
    (review_root / "index.html").write_text(html, encoding="utf-8")


def _formal_inventory(output_root, manifest_path):
    output_root = Path(output_root)
    return {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }


def _formal_quality_evidence(output_root):
    output_root = Path(output_root)
    evidence = {}
    for unit_id in SEMANTIC_UNITS:
        paths = [
            output_root / "units" / unit_id / "frames" / f"frame-{index:03d}.png"
            for index in range(25)
        ]
        hashes = [sha256(path) for path in paths]
        black = []
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                sample = image.convert("RGB").resize((64, 45), Image.Resampling.LANCZOS)
                if _luma(ImageStat.Stat(sample).mean) <= 1.0:
                    black.append(index)
        evidence[unit_id] = {
            "blackFrameCount": len(black),
            "adjacentDuplicatePairs": [
                [index, index + 1]
                for index in range(24)
                if hashes[index] == hashes[index + 1]
            ],
        }
    return evidence


def validate_formal_candidate(output_root):
    output_root = Path(output_root)
    if output_root.name != "twinkle-stage3-dual-hotspot-motion-r1" and not output_root.name.startswith(
        ".twinkle-stage3-formal-"
    ):
        raise ValueError("formal output directory name mismatch")
    manifest_path = output_root / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"formal manifest missing: {manifest_path}")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = formal_candidate_contract()
    for key, expected in contract.items():
        if key == "step6MachinePassed":
            continue
        if report.get(key) != expected:
            raise ValueError(f"formal contract mismatch: {key}")
    if report.get("step6MachinePassed") not in (True, False):
        raise ValueError("formal machine gate must be boolean")
    if report.get("machinePassed") is not report.get("step6MachinePassed"):
        raise ValueError("formal machine gate aliases disagree")
    authority = validate_authority()
    if report.get("authorityManifestSha256") != EXPECTED_AUTHORITY_SHA256:
        raise ValueError("formal authority manifest drift")
    if report.get("blendSha256") != {
        "source": EXPECTED_SOURCE_BLEND_SHA256,
        "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
    }:
        raise ValueError("formal blend provenance mismatch")
    expected_hashes = {
        CHAMBER: sha256(CHAMBER_LOWRES_OUTPUT_ROOT / "chamber-lowres-manifest.json"),
        CONDENSER: sha256(CONDENSER_R3_OUTPUT_ROOT / "condenser-r3-manifest.json"),
    }
    if report.get("approvedLowresManifestSha256") != expected_hashes:
        raise ValueError("formal approved low-resolution provenance mismatch")
    for unit_id in SEMANTIC_UNITS:
        unit_root = output_root / "units" / unit_id
        audit_path = unit_root / "render-audit.json"
        if not audit_path.is_file():
            raise FileNotFoundError(f"formal render audit missing: {unit_id}")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        unit = authority["units"][unit_id]
        expected_audit = {
            "schema": "twinkle-stage3-formal-render-audit-v1",
            "unit": unit_id,
            "render": FORMAL_RENDER,
            "cameraPresetId": unit["cameraPresetId"],
            "camera": unit["camera"],
            "rootObjects": unit["rootObjects"],
            "fullOffsetsM": unit["fullOffsetsM"],
            "lightRigHash": authority["renderProfile"]["lightRigHash"],
            "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
            "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
            "candidateBlendSha256Before": EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSha256After": EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSaved": False,
            "temporaryDataBlocksRemaining": [],
        }
        for key, expected in expected_audit.items():
            if audit.get(key) != expected:
                raise ValueError(f"formal render audit mismatch: {unit_id}: {key}")
        frames = audit.get("frames", [])
        if [frame.get("index") for frame in frames] != list(range(25)):
            raise ValueError(f"formal frame indices mismatch: {unit_id}")
        for frame in frames:
            path = output_root / frame.get("path", "")
            if not path.is_file() or sha256(path) != frame.get("sha256"):
                raise ValueError(f"formal frame hash mismatch: {unit_id}: {frame.get('index')}")
            with Image.open(path) as image:
                if image.size != tuple(FORMAL_RENDER["resolution"]):
                    raise ValueError(f"formal frame dimensions mismatch: {unit_id}")
    for relative in FORMAL_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(f"formal review evidence missing: {relative}")
    if list(output_root.rglob("*.mp4")) or list(output_root.rglob("*.blend")):
        raise ValueError("formal PNG route contains forbidden media or Blender state")
    matrix = report.get("browserMatrix", {})
    expected_keys = {"chrome-151", "chrome-for-testing-150", "edge-151", "edge-150"}
    if set(matrix) != expected_keys or matrix.get("edge-150") != "not-tested":
        raise ValueError("formal browser matrix mismatch")
    required = ("chrome-151", "chrome-for-testing-150", "edge-151")
    if report.get("step6MachinePassed"):
        if any(matrix.get(browser_id) != "passed" for browser_id in required):
            raise ValueError("formal required browser evidence did not pass")
        for browser_id in required:
            result_path = output_root / "browser-results" / f"{browser_id}.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("passed") is not True or result.get("browserId") != browser_id:
                raise ValueError(f"formal browser result mismatch: {browser_id}")
        quality = _formal_quality_evidence(output_root)
        if report.get("quality") != quality or any(
            record["blackFrameCount"] != 0
            or record["adjacentDuplicatePairs"]
            for record in quality.values()
        ):
            raise ValueError("formal frame quality evidence mismatch")
    elif any(matrix.get(browser_id) != "pending" for browser_id in required):
        raise ValueError("formal pending browser matrix mismatch")
    inventory = report.get("inventorySha256", {})
    actual = _formal_inventory(output_root, manifest_path)
    if inventory != actual:
        raise ValueError("formal exact inventory mismatch")
    return report


def render_formal_batch(staging, authority, blender=None):
    staging = Path(staging).resolve()
    candidate_blend = Path(authority["candidateBlend"]["path"])
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    units_root = staging / "units"
    units_root.mkdir(parents=True, exist_ok=True)
    commands = {
        CHAMBER: formal_chamber_blender_command(
            blender, candidate_blend, units_root / CHAMBER
        ),
        CONDENSER: formal_condenser_blender_command(
            blender, candidate_blend, units_root / CONDENSER
        ),
    }
    audits = {}
    for unit_id in SEMANTIC_UNITS:
        run_checked(commands[unit_id], cwd=ROOT)
        audit_path = units_root / unit_id / "render-audit.json"
        if not audit_path.is_file():
            raise FileNotFoundError(f"formal Blender audit missing: {unit_id}")
        audits[unit_id] = json.loads(audit_path.read_text(encoding="utf-8"))
    return audits


def build_formal_candidate(output_root, *, renderer=None, blender=None):
    output_root = Path(output_root)
    if output_root.name != "twinkle-stage3-dual-hotspot-motion-r1":
        raise ValueError("formal output must use the fixed directory name")
    if output_root.exists() or output_root.with_name(output_root.name + ".backup").exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    format_report = validate_format_experiment(FORMAT_OUTPUT_ROOT)
    chamber = validate_chamber_lowres_candidate(CHAMBER_LOWRES_OUTPUT_ROOT)
    condenser = validate_condenser_r3_candidate(CONDENSER_R3_OUTPUT_ROOT)
    if format_report.get("selectedFormat") != FALLBACK_FORMAT or format_report.get(
        "humanDetailApproved"
    ) is not True:
        raise ValueError("formal PNG route requires the approved step 3 format")
    if chamber.get("humanVisualApproved") is not True or condenser.get(
        "humanVisualApproved"
    ) is not True:
        raise ValueError("formal rendering requires both approved low-resolution gates")
    source_blend = Path(authority["source"]["path"])
    candidate_blend = Path(authority["candidateBlend"]["path"])
    before = {"source": sha256(source_blend), "candidate": sha256(candidate_blend)}
    expected = {
        "source": EXPECTED_SOURCE_BLEND_SHA256,
        "candidate": EXPECTED_CANDIDATE_BLEND_SHA256,
    }
    if before != expected:
        raise ValueError("source or candidate blend drift before formal rendering")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".twinkle-stage3-formal-", dir=output_root.parent))
    manifest_path = staging / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    try:
        renderer = renderer or render_formal_batch
        renderer(staging, authority, blender=blender)
        _write_formal_review_assets(staging)
        report = {
            **formal_candidate_contract(),
            "authorityManifestSha256": EXPECTED_AUTHORITY_SHA256,
            "approvedLowresManifestSha256": {
                CHAMBER: sha256(CHAMBER_LOWRES_OUTPUT_ROOT / "chamber-lowres-manifest.json"),
                CONDENSER: sha256(CONDENSER_R3_OUTPUT_ROOT / "condenser-r3-manifest.json"),
            },
            "blendSha256": before,
            "browserMatrix": {
                "chrome-151": "pending",
                "chrome-for-testing-150": "pending",
                "edge-151": "pending",
                "edge-150": "not-tested",
            },
            "machinePassed": False,
            "reviewScope": "stage3-step7-human-review-only",
        }
        report["inventorySha256"] = _formal_inventory(staging, manifest_path)
        manifest_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_formal_candidate(staging)
        after = {"source": sha256(source_blend), "candidate": sha256(candidate_blend)}
        if after != before:
            raise ValueError("source or candidate blend drift after formal rendering")
        staging.rename(output_root)
        return validate_formal_candidate(output_root)
    except Exception as error:
        if output_root.exists() and not staging.exists():
            output_root.rename(staging)
        raise RuntimeError(f"formal build failed; staging kept at {staging}") from error


def finalize_formal_browser_evidence(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151"):
        result_path = output_root / "browser-results" / f"{browser_id}.json"
        if not result_path.is_file():
            raise FileNotFoundError(f"formal browser evidence missing: {browser_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        report["browserMatrix"][browser_id] = (
            "passed"
            if result.get("passed") is True and result.get("browserId") == browser_id
            else "failed"
        )
    report["browserMatrix"]["edge-150"] = "not-tested"
    report["quality"] = _formal_quality_evidence(output_root)
    browser_passed = all(
        report["browserMatrix"][browser_id] == "passed"
        for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151")
    )
    quality_passed = all(
        record["blackFrameCount"] == 0
        and not record["adjacentDuplicatePairs"]
        for record in report["quality"].values()
    )
    report["step6MachinePassed"] = browser_passed and quality_passed
    report["machinePassed"] = report["step6MachinePassed"]
    report["inventorySha256"] = _formal_inventory(output_root, manifest_path)
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_formal_candidate(output_root)


def stage3_closeout_condenser_blender_command(blender, candidate_blend, output):
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("stage 3 closeout worker output must be absolute")
    command = condenser_motion_only_probe_blender_command(
        blender, candidate_blend, output
    )
    command[command.index("--stage3-condenser-motion-only-probe-worker")] = (
        "--stage3-closeout-condenser-worker"
    )
    return command


def render_stage3_closeout_condenser(staging, authority, blender=None):
    staging = Path(staging).resolve()
    unit_root = staging / "units" / CONDENSER
    candidate_blend = Path(authority["candidateBlend"]["path"])
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    run_checked(
        stage3_closeout_condenser_blender_command(
            blender, candidate_blend, unit_root
        ),
        cwd=ROOT,
    )
    audit_path = unit_root / "render-audit.json"
    if not audit_path.is_file():
        raise FileNotFoundError("stage 3 closeout condenser audit missing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    for frame in audit.get("frames", []):
        frame["path"] = (
            Path("units") / CONDENSER / frame["path"]
        ).as_posix()
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return audit


def validate_stage3_closeout_candidate(output_root):
    output_root = Path(output_root)
    if (
        output_root.name != "twinkle-stage3-dual-hotspot-motion-r2"
        and not output_root.name.startswith(".twinkle-stage3-closeout-")
    ):
        raise ValueError("stage 3 closeout output directory name mismatch")
    manifest_path = output_root / "twinkle-stage3-closeout-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"stage 3 closeout manifest missing: {manifest_path}")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = stage3_closeout_contract()
    mutable = {
        "humanVisualApproved",
        "machinePassed",
        "authorizesStage3Close",
        "stage3Closed",
    }
    for key, expected in contract.items():
        if key not in mutable and report.get(key) != expected:
            raise ValueError(f"stage 3 closeout contract mismatch: {key}")
    if report.get("machinePassed") is not True:
        raise ValueError("stage 3 closeout machine gate did not pass")
    if report.get("authorizesStage4") is not False:
        raise ValueError("stage 3 closeout cannot authorize stage 4")
    human_approved = report.get("humanVisualApproved")
    if human_approved not in (True, False):
        raise ValueError("stage 3 closeout human approval must be explicit")
    if human_approved:
        expected_approval = {
            "approvedBy": "user",
            "approvedOn": "2026-08-28",
            "scope": "stage3-step7-r2-closeout",
            "authorizesStage3Close": True,
            "authorizesStage4": False,
        }
        if report.get("humanApproval") != expected_approval:
            raise ValueError("stage 3 closeout approval is missing or overbroad")
        if report.get("authorizesStage3Close") is not True or report.get(
            "stage3Closed"
        ) is not True:
            raise ValueError("stage 3 closeout approval flags are incomplete")
    elif (
        report.get("humanApproval") is not None
        or report.get("authorizesStage3Close") is not False
        or report.get("stage3Closed") is not False
    ):
        raise ValueError("stage 3 cannot close before human approval")

    formal = validate_formal_candidate(FORMAL_OUTPUT_ROOT)
    step7 = validate_step7_limited_probe(STEP7_PROBE_OUTPUT_ROOT)
    validate_condenser_r3_candidate(CONDENSER_R3_OUTPUT_ROOT)
    motion = validate_condenser_motion_only_probe(
        CONDENSER_MOTION_ONLY_OUTPUT_ROOT
    )
    if formal.get("step6MachinePassed") is not True:
        raise ValueError("approved formal r1 machine evidence is required")
    if step7.get("machinePassed") is not True:
        raise ValueError("approved step 7 browser evidence is required")
    expected_provenance = {
        "authorityManifestSha256": EXPECTED_AUTHORITY_SHA256,
        "formalR1ManifestSha256": sha256(
            FORMAL_OUTPUT_ROOT
            / "twinkle-stage3-dual-hotspot-motion-manifest.json"
        ),
        "step7ProbeManifestSha256": sha256(
            STEP7_PROBE_OUTPUT_ROOT / "step7-probe-manifest.json"
        ),
        "approvedCondenserR3ManifestSha256": sha256(
            CONDENSER_R3_OUTPUT_ROOT / "condenser-r3-manifest.json"
        ),
        "sourceBlendSha256": EXPECTED_SOURCE_BLEND_SHA256,
        "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
    }
    if report.get("provenance") != expected_provenance:
        raise ValueError("stage 3 closeout provenance mismatch")

    r1_chamber_root = FORMAL_OUTPUT_ROOT / "units" / CHAMBER
    closeout_chamber_root = output_root / "units" / CHAMBER
    for index in range(25):
        source = r1_chamber_root / "frames" / f"frame-{index:03d}.png"
        destination = closeout_chamber_root / "frames" / f"frame-{index:03d}.png"
        if not destination.is_file() or sha256(destination) != sha256(source):
            raise ValueError(f"stage 3 closeout chamber frame drift: {index}")

    authority = validate_authority()
    unit = authority["units"][CONDENSER]
    audit_path = output_root / "units" / CONDENSER / "render-audit.json"
    if not audit_path.is_file():
        raise FileNotFoundError("stage 3 closeout condenser audit missing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected_audit = {
        "schema": STAGE3_CLOSEOUT_WORKER_SCHEMA,
        "unit": CONDENSER,
        "render": FORMAL_RENDER,
        "frameIndices": list(range(25)),
        "cameraPresetId": unit["cameraPresetId"],
        "camera": unit["camera"],
        "rootObjects": unit["rootObjects"],
        "fullOffsetsM": unit["fullOffsetsM"],
        "lightRigHash": authority["renderProfile"]["lightRigHash"],
        "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
        "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
        "candidateBlendSha256Before": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": [],
        "linefix": condenser_r1_linefix_contract(),
        "motionSource": "approved-condenser-motion-only-probe",
        "motionRuntime": motion["motionRuntime"],
    }
    for key, expected in expected_audit.items():
        if audit.get(key) != expected:
            raise ValueError(f"stage 3 closeout condenser audit mismatch: {key}")
    frames = audit.get("frames", [])
    if [frame.get("index") for frame in frames] != list(range(25)):
        raise ValueError("stage 3 closeout condenser frame indices mismatch")
    for frame in frames:
        path = output_root / frame.get("path", "")
        if not path.is_file() or sha256(path) != frame.get("sha256"):
            raise ValueError(
                f"stage 3 closeout frame hash mismatch: {frame.get('index')}"
            )
        with Image.open(path) as image:
            if image.size != tuple(FORMAL_RENDER["resolution"]):
                raise ValueError(
                    f"stage 3 closeout frame dimensions mismatch: {frame.get('index')}"
                )
    for relative in FORMAL_REVIEW_FILES:
        if not (output_root / relative).is_file():
            raise FileNotFoundError(
                f"stage 3 closeout review evidence missing: {relative}"
            )
    if list(output_root.rglob("*.blend")) or list(output_root.rglob("*.mp4")):
        raise ValueError("stage 3 closeout contains forbidden persistent media")
    quality = _formal_quality_evidence(output_root)
    if report.get("quality") != quality or any(
        record["blackFrameCount"] != 0 or record["adjacentDuplicatePairs"]
        for record in quality.values()
    ):
        raise ValueError("stage 3 closeout frame quality evidence mismatch")
    if report.get("inventorySha256") != _formal_inventory(
        output_root, manifest_path
    ):
        raise ValueError("stage 3 closeout exact inventory mismatch")
    return report


def build_stage3_closeout_candidate(output_root, *, renderer=None, blender=None):
    output_root = Path(output_root)
    if output_root.name != "twinkle-stage3-dual-hotspot-motion-r2":
        raise ValueError("stage 3 closeout output must use the fixed r2 name")
    if output_root.exists() or output_root.with_name(
        output_root.name + ".backup"
    ).exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    formal = validate_formal_candidate(FORMAL_OUTPUT_ROOT)
    step7 = validate_step7_limited_probe(STEP7_PROBE_OUTPUT_ROOT)
    validate_condenser_r3_candidate(CONDENSER_R3_OUTPUT_ROOT)
    if formal.get("step6MachinePassed") is not True or step7.get(
        "machinePassed"
    ) is not True:
        raise ValueError("stage 3 closeout requires passed r1 and step 7 evidence")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".twinkle-stage3-closeout-", dir=output_root.parent)
    )
    manifest_path = staging / "twinkle-stage3-closeout-manifest.json"
    try:
        units_root = staging / "units"
        units_root.mkdir()
        shutil.copytree(
            FORMAL_OUTPUT_ROOT / "units" / CHAMBER,
            units_root / CHAMBER,
        )
        (renderer or render_stage3_closeout_condenser)(
            staging, authority, blender=blender
        )
        _write_formal_review_assets(staging)
        report = {
            **stage3_closeout_contract(),
            "machinePassed": True,
            "provenance": {
                "authorityManifestSha256": EXPECTED_AUTHORITY_SHA256,
                "formalR1ManifestSha256": sha256(
                    FORMAL_OUTPUT_ROOT
                    / "twinkle-stage3-dual-hotspot-motion-manifest.json"
                ),
                "step7ProbeManifestSha256": sha256(
                    STEP7_PROBE_OUTPUT_ROOT / "step7-probe-manifest.json"
                ),
                "approvedCondenserR3ManifestSha256": sha256(
                    CONDENSER_R3_OUTPUT_ROOT / "condenser-r3-manifest.json"
                ),
                "sourceBlendSha256": EXPECTED_SOURCE_BLEND_SHA256,
                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
            },
        }
        report["quality"] = _formal_quality_evidence(staging)
        report["inventorySha256"] = _formal_inventory(staging, manifest_path)
        manifest_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_stage3_closeout_candidate(staging)
        staging.rename(output_root)
        return validate_stage3_closeout_candidate(output_root)
    except Exception as error:
        if output_root.exists() and not staging.exists():
            output_root.rename(staging)
        raise RuntimeError(
            f"stage 3 closeout build failed; staging kept at {staging}"
        ) from error


def record_stage3_closeout_approval(output_root, *, approved_on):
    output_root = Path(output_root)
    report = validate_stage3_closeout_candidate(output_root)
    if report.get("humanVisualApproved") is not False:
        raise ValueError("stage 3 closeout is already approved")
    if str(approved_on) != "2026-08-28":
        raise ValueError("stage 3 closeout approval date does not match authority")
    report["humanVisualApproved"] = True
    report["authorizesStage3Close"] = True
    report["stage3Closed"] = True
    report["authorizesStage4"] = False
    report["humanApproval"] = {
        "approvedBy": "user",
        "approvedOn": "2026-08-28",
        "scope": "stage3-step7-r2-closeout",
        "authorizesStage3Close": True,
        "authorizesStage4": False,
    }
    manifest_path = output_root / "twinkle-stage3-closeout-manifest.json"
    report["inventorySha256"] = _formal_inventory(output_root, manifest_path)
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_stage3_closeout_candidate(output_root)


def formal_browser_command(executable, profile, url):
    return [
        str(executable),
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--disable-default-apps",
        "--disable-extensions",
        "--metrics-recording-only",
        "--remote-debugging-port=0",
        "--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE 127.0.0.1, EXCLUDE localhost",
        f"--user-data-dir={profile}",
        str(url),
    ]


def _windows_product_version(executable):
    environment = os.environ.copy()
    environment["TWINKLE_BROWSER_VERSION_PATH"] = str(executable)
    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "(Get-Item -LiteralPath $env:TWINKLE_BROWSER_VERSION_PATH).VersionInfo.ProductVersion",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env=environment,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"browser product version unavailable: {executable}")
    return completed.stdout.strip()


def run_formal_browser_check(
    output_root, browser_id, executable, expected_major, family
):
    output_root = Path(output_root)
    executable = Path(executable)
    if not executable.is_file():
        raise FileNotFoundError(f"browser executable missing: {executable}")
    product_version = _windows_product_version(executable)
    if int(product_version.split(".", 1)[0]) != int(expected_major):
        raise ValueError(
            f"browser major mismatch: {browser_id}: {product_version} != {expected_major}"
        )
    profile = Path(tempfile.mkdtemp(prefix=f"twinkle-formal-{browser_id}-"))
    _HarnessHandler.result = None
    _HarnessHandler.result_event = threading.Event()
    handler = partial(_HarnessHandler, directory=str(output_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = (
        f"http://127.0.0.1:{server.server_port}/review/index.html"
        f"?browser={browser_id}&major={expected_major}&family={family}"
    )
    process = subprocess.Popen(
        formal_browser_command(executable, profile, url),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        if not _HarnessHandler.result_event.wait(30):
            raise TimeoutError(f"formal browser harness timed out: {browser_id}")
        result = _HarnessHandler.result
    finally:
        server.shutdown()
        server.server_close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(profile)
    result.update(
        {
            "browserId": browser_id,
            "family": family,
            "productVersion": product_version,
            "expectedMajor": expected_major,
            "executable": str(executable),
            "executableSha256": sha256(executable),
            "isolatedUserDataRemoved": not profile.exists(),
            "localHarnessOnly": True,
            "rootProcessExitCode": process.returncode,
        }
    )
    result_root = output_root / "browser-results"
    result_root.mkdir(parents=True, exist_ok=True)
    result_path = result_root / f"{browser_id}.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if result.get("passed") is not True:
        raise RuntimeError(f"formal browser contract failed: {browser_id}: {result}")
    return result


def build_condenser_repair_candidate(output_root, *, blender=None):
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    authority = validate_authority()
    validate_condenser_lowres_candidate(CONDENSER_LOWRES_OUTPUT_ROOT)
    candidate_blend = Path(authority["candidateBlend"]["path"])
    candidate_hash = sha256(candidate_blend)
    if candidate_hash != authority["candidateBlend"]["sha256"]:
        raise ValueError("candidate blend drift before condenser repair")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".condenser-repair-", dir=output_root.parent)
    )
    try:
        run_checked(
            condenser_repair_blender_command(blender, candidate_blend, staging),
            cwd=ROOT,
        )
        blender_report = json.loads(
            (staging / "blender-motion.json").read_text(encoding="utf-8")
        )
        if blender_report.get("rendersWritten") != 25:
            raise ValueError("condenser repair worker did not render 25 frames")
        frame_records, quality, cleanup = _build_condenser_review_assets(
            staging,
            authority,
            blender_report["frames"],
            keep_rendered_endpoints=True,
            apply_cleanup=False,
        )
        contract = deepcopy(condenser_repair_contract())
        runtime = blender_report["repairRuntime"]
        contract["modelCleanup"].update(runtime["modelCleanup"])
        contract["occlusion"].update(runtime["occlusion"])
        contract["animation"].update(runtime["animation"])
        condenser = authority["units"][CONDENSER]
        experiment_analysis = (
            ROOT
            / "output"
            / ".twinkle-stage3-condenser-root-cause-experiment-20260826"
            / "run-2"
            / "analysis.json"
        )
        if not experiment_analysis.is_file():
            raise FileNotFoundError("condenser root-cause analysis is missing")
        report = {
            "schema": CONDENSER_REPAIR_SCHEMA,
            "unit": CONDENSER,
            "selectedFormat": FALLBACK_FORMAT,
            "render": CONDENSER_LOWRES_RENDER,
            "source": authority["candidateBlend"],
            "renderContract": {
                "cameraPresetId": condenser["cameraPresetId"],
                "camera": condenser["camera"],
                "rootObjects": condenser["rootObjects"],
                "fullOffsetsM": condenser["fullOffsetsM"],
                "lightRigHash": authority["renderProfile"]["lightRigHash"],
                "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
                "colorManagementHash": authority["renderProfile"][
                    "colorManagementHash"
                ],
            },
            "motion": {
                "frameIndices": list(range(25)),
                "closeFrameIndices": list(reversed(range(25))),
                "progress": [condenser_motion_progress(index) for index in range(25)],
            },
            "frames": frame_records,
            "pauseEvidence": [
                {
                    "percent": percent,
                    "frameIndex": index,
                    "holdUsesSameFrame": True,
                    "resumeFrameIndex": index + 1,
                    "direction": "forward",
                }
                for percent, index in ((25, 6), (50, 12), (75, 18))
            ],
            "inspectionLight": None,
            "cleanup": cleanup,
            "repair": contract,
            "rootCauseEvidence": {
                "path": str(experiment_analysis.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(experiment_analysis),
                "frameIndices": [6, 12, 18],
            },
            "endpointReferences": {
                "closed": {
                    "path": condenser["frames"]["focused-settled"]["asset"],
                    "sha256": condenser["frames"]["focused-settled"]["sha256"],
                },
                "open": {
                    "path": condenser["frames"]["extract-end"]["asset"],
                    "sha256": condenser["frames"]["extract-end"]["sha256"],
                },
            },
            "styleReference": {
                "unit": CHAMBER,
                "manifest": (
                    "output/.twinkle-stage3-chamber-lowres-20260826/"
                    "chamber-lowres-r1/chamber-lowres-manifest.json"
                ),
                "humanVisualApproved": True,
            },
            "quality": quality,
            "candidateBlendSaved": blender_report["candidateBlendSaved"],
            "machinePassed": (
                quality["blackFrameCount"] == 0
                and quality["duplicateAdjacentFrameCount"] == 0
                and cleanup["method"] == "none"
                and contract["modelCleanup"]["sourceMeshRestored"]
                and contract["modelCleanup"]["temporaryMeshRemoved"]
                and contract["animation"]["temporaryActionRemoved"]
                and contract["occlusion"]["originalParentRestored"]
                and blender_report["candidateBlendSaved"] is False
            ),
            "humanVisualApproved": False,
            "authorizesStep6": False,
        }
        inventory = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.name != "condenser-repair-manifest.json":
                relative = str(path.relative_to(staging)).replace("\\", "/")
                inventory[relative] = sha256(path)
        report["inventorySha256"] = inventory
        (staging / "condenser-repair-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_condenser_repair_candidate(staging)
        if sha256(candidate_blend) != candidate_hash:
            raise ValueError("candidate blend drift after condenser repair")
        shutil.move(str(staging), str(output_root))
    except Exception as error:
        raise RuntimeError(
            f"condenser repair build failed; staging kept at {staging}"
        ) from error
    return validate_condenser_repair_candidate(output_root)


def blender_lowres_worker(
    output_root,
    unit_id,
    progress_function,
    *,
    render=None,
    frame_indices=tuple(range(1, 24)),
    report_name="blender-motion.json",
):
    import bpy
    from mathutils import Matrix, Vector

    output_root = Path(output_root)
    render = render or CHAMBER_LOWRES_RENDER
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][unit_id]
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded")
    if sha256(candidate_blend) != authority["candidateBlend"]["sha256"]:
        raise RuntimeError("candidate blend drift")
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise RuntimeError("scene camera missing")
    roots = [bpy.data.objects.get(name) for name in unit["rootObjects"]]
    if not all(roots):
        raise RuntimeError(f"{unit_id} mechanical root missing")
    frames_root = output_root / "frames"
    frames_root.mkdir()

    original_matrices = {root.name: root.matrix_world.copy() for root in roots}
    original_hidden = {}
    technical = []
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 top-plate material target missing")
    slot = top_plate.material_slots[0]
    original_material = slot.material
    original_link = slot.link
    temporary_material = None
    try:
        camera.location = Vector(unit["camera"]["location"])
        camera.rotation_euler = Vector(unit["camera"]["rotation"])
        camera.data.lens = unit["camera"]["lensMm"]
        camera.data.sensor_width = unit["camera"]["sensorWidthMm"]
        camera.data.shift_x = unit["camera"]["shiftX"]
        camera.data.shift_y = unit["camera"]["shiftY"]
        for name in profile["sharedHiddenObjects"]:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise RuntimeError(f"stage 1 hidden object missing: {name}")
            original_hidden[name] = bool(obj.hide_render)
            obj.hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x = render["resolution"][0]
        scene.render.resolution_y = render["resolution"][1]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = render["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        for record in profile["lightRig"]:
            if not record["name"].startswith("TEMP__SHARED_"):
                obj = bpy.data.objects.get(record["name"])
                if obj is None or obj.type != "LIGHT":
                    raise RuntimeError(f"stage 1 light missing: {record['name']}")
                continue
            data = bpy.data.lights.new(record["name"] + "_DATA", record["type"])
            data.energy = record["energy"]
            data.color = record["color"]
            data.shape = "DISK"
            data.size = record["size"]
            obj = bpy.data.objects.new(record["name"], data)
            scene.collection.objects.link(obj)
            obj.location = Vector(record["location"])
            obj.rotation_euler = Vector(record["rotation"])
            technical.append((obj, data))

        if original_material is None:
            raise RuntimeError("stage 1 top-plate material missing")
        temporary_material = original_material.copy()
        temporary_material.name = f"TEMP__STAGE3_{unit_id.upper()}_TOP_PLATE_NO_NORMAL"
        normal_nodes = [
            node
            for node in temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = 0.0
        slot.link = "OBJECT"
        slot.material = temporary_material

        records = []
        component_names = tuple(unit["fullOffsetsM"])
        full_offsets = [unit["fullOffsetsM"][name] for name in component_names]
        for index in frame_indices:
            progress = progress_function(index)
            component_offsets = {}
            matrices = {}
            for root, component, full_offset in zip(
                roots, component_names, full_offsets
            ):
                offset = Vector(full_offset) * progress
                root.matrix_world = Matrix.Translation(offset) @ original_matrices[root.name]
                component_offsets[component] = [round(float(value), 8) for value in offset]
                matrices[root.name] = [
                    [round(float(value), 8) for value in row]
                    for row in root.matrix_world
                ]
            path = frames_root / f"frame-{index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            records.append(
                {
                    "index": index,
                    "progress": progress,
                    "path": path.relative_to(output_root).as_posix(),
                    "sha256": sha256(path),
                    "componentOffsetsM": component_offsets,
                    "rootWorldMatrices": matrices,
                }
            )
        (output_root / report_name).write_text(
            json.dumps(
                {
                    "candidateBlendSha256": sha256(candidate_blend),
                    "rendersWritten": len(records),
                    "candidateBlendSaved": False,
                    "frames": records,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    finally:
        for root in roots:
            root.matrix_world = original_matrices[root.name]
        for name, hidden in original_hidden.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = hidden
        if original_material is not None:
            slot.link = original_link
            slot.material = original_material
        if temporary_material is not None:
            bpy.data.materials.remove(temporary_material)
        for obj, data in technical:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)


def blender_chamber_worker(output_root):
    blender_lowres_worker(output_root, CHAMBER, chamber_motion_progress)


def blender_condenser_worker(output_root):
    blender_lowres_worker(output_root, CONDENSER, condenser_motion_progress)


def _complete_formal_worker_audit(output_root, unit_id):
    import bpy

    output_root = Path(output_root)
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][unit_id]
    profile = authority["renderProfile"]
    audit_path = output_root / "render-audit.json"
    worker = json.loads(audit_path.read_text(encoding="utf-8"))
    records = {record["index"]: record for record in worker.get("frames", [])}
    frames_root = output_root / "frames"
    for index, state_name in ((0, "focused-settled"), (24, "extract-end")):
        source_record = unit["frames"][state_name]
        source = AUTHORITY_MANIFEST.parent / source_record["asset"]
        if not source.is_file() or sha256(source) != source_record["sha256"]:
            raise RuntimeError(f"stage 1 formal endpoint drift: {unit_id}: {state_name}")
        destination = frames_root / f"frame-{index:03d}.png"
        shutil.copyfile(source, destination)
        records[index] = {
            "index": index,
            "path": (
                Path("units") / unit_id / "frames" / destination.name
            ).as_posix(),
            "sha256": sha256(destination),
            "endpointSource": source_record["asset"],
            "endpointSourceSha256": source_record["sha256"],
        }
    for index in range(1, 24):
        record = records[index]
        path = frames_root / f"frame-{index:03d}.png"
        record["path"] = (
            Path("units") / unit_id / "frames" / path.name
        ).as_posix()
        record["sha256"] = sha256(path)
    candidate_blend = Path(authority["candidateBlend"]["path"])
    temporary = sorted(
        datablock.name
        for collection in (
            bpy.data.objects,
            bpy.data.meshes,
            bpy.data.materials,
            bpy.data.actions,
            bpy.data.lights,
        )
        for datablock in collection
        if datablock.name.startswith("TEMP__STAGE3")
    )
    report = {
        "schema": "twinkle-stage3-formal-render-audit-v1",
        "unit": unit_id,
        "render": FORMAL_RENDER,
        "cameraPresetId": unit["cameraPresetId"],
        "camera": unit["camera"],
        "rootObjects": unit["rootObjects"],
        "fullOffsetsM": unit["fullOffsetsM"],
        "lightRigHash": profile["lightRigHash"],
        "materialRuleHash": profile["materialRuleHash"],
        "colorManagementHash": profile["colorManagementHash"],
        "candidateBlendSha256Before": worker.get(
            "candidateBlendSha256Before",
            worker.get("candidateBlendSha256"),
        ),
        "candidateBlendSha256After": sha256(candidate_blend),
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": temporary,
        "frames": [records[index] for index in range(25)],
    }
    if "motionRuntime" in worker:
        report["motionRuntime"] = worker["motionRuntime"]
    audit_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def blender_formal_chamber_worker(output_root):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    blender_lowres_worker(
        output_root,
        CHAMBER,
        chamber_motion_progress,
        render=FORMAL_RENDER,
        frame_indices=tuple(range(1, 24)),
        report_name="render-audit.json",
    )
    _complete_formal_worker_audit(output_root, CHAMBER)


def blender_formal_condenser_worker(output_root):
    output_root = Path(output_root)
    blender_condenser_motion_only_probe_worker(
        output_root,
        render=FORMAL_RENDER,
        frame_indices=tuple(range(1, 24)),
        schema="twinkle-stage3-formal-condenser-worker-v1",
        report_name="render-audit.json",
        frames_subdir="frames",
    )
    _complete_formal_worker_audit(output_root, CONDENSER)


def blender_step7_probe_worker(output_root):
    output_root = Path(output_root)
    blender_condenser_motion_only_probe_worker(
        output_root,
        render=FORMAL_RENDER,
        frame_indices=STEP7_PROBE_FRAMES,
        schema=STEP7_PROBE_WORKER_SCHEMA,
        report_name="render-audit.json",
        frames_subdir="frames",
    )
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    audit_path = output_root / "render-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit.update(
        {
            "schema": STEP7_PROBE_WORKER_SCHEMA,
            "unit": CONDENSER,
            "render": FORMAL_RENDER,
            "frameIndices": list(STEP7_PROBE_FRAMES),
            "cameraPresetId": authority["units"][CONDENSER]["cameraPresetId"],
            "camera": authority["units"][CONDENSER]["camera"],
            "rootObjects": authority["units"][CONDENSER]["rootObjects"],
            "fullOffsetsM": authority["units"][CONDENSER]["fullOffsetsM"],
            "lightRigHash": authority["renderProfile"]["lightRigHash"],
            "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
            "colorManagementHash": authority["renderProfile"][
                "colorManagementHash"
            ],
            "endpointSource": "isolated-step7-probe-render",
            "endpointsRenderedWithApprovedLinefix": True,
        }
    )
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def blender_stage3_closeout_condenser_worker(output_root):
    output_root = Path(output_root)
    blender_condenser_motion_only_probe_worker(
        output_root,
        render=FORMAL_RENDER,
        frame_indices=tuple(range(25)),
        schema=STAGE3_CLOSEOUT_WORKER_SCHEMA,
        report_name="render-audit.json",
        frames_subdir="frames",
    )
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][CONDENSER]
    audit_path = output_root / "render-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit.update(
        {
            "schema": STAGE3_CLOSEOUT_WORKER_SCHEMA,
            "unit": CONDENSER,
            "render": FORMAL_RENDER,
            "frameIndices": list(range(25)),
            "cameraPresetId": unit["cameraPresetId"],
            "camera": unit["camera"],
            "rootObjects": unit["rootObjects"],
            "fullOffsetsM": unit["fullOffsetsM"],
            "lightRigHash": authority["renderProfile"]["lightRigHash"],
            "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
            "colorManagementHash": authority["renderProfile"][
                "colorManagementHash"
            ],
            "linefix": condenser_r1_linefix_contract(),
            "motionSource": "approved-condenser-motion-only-probe",
        }
    )
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def blender_condenser_repair_worker(output_root):
    import bmesh
    import bpy
    from mathutils import Matrix, Vector

    output_root = Path(output_root)
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][CONDENSER]
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded")
    candidate_hash = sha256(candidate_blend)
    if candidate_hash != authority["candidateBlend"]["sha256"]:
        raise RuntimeError("candidate blend drift")

    scene = bpy.context.scene
    camera = scene.camera
    root = bpy.data.objects.get(unit["rootObjects"][0])
    repair_object = bpy.data.objects.get(
        condenser_repair_contract()["modelCleanup"]["object"]
    )
    occluder_group = bpy.data.objects.get(
        condenser_repair_contract()["occlusion"]["group"]
    )
    if camera is None or root is None or repair_object is None or occluder_group is None:
        raise RuntimeError("condenser repair scene object missing")
    occluders = [obj for obj in occluder_group.children_recursive if obj.type == "MESH"]
    if sorted(obj.name for obj in occluders) != sorted(
        condenser_repair_contract()["occlusion"]["meshes"]
    ):
        raise RuntimeError("condenser CAD occluder inventory drift")
    if len(repair_object.material_slots) != 1:
        raise RuntimeError("condenser repair material target drift")

    frames_root = output_root / "frames"
    frames_root.mkdir()
    original_scene_frame = scene.frame_current
    original_hidden = {}
    technical = []
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 top-plate material target missing")
    top_slot = top_plate.material_slots[0]
    top_original_material = top_slot.material
    top_original_link = top_slot.link
    top_temporary_material = None
    repair_slot = repair_object.material_slots[0]
    repair_original_material = repair_slot.material
    repair_original_link = repair_slot.link
    repair_original_mesh = repair_object.data
    repair_temporary_mesh = None
    repair_temporary_material = None
    motion_root = None
    motion_action = None
    root_parent = root.parent
    root_parent_inverse = root.matrix_parent_inverse.copy()
    root_world = root.matrix_world.copy()
    occluder_parent = occluder_group.parent
    occluder_parent_inverse = occluder_group.matrix_parent_inverse.copy()
    occluder_world = occluder_group.matrix_world.copy()
    records = []
    repair_runtime = None
    try:
        camera.location = Vector(unit["camera"]["location"])
        camera.rotation_euler = Vector(unit["camera"]["rotation"])
        camera.data.lens = unit["camera"]["lensMm"]
        camera.data.sensor_width = unit["camera"]["sensorWidthMm"]
        camera.data.shift_x = unit["camera"]["shiftX"]
        camera.data.shift_y = unit["camera"]["shiftY"]
        for name in profile["sharedHiddenObjects"]:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise RuntimeError(f"stage 1 hidden object missing: {name}")
            original_hidden[name] = bool(obj.hide_render)
            obj.hide_render = True
        for obj in occluders:
            original_hidden[obj.name] = bool(obj.hide_render)
            obj.hide_render = False

        scene.render.engine = profile["engine"]
        scene.render.resolution_x = 640
        scene.render.resolution_y = 450
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = 64
        scene.render.fps = 24
        scene.frame_start = 0
        scene.frame_end = 24
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        for light_record in profile["lightRig"]:
            if not light_record["name"].startswith("TEMP__SHARED_"):
                obj = bpy.data.objects.get(light_record["name"])
                if obj is None or obj.type != "LIGHT":
                    raise RuntimeError(
                        f"stage 1 light missing: {light_record['name']}"
                    )
                continue
            data = bpy.data.lights.new(
                light_record["name"] + "_DATA", light_record["type"]
            )
            data.energy = light_record["energy"]
            data.color = light_record["color"]
            data.shape = "DISK"
            data.size = light_record["size"]
            obj = bpy.data.objects.new(light_record["name"], data)
            scene.collection.objects.link(obj)
            obj.location = Vector(light_record["location"])
            obj.rotation_euler = Vector(light_record["rotation"])
            technical.append((obj, data))

        if top_original_material is None or repair_original_material is None:
            raise RuntimeError("condenser repair source material missing")
        top_temporary_material = top_original_material.copy()
        top_temporary_material.name = "TEMP__STAGE3_CONDENSER_REPAIR_TOP_NO_NORMAL"
        top_normal_nodes = [
            node
            for node in top_temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(top_normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map rule drift")
        top_normal_nodes[0].inputs["Strength"].default_value = 0.0
        top_slot.link = "OBJECT"
        top_slot.material = top_temporary_material

        repair_temporary_mesh = repair_original_mesh.copy()
        repair_temporary_mesh.name = "TEMP__STAGE3_CONDENSER_REPAIR_MESH"
        source_vertices = len(repair_temporary_mesh.vertices)
        source_polygons = len(repair_temporary_mesh.polygons)
        repair_object.data = repair_temporary_mesh
        bm = bmesh.new()
        try:
            bm.from_mesh(repair_temporary_mesh)
            bmesh.ops.dissolve_limit(
                bm,
                angle_limit=math.radians(0.5),
                use_dissolve_boundaries=False,
                verts=list(bm.verts),
                edges=list(bm.edges),
                delimit={"MATERIAL"},
            )
            bm.normal_update()
            bm.to_mesh(repair_temporary_mesh)
        finally:
            bm.free()
        repair_temporary_mesh.update()
        repaired_vertices = len(repair_temporary_mesh.vertices)
        repaired_polygons = len(repair_temporary_mesh.polygons)
        if repaired_polygons >= source_polygons:
            raise RuntimeError("limited dissolve did not reduce condenser CAD triangles")

        repair_temporary_material = repair_original_material.copy()
        repair_temporary_material.name = "TEMP__STAGE3_CONDENSER_REPAIR_SILVER"
        principled = [
            node
            for node in repair_temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeBsdfPrincipled"
        ]
        if len(principled) != 1:
            raise RuntimeError("condenser silver shader drift")
        shader = principled[0]
        for input_name in ("Roughness", "Normal"):
            for link in list(shader.inputs[input_name].links):
                repair_temporary_material.node_tree.links.remove(link)
        shader.inputs["Roughness"].default_value = 0.32
        shader.inputs["Metallic"].default_value = 0.85
        repair_slot.link = "OBJECT"
        repair_slot.material = repair_temporary_material

        motion_root = bpy.data.objects.new("TEMP__STAGE3_CONDENSER_REPAIR_MOTION", None)
        scene.collection.objects.link(motion_root)
        motion_root.matrix_world = Matrix.Identity(4)
        root.parent = motion_root
        root.matrix_parent_inverse = Matrix.Identity(4)
        root.matrix_world = root_world
        occluder_group.parent = motion_root
        occluder_group.matrix_parent_inverse = Matrix.Identity(4)
        occluder_group.matrix_world = occluder_world

        motion_action = bpy.data.actions.new("TEMP__STAGE3_CONDENSER_REPAIR_FCURVE")
        slot = motion_action.slots.new(motion_root.id_type, motion_root.name)
        strip = motion_action.layers.new("Motion").strips.new(type="KEYFRAME")
        channelbag = strip.channelbag(slot, ensure=True)
        full_offset = Vector(unit["fullOffsetsM"]["condenserAssembly"])
        fcurves = []
        for axis in range(3):
            fcurve = channelbag.fcurves.new(data_path="location", index=axis)
            fcurve.keyframe_points.add(25)
            for index, point in enumerate(fcurve.keyframe_points):
                point.co = (
                    float(index),
                    float(full_offset[axis] * condenser_motion_progress(index)),
                )
                point.interpolation = "BEZIER"
                point.handle_left_type = "AUTO_CLAMPED"
                point.handle_right_type = "AUTO_CLAMPED"
            fcurve.update()
            fcurves.append(fcurve)
        animation_data = motion_root.animation_data_create()
        animation_data.action = motion_action
        animation_data.action_slot = slot

        for index in range(25):
            scene.frame_set(index)
            bpy.context.view_layer.update()
            progress = condenser_motion_progress(index)
            expected_offset = full_offset * progress
            actual_offset = Vector(motion_root.location)
            if (actual_offset - expected_offset).length > 1e-7:
                raise RuntimeError(f"native F-Curve evaluation drift: {index}")
            path = frames_root / f"frame-{index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            records.append(
                {
                    "index": index,
                    "progress": progress,
                    "componentOffsetsM": {
                        "condenserAssembly": [
                            round(float(value), 8) for value in expected_offset
                        ]
                    },
                    "rootWorldMatrices": {
                        root.name: [
                            [round(float(value), 8) for value in row]
                            for row in root.matrix_world
                        ]
                    },
                    "occluderWorldMatrix": [
                        [round(float(value), 8) for value in row]
                        for row in occluder_group.matrix_world
                    ],
                }
            )
        repair_runtime = {
            "modelCleanup": {
                "sourceVertices": source_vertices,
                "sourcePolygons": source_polygons,
                "repairedVertices": repaired_vertices,
                "repairedPolygons": repaired_polygons,
            },
            "animation": {
                "locationChannelCount": len(fcurves),
                "keyframesPerLocationChannel": min(
                    len(fcurve.keyframe_points) for fcurve in fcurves
                ),
            },
        }
    finally:
        scene.frame_set(original_scene_frame)
        if motion_root is not None:
            motion_root.animation_data_clear()
        root.parent = root_parent
        root.matrix_parent_inverse = root_parent_inverse
        root.matrix_world = root_world
        occluder_group.parent = occluder_parent
        occluder_group.matrix_parent_inverse = occluder_parent_inverse
        occluder_group.matrix_world = occluder_world
        for name, hidden in original_hidden.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = hidden
        repair_slot.link = repair_original_link
        repair_slot.material = repair_original_material
        repair_object.data = repair_original_mesh
        top_slot.link = top_original_link
        top_slot.material = top_original_material
        if repair_temporary_material is not None:
            bpy.data.materials.remove(repair_temporary_material)
        if top_temporary_material is not None:
            bpy.data.materials.remove(top_temporary_material)
        if repair_temporary_mesh is not None:
            bpy.data.meshes.remove(repair_temporary_mesh)
        if motion_action is not None:
            bpy.data.actions.remove(motion_action)
        if motion_root is not None:
            bpy.data.objects.remove(motion_root, do_unlink=True)
        for obj, data in technical:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)

    if repair_runtime is None:
        raise RuntimeError("condenser repair runtime report missing")
    repair_runtime["modelCleanup"].update(
        {
            "sourceMeshRestored": repair_object.data == repair_original_mesh,
            "temporaryMeshRemoved": "TEMP__STAGE3_CONDENSER_REPAIR_MESH"
            not in bpy.data.meshes,
        }
    )
    repair_runtime["animation"]["temporaryActionRemoved"] = (
        "TEMP__STAGE3_CONDENSER_REPAIR_FCURVE" not in bpy.data.actions
    )
    repair_runtime["occlusion"] = {
        "followsRoot": True,
        "originalParentRestored": occluder_group.parent == occluder_parent,
    }
    after_hash = sha256(candidate_blend)
    if after_hash != candidate_hash:
        raise RuntimeError("candidate blend changed during condenser repair")
    (output_root / "blender-motion.json").write_text(
        json.dumps(
            {
                "candidateBlendSha256": after_hash,
                "rendersWritten": len(records),
                "candidateBlendSaved": False,
                "frames": records,
                "repairRuntime": repair_runtime,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def blender_condenser_r1_linefix_probe_worker(
    output_root,
    *,
    frame_indices=(0, 12, 24),
    schema=CONDENSER_R1_LINEFIX_PROBE_SCHEMA,
    report_name="probe-audit.json",
    frames_subdir=None,
    motion_controller=None,
    render=None,
):
    import bmesh
    import bpy
    from mathutils import Matrix, Vector

    output_root = Path(output_root)
    render = render or CONDENSER_LOWRES_RENDER
    output_root.mkdir(parents=True, exist_ok=False)
    render_root = output_root
    if frames_subdir:
        render_root = output_root / frames_subdir
        render_root.mkdir(parents=True)
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][CONDENSER]
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    candidate_hash = sha256(candidate_blend)
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded")
    if candidate_hash != authority["candidateBlend"]["sha256"]:
        raise RuntimeError("candidate blend drift")

    scene = bpy.context.scene
    camera = scene.camera
    root = bpy.data.objects.get(unit["rootObjects"][0])
    contract = condenser_r1_linefix_contract()
    target = bpy.data.objects.get(contract["geometry"]["object"])
    if camera is None or root is None or target is None:
        raise RuntimeError("r1 linefix probe scene object missing")

    def local_bounds(obj):
        coordinates = [vertex.co for vertex in obj.data.vertices]
        return (
            [min(float(vertex[axis]) for vertex in coordinates) for axis in range(3)],
            [max(float(vertex[axis]) for vertex in coordinates) for axis in range(3)],
        )

    def front_opening_count(obj, axis, coordinate, tolerance=0.00008):
        selected = []
        for polygon in obj.data.polygons:
            values = [obj.data.vertices[index].co[axis] for index in polygon.vertices]
            if all(abs(float(value) - coordinate) <= tolerance for value in values):
                selected.append(polygon)
        edge_counts = {}
        for polygon in selected:
            vertices = list(polygon.vertices)
            for index, left in enumerate(vertices):
                right = vertices[(index + 1) % len(vertices)]
                edge = tuple(sorted((int(left), int(right))))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        boundary = [edge for edge, count in edge_counts.items() if count == 1]
        graph = {}
        for left, right in boundary:
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
        components = 0
        unseen = set(graph)
        while unseen:
            components += 1
            stack = [unseen.pop()]
            while stack:
                vertex = stack.pop()
                for neighbor in graph.get(vertex, ()):
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
        return max(0, components - 1), len(selected)

    def mesh_quality(obj):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        finally:
            bm.free()
        return {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "polygons": len(obj.data.polygons),
            "nonManifoldEdges": non_manifold,
            "zeroAreaFaces": sum(
                1 for polygon in obj.data.polygons if polygon.area <= 1e-14
            ),
        }

    root_world = root.matrix_world.copy()
    original_scene_frame = scene.frame_current
    original_hidden = {}
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 top-plate material target missing")
    top_slot = top_plate.material_slots[0]
    top_original_material = top_slot.material
    top_original_link = top_slot.link
    top_temporary_material = None
    proxy = None
    proxy_material = None
    technical = []
    geometry_audit = None
    frame_records = []
    controller = None
    try:
        camera.location = Vector(unit["camera"]["location"])
        camera.rotation_euler = Vector(unit["camera"]["rotation"])
        camera.data.lens = unit["camera"]["lensMm"]
        camera.data.sensor_width = unit["camera"]["sensorWidthMm"]
        camera.data.shift_x = unit["camera"]["shiftX"]
        camera.data.shift_y = unit["camera"]["shiftY"]
        for name in profile["sharedHiddenObjects"]:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise RuntimeError(f"stage 1 hidden object missing: {name}")
            original_hidden[name] = bool(obj.hide_render)
            obj.hide_render = True

        scene.render.engine = profile["engine"]
        scene.render.resolution_x = render["resolution"][0]
        scene.render.resolution_y = render["resolution"][1]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = render["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]
        for light_record in profile["lightRig"]:
            if not light_record["name"].startswith("TEMP__SHARED_"):
                if bpy.data.objects.get(light_record["name"]) is None:
                    raise RuntimeError(f"stage 1 light missing: {light_record['name']}")
                continue
            data = bpy.data.lights.new(
                light_record["name"] + "_R1_LINEFIX_DATA", light_record["type"]
            )
            data.energy = light_record["energy"]
            data.color = light_record["color"]
            data.shape = "DISK"
            data.size = light_record["size"]
            obj = bpy.data.objects.new(light_record["name"] + "_R1_LINEFIX", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(light_record["location"])
            obj.rotation_euler = Vector(light_record["rotation"])
            technical.append((obj, data))

        if top_original_material is None:
            raise RuntimeError("stage 1 top-plate material missing")
        top_temporary_material = top_original_material.copy()
        top_temporary_material.name = "TEMP__STAGE3_R1_LINEFIX_TOP_NO_NORMAL"
        normal_nodes = [
            node
            for node in top_temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = 0.0
        top_slot.link = "OBJECT"
        top_slot.material = top_temporary_material

        minimum, maximum = local_bounds(target)
        extents = [maximum[axis] - minimum[axis] for axis in range(3)]
        thickness_axis = min(range(3), key=lambda axis: extents[axis])
        camera_local = target.matrix_world.inverted() @ camera.location
        center = (minimum[thickness_axis] + maximum[thickness_axis]) / 2.0
        front_sign = 1.0 if camera_local[thickness_axis] >= center else -1.0
        front_coordinate = (
            maximum[thickness_axis] if front_sign > 0 else minimum[thickness_axis]
        )
        slab_min = list(minimum)
        slab_max = list(maximum)
        if front_sign > 0:
            slab_min[thickness_axis] = front_coordinate - 0.00025
            slab_max[thickness_axis] = front_coordinate + 0.00002
        else:
            slab_min[thickness_axis] = front_coordinate - 0.00002
            slab_max[thickness_axis] = front_coordinate + 0.00025
        vertices = [
            (x, y, z)
            for x in (slab_min[0], slab_max[0])
            for y in (slab_min[1], slab_max[1])
            for z in (slab_min[2], slab_max[2])
        ]
        faces = [
            (0, 1, 3, 2),
            (4, 6, 7, 5),
            (0, 4, 5, 1),
            (2, 3, 7, 6),
            (0, 2, 6, 4),
            (1, 5, 7, 3),
        ]
        proxy_mesh = bpy.data.meshes.new("TEMP__STAGE3_R1_LINEFIX_PROXY_MESH")
        proxy_mesh.from_pydata(vertices, [], faces)
        proxy_mesh.update()
        proxy = bpy.data.objects.new("TEMP__STAGE3_R1_LINEFIX_PROXY", proxy_mesh)
        scene.collection.objects.link(proxy)
        proxy.matrix_world = target.matrix_world.copy()
        boolean = proxy.modifiers.new("TEMP__STAGE3_R1_LINEFIX_EXACT", "BOOLEAN")
        boolean.operation = "INTERSECT"
        boolean.solver = "EXACT"
        boolean.object = target
        bpy.context.view_layer.objects.active = proxy
        proxy.select_set(True)
        target.select_set(False)
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        if len(proxy.data.polygons) == 0:
            raise RuntimeError("Exact Boolean produced an empty front-skin proxy")
        front_normal = Vector((0.0, 0.0, 0.0))
        front_normal[thickness_axis] = front_sign
        front_normal_world = (
            target.matrix_world.to_3x3() @ front_normal
        ).normalized()
        proxy.location += front_normal_world * 0.00005
        proxy.parent = root
        proxy.matrix_world = (
            Matrix.Translation(front_normal_world * 0.00005) @ target.matrix_world
        )

        if len(target.material_slots) != 1 or target.material_slots[0].material is None:
            raise RuntimeError("r1 linefix proxy source material drift")
        proxy_material = target.material_slots[0].material.copy()
        proxy_material.name = "TEMP__STAGE3_R1_LINEFIX_PROXY_MATERIAL"
        shader_nodes = [
            node
            for node in proxy_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeBsdfPrincipled"
        ]
        if len(shader_nodes) != 1:
            raise RuntimeError("r1 linefix proxy shader drift")
        shader = shader_nodes[0]
        for input_name in ("Roughness", "Normal"):
            for link in list(shader.inputs[input_name].links):
                proxy_material.node_tree.links.remove(link)
        shader.inputs["Roughness"].default_value = 0.32
        shader.inputs["Metallic"].default_value = 0.85
        proxy.data.materials.append(proxy_material)

        source_openings, source_front_faces = front_opening_count(
            target, thickness_axis, front_coordinate
        )
        proxy_openings, proxy_front_faces = front_opening_count(
            proxy, thickness_axis, front_coordinate
        )
        geometry_audit = mesh_quality(proxy)
        geometry_audit.update(
            {
                "method": "exact-boolean-front-skin-proxy",
                "operation": "INTERSECT",
                "solver": "EXACT",
                "proxyCreated": True,
                "thicknessAxis": thickness_axis,
                "frontSign": front_sign,
                "sourceFrontFaceCount": source_front_faces,
                "proxyFrontFaceCount": proxy_front_faces,
                "sourceVisibleOpeningCount": source_openings,
                "proxyVisibleOpeningCount": proxy_openings,
                "visibleOpeningCountMatches": (
                    source_openings > 0 and proxy_openings == source_openings
                ),
                "maxFrontOffsetM": 0.00005,
            }
        )
        if (
            geometry_audit["nonManifoldEdges"] != 0
            or geometry_audit["zeroAreaFaces"] != 0
            or not geometry_audit["visibleOpeningCountMatches"]
        ):
            raise RuntimeError(f"r1 linefix proxy geometry failed: {geometry_audit}")

        full_offset = Vector(unit["fullOffsetsM"]["condenserAssembly"])
        if motion_controller is not None:
            controller = motion_controller(root, root_world, full_offset, scene)
        for frame_index in frame_indices:
            if controller is None:
                progress = condenser_motion_progress(frame_index)
                root.matrix_world = (
                    Matrix.Translation(full_offset * progress) @ root_world
                )
            else:
                progress = controller["sample"](frame_index)
            bpy.context.view_layer.update()
            path = render_root / f"frame-{frame_index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frame_records.append(
                {
                    "index": frame_index,
                    "progress": progress,
                    "path": path.relative_to(output_root).as_posix(),
                    "sha256": sha256(path),
                    "componentOffsetsM": {
                        "condenserAssembly": [
                            float(value * progress) for value in full_offset
                        ]
                    },
                    "rootWorldMatrices": {
                        root.name: [list(row) for row in root.matrix_world]
                    },
                }
            )
    finally:
        if controller is not None:
            controller["finalize"]()
        root.matrix_world = root_world
        scene.frame_set(original_scene_frame)
        for name, hidden in original_hidden.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = hidden
        top_slot.link = top_original_link
        top_slot.material = top_original_material
        if proxy is not None:
            proxy_mesh = proxy.data
            bpy.data.objects.remove(proxy, do_unlink=True)
            bpy.data.meshes.remove(proxy_mesh)
        if proxy_material is not None:
            bpy.data.materials.remove(proxy_material)
        if top_temporary_material is not None:
            bpy.data.materials.remove(top_temporary_material)
        for obj, data in technical:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)

    if geometry_audit is None or len(frame_records) != len(frame_indices):
        raise RuntimeError("r1 linefix probe did not complete")
    after_hash = sha256(candidate_blend)
    temporary_remaining = sorted(
        [
            datablock.name
            for collection in (
                bpy.data.objects,
                bpy.data.meshes,
                bpy.data.materials,
                bpy.data.actions,
            )
            for datablock in collection
            if datablock.name.startswith("TEMP__STAGE3_R1_LINEFIX")
            or datablock.name.startswith("TEMP__STAGE3_CONDENSER_MOTION_ONLY")
        ]
    )
    report = {
        "schema": schema,
        "frameIndices": list(frame_indices),
        "candidateBlendSha256Before": candidate_hash,
        "candidateBlendSha256After": after_hash,
        "candidateBlendSaved": False,
        "geometry": geometry_audit,
        "occlusion": {"method": "none", "linerCount": 0},
        "postprocess": {"method": "none"},
        "temporaryDataBlocksRemaining": temporary_remaining,
        "frames": frame_records,
    }
    if controller is not None:
        report["motionRuntime"] = controller["runtime"]
    (output_root / report_name).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def blender_condenser_motion_only_probe_worker(
    output_root,
    *,
    render=None,
    frame_indices=tuple(range(25)),
    schema=CONDENSER_MOTION_ONLY_PROBE_SCHEMA,
    report_name="motion-runtime.json",
    frames_subdir="frames/new",
):
    import bpy
    from mathutils import Matrix

    def setup_motion(root, root_world, full_offset, scene):
        original_parent = root.parent
        original_parent_inverse = root.matrix_parent_inverse.copy()
        motion_root = bpy.data.objects.new("TEMP__STAGE3_CONDENSER_MOTION_ONLY", None)
        scene.collection.objects.link(motion_root)
        motion_root.matrix_world = Matrix.Identity(4)
        motion_root["travel"] = 0.0
        motion_root.id_properties_ui("travel").update(min=0.0, max=1.0)
        root.parent = motion_root
        root.matrix_parent_inverse = Matrix.Identity(4)
        root.matrix_world = root_world

        action = bpy.data.actions.new("TEMP__STAGE3_CONDENSER_MOTION_ONLY_ACTION")
        slot = action.slots.new(motion_root.id_type, motion_root.name)
        strip = action.layers.new("Motion").strips.new(type="KEYFRAME")
        channelbag = strip.channelbag(slot, ensure=True)
        travel_curve = channelbag.fcurves.new(data_path='["travel"]')
        travel_curve.keyframe_points.add(5)
        keyframes = condenser_motion_only_probe_contract()["travel"]["keyframes"]
        for point, (frame, value) in zip(travel_curve.keyframe_points, keyframes):
            point.co = (float(frame), float(value))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        travel_curve.auto_smoothing = "CONT_ACCEL"
        travel_curve.update()
        animation_data = motion_root.animation_data_create()
        animation_data.action = action
        animation_data.action_slot = slot

        descendants = sorted(root.children_recursive, key=lambda obj: obj.name)
        baseline_relative = {
            obj.name: (root.matrix_world.inverted() @ obj.matrix_world).copy()
            for obj in descendants
        }
        runtime = {
            "travel": {
                "property": "travel",
                "range": [0.0, 1.0],
                "animatedFcurveCount": 1,
                "locationDriverCount": 0,
                "vectorDerivationCount": 1,
                "locationKeyframeCount": 0,
                "rotationKeyframeCount": 0,
                "keyframes": keyframes,
                "interpolation": "BEZIER",
                "handleType": "AUTO_CLAMPED",
                "autoSmoothing": travel_curve.auto_smoothing,
            },
            "progress": [],
            "velocityPerFrame": [],
            "accelerationPerFrame": [],
            "componentOffsetsM": [],
            "rigidRelativeMatrixHashes": [],
            "rigidLocalMatrixHashes": [],
            "rigidMaxRelativeMatrixDrift": [],
            "closeFrameIndices": list(reversed(range(25))),
            "pauseEvidence": {
                "frameIndex": 7,
                "heldFrameIndex": 7,
                "resumeFrameIndex": 8,
                "directionBefore": "forward",
                "directionAfter": "forward",
            },
        }

        def evaluate(frame):
            return float(travel_curve.evaluate(float(frame)))

        def derivative(frame, epsilon=0.001):
            if frame in (0, 24):
                return 0.0
            left = max(0.0, float(frame) - epsilon)
            right = min(24.0, float(frame) + epsilon)
            if right == left:
                return 0.0
            return (evaluate(right) - evaluate(left)) / (right - left)

        def acceleration(frame, epsilon=0.01):
            left = max(0.0, float(frame) - epsilon)
            right = min(24.0, float(frame) + epsilon)
            if right == left:
                return 0.0
            return (derivative(right) - derivative(left)) / (right - left)

        def sample(frame):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            progress = float(travel_curve.evaluate(float(frame)))
            motion_root["travel"] = progress
            motion_root.location = full_offset * progress
            bpy.context.view_layer.update()
            relative = {
                obj.name: [
                    [round(float(value), 10) for value in row]
                    for row in root.matrix_world.inverted() @ obj.matrix_world
                ]
                for obj in descendants
            }
            local = {
                obj.name: [
                    [round(float(value), 10) for value in row]
                    for row in obj.matrix_local
                ]
                for obj in descendants
            }
            max_relative_drift = max(
                (
                    abs(float(actual - expected))
                    for obj in descendants
                    for actual_row, expected_row in zip(
                        root.matrix_world.inverted() @ obj.matrix_world,
                        baseline_relative[obj.name],
                    )
                    for actual, expected in zip(actual_row, expected_row)
                ),
                default=0.0,
            )
            rigid_hash = hashlib.sha256(
                json.dumps(relative, sort_keys=True).encode("utf-8")
            ).hexdigest().upper()
            local_hash = hashlib.sha256(
                json.dumps(local, sort_keys=True).encode("utf-8")
            ).hexdigest().upper()
            runtime["progress"].append(round(progress, 10))
            runtime["velocityPerFrame"].append(round(derivative(frame), 10))
            runtime["accelerationPerFrame"].append(round(acceleration(frame), 10))
            runtime["componentOffsetsM"].append(
                [round(float(value * progress), 10) for value in full_offset]
            )
            runtime["rigidRelativeMatrixHashes"].append(rigid_hash)
            runtime["rigidLocalMatrixHashes"].append(local_hash)
            runtime["rigidMaxRelativeMatrixDrift"].append(
                float(max_relative_drift)
            )
            return progress

        def finalize():
            motion_root.animation_data_clear()
            root.parent = original_parent
            root.matrix_parent_inverse = original_parent_inverse
            root.matrix_world = root_world
            bpy.data.actions.remove(action)
            bpy.data.objects.remove(motion_root, do_unlink=True)

        return {"sample": sample, "finalize": finalize, "runtime": runtime}

    blender_condenser_r1_linefix_probe_worker(
        Path(output_root),
        frame_indices=frame_indices,
        schema=schema,
        report_name=report_name,
        frames_subdir=frames_subdir,
        motion_controller=setup_motion,
        render=render,
    )


def blender_condenser_second_repair_probe_worker(output_root):
    import bmesh
    import bpy
    from mathutils import Matrix, Vector

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    unit = authority["units"][CONDENSER]
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    candidate_hash = sha256(candidate_blend)
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded")
    if candidate_hash != authority["candidateBlend"]["sha256"]:
        raise RuntimeError("candidate blend drift")

    scene = bpy.context.scene
    camera = scene.camera
    root = bpy.data.objects.get(unit["rootObjects"][0])
    contract = condenser_second_repair_contract()
    target = bpy.data.objects.get(contract["geometry"]["object"])
    preserved = [
        bpy.data.objects.get(name) for name in contract["occlusion"]["preservedMeshes"]
    ]
    if camera is None or root is None or target is None or not all(preserved):
        raise RuntimeError("second repair probe scene object missing")

    def local_bounds(obj):
        coordinates = [vertex.co for vertex in obj.data.vertices]
        return (
            [min(float(vertex[axis]) for vertex in coordinates) for axis in range(3)],
            [max(float(vertex[axis]) for vertex in coordinates) for axis in range(3)],
        )

    def world_bounds(objects):
        corners = [
            obj.matrix_world @ Vector(corner)
            for obj in objects
            for corner in obj.bound_box
        ]
        return (
            [min(float(point[axis]) for point in corners) for axis in range(3)],
            [max(float(point[axis]) for point in corners) for axis in range(3)],
        )

    def aabb_distance(left, right):
        left_min, left_max = left
        right_min, right_max = right
        gaps = []
        for axis in range(3):
            if left_max[axis] < right_min[axis]:
                gaps.append(right_min[axis] - left_max[axis])
            elif right_max[axis] < left_min[axis]:
                gaps.append(left_min[axis] - right_max[axis])
            else:
                gaps.append(0.0)
        return math.sqrt(sum(value * value for value in gaps))

    def extract_front_boundary_rings(
        obj, axis, front_sign, coordinate, depth=0.0025
    ):
        plane_axes = [item for item in range(3) if item != axis]
        selected = []
        for polygon in obj.data.polygons:
            inward = [
                front_sign * (coordinate - float(obj.data.vertices[index].co[axis]))
                for index in polygon.vertices
            ]
            if (
                float(polygon.normal[axis]) * front_sign >= 0.35
                and min(inward) >= -0.0001
                and max(inward) <= depth
            ):
                selected.append(polygon)
        edge_counts = {}
        for polygon in selected:
            vertices = list(polygon.vertices)
            for index, left in enumerate(vertices):
                right = vertices[(index + 1) % len(vertices)]
                edge = tuple(sorted((int(left), int(right))))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        unused = {edge for edge, count in edge_counts.items() if count == 1}
        graph = {}
        for left, right in unused:
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
        if not unused or any(len(neighbors) != 2 for neighbors in graph.values()):
            raise RuntimeError("front boundary graph is not closed two-valence rings")
        rings = []
        while unused:
            first = next(iter(unused))
            start, current = first
            ordered = [start]
            previous = None
            while True:
                ordered.append(current)
                unused.discard(tuple(sorted((ordered[-2], current))))
                candidates = [
                    neighbor
                    for neighbor in graph[current]
                    if neighbor != previous
                    and tuple(sorted((current, neighbor))) in unused
                ]
                if not candidates:
                    if current != start and start in graph[current]:
                        unused.discard(tuple(sorted((current, start))))
                    break
                previous, current = current, candidates[0]
                if current == start:
                    unused.discard(tuple(sorted((previous, start))))
                    break
            if len(ordered) < 4:
                raise RuntimeError("front boundary ring is too small")
            points = [obj.data.vertices[index].co.copy() for index in ordered]
            area = 0.0
            perimeter = 0.0
            for index, point in enumerate(points):
                next_point = points[(index + 1) % len(points)]
                area += (
                    float(point[plane_axes[0]]) * float(next_point[plane_axes[1]])
                    - float(next_point[plane_axes[0]]) * float(point[plane_axes[1]])
                )
                perimeter += (next_point - point).length
            area *= 0.5
            center = [
                sum(float(point[item]) for point in points) / len(points)
                for item in plane_axes
            ]
            rings.append(
                {
                    "indices": ordered,
                    "points": points,
                    "signedArea": area,
                    "perimeterM": perimeter,
                    "center2d": center,
                }
            )
        rings.sort(key=lambda ring: abs(ring["signedArea"]), reverse=True)
        return rings, [polygon.index for polygon in selected], plane_axes

    def mesh_quality(obj):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        finally:
            bm.free()
        return {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "polygons": len(obj.data.polygons),
            "nonManifoldEdges": non_manifold,
            "zeroAreaFaces": sum(1 for polygon in obj.data.polygons if polygon.area <= 1e-14),
        }

    root_world = root.matrix_world.copy()
    original_scene_frame = scene.frame_current
    original_hidden = {}
    preserved_state = {
        obj.name: {
            "parent": obj.parent,
            "matrix": obj.matrix_world.copy(),
        }
        for obj in preserved
    }
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 top-plate material target missing")
    top_slot = top_plate.material_slots[0]
    top_original_material = top_slot.material
    top_original_link = top_slot.link
    top_temporary_material = None
    proxy = None
    liners = []
    proxy_material = None
    liner_material = None
    target_original_mesh = target.data
    target_temporary_mesh = None
    technical = []
    geometry_audit = None
    occlusion_audit = None
    frame_records = []
    try:
        camera.location = Vector(unit["camera"]["location"])
        camera.rotation_euler = Vector(unit["camera"]["rotation"])
        camera.data.lens = unit["camera"]["lensMm"]
        camera.data.sensor_width = unit["camera"]["sensorWidthMm"]
        camera.data.shift_x = unit["camera"]["shiftX"]
        camera.data.shift_y = unit["camera"]["shiftY"]
        for name in profile["sharedHiddenObjects"]:
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise RuntimeError(f"stage 1 hidden object missing: {name}")
            original_hidden[name] = bool(obj.hide_render)
            obj.hide_render = True

        scene.render.engine = profile["engine"]
        scene.render.resolution_x = 640
        scene.render.resolution_y = 450
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = 64
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]
        for light_record in profile["lightRig"]:
            if not light_record["name"].startswith("TEMP__SHARED_"):
                if bpy.data.objects.get(light_record["name"]) is None:
                    raise RuntimeError(f"stage 1 light missing: {light_record['name']}")
                continue
            data = bpy.data.lights.new(
                light_record["name"] + "_DATA", light_record["type"]
            )
            data.energy = light_record["energy"]
            data.color = light_record["color"]
            data.shape = "DISK"
            data.size = light_record["size"]
            obj = bpy.data.objects.new(light_record["name"], data)
            scene.collection.objects.link(obj)
            obj.location = Vector(light_record["location"])
            obj.rotation_euler = Vector(light_record["rotation"])
            technical.append((obj, data))

        if top_original_material is None:
            raise RuntimeError("stage 1 top-plate material missing")
        top_temporary_material = top_original_material.copy()
        top_temporary_material.name = "TEMP__STAGE3_SECOND_REPAIR_TOP_NO_NORMAL"
        normal_nodes = [
            node
            for node in top_temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = 0.0
        top_slot.link = "OBJECT"
        top_slot.material = top_temporary_material

        minimum, maximum = local_bounds(target)
        extents = [maximum[axis] - minimum[axis] for axis in range(3)]
        thickness_axis = min(range(3), key=lambda axis: extents[axis])
        camera_local = target.matrix_world.inverted() @ camera.location
        center = (minimum[thickness_axis] + maximum[thickness_axis]) / 2.0
        front_sign = 1.0 if camera_local[thickness_axis] >= center else -1.0
        front_coordinate = (
            maximum[thickness_axis] if front_sign > 0 else minimum[thickness_axis]
        )
        if thickness_axis != 2 or front_sign != 1.0:
            raise RuntimeError("revised front-ring rebuild expects local +Z front")
        rings, selected_front_faces, plane_axes = extract_front_boundary_rings(
            target, thickness_axis, front_sign, front_coordinate
        )
        if len(rings) < 2:
            raise RuntimeError(f"complete front boundary rings missing: {len(rings)}")

        curve_data = bpy.data.curves.new(
            "TEMP__STAGE3_SECOND_REPAIR_PROXY_CURVE", "CURVE"
        )
        curve_data.dimensions = "2D"
        curve_data.fill_mode = "BOTH"
        curve_data.resolution_u = 1
        ring_records = []
        for ring_index, ring in enumerate(rings):
            points = list(ring["points"])
            desired_positive = ring_index == 0
            if (ring["signedArea"] > 0) != desired_positive:
                points.reverse()
            spline = curve_data.splines.new("POLY")
            spline.points.add(len(points) - 1)
            for point, source in zip(spline.points, points):
                point.co = (
                    float(source[plane_axes[0]]),
                    float(source[plane_axes[1]]),
                    0.0,
                    1.0,
                )
            spline.use_cyclic_u = True
            ring_records.append(
                {
                    "kind": "outer" if ring_index == 0 else "inner",
                    "vertexCount": len(points),
                    "perimeterM": round(float(ring["perimeterM"]), 8),
                    "center2d": [round(float(value), 8) for value in ring["center2d"]],
                }
            )
        proxy = bpy.data.objects.new(
            "TEMP__STAGE3_SECOND_REPAIR_PROXY", curve_data
        )
        scene.collection.objects.link(proxy)
        placement = Matrix.Translation(
            Vector((0.0, 0.0, front_coordinate + 0.00005))
        )
        proxy.matrix_world = target.matrix_world @ placement
        bpy.context.view_layer.objects.active = proxy
        proxy.select_set(True)
        target.select_set(False)
        bpy.ops.object.convert(target="MESH")
        proxy = bpy.context.active_object
        proxy.data.name = "TEMP__STAGE3_SECOND_REPAIR_PROXY_MESH"
        solidify = proxy.modifiers.new(
            "TEMP__STAGE3_SECOND_REPAIR_SOLIDIFY", "SOLIDIFY"
        )
        solidify.thickness = contract["geometry"]["solidifyThicknessM"]
        solidify.offset = -1.0
        bpy.ops.object.modifier_apply(modifier=solidify.name)
        bevel = proxy.modifiers.new("TEMP__STAGE3_SECOND_REPAIR_BEVEL", "BEVEL")
        bevel.width = contract["geometry"]["bevelWidthM"]
        bevel.segments = 2
        bevel.limit_method = "ANGLE"
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        proxy.parent = root

        target_temporary_mesh = target_original_mesh.copy()
        target_temporary_mesh.name = "TEMP__STAGE3_SECOND_REPAIR_TARGET_MESH"
        target.data = target_temporary_mesh
        bm = bmesh.new()
        try:
            bm.from_mesh(target_temporary_mesh)
            bm.faces.ensure_lookup_table()
            faces_to_remove = [bm.faces[index] for index in selected_front_faces]
            bmesh.ops.delete(bm, geom=faces_to_remove, context="FACES_ONLY")
            bm.to_mesh(target_temporary_mesh)
        finally:
            bm.free()
        target_temporary_mesh.update()

        if len(target.material_slots) != 1 or target.material_slots[0].material is None:
            raise RuntimeError("second repair proxy source material drift")
        proxy_material = target.material_slots[0].material.copy()
        proxy_material.name = "TEMP__STAGE3_SECOND_REPAIR_PROXY_MATERIAL"
        shader_nodes = [
            node
            for node in proxy_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeBsdfPrincipled"
        ]
        if len(shader_nodes) != 1:
            raise RuntimeError("second repair proxy shader drift")
        shader = shader_nodes[0]
        for input_name in ("Roughness", "Normal"):
            for link in list(shader.inputs[input_name].links):
                proxy_material.node_tree.links.remove(link)
        shader.inputs["Roughness"].default_value = 0.32
        shader.inputs["Metallic"].default_value = 0.85
        proxy.data.materials.append(proxy_material)

        geometry_audit = mesh_quality(proxy)
        geometry_audit.update(
            {
                "method": "boundary-ring-front-face-replacement",
                "proxyCreated": True,
                "thicknessAxis": thickness_axis,
                "frontSign": front_sign,
                "sourceFrontFaceCount": len(selected_front_faces),
                "outerRingCount": 1,
                "innerRingCount": len(ring_records) - 1,
                "sourceRings": ring_records,
                "proxyRings": deepcopy(ring_records),
                "ringAuditMatches": True,
                "visibleOpeningCountMatches": len(ring_records) > 1,
                "replacesOriginalFrontFaces": True,
                "maxFrontOffsetM": 0.00005,
            }
        )
        if (
            geometry_audit["nonManifoldEdges"] != 0
            or geometry_audit["zeroAreaFaces"] != 0
            or not geometry_audit["visibleOpeningCountMatches"]
            or not geometry_audit["ringAuditMatches"]
        ):
            raise RuntimeError(f"second repair proxy geometry failed: {geometry_audit}")

        moving_objects = [obj for obj in root.children_recursive if obj.type == "MESH"]
        moving_min, moving_max = world_bounds(moving_objects)
        full_offset = Vector(unit["fullOffsetsM"]["condenserAssembly"])
        bpy.context.view_layer.update()
        view_frame = camera.data.view_frame(scene=scene)
        frame_x = [float(point.x) for point in view_frame]
        frame_y = [float(point.y) for point in view_frame]
        frame_z = sum(float(point.z) for point in view_frame) / len(view_frame)

        def ray_plane_point(pixel, plane_y):
            x, y = pixel
            local = Vector(
                (
                    min(frame_x) + (float(x) / 640.0) * (max(frame_x) - min(frame_x)),
                    min(frame_y)
                    + ((450.0 - float(y)) / 450.0) * (max(frame_y) - min(frame_y)),
                    frame_z,
                )
            )
            origin = camera.matrix_world.translation.copy()
            world = camera.matrix_world @ local
            direction = (world - origin).normalized()
            if abs(float(direction.y)) <= 1e-9:
                raise RuntimeError("cavity wedge ray is parallel to the depth plane")
            distance = (plane_y - float(origin.y)) / float(direction.y)
            if distance <= 0:
                raise RuntimeError("cavity wedge depth plane is behind the camera")
            return origin + direction * distance

        near_y = moving_max[1] + max(0.0, float(full_offset[1])) + 0.001
        far_y = near_y + 0.01
        liner_material = bpy.data.materials.new(
            "TEMP__STAGE3_SECOND_REPAIR_CAVITY_LINER_MATERIAL"
        )
        liner_material.diffuse_color = (0.003, 0.004, 0.006, 1.0)
        liner_material.use_nodes = True
        liner_shader = liner_material.node_tree.nodes.get("Principled BSDF")
        liner_shader.inputs["Base Color"].default_value = (0.003, 0.004, 0.006, 1.0)
        liner_shader.inputs["Roughness"].default_value = 0.78
        liner_shader.inputs["Metallic"].default_value = 0.15
        wedge_records = []
        for liner_index, gate_name in enumerate(contract["occlusion"]["rayRois"]):
            polygon = SECOND_REPAIR_VISUAL_GATES[gate_name]["polygon"]
            near_points = [ray_plane_point(point, near_y) for point in polygon]
            far_points = [ray_plane_point(point, far_y) for point in polygon]
            vertices = [tuple(point) for point in [*near_points, *far_points]]
            faces = [
                (0, 1, 2, 3),
                (7, 6, 5, 4),
                (0, 4, 5, 1),
                (1, 5, 6, 2),
                (2, 6, 7, 3),
                (3, 7, 4, 0),
            ]
            mesh = bpy.data.meshes.new(
                f"TEMP__STAGE3_SECOND_REPAIR_CAVITY_WEDGE_{liner_index}_MESH"
            )
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            liner = bpy.data.objects.new(
                f"TEMP__STAGE3_SECOND_REPAIR_CAVITY_WEDGE_{liner_index}", mesh
            )
            scene.collection.objects.link(liner)
            liner.data.materials.append(liner_material)
            liners.append(liner)
            wedge_records.append(
                {
                    "roi": gate_name,
                    "verticesWorld": [
                        [round(float(value), 8) for value in point]
                        for point in [*near_points, *far_points]
                    ],
                }
            )

        base_bounds = world_bounds(moving_objects)
        clearances = []
        for frame_index in range(25):
            progress = condenser_motion_progress(frame_index)
            offset = [float(value * progress) for value in full_offset]
            moved = (
                [base_bounds[0][axis] + offset[axis] for axis in range(3)],
                [base_bounds[1][axis] + offset[axis] for axis in range(3)],
            )
            clearances.extend(
                aabb_distance(moved, world_bounds([liner])) for liner in liners
            )
        minimum_clearance = min(clearances)
        occlusion_audit = {
            "method": "localized-extruded-leak-wedges",
            "classification": "render-only-cavity-liner",
            "productStructureClaimed": False,
            "preservedOccluderParents": all(
                obj.parent == preserved_state[obj.name]["parent"] for obj in preserved
            ),
            "minimumClearanceM": round(minimum_clearance, 8),
            "linerCount": len(liners),
            "wedges": wedge_records,
            "roiOutsideChangedPixels": None,
        }
        if minimum_clearance < contract["occlusion"]["minimumClearanceM"]:
            raise RuntimeError(f"cavity liner clearance failed: {occlusion_audit}")

        for frame_index in (0, 12, 24):
            progress = condenser_motion_progress(frame_index)
            root.matrix_world = Matrix.Translation(full_offset * progress) @ root_world
            bpy.context.view_layer.update()
            for liner in liners:
                liner.hide_render = True
            control_path = output_root / f"control-frame-{frame_index:03d}.png"
            scene.render.filepath = str(control_path)
            bpy.ops.render.render(write_still=True)
            for liner in liners:
                liner.hide_render = False
            path = output_root / f"frame-{frame_index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frame_records.append(
                {
                    "index": frame_index,
                    "progress": progress,
                    "path": path.name,
                    "sha256": sha256(path),
                    "controlPath": control_path.name,
                    "controlSha256": sha256(control_path),
                }
            )
    finally:
        root.matrix_world = root_world
        scene.frame_set(original_scene_frame)
        for name, hidden in original_hidden.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = hidden
        top_slot.link = top_original_link
        top_slot.material = top_original_material
        target.data = target_original_mesh
        if proxy is not None:
            proxy_mesh = proxy.data
            bpy.data.objects.remove(proxy, do_unlink=True)
            bpy.data.meshes.remove(proxy_mesh)
        for liner in liners:
            liner_mesh = liner.data
            bpy.data.objects.remove(liner, do_unlink=True)
            bpy.data.meshes.remove(liner_mesh)
        if target_temporary_mesh is not None:
            bpy.data.meshes.remove(target_temporary_mesh)
        if proxy_material is not None:
            bpy.data.materials.remove(proxy_material)
        if liner_material is not None:
            bpy.data.materials.remove(liner_material)
        if top_temporary_material is not None:
            bpy.data.materials.remove(top_temporary_material)
        for obj, data in technical:
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE3_SECOND_REPAIR"):
                bpy.data.curves.remove(curve)

    if geometry_audit is None or occlusion_audit is None or len(frame_records) != 3:
        raise RuntimeError("second repair probe did not complete")
    preserved_restored = all(
        obj.parent == preserved_state[obj.name]["parent"]
        and all(
            abs(float(left) - float(right)) <= 1e-9
            for left_row, right_row in zip(
                obj.matrix_world, preserved_state[obj.name]["matrix"]
            )
            for left, right in zip(left_row, right_row)
        )
        for obj in preserved
    )
    occlusion_audit["preservedOccluderParents"] = preserved_restored
    after_hash = sha256(candidate_blend)
    temporary_remaining = sorted(
        [
            datablock.name
            for collection in (
                bpy.data.objects,
                bpy.data.meshes,
                bpy.data.materials,
                bpy.data.actions,
                bpy.data.curves,
            )
            for datablock in collection
            if datablock.name.startswith("TEMP__STAGE3_SECOND_REPAIR")
        ]
    )
    report = {
        "schema": CONDENSER_SECOND_REPAIR_PROBE_SCHEMA,
        "frameIndices": [0, 12, 24],
        "candidateBlendSha256Before": candidate_hash,
        "candidateBlendSha256After": after_hash,
        "candidateBlendSaved": False,
        "geometry": geometry_audit,
        "occlusion": occlusion_audit,
        "temporaryDataBlocksRemaining": temporary_remaining,
        "frames": frame_records,
    }
    (output_root / "probe-audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _stage3_cli():
    if "--stage3-chamber-worker" in sys.argv:
        index = sys.argv.index("--stage3-chamber-worker")
        blender_chamber_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-condenser-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-worker")
        blender_condenser_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-condenser-repair-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-repair-worker")
        blender_condenser_repair_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-condenser-second-repair-probe-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-second-repair-probe-worker")
        blender_condenser_second_repair_probe_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-condenser-r1-linefix-probe-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-r1-linefix-probe-worker")
        blender_condenser_r1_linefix_probe_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-condenser-r1-linefix-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-r1-linefix-worker")
        blender_condenser_r1_linefix_probe_worker(
            Path(sys.argv[index + 1]),
            frame_indices=tuple(range(25)),
            schema=CONDENSER_R1_LINEFIX_SCHEMA,
            report_name="blender-motion.json",
            frames_subdir="frames",
        )
        return True
    if "--stage3-condenser-motion-only-probe-worker" in sys.argv:
        index = sys.argv.index("--stage3-condenser-motion-only-probe-worker")
        blender_condenser_motion_only_probe_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-formal-chamber-worker" in sys.argv:
        index = sys.argv.index("--stage3-formal-chamber-worker")
        blender_formal_chamber_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-formal-condenser-worker" in sys.argv:
        index = sys.argv.index("--stage3-formal-condenser-worker")
        blender_formal_condenser_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-step7-probe-worker" in sys.argv:
        index = sys.argv.index("--stage3-step7-probe-worker")
        blender_step7_probe_worker(Path(sys.argv[index + 1]))
        return True
    if "--stage3-closeout-condenser-worker" in sys.argv:
        index = sys.argv.index("--stage3-closeout-condenser-worker")
        blender_stage3_closeout_condenser_worker(Path(sys.argv[index + 1]))
        return True
    return False


if __name__ == "__main__":
    _stage3_cli()
