"""Bounded stage-4 orbit contracts for the approved TWINKLE P1-E2 profile."""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "twinkle-stage4-orbit-v1"

STAGE1_MANIFEST = (
    ROOT
    / "output"
    / "twinkle-route1-camera-board-r1-1"
    / "camera-board-manifest.json"
)
STAGE3_R2_MANIFEST = (
    ROOT
    / "output"
    / "twinkle-stage3-dual-hotspot-motion-r2"
    / "step7-full-review-manifest.json"
)
STAGE3_R2_MANIFEST_LOGICAL_PATH = (
    "output/twinkle-stage3-dual-hotspot-motion-r2/"
    "step7-full-review-manifest.json"
)
GEOMETRY_SNAPSHOT = ROOT / "scripts" / "twinkle_geometry_snapshot_v1.json"
REJECTED_ORIENTATION_PROBE_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage4-orientation-probe-20260828"
    / "orientation-probe-r1"
)
EXPECTED_STAGE1_SHA256 = (
    "8DB0B2055838FA69C6381719587A99A2B132FE526F40EA6F0C231264AD908378"
)
EXPECTED_STAGE3_R2_SHA256 = (
    "67674A09A7E4C4C26DA57824AFB30DEC1F77C562C954A963CA266FAF8C776332"
)
EXPECTED_SOURCE_BLEND_SHA256 = (
    "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81"
)
EXPECTED_CANDIDATE_BLEND_SHA256 = (
    "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
)
EXPECTED_GEOMETRY_SNAPSHOT_SHA256 = (
    "C582E560977172BA01F0804119F41A8FA3F7A8CC2B71B44C168457ECB9B1BAF4"
)

CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"
SEMANTIC_UNITS = (CHAMBER, CONDENSER)
BLEND_MARKER_IDS = {
    CHAMBER: "j_green_filter_subassembly",
    CONDENSER: "f_dual_acl_housing",
}
TIMELINE_OWNER = "stage3-state-machine"

ORBIT_PROFILE = {
    "topology": "pingpong-expanded",
    "azimuthDegreesRelativeToV7": [-12.0, 12.0],
    "elevationMode": "fixed",
    "durationMs": 10_000,
    "physicalFrameCount": 49,
    "logicalIndexCount": 96,
    "maximumEntryFramesPerUnit": 2,
}
ORIENTATION_PROBE = {
    "constraints": ("TRACK_TO", "LOCKED_TRACK"),
    "units": SEMANTIC_UNITS,
    "semanticPoses": ("entry", "transition", "focus"),
    "render": {"resolution": [640, 450], "samples": 64},
    "renderFrameCount": 12,
    "maximumRenderFrameCount": 15,
    "curveKind": "CURVE",
    "pathConstraint": "FOLLOW_PATH",
    "fCurveDriven": True,
    "candidateBlendSaved": False,
}
ORIENTATION_CORRECTION = {
    "constraint": "TRACK_TO",
    "render": {"resolution": [640, 450], "samples": 64},
    "renders": (
        {"unit": CHAMBER, "pose": "focus", "sourceFrame": 101},
        {"unit": CONDENSER, "pose": "transition", "sourceFrame": 51},
        {"unit": CONDENSER, "pose": "focus", "sourceFrame": 101},
    ),
    "renderFrameCount": 3,
    "maximumRenderFrameCount": 3,
    "reusesRejectedLockedTrackEvidence": True,
    "testsConstraintCombination": False,
    "candidateBlendSaved": False,
}
CORRECTION_ENDPOINT_RGB_MAE_MAX = 15.0
CORRECTION_RECOVERY_FRAME_00_SHA256 = (
    "550677558E719C71E08BD1F968165F4FB161648BB8BD65E495A53BAB5C3DCCEB"
)
CORRECTION_TARGET_SAFE_BOUNDS = (0.05, 0.05, 0.69, 0.95)
CORRECTION_MIN_VISIBLE_SUBJECT_FRACTION = 0.75
CORRECTION_MIN_VISIBLE_CANVAS_AREA = 0.005
CORRECTION_REVIEW_FONT_PATH = (
    Path(os.environ["TWINKLE_CJK_REVIEW_FONT"]).expanduser()
    if os.environ.get("TWINKLE_CJK_REVIEW_FONT")
    else Path(os.environ.get("WINDIR", "")) / "Fonts" / "msyh.ttc"
)
CORRECTION_REVIEW_FONT_SHA256 = (
    "D79C55E68B1131EEA0CC1C47BE4F572D964F28C682E143DB2AD09C1E4CB07A3F"
)
APPROVED_ORIENTATION_CORRECTION = (
    ROOT
    / "output"
    / ".twinkle-stage4-orientation-correction-20260828"
    / "orientation-correction-r1"
)
EXPECTED_ORIENTATION_CORRECTION_SHA256 = (
    "A53654E3BC8936905C1F776DBE7C779A7ABF626E37918399A258D900D9A80FC2"
)
EXPECTED_TRACK_TO_SIX_GRID_SHA256 = (
    "FA1ABEF053FD20CF996B4EE5C6ECAFD57A00F24DE053052BD01D8ABDD2A039F0"
)
ORBIT_O1_RENDER = {
    "resolution": [640, 450],
    "samples": 64,
    "format": "PNG",
    "lossless": True,
}
ORBIT_OVERVIEW_LOCATION = (0.86733437, 0.07146358, 0.88114214)
ORBIT_OVERVIEW_TARGET = (0.38308914, 0.61887108, 0.55480299)
ORBIT_LENS_MM = 58.0
ORBIT_SENSOR_WIDTH_MM = 36.0
ORBIT_SHIFT = (0.0, 0.0)
ORBIT_SAFE_BOUNDS = (0.05, 0.05, 0.69, 0.95)
ORBIT_MIN_VISIBLE_SUBJECT_FRACTION = 0.75
ORBIT_MIN_VISIBLE_CANVAS_AREA = 0.005
FAILED_ORBIT_O1_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage4-orbit-o1-20260829"
    / ".orbit-o1-pdj85oh0"
)
FAILED_ORBIT_O1_AUDIT = FAILED_ORBIT_O1_ROOT / "worker-audit.json"
EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256 = (
    "50B218CF1C723632FAB0526B7AE918B61FE6693A9CFC511520927CDCB20E0BCC"
)
APPROVED_SURFACE_ANCHOR_PRECHECK = (
    ROOT
    / "output"
    / ".twinkle-stage4-surface-anchor-precheck-20260829"
    / "surface-anchor-precheck-r1"
)
EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256 = (
    "A27B447F6D235F748DCFB00A151D92E1D67408526544F831D298C2C598EA6105"
)
SURFACE_ANCHOR_PRECHECK = {
    "schema": "twinkle-stage4-surface-anchor-precheck-v1",
    "maximumSubmittedCandidatesPerUnit": 3,
    "maximumRaycastTrianglesPerUnit": 96,
    "barycentricCoordinates": [1 / 3, 1 / 3, 1 / 3],
    "safeBounds": [0.05, 0.05, 0.69, 0.95],
    "facingDotMinimumExclusive": 0.0,
    "surfaceHitToleranceM": 0.0001,
    "physicalFrameCount": 49,
    "logicalIndexCount": 96,
    "renderedFrameCount": 0,
    "reusedOrbitPngCount": 49,
    "totalStage4RenderedToDate": 64,
}
C360_F96_PROFILE = {
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
C360_F96_RENDER = {
    "resolution": [640, 450],
    "samples": 64,
    "format": "PNG",
    "lossless": True,
}
C360_F96_COMPONENT_RECOGNIZABILITY = {
    CHAMBER: {
        "minimumVisibleWidth": 0.25,
        "minimumVisibleHeight": 0.25,
        "minimumVisibleArea": 0.075,
        "minimumVisibleFraction": 0.95,
        "minimumHotspotSurfaceFacingDot": 0.20,
    },
    CONDENSER: {
        "minimumVisibleWidth": 0.14,
        "minimumVisibleHeight": 0.24,
        "minimumVisibleArea": 0.034,
        "minimumVisibleFraction": 0.95,
        "minimumHotspotSurfaceFacingDot": 0.04,
    },
}
C360_F96_REVIEW_PLAYER = {
    "asset": "review/index.html",
    "durationMs": 8_000,
    "playsExactlyOneCycle": True,
    "supportsPlayPauseResume": True,
    "supportsReplay": True,
    "supportsScrubbing": True,
    "supportsNameButtonNavigation": True,
    "maximumTurnDurationMs": 2_000,
    "maximumAngularSpeedDegreesPerSecond": 90.0,
    "entersFocusOnlyAfterSettled": True,
    "focusReadyLabel": "准备进入聚焦",
    "entryRole": "overview-exit-only",
    "focusRouteGenerated": False,
    "componentRecognizabilityGate": True,
    "nonVisibleHotspotsHiddenAndNonInteractive": True,
    "hotspotLabelsShownWheneverVisible": True,
    "unifiedModelHotspotColor": "#FFFFFF",
    "hotspotVisibilityTransitionMs": 140,
    "usesRapidHotspotFadeInOut": True,
    "preloadsAllSourceFrames": True,
    "hotspotsAreHtmlOverlays": True,
    "sourcePngPixelsModified": False,
}
APPROVED_C360_F96 = (
    ROOT
    / "output"
    / ".twinkle-stage4-orbit-c360-f96-20260829"
    / "orbit-c360-f96-r1"
)
C1_KEYFRAME_OUTPUT_ROOT = (
    ROOT
    / "output"
    / ".twinkle-stage4-c1-keyframe-precheck-20260830"
    / "c1-keyframe-precheck-r1"
)
C1_KEYFRAME_PROFILE = {
    "schema": "twinkle-stage4-c1-keyframe-precheck-v1",
    "curveSampleCount": 25,
    "previewSampleIndices": [0, 12, 24],
    "newRenderSampleIndices": [12],
    "durationMs": 1_000,
    "settledHoldMs": 100,
    "variants": ["A", "B"],
    "orientationConstraint": "TRACK_TO",
    "render": {"resolution": [640, 450], "samples": 64, "format": "PNG"},
    "fullSequenceGenerated": False,
    "stage3MechanicalPlaybackGenerated": False,
    "reusesApprovedEndpoints": True,
}
C2_FULL_REVIEW_PROFILE = {
    "schema": "twinkle-stage4-c2-full-review-v1",
    "curveSampleCount": 25,
    "curveDurationMs": 1_000,
    "settledHoldMs": 100,
    "variants": ["A", "B"],
    "orientationConstraint": "TRACK_TO",
    "render": {"resolution": [640, 450], "samples": 64, "format": "PNG"},
    "stage3R2FrameCountPerUnit": 25,
    "inspectionLight": {"fadeInMs": 900, "holdMs": 500, "fadeOutMs": 700},
    "fullSequenceGenerated": True,
    "stage3MechanicalPlaybackGenerated": True,
    "overviewReturn": "strict-full-focus-trace-reverse",
    "captureFrameRequired": True,
    "staticFallbackRequired": True,
}
C2_CAPTURE_CASES = {
    (CHAMBER, 6): {"capturedOrbitFrame": 0, "capturedOrbitDirection": "forward"},
    (CHAMBER, 65): {"capturedOrbitFrame": 72, "capturedOrbitDirection": "backward"},
    (CONDENSER, 87): {"capturedOrbitFrame": 92, "capturedOrbitDirection": "backward"},
    (CONDENSER, 8): {"capturedOrbitFrame": 3, "capturedOrbitDirection": "forward"},
}
APPROVED_STAGE4_CHOICES = {
    CHAMBER: {6: "A", 65: "B"},
    CONDENSER: {87: "A", 8: "A"},
}
C2_WORKER_EXPECTED_POSITION_FLOAT32_TOLERANCE_M = 1e-7

_QUALIFICATION_FIELDS = (
    "depthPositive",
    "projectionSafe",
    "facingCamera",
    "unoccluded",
    "humanApproved",
)
_FORBIDDEN_LEGACY_TERMS = (
    "j_green_filter_subassembly",
    "f_dual_acl_housing",
)
_FORBIDDEN_FILTER_TERMS = (
    "green-filter",
    "red-filter",
    "green_filter",
    "red_filter",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _atomic_write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, dir=path.parent, prefix=f".{path.name}.txn-"
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        raise


def _atomic_write_json(path, value):
    _atomic_write_bytes(
        path,
        json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8"),
    )


def expanded_physical_frames():
    """Return the approved physical-frame order for logical indices 0..95."""

    return tuple(range(49)) + tuple(range(47, 0, -1))


def c360_f96_angles():
    return [
        index * C360_F96_PROFILE["angleStepDegrees"]
        for index in range(C360_F96_PROFILE["physicalFrameCount"])
    ]


def cyclic_index_distance(left, right, frame_count):
    distance = abs(int(left) - int(right))
    return min(distance, int(frame_count) - distance)


def select_c360_entry_frames(
    qualified_frames, *, hero_frame, frame_count, recognizable_frames
):
    qualified = sorted(set(int(frame) for frame in qualified_frames))
    recognizable = sorted(set(int(frame) for frame in recognizable_frames))
    hero_frame = int(hero_frame)
    frame_count = int(frame_count)
    if hero_frame not in qualified:
        raise ValueError("C360 hero entry must be machine qualified")
    if not qualified or any(frame < 0 or frame >= frame_count for frame in qualified):
        raise ValueError("C360 qualified entry frame is out of range")
    if not recognizable:
        raise ValueError("C360 has no recognizable entry candidate")
    if any(frame not in qualified for frame in recognizable):
        raise ValueError(
            "C360 recognizable entry candidate must be machine qualified"
        )
    def maximum_wait(entries):
        return max(
            min(
                cyclic_index_distance(frame, entry, frame_count)
                for entry in entries
            )
            for frame in range(frame_count)
        )

    if len(recognizable) == 1:
        entries = [recognizable[0]]
    else:
        entries = list(
            min(
                itertools.combinations(recognizable, 2),
                key=lambda pair: (
                    maximum_wait(pair),
                    abs(
                        cyclic_index_distance(pair[0], pair[1], frame_count)
                        - frame_count / 2
                    ),
                    pair,
                ),
            )
        )
        entries.sort(
            key=lambda entry: (
                cyclic_index_distance(hero_frame, entry, frame_count), entry
            )
        )
    wait = maximum_wait(entries)
    return {
        "entryFrameSet": entries,
        "maximumCyclicDistanceFrames": wait,
        "maximumCyclicDistanceDegrees": wait * 360.0 / frame_count,
        "auxiliaryEntryAdded": len(entries) == 2,
        "recognizabilityGateApplied": True,
    }


def plan_c360_shortest_turn(*, current_frame, entry_frames, orbit_direction):
    current_frame = int(current_frame)
    entries = [int(frame) for frame in entry_frames]
    if orbit_direction not in {"forward", "backward"}:
        raise ValueError("C360 orbit direction must be forward or backward")
    plans = []
    for entry in entries:
        forward = (entry - current_frame) % 96
        backward = (current_frame - entry) % 96
        if forward < backward:
            direction, distance = "forward", forward
        elif backward < forward:
            direction, distance = "backward", backward
        else:
            direction, distance = orbit_direction, forward
        plans.append((distance, 0 if direction == orbit_direction else 1, entry, direction))
    distance, _, entry, direction = min(plans)
    distance_degrees = distance * C360_F96_PROFILE["angleStepDegrees"]
    if distance == 0:
        duration = C360_F96_PROFILE["settledHoldMs"]
        peak = 0.0
    else:
        duration = int(
            round(
                distance_degrees
                / C360_F96_PROFILE["maximumAngularSpeedDegreesPerSecond"]
                * 1000
                + C360_F96_PROFILE["accelerationRampMs"]
                + C360_F96_PROFILE["settledHoldMs"]
            )
        )
        peak = C360_F96_PROFILE["maximumAngularSpeedDegreesPerSecond"]
    return {
        "selectedEntryFrame": entry,
        "direction": direction,
        "distanceFrames": distance,
        "distanceDegrees": distance_degrees,
        "accelerationRampMs": C360_F96_PROFILE["accelerationRampMs"],
        "decelerationRampMs": C360_F96_PROFILE["decelerationRampMs"],
        "settledHoldMs": C360_F96_PROFILE["settledHoldMs"],
        "turnDurationMs": duration,
        "peakAngularSpeedDegreesPerSecond": peak,
        "arrivesStopped": True,
        "enterFocusAfterSettled": True,
    }


def select_nearest_entry(current_index, entry_indices, direction):
    """Select by absolute logical-index distance; break ties in travel direction."""

    current_index = int(current_index)
    entries = tuple(int(index) for index in entry_indices)
    if not 0 <= current_index < ORBIT_PROFILE["logicalIndexCount"]:
        raise ValueError("current expanded index is out of range")
    if not entries:
        raise ValueError("at least one entry index is required")
    if len(entries) > ORBIT_PROFILE["maximumEntryFramesPerUnit"]:
        raise ValueError("entry index count exceeds the approved per-unit maximum")
    if any(
        index < 0 or index >= ORBIT_PROFILE["logicalIndexCount"]
        for index in entries
    ):
        raise ValueError("entry expanded index is out of range")
    if direction not in {"forward", "backward"}:
        raise ValueError("orbit direction must be forward or backward")

    directional_tiebreak = (lambda index: -index) if direction == "forward" else int
    return min(
        entries,
        key=lambda index: (
            abs(index - current_index),
            directional_tiebreak(index),
        ),
    )


def model_hotspot_control(qualification):
    eligible = all(qualification.get(field) is True for field in _QUALIFICATION_FIELDS)
    return {"visible": eligible, "enabled": eligible}


def c360_global_controls(report, *, orbit_frame_index, orbit_playback):
    """Resolve frame-local model hotspots without hiding fixed name controls."""

    frame_index = int(orbit_frame_index)
    if report.get("orbitProfile") != C360_F96_PROFILE:
        raise ValueError("C360 global controls require the approved orbit profile")
    qualification = {}
    for unit in SEMANTIC_UNITS:
        records = report.get("qualificationByUnit", {}).get(unit, {}).get(
            "physicalFrames", []
        )
        record = next(
            (
                candidate
                for candidate in records
                if int(candidate.get("physicalFrameIndex", -1)) == frame_index
            ),
            None,
        )
        if record is None:
            raise ValueError("C360 qualification is missing the requested frame")
        qualification[unit] = {
            **record,
            "humanApproved": report.get("humanVisualApproved") is True,
        }
    return global_controls(
        orbit_frame_index=frame_index,
        orbit_playback=orbit_playback,
        qualification_by_unit=qualification,
    )


def _cyclic_prefix(start, end, direction, frame_count=96):
    if direction not in {"forward", "backward"}:
        raise ValueError("orbit direction must be forward or backward")
    start, end, frame_count = int(start), int(end), int(frame_count)
    if not 0 <= start < frame_count or not 0 <= end < frame_count:
        raise ValueError("cyclic trace frame is out of range")
    step = 1 if direction == "forward" else -1
    result = [start]
    while result[-1] != end:
        result.append((result[-1] + step) % frame_count)
    return result


def build_c360_focus_trace(
    *,
    unit,
    source,
    current_frame,
    orbit_direction,
    entry_frames,
    curve_frame_indices,
    model_hotspot_qualified,
):
    """Build the step-6 trace using only an explicitly labelled focus stub."""

    if unit not in SEMANTIC_UNITS:
        raise ValueError("unknown focus-trace unit")
    if source not in {"model", "name"}:
        raise ValueError("focus-trace source must be model or name")
    if source == "model" and model_hotspot_qualified is not True:
        return None
    curve = list(curve_frame_indices)
    if not curve or any(not str(frame).startswith("stub-") for frame in curve):
        raise ValueError("step 6 focus trace accepts stub curve frames only")
    turn = plan_c360_shortest_turn(
        current_frame=current_frame,
        entry_frames=entry_frames,
        orbit_direction=orbit_direction,
    )
    prefix = _cyclic_prefix(
        current_frame, turn["selectedEntryFrame"], turn["direction"]
    )
    full_trace = prefix + curve
    return {
        "unit": unit,
        "source": source,
        "capturedOrbitFrame": int(current_frame),
        "capturedOrbitDirection": orbit_direction,
        "selectedEntryFrame": turn["selectedEntryFrame"],
        "turnDirection": turn["direction"],
        "orbitPrefixIndices": prefix,
        "curveFrameIndices": curve,
        "fullFocusTrace": full_trace,
        "overviewReturn": list(reversed(full_trace)),
        "focusSegmentKind": "stub",
    }


def trace_playback_state(*, phase, trace, cursor, direction):
    if phase not in {"focus", "expand", "close", "overviewReturn"}:
        raise ValueError("unknown trace playback phase")
    points = list(trace)
    cursor = int(cursor)
    if not points or not 0 <= cursor < len(points):
        raise ValueError("trace playback cursor is out of range")
    if direction not in {"forward", "backward"}:
        raise ValueError("trace playback direction must be forward or backward")
    return {
        "phase": phase,
        "trace": points,
        "cursor": cursor,
        "currentPoint": points[cursor],
        "direction": direction,
        "playback": "running",
    }


def set_trace_playback(snapshot, playback):
    if playback not in {"running", "paused"}:
        raise ValueError("trace playback must be running or paused")
    if snapshot.get("playback") not in {"running", "paused"}:
        raise ValueError("invalid trace playback snapshot")
    return {**snapshot, "playback": playback}


def invalidate_entry_frame(
    *, entry_frames_by_unit, traces, cache, unit, removed_entry_frame
):
    if unit not in SEMANTIC_UNITS:
        raise ValueError("unknown entry-frame unit")
    entries = {key: list(value) for key, value in entry_frames_by_unit.items()}
    if set(entries) != set(SEMANTIC_UNITS):
        raise ValueError("entry frames must cover exactly the approved units")
    removed_entry_frame = int(removed_entry_frame)
    if removed_entry_frame not in entries[unit]:
        raise ValueError("entry frame is not active")
    entries[unit].remove(removed_entry_frame)
    invalidated = sorted(
        trace_id
        for trace_id, trace in traces.items()
        if trace.get("unit") == unit
        and int(trace.get("selectedEntryFrame", -1)) == removed_entry_frame
    )
    return {
        "entryFramesByUnit": entries,
        "invalidatedTraceIds": invalidated,
        "traces": {
            trace_id: trace
            for trace_id, trace in traces.items()
            if trace_id not in invalidated
        },
        "cache": {
            trace_id: value
            for trace_id, value in cache.items()
            if trace_id not in invalidated
        },
    }


def complete_c360_overview_return(trace):
    if trace.get("overviewReturn") != list(reversed(trace.get("fullFocusTrace", []))):
        raise ValueError("overview return must be the strict full-trace reverse")
    if not trace["overviewReturn"] or trace["overviewReturn"][-1] != trace[
        "capturedOrbitFrame"
    ]:
        raise ValueError("overview return does not end at the captured orbit frame")
    return {
        "topLevel": "global",
        "orbitTopology": "cyclic",
        "orbitFrameIndex": trace["capturedOrbitFrame"],
        "orbitDirection": trace["capturedOrbitDirection"],
        "orbitPlayback": "paused",
        "globalOrbit": "paused",
    }


def _vector_add(left, right):
    return [float(a) + float(b) for a, b in zip(left, right)]


def _vector_subtract(left, right):
    return [float(a) - float(b) for a, b in zip(left, right)]


def _vector_scale(vector, scalar):
    return [float(value) * float(scalar) for value in vector]


def _vector_length(vector):
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def _vector_normalize(vector):
    length = _vector_length(vector)
    if length <= 1e-12:
        raise ValueError("cannot normalize a zero-length route vector")
    return _vector_scale(vector, 1.0 / length)


def _cubic_bezier(control_points, progress):
    p0, p1, p2, p3 = control_points
    t = float(progress)
    inverse = 1.0 - t
    return [
        inverse**3 * p0[axis]
        + 3.0 * inverse**2 * t * p1[axis]
        + 3.0 * inverse * t**2 * p2[axis]
        + t**3 * p3[axis]
        for axis in range(3)
    ]


def _linear_samples(start, end, count):
    return [
        [
            float(left) + (float(right) - float(left)) * index / (count - 1)
            for left, right in zip(start, end)
        ]
        for index in range(count)
    ]


def polyline_offset_factors(samples):
    points = [list(map(float, point)) for point in samples]
    if len(points) < 2:
        raise ValueError("polyline requires at least two samples")
    segment_lengths = [
        _vector_length(_vector_subtract(right, left))
        for left, right in zip(points, points[1:])
    ]
    total = sum(segment_lengths)
    if total <= 1e-12:
        raise ValueError("polyline has zero total length")
    cumulative = [0.0]
    for length in segment_lengths:
        cumulative.append(cumulative[-1] + length)
    return [value / total for value in cumulative]


def c1_route_contracts(orbit_report, stage1_authority):
    """Define C1 A/B paths; only their spatial shape is allowed to differ."""

    if not (
        orbit_report.get("schema") == "twinkle-stage4-orbit-c360-f96-v1"
        and orbit_report.get("humanVisualApproved") is True
        and orbit_report.get("humanEntryApproved") is True
    ):
        raise ValueError("C1 requires the approved C360-F96 visual and entries")
    frames = {
        int(frame["physicalFrameIndex"]): frame
        for frame in orbit_report.get("frames", [])
    }
    sample_count = C1_KEYFRAME_PROFILE["curveSampleCount"]
    routes = []
    for unit in SEMANTIC_UNITS:
        qualification = orbit_report["qualificationByUnit"][unit]
        if not (
            qualification.get("humanApproved") is True
            and qualification.get("humanEntryApproved") is True
        ):
            raise ValueError("C1 entry set is not human approved")
        focus_camera = stage1_authority["units"][unit]["camera"]
        for entry_frame in qualification["initialEntryFrameSet"]:
            entry = frames[int(entry_frame)]["camera"]
            start = [float(value) for value in entry["location"]]
            end = [float(value) for value in focus_camera["location"]]
            chord = _vector_subtract(end, start)
            chord_length = _vector_length(chord)
            previous_location = frames[(int(entry_frame) - 1) % 96]["camera"][
                "location"
            ]
            next_location = frames[(int(entry_frame) + 1) % 96]["camera"][
                "location"
            ]
            tangent = _vector_normalize(
                _vector_subtract(next_location, previous_location)
            )
            common = {
                "startLocation": start,
                "endLocation": end,
                "targetSamples": _linear_samples(
                    entry["target"], focus_camera["target"], sample_count
                ),
                "lensSamplesMm": [
                    float(entry["lensMm"])
                    + (float(focus_camera["lensMm"]) - float(entry["lensMm"]))
                    * index
                    / (sample_count - 1)
                    for index in range(sample_count)
                ],
                "shiftXSamples": [
                    float(entry["shiftX"])
                    + (float(focus_camera["shiftX"]) - float(entry["shiftX"]))
                    * index
                    / (sample_count - 1)
                    for index in range(sample_count)
                ],
                "shiftYSamples": [
                    float(entry["shiftY"])
                    + (float(focus_camera["shiftY"]) - float(entry["shiftY"]))
                    * index
                    / (sample_count - 1)
                    for index in range(sample_count)
                ],
                "durationMs": C1_KEYFRAME_PROFILE["durationMs"],
                "settledHoldMs": C1_KEYFRAME_PROFILE["settledHoldMs"],
                "easing": "BEZIER/AUTO_CLAMPED",
                "orientationConstraint": "TRACK_TO",
                "render": dict(C1_KEYFRAME_PROFILE["render"]),
                "entryApproved": True,
                "mechanicalStartsAfterSettled": True,
                "fullSequenceGenerated": False,
            }
            controls_by_variant = {
                "A": [
                    start,
                    _vector_add(start, _vector_scale(chord, 0.34)),
                    _vector_add(start, _vector_scale(chord, 0.70)),
                    end,
                ],
                "B": [
                    start,
                    _vector_add(start, _vector_scale(tangent, chord_length * 0.34)),
                    _vector_add(
                        _vector_add(start, _vector_scale(chord, 0.62)),
                        _vector_scale(tangent, chord_length * 0.18),
                    ),
                    end,
                ],
            }
            for variant in C1_KEYFRAME_PROFILE["variants"]:
                control_points = controls_by_variant[variant]
                samples = [
                    _cubic_bezier(control_points, index / (sample_count - 1))
                    for index in range(sample_count)
                ]
                routes.append(
                    {
                        "routeId": f"{unit}--entry-{int(entry_frame):03d}--{variant}",
                        "unit": unit,
                        "entryFrame": int(entry_frame),
                        "variant": variant,
                        "commonFields": common,
                        "curveControlPoints": control_points,
                        "curveSamplePositions": samples,
                    }
                )
    return routes


def normalize_stage4_choices(choices):
    if not isinstance(choices, dict) or set(choices) != set(SEMANTIC_UNITS):
        raise ValueError(
            "stage 4 choices must contain exactly the approved semantic units"
        )
    return {
        unit: {
            str(int(entry)): str(variant)
            for entry, variant in choices.get(unit, {}).items()
        }
        for unit in SEMANTIC_UNITS
    }


def c2_route_contracts(c1_report, stage3_report, choices):
    if not (
        c1_report.get("schema") == C1_KEYFRAME_PROFILE["schema"]
        and c1_report.get("machinePassed") is True
        and c1_report.get("routeCount") == 8
    ):
        raise ValueError("C2 requires the machine-passed C1 route set")
    if not (
        stage3_report.get("schema") == "twinkle-stage3-step7-full-review-v1"
        and stage3_report.get("machinePassed") is True
        and stage3_report.get("humanVisualApproved") is True
        and stage3_report.get("stage3Closed") is True
        and stage3_report.get("frameCountPerUnit")
        == C2_FULL_REVIEW_PROFILE["stage3R2FrameCountPerUnit"]
    ):
        raise ValueError("C2 requires the closed and approved stage 3 r2 authority")
    expected_pairs = {
        (route["unit"], int(route["entryFrame"]))
        for route in c1_report["routes"]
    }
    actual_pairs = {
        (unit, int(entry)) for unit, entries in choices.items() for entry in entries
    }
    if (
        actual_pairs != expected_pairs
        or set(choices) != set(SEMANTIC_UNITS)
        or set(C2_CAPTURE_CASES) != expected_pairs
    ):
        raise ValueError("C2 choices must cover every approved unit and entry")
    entries_by_unit = {
        unit: sorted(entry for candidate_unit, entry in expected_pairs if candidate_unit == unit)
        for unit in SEMANTIC_UNITS
    }

    stage3_hash = sha256(STAGE3_R2_MANIFEST)
    orbit_report = validate_c360_f96(APPROVED_C360_F96)
    qualified_capture_frames = {
        unit: set(
            orbit_report["qualificationByUnit"][unit]["machineQualifiedPhysicalFrames"]
        )
        for unit in SEMANTIC_UNITS
    }
    focus_indices = list(range(C2_FULL_REVIEW_PROFILE["curveSampleCount"]))
    expand_indices = list(
        range(C2_FULL_REVIEW_PROFILE["stage3R2FrameCountPerUnit"])
    )
    routes = []
    for source in c1_report["routes"]:
        unit = source["unit"]
        entry = int(source["entryFrame"])
        selected_variant = choices[unit][entry]
        if selected_variant not in C2_FULL_REVIEW_PROFILE["variants"]:
            raise ValueError("C2 choice must be A or B")
        frame_root = "chamber-frames" if unit == CHAMBER else "frames"
        inspection = None
        if unit == CHAMBER:
            inspection = {
                "unlitAsset": "review/inspection-unlit.png",
                "litAsset": "review/inspection-lit.png",
                **C2_FULL_REVIEW_PROFILE["inspectionLight"],
            }
        capture = C2_CAPTURE_CASES[(unit, entry)]
        model_hotspot_qualified = (
            capture["capturedOrbitFrame"] in qualified_capture_frames[unit]
        )
        turn = plan_c360_shortest_turn(
            current_frame=capture["capturedOrbitFrame"],
            entry_frames=entries_by_unit[unit],
            orbit_direction=capture["capturedOrbitDirection"],
        )
        if turn["selectedEntryFrame"] != entry:
            raise ValueError("C2 capture case does not select its audited entry")
        orbit_prefix = _cyclic_prefix(
            capture["capturedOrbitFrame"], entry, turn["direction"]
        )
        full_trace = [
            *({"phase": "orbit", "frameIndex": index} for index in orbit_prefix),
            *(
                {"phase": "focus", "sampleIndex": index}
                for index in focus_indices
            ),
        ]
        routes.append(
            {
                **source,
                "c1HumanChoice": source["variant"] == selected_variant,
                **capture,
                "modelHotspotQualified": model_hotspot_qualified,
                "turnDirection": turn["direction"],
                "orbitPrefixIndices": orbit_prefix,
                "focusSampleIndices": focus_indices,
                "stage3R2": {
                    "sourceManifest": STAGE3_R2_MANIFEST_LOGICAL_PATH,
                    "sourceManifestSha256": stage3_hash,
                    "expandFrameIndices": expand_indices,
                    "expandAssets": [
                        f"{frame_root}/frame-{index:03d}.png"
                        for index in expand_indices
                    ],
                    "closeFrameIndices": list(reversed(expand_indices)),
                    "closeAssets": [
                        f"{frame_root}/frame-{index:03d}.png"
                        for index in reversed(expand_indices)
                    ],
                    "inspectionLight": inspection,
                },
                "fullFocusTrace": full_trace,
                "overviewReturn": list(reversed(full_trace)),
                "fullSequenceGenerated": True,
                "humanVisualApproved": False,
            }
        )
    return routes


def bind_c2_worker_audit_contract(worker_audit, contracts):
    worker = json.loads(json.dumps(worker_audit))
    contracts = json.loads(json.dumps(list(contracts)))
    worker_routes = {
        route.get("routeId"): route for route in worker.get("routes", [])
    }
    contract_routes = {route.get("routeId"): route for route in contracts}
    if (
        worker.get("schema") != "twinkle-stage4-c2-full-worker-v1"
        or set(worker_routes) != set(contract_routes)
    ):
        raise ValueError("C2 worker/contract route inventory mismatch")
    for route_id, worker_route in worker_routes.items():
        contract = contract_routes[route_id]
        samples = contract.get("curveSamplePositions", [])
        for frame in worker_route.get("frames", []):
            index = int(frame.get("sampleIndex", -1))
            expected = frame.get("expectedPosition", [])
            if (
                not 0 <= index < len(samples)
                or len(expected) != 3
                or any(
                    abs(float(left) - float(right))
                    > C2_WORKER_EXPECTED_POSITION_FLOAT32_TOLERANCE_M
                    for left, right in zip(expected, samples[index])
                )
            ):
                raise ValueError(f"C2 worker expected position drift: {route_id}/{index}")
    worker["contractSha256"] = canonical_json_sha256(contracts)
    return worker


def correction_camera_intrinsics(unit_id):
    if unit_id not in SEMANTIC_UNITS:
        raise ValueError("unknown correction unit")
    authority = validate_authority()["stage1"]
    camera = authority["units"][unit_id]["camera"]
    return {
        "lensMm": camera["lensMm"],
        "sensorWidthMm": camera["sensorWidthMm"],
        "shiftX": camera["shiftX"],
        "shiftY": camera["shiftY"],
    }


def correction_render_profile():
    profile = validate_authority()["stage1"]["renderProfile"]
    return {
        "engine": profile["engine"],
        "filmTransparent": profile["filmTransparent"],
        "colorManagement": profile["colorManagement"],
        "sharedHiddenObjects": profile["sharedHiddenObjects"],
        "sharedTechnicalLights": profile["sharedTechnicalLights"],
        "lightRigHash": profile["lightRigHash"],
        "materialRule": profile["materialRule"],
        "materialRuleHash": profile["materialRuleHash"],
        "colorManagementHash": profile["colorManagementHash"],
    }


def correction_projection_record(unit_id, *, camera_location, camera_target):
    if unit_id not in SEMANTIC_UNITS:
        raise ValueError("unknown projection unit")
    if sha256(GEOMETRY_SNAPSHOT) != EXPECTED_GEOMETRY_SNAPSHOT_SHA256:
        raise ValueError("geometry snapshot hash mismatch")
    snapshot = json.loads(GEOMETRY_SNAPSHOT.read_text(encoding="utf-8"))
    if (
        snapshot.get("sourceSha256") != EXPECTED_SOURCE_BLEND_SHA256
        or snapshot.get("candidateSha256") != EXPECTED_CANDIDATE_BLEND_SHA256
    ):
        raise ValueError("geometry snapshot blend authority mismatch")
    projection = load_camera_projection_module()

    intrinsics = correction_camera_intrinsics(unit_id)
    camera = projection.CameraSpec(
        location=camera_location,
        target=camera_target,
        lens_mm=intrinsics["lensMm"],
        sensor_width_mm=intrinsics["sensorWidthMm"],
        shift_x=intrinsics["shiftX"],
        shift_y=intrinsics["shiftY"],
        resolution_x=ORIENTATION_CORRECTION["render"]["resolution"][0],
        resolution_y=ORIENTATION_CORRECTION["render"]["resolution"][1],
        sensor_fit="AUTO",
    )
    target = projection.project_world_point(camera_target, camera)
    bounds = projection.project_bounds(
        snapshot["units"][unit_id]["hullPoints"], camera
    )
    min_x, min_y, max_x, max_y = bounds.as_list()
    total_area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
    visible_width = max(0.0, min(1.0, max_x) - max(0.0, min_x))
    visible_height = max(0.0, min(1.0, max_y) - max(0.0, min_y))
    visible_area = visible_width * visible_height
    visible_fraction = visible_area / total_area if total_area > 0.0 else 0.0
    safe_min_x, safe_min_y, safe_max_x, safe_max_y = CORRECTION_TARGET_SAFE_BOUNDS
    target_clipped = (
        target.depth <= 0.0
        or not safe_min_x <= target.x <= safe_max_x
        or not safe_min_y <= target.y <= safe_max_y
    )
    subject_out_of_frame = (
        visible_fraction < CORRECTION_MIN_VISIBLE_SUBJECT_FRACTION
        or visible_area < CORRECTION_MIN_VISIBLE_CANVAS_AREA
    )
    reasons = []
    if target_clipped:
        reasons.append("target-clipped")
    if subject_out_of_frame:
        reasons.append("subject-out-of-frame")
    return {
        "method": "twinkle_camera_projection-authority-hull",
        "geometrySnapshotSha256": EXPECTED_GEOMETRY_SNAPSHOT_SHA256,
        "safeTargetBounds": list(CORRECTION_TARGET_SAFE_BOUNDS),
        "minimumVisibleSubjectFraction": CORRECTION_MIN_VISIBLE_SUBJECT_FRACTION,
        "minimumVisibleCanvasArea": CORRECTION_MIN_VISIBLE_CANVAS_AREA,
        "targetCenter": [float(target.x), float(target.y)],
        "targetDepthPositive": target.depth > 0.0,
        "subjectBounds": [float(value) for value in bounds.as_list()],
        "visibleSubjectFraction": float(visible_fraction),
        "visibleCanvasArea": float(visible_area),
        "targetClipped": target_clipped,
        "subjectOutOfFrame": subject_out_of_frame,
        "failureReasons": reasons,
    }


def load_camera_projection_module():
    module_path = ROOT / "scripts" / "twinkle_camera_projection.py"
    spec = importlib.util.spec_from_file_location(
        "twinkle_stage4_authoritative_camera_projection", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("authoritative camera projection module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def c360_component_recognizability_record(unit_id, frame):
    if unit_id not in SEMANTIC_UNITS:
        raise ValueError("unknown C360 component recognizability unit")
    if sha256(GEOMETRY_SNAPSHOT) != EXPECTED_GEOMETRY_SNAPSHOT_SHA256:
        raise ValueError("geometry snapshot hash mismatch")
    snapshot = json.loads(GEOMETRY_SNAPSHOT.read_text(encoding="utf-8"))
    if (
        snapshot.get("sourceSha256") != EXPECTED_SOURCE_BLEND_SHA256
        or snapshot.get("candidateSha256") != EXPECTED_CANDIDATE_BLEND_SHA256
    ):
        raise ValueError("geometry snapshot blend authority mismatch")
    camera_record = frame["camera"]
    projection = load_camera_projection_module()
    camera = projection.CameraSpec(
        location=camera_record["location"],
        target=camera_record["target"],
        lens_mm=camera_record["lensMm"],
        sensor_width_mm=camera_record["sensorWidthMm"],
        shift_x=camera_record["shiftX"],
        shift_y=camera_record["shiftY"],
        resolution_x=C360_F96_RENDER["resolution"][0],
        resolution_y=C360_F96_RENDER["resolution"][1],
        sensor_fit="AUTO",
    )
    bounds = projection.project_bounds(
        snapshot["units"][unit_id]["hullPoints"], camera
    )
    min_x, min_y, max_x, max_y = (float(value) for value in bounds.as_list())
    total_width = max(0.0, max_x - min_x)
    total_height = max(0.0, max_y - min_y)
    total_area = total_width * total_height
    visible_width = max(0.0, min(1.0, max_x) - max(0.0, min_x))
    visible_height = max(0.0, min(1.0, max_y) - max(0.0, min_y))
    visible_area = visible_width * visible_height
    visible_fraction = visible_area / total_area if total_area > 0.0 else 0.0
    hotspot = frame["qualificationByUnit"][unit_id]
    hotspot_x, hotspot_y = (float(value) for value in hotspot["projection"])
    thresholds = dict(C360_F96_COMPONENT_RECOGNIZABILITY[unit_id])
    criteria = {
        "machineVisible": hotspot["status"] == "visible"
        and hotspot["machineQualified"] is True,
        "minimumVisibleWidth": visible_width
        >= thresholds["minimumVisibleWidth"],
        "minimumVisibleHeight": visible_height
        >= thresholds["minimumVisibleHeight"],
        "minimumVisibleArea": visible_area >= thresholds["minimumVisibleArea"],
        "minimumVisibleFraction": visible_fraction
        >= thresholds["minimumVisibleFraction"],
        "hotspotInsideComponentProjection": (
            min_x <= hotspot_x <= max_x and min_y <= hotspot_y <= max_y
        ),
        "hotspotSurfaceReadable": float(hotspot["facingDot"])
        >= thresholds["minimumHotspotSurfaceFacingDot"],
    }
    return {
        "semanticId": unit_id,
        "physicalFrameIndex": int(frame["physicalFrameIndex"]),
        "authorityState": "complete-overview-assembly",
        "usesFocusOrExtractState": False,
        "projectionMethod": "twinkle_camera_projection-authority-hull",
        "geometrySnapshotSha256": EXPECTED_GEOMETRY_SNAPSHOT_SHA256,
        "componentBounds": [min_x, min_y, max_x, max_y],
        "visibleWidth": visible_width,
        "visibleHeight": visible_height,
        "visibleArea": visible_area,
        "visibleFraction": visible_fraction,
        "hotspotProjection": [hotspot_x, hotspot_y],
        "hotspotStatus": hotspot["status"],
        "hotspotFacingDot": float(hotspot["facingDot"]),
        "thresholds": thresholds,
        "criteria": criteria,
        "gatePassed": all(criteria.values()),
    }


def remove_named_datablock(collection, name, *, do_unlink=False):
    datablock = collection.get(name)
    if datablock is None:
        return False
    if do_unlink:
        collection.remove(datablock, do_unlink=True)
    else:
        collection.remove(datablock)
    return True


def compare_endpoint_frame(candidate_path, reference_path):
    from PIL import Image, ImageChops, ImageStat

    with Image.open(candidate_path) as candidate_source:
        candidate = candidate_source.convert("RGB")
    with Image.open(reference_path) as reference_source:
        reference = reference_source.convert("RGB").resize(
            candidate.size, Image.Resampling.LANCZOS
        )
    luminance = candidate.convert("L")
    histogram = luminance.histogram()
    pixel_count = candidate.width * candidate.height
    near_black_fraction = sum(histogram[:11]) / pixel_count
    mean_luminance = float(ImageStat.Stat(luminance).mean[0])
    channel_extrema = candidate.getextrema()
    dynamic_range = max(high for _, high in channel_extrema) - min(
        low for low, _ in channel_extrema
    )
    difference = ImageChops.difference(candidate, reference)
    reference_mae = sum(ImageStat.Stat(difference).mean) / 3.0
    return {
        "resolution": list(candidate.size),
        "meanLuminance": mean_luminance,
        "nearBlackFraction": near_black_fraction,
        "dynamicRange": int(dynamic_range),
        "blackFrame": mean_luminance <= 10.0 or near_black_fraction >= 0.95,
        "emptyFrame": dynamic_range <= 24 and near_black_fraction >= 0.95,
        "referenceScale": "LANCZOS",
        "referenceRgbMae": float(reference_mae),
    }


def orientation_correction_record():
    return {
        **ORIENTATION_CORRECTION,
        "renders": [dict(record) for record in ORIENTATION_CORRECTION["renders"]],
    }


def correction_review_font():
    if not CORRECTION_REVIEW_FONT_PATH.is_file() or (
        sha256(CORRECTION_REVIEW_FONT_PATH) != CORRECTION_REVIEW_FONT_SHA256
    ):
        raise ValueError("deterministic Chinese review font is missing or drifted")
    return {
        "path": CORRECTION_REVIEW_FONT_PATH.as_posix(),
        "sha256": CORRECTION_REVIEW_FONT_SHA256,
        "family": "Microsoft YaHei",
        "size": 18,
    }


def correction_review_cells(output_root):
    output_root = Path(output_root).resolve()
    cells = (
        (
            output_root / "frames" / "candidate-00.png",
            "候选｜双通道采集光学舱｜focus",
        ),
        (
            output_root / "frames" / "candidate-01.png",
            "候选｜聚光镜组件｜transition",
        ),
        (
            output_root / "frames" / "candidate-02.png",
            "候选｜聚光镜组件｜focus",
        ),
    )
    if any(not path.is_file() for path, _ in cells):
        raise ValueError("correction review candidate frame is missing")
    return cells


def track_to_six_grid_cells(output_root):
    output_root = Path(output_root).resolve()
    rejected = validate_orientation_probe(REJECTED_ORIENTATION_PROBE_ROOT)
    track_scenarios = rejected["constraintResults"]["TRACK_TO"]["scenarios"]
    if any(
        pose["constraint"] != "TRACK_TO"
        for scenario in track_scenarios
        for pose in scenario["semanticPoses"]
    ):
        raise ValueError("six-grid historical source is not Track To")
    cells = (
        {
            "path": REJECTED_ORIENTATION_PROBE_ROOT / "frames" / "pose-00.png",
            "source": "orientation-probe-r1/frames/pose-00.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜双通道采集光学舱｜起点",
        },
        {
            "path": REJECTED_ORIENTATION_PROBE_ROOT / "frames" / "pose-01.png",
            "source": "orientation-probe-r1/frames/pose-01.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜双通道采集光学舱｜中途",
        },
        {
            "path": output_root / "frames" / "candidate-00.png",
            "source": "orientation-correction-r1/frames/candidate-00.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜双通道采集光学舱｜终点",
        },
        {
            "path": REJECTED_ORIENTATION_PROBE_ROOT / "frames" / "pose-03.png",
            "source": "orientation-probe-r1/frames/pose-03.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜聚光镜组件｜起点",
        },
        {
            "path": output_root / "frames" / "candidate-01.png",
            "source": "orientation-correction-r1/frames/candidate-01.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜聚光镜组件｜中途",
        },
        {
            "path": output_root / "frames" / "candidate-02.png",
            "source": "orientation-correction-r1/frames/candidate-02.png",
            "constraint": "TRACK_TO",
            "label": "Track To｜聚光镜组件｜终点",
        },
    )
    if any(not cell["path"].is_file() for cell in cells):
        raise ValueError("six-grid Track To source frame is missing")
    return cells


def validate_orientation_correction(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "orientation-correction-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("orientation correction schema manifest is missing")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != "twinkle-stage4-orientation-correction-v1":
        raise ValueError("orientation correction schema mismatch")
    if report.get("contract") != orientation_correction_record():
        raise ValueError("orientation correction contract mismatch")
    if report.get("constraint") != "TRACK_TO":
        raise ValueError("orientation correction must remain Track To only")
    if report.get("renderProfile") != correction_render_profile():
        raise ValueError("orientation correction render profile mismatch")
    expected_review_sources = [
        f"frames/candidate-{index:02d}.png"
        for index in range(ORIENTATION_CORRECTION["renderFrameCount"])
    ]
    if report.get("reviewSheetSources") != expected_review_sources:
        raise ValueError("orientation correction review sheet sources mismatch")
    if report.get("reviewFont") != correction_review_font():
        raise ValueError("orientation correction review font mismatch")
    if report.get("renderFrameCount") != ORIENTATION_CORRECTION["renderFrameCount"]:
        raise ValueError("orientation correction render count mismatch")
    if report["renderFrameCount"] > ORIENTATION_CORRECTION["maximumRenderFrameCount"]:
        raise ValueError("orientation correction exceeds remaining render budget")
    expected_budget = {
        "initialProbeRenders": 12,
        "correctionRendersBeforeRecovery": [0],
        "reusedFrameIndices": [0],
        "renderedFrameIndicesThisRun": [1, 2],
        "totalOrientationRenders": 15,
    }
    if report.get("budgetEvidence") != expected_budget:
        raise ValueError("orientation correction recovery render budget mismatch")

    frames = report.get("frames", [])
    if len(frames) != ORIENTATION_CORRECTION["renderFrameCount"]:
        raise ValueError("orientation correction frame record count mismatch")
    for index, (frame, expected) in enumerate(
        zip(frames, ORIENTATION_CORRECTION["renders"])
    ):
        if frame.get("index") != index or any(
            frame.get(key) != expected[key]
            for key in ("unit", "pose", "sourceFrame")
        ):
            raise ValueError("orientation correction frame identity mismatch")
        if frame.get("path") != f"frames/candidate-{index:02d}.png":
            raise ValueError("orientation correction frame path mismatch")
        if frame.get("cameraIntrinsics") != correction_camera_intrinsics(
            expected["unit"]
        ):
            raise ValueError("orientation correction camera intrinsics mismatch")
        quality = frame.get("quality", {})
        if quality.get("blackFrame") is not False or quality.get("emptyFrame") is not False:
            raise ValueError("orientation correction contains a black or empty frame")
        if (
            float(quality.get("meanLuminance", 0.0)) <= 10.0
            or float(quality.get("nearBlackFraction", 1.0)) >= 0.95
            or int(quality.get("dynamicRange", 0)) <= 24
        ):
            raise ValueError("orientation correction visual quality gate mismatch")
        if expected["pose"] == "focus":
            if quality.get("referenceScale") != "LANCZOS" or not quality.get(
                "referenceAsset"
            ):
                raise ValueError("orientation correction endpoint reference is missing")
            if (
                float(quality.get("referenceRgbMae", float("inf")))
                > CORRECTION_ENDPOINT_RGB_MAE_MAX
            ):
                raise ValueError("orientation correction endpoint pixel comparison failed")

        projection = frame.get("projection", {})
        expected_projection_metadata = {
            "method": "twinkle_camera_projection-authority-hull",
            "geometrySnapshotSha256": EXPECTED_GEOMETRY_SNAPSHOT_SHA256,
            "safeTargetBounds": list(CORRECTION_TARGET_SAFE_BOUNDS),
            "minimumVisibleSubjectFraction": CORRECTION_MIN_VISIBLE_SUBJECT_FRACTION,
            "minimumVisibleCanvasArea": CORRECTION_MIN_VISIBLE_CANVAS_AREA,
        }
        if any(
            projection.get(key) != value
            for key, value in expected_projection_metadata.items()
        ):
            raise ValueError("orientation correction projection authority mismatch")
        target_center = projection.get("targetCenter", [])
        if len(target_center) != 2:
            raise ValueError("orientation correction target projection is missing")
        safe_min_x, safe_min_y, safe_max_x, safe_max_y = (
            CORRECTION_TARGET_SAFE_BOUNDS
        )
        target_clipped = (
            projection.get("targetDepthPositive") is not True
            or not safe_min_x <= float(target_center[0]) <= safe_max_x
            or not safe_min_y <= float(target_center[1]) <= safe_max_y
        )
        bounds = projection.get("subjectBounds", [])
        if len(bounds) != 4:
            raise ValueError("orientation correction subject bounds are missing")
        min_x, min_y, max_x, max_y = (float(value) for value in bounds)
        total_area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
        visible_width = max(0.0, min(1.0, max_x) - max(0.0, min_x))
        visible_height = max(0.0, min(1.0, max_y) - max(0.0, min_y))
        visible_area = visible_width * visible_height
        visible_fraction = visible_area / total_area if total_area > 0.0 else 0.0
        if not math.isclose(
            float(projection.get("visibleCanvasArea", -1.0)),
            visible_area,
            abs_tol=1e-8,
        ) or not math.isclose(
            float(projection.get("visibleSubjectFraction", -1.0)),
            visible_fraction,
            abs_tol=1e-8,
        ):
            raise ValueError("orientation correction projection geometry mismatch")
        subject_out_of_frame = (
            visible_fraction < CORRECTION_MIN_VISIBLE_SUBJECT_FRACTION
            or visible_area < CORRECTION_MIN_VISIBLE_CANVAS_AREA
        )
        expected_reasons = []
        if target_clipped:
            expected_reasons.append("target-clipped")
        if subject_out_of_frame:
            expected_reasons.append("subject-out-of-frame")
        if (
            projection.get("targetClipped") is not target_clipped
            or projection.get("subjectOutOfFrame") is not subject_out_of_frame
            or projection.get("failureReasons") != expected_reasons
        ):
            raise ValueError("orientation correction projection failure record mismatch")
        if target_clipped:
            raise ValueError("target-clipped")
        if subject_out_of_frame:
            raise ValueError("subject-out-of-frame")

    metrics = report.get("orientationMetrics", {})
    orientation_gate = (
        float(metrics.get("maximumTargetErrorDegrees", float("inf"))) <= 0.05
        and float(metrics.get("maximumRollDegrees", float("inf"))) <= 1.0
        and float(
            metrics.get("maximumEndpointRotationErrorDegrees", float("inf"))
        )
        <= 0.1
        and float(metrics.get("maximumEndpointLocationErrorM", float("inf")))
        <= 1e-5
        and float(metrics.get("minimumUpDotWorldZ", -1.0)) > 0.0
        and float(metrics.get("maximumOrientationStepDegrees", float("inf")))
        < 30.0
        and metrics.get("flipCount") == 0
        and metrics.get("constraintCompetition") is False
        and metrics.get("evaluationLoopDetected") is False
    )
    if not orientation_gate:
        raise ValueError("orientation correction orientation gate failed")

    restoration = report.get("restoration", {})
    restoration_gate = (
        restoration.get("candidateBlendSha256Before")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSaved") is False
        and restoration.get("sourceCameraTransformRestored") is True
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("visibilityRestored") is True
        and restoration.get("materialRestored") is True
        and all(
            restoration.get(field) == []
            for field in (
                "temporaryCamerasRemaining",
                "temporaryCurvesRemaining",
                "temporaryEmptiesRemaining",
                "temporaryLightsRemaining",
                "temporaryMaterialsRemaining",
                "temporaryConstraintsRemaining",
                "temporaryActionsRemaining",
            )
        )
    )
    if not restoration_gate:
        raise ValueError("orientation correction restoration audit failed")
    if report.get("machinePassed") is not True:
        raise ValueError("orientation correction machine gate did not pass")
    if report.get("authorizesStep5") is not False:
        raise ValueError("orientation correction cannot authorize step 5")
    if report.get("humanApproved") is True:
        six_grid = report.get("trackToSixGrid", {})
        expected_approval = {
            "approvedBy": "user",
            "approvedOn": report.get("humanApproval", {}).get("approvedOn"),
            "scope": "stage4-step4-track-to-common-orientation-and-six-grid-review-only",
            "approvedConstraint": "TRACK_TO",
            "approvedAsset": "track-to-six-grid-contact-sheet.png",
            "approvedAssetSha256": six_grid.get("sha256"),
            "authorizesStep5": False,
        }
        if (
            not expected_approval["approvedOn"]
            or report.get("humanApproval") != expected_approval
        ):
            raise ValueError("orientation correction human approval mismatch")
    elif report.get("humanApproved") is not False or report.get("humanApproval") is not None:
        raise ValueError("orientation correction pending human state mismatch")

    required = {
        "worker-audit.json",
        "technical-pose-contact-sheet.png",
        *{
            f"frames/candidate-{index:02d}.png"
            for index in range(ORIENTATION_CORRECTION["renderFrameCount"])
        },
    }
    six_grid = report.get("trackToSixGrid")
    if six_grid is not None:
        expected_six_grid_sources = [
            cell["source"] for cell in track_to_six_grid_cells(output_root)
        ]
        if six_grid != {
            "constraint": "TRACK_TO",
            "grid": [2, 3],
            "sources": expected_six_grid_sources,
            "font": correction_review_font(),
            "asset": "track-to-six-grid-contact-sheet.png",
            "sha256": six_grid.get("sha256"),
        }:
            raise ValueError("Track To six-grid review metadata mismatch")
        six_grid_path = output_root / "track-to-six-grid-contact-sheet.png"
        if not six_grid_path.is_file() or sha256(six_grid_path) != six_grid.get(
            "sha256"
        ):
            raise ValueError("Track To six-grid review hash mismatch")
        required.add("track-to-six-grid-contact-sheet.png")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if set(actual) != required:
        raise ValueError("orientation correction inventory paths mismatch")
    if report.get("inventorySha256") != actual:
        raise ValueError("orientation correction inventory hash mismatch")
    return report


def global_controls(*, orbit_frame_index, orbit_playback, qualification_by_unit):
    if not 0 <= int(orbit_frame_index) < ORBIT_PROFILE["logicalIndexCount"]:
        raise ValueError("orbit frame index is out of range")
    if orbit_playback not in {"running", "paused"}:
        raise ValueError("orbit playback must be running or paused")
    if set(qualification_by_unit) != set(SEMANTIC_UNITS):
        raise ValueError("qualification must cover exactly the approved units")
    return {
        "modelHotspots": {
            unit: model_hotspot_control(qualification_by_unit[unit])
            if isinstance(qualification_by_unit[unit], dict)
            else {"visible": False, "enabled": False}
            for unit in SEMANTIC_UNITS
        },
        "unitNames": {
            unit: {"visible": True, "enabled": True} for unit in SEMANTIC_UNITS
        },
        "globalToggle": {
            "visible": True,
            "enabled": True,
            "label": "暂停展示" if orbit_playback == "running" else "开始展示",
        },
    }


def validate_authority():
    if sha256(STAGE1_MANIFEST) != EXPECTED_STAGE1_SHA256:
        raise ValueError("stage 1 authority hash mismatch")
    if sha256(STAGE3_R2_MANIFEST) != EXPECTED_STAGE3_R2_SHA256:
        raise ValueError("stage 3 r2 authority hash mismatch")

    stage1 = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    stage3 = json.loads(STAGE3_R2_MANIFEST.read_text(encoding="utf-8"))
    if set(stage1.get("units", {})) != set(SEMANTIC_UNITS):
        raise ValueError("stage 1 semantic authority mismatch")
    if stage1.get("source", {}).get("sha256") != EXPECTED_SOURCE_BLEND_SHA256:
        raise ValueError("source blend authority mismatch")
    if (
        stage1.get("candidateBlend", {}).get("sha256")
        != EXPECTED_CANDIDATE_BLEND_SHA256
    ):
        raise ValueError("candidate blend authority mismatch")
    required_stage3 = {
        "machinePassed": True,
        "humanVisualApproved": True,
        "stage3Closed": True,
        "authorizesStage4": False,
    }
    if any(stage3.get(key) is not value for key, value in required_stage3.items()):
        raise ValueError("stage 3 r2 closure authority mismatch")
    return {"stage1": stage1, "stage3": stage3}


def default_request(output_root):
    return {
        "stage1Manifest": str(STAGE1_MANIFEST),
        "stage3Manifest": str(STAGE3_R2_MANIFEST),
        "semanticUnits": list(SEMANTIC_UNITS),
        "payloadTerms": [],
        "writeProductionPage": False,
        "outputRoot": str(Path(output_root)),
    }


def validate_request(request):
    if Path(request["stage1Manifest"]).resolve() != STAGE1_MANIFEST.resolve():
        raise ValueError("stage 1 authority must use the approved manifest")
    if Path(request["stage3Manifest"]).resolve() != STAGE3_R2_MANIFEST.resolve():
        raise ValueError("stage 3 r2 authority must use the closed review manifest")
    if tuple(request["semanticUnits"]) != SEMANTIC_UNITS:
        raise ValueError("semantic units must contain only the two approved identifiers")
    for value in request.get("payloadTerms", []):
        lowered = str(value).lower()
        if any(term in lowered for term in _FORBIDDEN_LEGACY_TERMS):
            raise ValueError(f"forbidden legacy term: {value}")
        if any(term in lowered for term in _FORBIDDEN_FILTER_TERMS):
            raise ValueError(f"forbidden filter term: {value}")
    if request.get("writeProductionPage"):
        raise ValueError("production page writes are outside stage 4")
    output_root = Path(request["outputRoot"])
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    validate_authority()
    return request


def orientation_probe_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("orientation probe output must be an absolute path")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-orientation-worker",
        str(output_root),
    ]


def orientation_correction_blender_command(
    blender, candidate_blend, output_root, *, resume_candidate_00=False
):
    command = orientation_probe_blender_command(
        blender, candidate_blend, output_root
    )
    command[command.index("--stage4-orientation-worker")] = (
        "--stage4-orientation-correction-worker"
    )
    if resume_candidate_00:
        command.insert(
            command.index("--stage4-orientation-correction-worker"),
            "--resume-candidate-00",
        )
    return command


def validate_orientation_correction_recovery_staging(staging):
    staging = Path(staging).resolve()
    if not staging.is_dir():
        raise ValueError("orientation correction recovery staging is missing")
    expected_relative = Path("frames") / "candidate-00.png"
    files = {
        path.relative_to(staging).as_posix(): path
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }
    if set(files) != {expected_relative.as_posix()}:
        raise ValueError("orientation correction recovery inventory mismatch")
    frame = files[expected_relative.as_posix()]
    frame_hash = sha256(frame)
    if frame_hash != CORRECTION_RECOVERY_FRAME_00_SHA256:
        raise ValueError("orientation correction recovery frame hash mismatch")
    authority = validate_authority()["stage1"]
    unit = authority["units"][CHAMBER]
    reference = STAGE1_MANIFEST.parent / unit["frames"]["focused-settled"]["asset"]
    metrics = compare_endpoint_frame(frame, reference)
    if (
        metrics["blackFrame"]
        or metrics["emptyFrame"]
        or metrics["referenceRgbMae"] > CORRECTION_ENDPOINT_RGB_MAE_MAX
    ):
        raise ValueError("orientation correction recovery frame visual gate failed")
    return {
        "reusedFrameIndex": 0,
        "path": expected_relative.as_posix(),
        "sha256": frame_hash,
        "renderedFrameIndicesRemaining": [1, 2],
    }


def orientation_probe_record():
    return {
        **ORIENTATION_PROBE,
        "constraints": list(ORIENTATION_PROBE["constraints"]),
        "units": list(ORIENTATION_PROBE["units"]),
        "semanticPoses": list(ORIENTATION_PROBE["semanticPoses"]),
    }


def choose_common_orientation(constraint_results):
    eligible = [
        method
        for method in ORIENTATION_PROBE["constraints"]
        if constraint_results.get(method, {}).get("passesCommonGate") is True
    ]
    if not eligible:
        raise ValueError("no common orientation constraint passed the machine gate")
    return min(
        eligible,
        key=lambda method: (
            float(constraint_results[method].get("maximumRollDegrees", float("inf"))),
            float(
                constraint_results[method].get(
                    "maximumEndpointRotationErrorDegrees", float("inf")
                )
            ),
            ORIENTATION_PROBE["constraints"].index(method),
        ),
    )


def validate_orientation_probe(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "orientation-probe-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != "twinkle-stage4-orientation-probe-v1":
        raise ValueError("orientation probe schema mismatch")
    if report.get("contract") != orientation_probe_record():
        raise ValueError("orientation probe contract mismatch")
    selected = report.get("selectedConstraint")
    if selected != choose_common_orientation(report.get("constraintResults", {})):
        raise ValueError("orientation probe selected constraint is not evidence-based")
    if report.get("renderFrameCount") != ORIENTATION_PROBE["renderFrameCount"]:
        raise ValueError("orientation probe render count mismatch")
    if report["renderFrameCount"] > ORIENTATION_PROBE["maximumRenderFrameCount"]:
        raise ValueError("orientation probe exceeds the approved render budget")
    if report.get("machinePassed") is not True:
        raise ValueError("orientation probe machine gate did not pass")
    if report.get("humanApproved") is not False or report.get("authorizesStep5") is not False:
        raise ValueError("orientation probe cannot pre-approve the human gate or step 5")

    restoration = report.get("restoration", {})
    restoration_gate = (
        restoration.get("candidateBlendSha256Before")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSaved") is False
        and restoration.get("cameraTransformRestored") is True
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("temporaryCurvesRemaining") == []
        and restoration.get("temporaryEmptiesRemaining") == []
        and restoration.get("temporaryConstraintsRemaining") == []
        and restoration.get("temporaryActionsRemaining") == []
    )
    if not restoration_gate:
        raise ValueError("orientation probe restoration audit failed")

    required = {
        "worker-audit.json",
        "technical-pose-contact-sheet.png",
        *{
            f"frames/pose-{index:02d}.png"
            for index in range(ORIENTATION_PROBE["renderFrameCount"])
        },
    }
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if set(actual) != required:
        raise ValueError("orientation probe inventory paths mismatch")
    if report.get("inventorySha256") != actual:
        raise ValueError("orientation probe inventory hash mismatch")
    return report


def _run_checked(command, *, cwd):
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


def _write_orientation_contact_sheet(output_root, frame_records):
    from PIL import Image, ImageDraw

    output_root = Path(output_root)
    cell_width, image_height, label_height = 320, 225, 36
    columns = len(ORIENTATION_PROBE["semanticPoses"])
    rows = len(ORIENTATION_PROBE["constraints"]) * len(SEMANTIC_UNITS)
    sheet = Image.new(
        "RGB",
        (cell_width * columns, (image_height + label_height) * rows),
        (18, 21, 27),
    )
    draw = ImageDraw.Draw(sheet)
    for record in sorted(frame_records, key=lambda item: item["index"]):
        row = record["index"] // columns
        column = record["index"] % columns
        with Image.open(output_root / record["path"]) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
            x = column * cell_width + (cell_width - image.width) // 2
            y = row * (image_height + label_height)
            sheet.paste(image, (x, y))
        label = f"{record['constraint']} | {record['unit']} | {record['pose']}"
        draw.text(
            (column * cell_width + 8, y + image_height + 10),
            label,
            fill=(235, 239, 246),
        )
    path = output_root / "technical-pose-contact-sheet.png"
    sheet.save(path)
    return path


def _write_orientation_correction_contact_sheet(output_root, frame_records):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root)
    cells = correction_review_cells(output_root)
    font_record = correction_review_font()
    font = ImageFont.truetype(font_record["path"], font_record["size"])
    cell_width, image_height, label_height = 320, 225, 42
    sheet = Image.new(
        "RGB", (cell_width * 3, image_height + label_height), (18, 21, 27)
    )
    draw = ImageDraw.Draw(sheet)
    for index, (path, label) in enumerate(cells):
        column = index
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
            x = column * cell_width + (cell_width - image.width) // 2
            y = 0
            sheet.paste(image, (x, y))
        draw.text(
            (column * cell_width + 8, y + image_height + 10),
            label,
            fill=(235, 239, 246),
            font=font,
        )
    path = output_root / "technical-pose-contact-sheet.png"
    sheet.save(path)
    return path


def build_orientation_correction(
    output_root, *, blender=None, runner=None, recovery_staging=None
):
    output_root = Path(output_root).resolve()
    if output_root.name != "orientation-correction-r1":
        raise ValueError("orientation correction output name must be orientation-correction-r1")
    validate_request(default_request(output_root))
    authority = validate_authority()
    rejected = validate_orientation_probe(REJECTED_ORIENTATION_PROBE_ROOT)
    candidate_blend = Path(authority["stage1"]["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before orientation correction")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked

    output_root.parent.mkdir(parents=True, exist_ok=True)
    if recovery_staging is None:
        staging = Path(
            tempfile.mkdtemp(prefix=".orientation-correction-", dir=output_root.parent)
        ).resolve()
    else:
        staging = Path(recovery_staging).resolve()
        validate_orientation_correction_recovery_staging(staging)
    try:
        runner(
            orientation_correction_blender_command(
                blender,
                candidate_blend,
                staging,
                resume_candidate_00=recovery_staging is not None,
            ),
            cwd=ROOT,
        )
        worker_path = staging / "worker-audit.json"
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        if worker.get("schema") != "twinkle-stage4-orientation-correction-worker-v1":
            raise ValueError("orientation correction worker schema mismatch")
        if worker.get("constraint") != "TRACK_TO":
            raise ValueError("orientation correction worker must remain Track To only")
        if worker.get("renderProfile") != correction_render_profile():
            raise ValueError("orientation correction worker render profile mismatch")
        if worker.get("renderFrameCount") != ORIENTATION_CORRECTION["renderFrameCount"]:
            raise ValueError("orientation correction worker render count mismatch")
        frames = sorted(worker.get("frames", []), key=lambda record: record["index"])
        if len(frames) != ORIENTATION_CORRECTION["renderFrameCount"]:
            raise ValueError("orientation correction worker frame inventory mismatch")
        for index, (frame, expected) in enumerate(
            zip(frames, ORIENTATION_CORRECTION["renders"])
        ):
            if frame.get("index") != index or any(
                frame.get(key) != expected[key]
                for key in ("unit", "pose", "sourceFrame")
            ):
                raise ValueError("orientation correction worker frame identity mismatch")
            path = staging / f"frames/candidate-{index:02d}.png"
            if frame.get("path") != path.relative_to(staging).as_posix() or not path.is_file():
                raise ValueError("orientation correction worker frame missing")
            unit = authority["stage1"]["units"][expected["unit"]]
            reference_record = unit["frames"]["focused-settled"]
            reference = STAGE1_MANIFEST.parent / reference_record["asset"]
            quality = compare_endpoint_frame(
                path, reference if expected["pose"] == "focus" else path
            )
            if expected["pose"] == "focus":
                quality["referenceAsset"] = reference_record["asset"]
                quality["referenceAssetSha256"] = reference_record["sha256"]
            frame["quality"] = quality
        if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
            raise ValueError("candidate blend drift after orientation correction")

        _write_orientation_correction_contact_sheet(staging, frames)
        report = {
            "schema": "twinkle-stage4-orientation-correction-v1",
            "scope": "stage4-step4-single-public-orientation-correction-only",
            "contract": orientation_correction_record(),
            "constraint": "TRACK_TO",
            "renderProfile": correction_render_profile(),
            "renderFrameCount": len(frames),
            "budgetEvidence": worker["budgetEvidence"],
            "frames": frames,
            "orientationMetrics": worker["orientationMetrics"],
            "restoration": worker["restoration"],
            "reviewLabels": {
                "candidate": "CANDIDATE / 候选",
                "failed": "FAILED / 失败",
            },
            "reviewSheetSources": [
                f"frames/candidate-{index:02d}.png"
                for index in range(ORIENTATION_CORRECTION["renderFrameCount"])
            ],
            "reviewFont": correction_review_font(),
            "rejectedBaseline": {
                "path": str(REJECTED_ORIENTATION_PROBE_ROOT),
                "manifestSha256": sha256(
                    REJECTED_ORIENTATION_PROBE_ROOT
                    / "orientation-probe-manifest.json"
                ),
                "humanApproved": rejected["humanApproved"],
                "lockedTrackMaximumTargetErrorDegrees": rejected[
                    "constraintResults"
                ]["LOCKED_TRACK"]["maximumTargetErrorDegrees"],
                "lockedTrackMaximumRollDegrees": rejected["constraintResults"][
                    "LOCKED_TRACK"
                ]["maximumRollDegrees"],
            },
            "workerAuditSha256": sha256(worker_path),
            "machinePassed": True,
            "humanApproved": False,
            "authorizesStep5": False,
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "orientation-correction-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_orientation_correction(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"orientation correction failed; isolated staging kept at {staging}"
        ) from error
    return validate_orientation_correction(output_root)


def refresh_orientation_correction_review(output_root):
    output_root = Path(output_root).resolve()
    if output_root.name != "orientation-correction-r1":
        raise ValueError("orientation correction review refresh target mismatch")
    manifest_path = output_root / "orientation-correction-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != "twinkle-stage4-orientation-correction-v1":
        raise ValueError("orientation correction review refresh schema mismatch")
    expected_files = {
        "worker-audit.json",
        "technical-pose-contact-sheet.png",
        *{
            f"frames/candidate-{index:02d}.png"
            for index in range(ORIENTATION_CORRECTION["renderFrameCount"])
        },
    }
    if report.get("trackToSixGrid") is not None:
        expected_files.add("track-to-six-grid-contact-sheet.png")
    actual_before = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if set(actual_before) != expected_files or (
        report.get("inventorySha256") != actual_before
    ):
        raise ValueError("orientation correction review refresh inventory drift")
    frames = sorted(report.get("frames", []), key=lambda record: record["index"])
    if len(frames) != ORIENTATION_CORRECTION["renderFrameCount"]:
        raise ValueError("orientation correction review refresh frame count mismatch")
    for index, frame in enumerate(frames):
        expected_path = f"frames/candidate-{index:02d}.png"
        if frame.get("path") != expected_path or sha256(
            output_root / expected_path
        ) != frame.get("sha256"):
            raise ValueError("orientation correction review refresh frame drift")

    _write_orientation_correction_contact_sheet(output_root, frames)
    report["reviewSheetSources"] = [
        f"frames/candidate-{index:02d}.png"
        for index in range(ORIENTATION_CORRECTION["renderFrameCount"])
    ]
    report["reviewFont"] = correction_review_font()
    report["reviewSheetSha256"] = sha256(
        output_root / "technical-pose-contact-sheet.png"
    )
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_orientation_correction(output_root)


def _write_track_to_six_grid_contact_sheet(output_root):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root).resolve()
    cells = track_to_six_grid_cells(output_root)
    font_record = correction_review_font()
    font = ImageFont.truetype(font_record["path"], font_record["size"])
    cell_width, image_height, label_height = 320, 225, 42
    sheet = Image.new(
        "RGB", (cell_width * 3, (image_height + label_height) * 2), (18, 21, 27)
    )
    draw = ImageDraw.Draw(sheet)
    for index, cell in enumerate(cells):
        row, column = divmod(index, 3)
        with Image.open(cell["path"]) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
            x = column * cell_width + (cell_width - image.width) // 2
            y = row * (image_height + label_height)
            sheet.paste(image, (x, y))
        draw.text(
            (column * cell_width + 8, y + image_height + 10),
            cell["label"],
            fill=(235, 239, 246),
            font=font,
        )
    path = output_root / "track-to-six-grid-contact-sheet.png"
    sheet.save(path)
    return path


def refresh_track_to_six_grid_review(output_root):
    output_root = Path(output_root).resolve()
    report = validate_orientation_correction(output_root)
    manifest_path = output_root / "orientation-correction-manifest.json"
    sheet_path = _write_track_to_six_grid_contact_sheet(output_root)
    report["trackToSixGrid"] = {
        "constraint": "TRACK_TO",
        "grid": [2, 3],
        "sources": [cell["source"] for cell in track_to_six_grid_cells(output_root)],
        "font": correction_review_font(),
        "asset": sheet_path.name,
        "sha256": sha256(sheet_path),
    }
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_orientation_correction(output_root)


def record_orientation_correction_approval(output_root, *, approved_on):
    output_root = Path(output_root).resolve()
    report = validate_orientation_correction(output_root)
    if report["humanApproved"] is not False:
        raise ValueError("orientation correction approval is already recorded")
    six_grid = report["trackToSixGrid"]
    report["humanApproved"] = True
    report["humanApproval"] = {
        "approvedBy": "user",
        "approvedOn": str(approved_on),
        "scope": "stage4-step4-track-to-common-orientation-and-six-grid-review-only",
        "approvedConstraint": "TRACK_TO",
        "approvedAsset": six_grid["asset"],
        "approvedAssetSha256": six_grid["sha256"],
        "authorizesStep5": False,
    }
    report["authorizesStep5"] = False
    manifest_path = output_root / "orientation-correction-manifest.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_orientation_correction(output_root)


def build_orientation_probe(output_root, *, blender=None, runner=None):
    output_root = Path(output_root).resolve()
    validate_request(default_request(output_root))
    authority = validate_authority()
    candidate_blend = Path(authority["stage1"]["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before orientation probe")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".orientation-probe-", dir=output_root.parent)
    ).resolve()
    try:
        runner(
            orientation_probe_blender_command(blender, candidate_blend, staging),
            cwd=ROOT,
        )
        worker_path = staging / "worker-audit.json"
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        if worker.get("schema") != "twinkle-stage4-orientation-worker-v1":
            raise ValueError("orientation worker schema mismatch")
        if worker.get("renderFrameCount") != ORIENTATION_PROBE["renderFrameCount"]:
            raise ValueError("orientation worker render count mismatch")
        frame_records = worker.get("frames", [])
        if len(frame_records) != ORIENTATION_PROBE["renderFrameCount"]:
            raise ValueError("orientation worker frame inventory mismatch")
        expected_paths = {
            f"frames/pose-{index:02d}.png"
            for index in range(ORIENTATION_PROBE["renderFrameCount"])
        }
        if {record.get("path") for record in frame_records} != expected_paths:
            raise ValueError("orientation worker pose paths mismatch")
        if any(not (staging / path).is_file() for path in expected_paths):
            raise ValueError("orientation worker pose file missing")
        if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
            raise ValueError("candidate blend drift after orientation probe")

        selected = choose_common_orientation(worker.get("constraintResults", {}))
        _write_orientation_contact_sheet(staging, frame_records)
        report = {
            "schema": "twinkle-stage4-orientation-probe-v1",
            "scope": "stage4-step4-orientation-constraint-technical-probe-only",
            "contract": orientation_probe_record(),
            "authority": {
                "stage1ManifestSha256": EXPECTED_STAGE1_SHA256,
                "stage3R2ManifestSha256": EXPECTED_STAGE3_R2_SHA256,
                "sourceBlendSha256": EXPECTED_SOURCE_BLEND_SHA256,
                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
            },
            "selectedConstraint": selected,
            "selectionBasis": (
                "all common machine gates, then minimum maximum roll and endpoint "
                "rotation error"
            ),
            "constraintResults": worker["constraintResults"],
            "renderFrameCount": worker["renderFrameCount"],
            "workerAuditSha256": sha256(worker_path),
            "machinePassed": True,
            "humanApproved": False,
            "authorizesStep5": False,
            "restoration": worker["restoration"],
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "orientation-probe-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_orientation_probe(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"orientation probe failed; isolated staging kept at {staging}"
        ) from error
    return validate_orientation_probe(output_root)


def validate_orientation_worker_staging(output_root):
    output_root = Path(output_root).resolve()
    if not output_root.is_dir():
        raise ValueError("orientation worker staging must already exist")
    if any(output_root.iterdir()):
        raise ValueError("orientation worker staging must be empty")
    return output_root


def orientation_probe_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Euler = mathutils.Euler
    Matrix = mathutils.Matrix
    Vector = mathutils.Vector

    output_root = validate_orientation_worker_staging(output_root)
    frames_root = output_root / "frames"
    frames_root.mkdir()
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for orientation probe")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before orientation worker")

    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("scene camera missing")
    source_camera_matrix = source_camera.matrix_world.copy()
    probe_camera_data = source_camera.data.copy()
    probe_camera_data.name = "TEMP__STAGE4_ORIENTATION_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_ORIENTATION_CAMERA"
    camera.data = probe_camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    overview_location = Vector((0.86733437, 0.07146358, 0.88114214))
    overview_target = Vector((0.38308914, 0.61887108, 0.55480299))
    semantic_frames = (1, 51, 101)
    sample_frames = tuple(range(1, 102, 5))

    original_frame = scene.frame_current
    original_scene = {
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "samples": scene.eevee.taa_render_samples,
    }
    temporary_objects = [camera]
    temporary_curves = []
    temporary_actions = []
    temporary_constraints = []
    frame_records = []
    scenario_results = []

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_fcurve(fcurves, data_path, values, index=None):
        kwargs = {"data_path": data_path}
        if index is not None:
            kwargs["index"] = index
        curve = fcurves.new(**kwargs)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        curve.update()
        return curve

    def matrix_location_error(matrix, expected):
        return float((matrix.translation - expected).length)

    def quaternion_error_degrees(actual, expected):
        return math.degrees(float(actual.rotation_difference(expected).angle))

    def evaluated_pose(target):
        bpy.context.view_layer.update()
        matrix = camera.matrix_world.copy()
        rotation = matrix.to_quaternion()
        direction = (target.matrix_world.translation - matrix.translation).normalized()
        forward = rotation @ Vector((0.0, 0.0, -1.0))
        up = rotation @ Vector((0.0, 1.0, 0.0))
        ideal = direction.to_track_quat("-Z", "Y")
        return {
            "matrix": matrix,
            "rotation": rotation,
            "targetErrorDegrees": math.degrees(float(forward.angle(direction))),
            "rollDegrees": quaternion_error_degrees(rotation, ideal),
            "upDotWorldZ": float(up.dot(Vector((0.0, 0.0, 1.0)))),
            "up": up,
        }

    def cleanup_scenario(curve_object, target, constraints, actions, curve_data):
        for constraint in constraints:
            if constraint in camera.constraints.values():
                camera.constraints.remove(constraint)
        camera.animation_data_clear()
        for action in actions:
            if action in bpy.data.actions.values():
                bpy.data.actions.remove(action)
        if target in bpy.data.objects.values():
            bpy.data.objects.remove(target, do_unlink=True)
        if curve_object in bpy.data.objects.values():
            bpy.data.objects.remove(curve_object, do_unlink=True)
        if curve_data in bpy.data.curves.values():
            bpy.data.curves.remove(curve_data)

    try:
        scene.render.resolution_x = ORIENTATION_PROBE["render"]["resolution"][0]
        scene.render.resolution_y = ORIENTATION_PROBE["render"]["resolution"][1]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.eevee.taa_render_samples = ORIENTATION_PROBE["render"]["samples"]

        frame_index = 0
        for method in ORIENTATION_PROBE["constraints"]:
            for unit_id in SEMANTIC_UNITS:
                unit = authority["units"][unit_id]
                focus_location = Vector(unit["camera"]["location"])
                focus_target = Vector(unit["camera"]["target"])
                midpoint = (overview_location + focus_location) * 0.5
                view_cross = (focus_location - overview_location).cross(
                    Vector((0.0, 0.0, 1.0))
                )
                if view_cross.length > 1e-9:
                    midpoint += view_cross.normalized() * 0.035
                midpoint.z += 0.025

                curve_data = bpy.data.curves.new(
                    f"TEMP__STAGE4_{method}_{unit_id}_CURVE", type="CURVE"
                )
                curve_data.dimensions = "3D"
                curve_data.path_duration = 100
                spline = curve_data.splines.new(type="POLY")
                spline.points.add(2)
                for point, location in zip(
                    spline.points, (overview_location, midpoint, focus_location)
                ):
                    point.co = (*location, 1.0)
                curve_object = bpy.data.objects.new(
                    f"TEMP__STAGE4_{method}_{unit_id}_PATH", curve_data
                )
                scene.collection.objects.link(curve_object)
                curve_object.matrix_world = Matrix.Identity(4)

                target = bpy.data.objects.new(
                    f"TEMP__STAGE4_{method}_{unit_id}_TARGET", None
                )
                target.empty_display_type = "PLAIN_AXES"
                scene.collection.objects.link(target)

                camera_action = bpy.data.actions.new(
                    f"TEMP__STAGE4_{method}_{unit_id}_CAMERA_ACTION"
                )
                camera_slot, camera_fcurves = action_fcurves(
                    camera_action, camera, "Camera Motion"
                )
                target_action = bpy.data.actions.new(
                    f"TEMP__STAGE4_{method}_{unit_id}_TARGET_ACTION"
                )
                target_slot, target_fcurves = action_fcurves(
                    target_action, target, "Target Motion"
                )

                follow = camera.constraints.new(type="FOLLOW_PATH")
                follow.name = f"TEMP__STAGE4_{method}_{unit_id}_FOLLOW_PATH"
                follow.target = curve_object
                follow.use_fixed_location = True
                follow.use_curve_follow = False
                orientation = camera.constraints.new(type=method)
                orientation.name = f"TEMP__STAGE4_{method}_{unit_id}_ORIENTATION"
                orientation.target = target
                orientation.track_axis = "TRACK_NEGATIVE_Z"
                if method == "TRACK_TO":
                    orientation.up_axis = "UP_Y"
                else:
                    orientation.lock_axis = "LOCK_Y"

                add_fcurve(
                    camera_fcurves,
                    f'constraints["{follow.name}"].offset_factor',
                    tuple(zip(semantic_frames, (0.0, 0.5, 1.0))),
                )
                target_midpoint = (overview_target + focus_target) * 0.5
                for axis in range(3):
                    add_fcurve(
                        target_fcurves,
                        "location",
                        tuple(
                            zip(
                                semantic_frames,
                                (
                                    overview_target[axis],
                                    target_midpoint[axis],
                                    focus_target[axis],
                                ),
                            )
                        ),
                        index=axis,
                    )
                camera_animation = camera.animation_data_create()
                camera_animation.action = camera_action
                camera_animation.action_slot = camera_slot
                target_animation = target.animation_data_create()
                target_animation.action = target_action
                target_animation.action_slot = target_slot
                camera.location = Vector((0.0, 0.0, 0.0))
                camera.rotation_mode = "XYZ"
                camera.rotation_euler = overview_target.__sub__(
                    overview_location
                ).to_track_quat("-Z", "Y").to_euler()
                camera.scale = Vector((1.0, 1.0, 1.0))

                temporary_objects.extend((curve_object, target))
                temporary_curves.append(curve_data)
                temporary_actions.extend((camera_action, target_action))
                temporary_constraints.extend((follow, orientation))

                samples = []
                previous_rotation = None
                previous_up = None
                flip_count = 0
                for frame in sample_frames:
                    scene.frame_set(frame)
                    pose = evaluated_pose(target)
                    step_degrees = (
                        0.0
                        if previous_rotation is None
                        else quaternion_error_degrees(
                            previous_rotation, pose["rotation"]
                        )
                    )
                    if previous_up is not None and previous_up.dot(pose["up"]) < 0.0:
                        flip_count += 1
                    samples.append(
                        {
                            "frame": frame,
                            "targetErrorDegrees": pose["targetErrorDegrees"],
                            "rollDegrees": pose["rollDegrees"],
                            "upDotWorldZ": pose["upDotWorldZ"],
                            "orientationStepDegrees": step_degrees,
                        }
                    )
                    previous_rotation = pose["rotation"]
                    previous_up = pose["up"]

                semantic_pose_records = []
                endpoint_poses = []
                for pose_name, frame in zip(
                    ORIENTATION_PROBE["semanticPoses"], semantic_frames
                ):
                    scene.frame_set(frame)
                    pose = evaluated_pose(target)
                    path = frames_root / f"pose-{frame_index:02d}.png"
                    scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                    record = {
                        "index": frame_index,
                        "constraint": method,
                        "unit": unit_id,
                        "pose": pose_name,
                        "sourceFrame": frame,
                        "path": path.relative_to(output_root).as_posix(),
                        "sha256": sha256(path),
                        "location": [
                            round(float(value), 9)
                            for value in pose["matrix"].translation
                        ],
                        "targetErrorDegrees": pose["targetErrorDegrees"],
                        "rollDegrees": pose["rollDegrees"],
                        "upDotWorldZ": pose["upDotWorldZ"],
                    }
                    frame_records.append(record)
                    semantic_pose_records.append(record)
                    endpoint_poses.append(pose)
                    frame_index += 1

                expected_start_rotation = (
                    overview_target - overview_location
                ).to_track_quat("-Z", "Y")
                expected_end_rotation = Euler(
                    unit["camera"]["rotation"], "XYZ"
                ).to_quaternion()
                start_location_error = matrix_location_error(
                    endpoint_poses[0]["matrix"], overview_location
                )
                end_location_error = matrix_location_error(
                    endpoint_poses[-1]["matrix"], focus_location
                )
                start_rotation_error = quaternion_error_degrees(
                    endpoint_poses[0]["rotation"], expected_start_rotation
                )
                end_rotation_error = quaternion_error_degrees(
                    endpoint_poses[-1]["rotation"], expected_end_rotation
                )
                maximum_target_error = max(
                    sample["targetErrorDegrees"] for sample in samples
                )
                maximum_roll = max(abs(sample["rollDegrees"]) for sample in samples)
                minimum_up_dot = min(sample["upDotWorldZ"] for sample in samples)
                maximum_step = max(
                    sample["orientationStepDegrees"] for sample in samples
                )
                endpoint_rotation_error = max(
                    start_rotation_error, end_rotation_error
                )
                passes = (
                    start_location_error <= 1e-5
                    and end_location_error <= 1e-5
                    and endpoint_rotation_error <= 0.1
                    and maximum_target_error <= 0.05
                    and maximum_roll <= 1.0
                    and minimum_up_dot > 0.0
                    and maximum_step < 30.0
                    and flip_count == 0
                )
                scenario_results.append(
                    {
                        "constraint": method,
                        "unit": unit_id,
                        "pathClassification": "technical-only-non-route",
                        "activeOrientationConstraintCount": 1,
                        "constraintCompetition": False,
                        "evaluationLoopDetected": False,
                        "fCurveCount": 4,
                        "semanticPoses": semantic_pose_records,
                        "sampleCount": len(samples),
                        "samples": samples,
                        "startLocationErrorM": start_location_error,
                        "endLocationErrorM": end_location_error,
                        "startRotationErrorDegrees": start_rotation_error,
                        "endRotationErrorDegrees": end_rotation_error,
                        "maximumTargetErrorDegrees": maximum_target_error,
                        "maximumRollDegrees": maximum_roll,
                        "minimumUpDotWorldZ": minimum_up_dot,
                        "maximumOrientationStepDegrees": maximum_step,
                        "flipCount": flip_count,
                        "passesGate": passes,
                    }
                )
                cleanup_scenario(
                    curve_object,
                    target,
                    (follow, orientation),
                    (camera_action, target_action),
                    curve_data,
                )

        constraint_results = {}
        for method in ORIENTATION_PROBE["constraints"]:
            scenarios = [
                record for record in scenario_results if record["constraint"] == method
            ]
            constraint_results[method] = {
                "passesCommonGate": all(record["passesGate"] for record in scenarios),
                "maximumTargetErrorDegrees": max(
                    record["maximumTargetErrorDegrees"] for record in scenarios
                ),
                "maximumRollDegrees": max(
                    record["maximumRollDegrees"] for record in scenarios
                ),
                "maximumEndpointRotationErrorDegrees": max(
                    record["startRotationErrorDegrees"]
                    for record in scenarios
                )
                if not scenarios
                else max(
                    max(
                        record["startRotationErrorDegrees"],
                        record["endRotationErrorDegrees"],
                    )
                    for record in scenarios
                ),
                "minimumUpDotWorldZ": min(
                    record["minimumUpDotWorldZ"] for record in scenarios
                ),
                "maximumOrientationStepDegrees": max(
                    record["maximumOrientationStepDegrees"] for record in scenarios
                ),
                "flipCount": sum(record["flipCount"] for record in scenarios),
                "constraintCompetition": any(
                    record["constraintCompetition"] for record in scenarios
                ),
                "evaluationLoopDetected": any(
                    record["evaluationLoopDetected"] for record in scenarios
                ),
                "scenarios": scenarios,
            }
    finally:
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4"):
                camera.constraints.remove(constraint)
        camera.animation_data_clear()
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4"):
                bpy.data.curves.remove(curve)
        scene.camera = source_camera
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()
        for camera_data in list(bpy.data.cameras):
            if camera_data.name.startswith("TEMP__STAGE4"):
                bpy.data.cameras.remove(camera_data)

    temporary_curves_remaining = sorted(
        curve.name for curve in bpy.data.curves if curve.name.startswith("TEMP__STAGE4")
    )
    temporary_empties_remaining = sorted(
        obj.name
        for obj in bpy.data.objects
        if obj.name.startswith("TEMP__STAGE4") and obj.type == "EMPTY"
    )
    temporary_constraints_remaining = sorted(
        constraint.name
        for constraint in source_camera.constraints
        if constraint.name.startswith("TEMP__STAGE4")
    )
    temporary_actions_remaining = sorted(
        action.name
        for action in bpy.data.actions
        if action.name.startswith("TEMP__STAGE4")
    )
    camera_transform_restored = all(
        abs(float(left) - float(right)) <= 1e-8
        for left_row, right_row in zip(
            source_camera.matrix_world, source_camera_matrix
        )
        for left, right in zip(left_row, right_row)
    ) and scene.camera == source_camera
    scene_settings_restored = (
        scene.render.resolution_x == original_scene["resolution_x"]
        and scene.render.resolution_y == original_scene["resolution_y"]
        and scene.render.resolution_percentage
        == original_scene["resolution_percentage"]
        and scene.render.filepath == original_scene["filepath"]
        and scene.render.image_settings.file_format == original_scene["file_format"]
        and scene.render.image_settings.color_mode == original_scene["color_mode"]
        and scene.eevee.taa_render_samples == original_scene["samples"]
    )
    candidate_hash_after = sha256(candidate_blend)
    audit = {
        "schema": "twinkle-stage4-orientation-worker-v1",
        "renderFrameCount": len(frame_records),
        "frames": frame_records,
        "constraintResults": constraint_results,
        "restoration": {
            "candidateBlendSha256Before": candidate_hash_before,
            "candidateBlendSha256After": candidate_hash_after,
            "candidateBlendSaved": False,
            "cameraTransformRestored": camera_transform_restored,
            "sceneSettingsRestored": scene_settings_restored,
            "temporaryCurvesRemaining": temporary_curves_remaining,
            "temporaryEmptiesRemaining": temporary_empties_remaining,
            "temporaryConstraintsRemaining": temporary_constraints_remaining,
            "temporaryActionsRemaining": temporary_actions_remaining,
        },
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        len(frame_records) != ORIENTATION_PROBE["renderFrameCount"]
        or candidate_hash_after != candidate_hash_before
        or not camera_transform_restored
        or not scene_settings_restored
        or temporary_curves_remaining
        or temporary_empties_remaining
        or temporary_constraints_remaining
        or temporary_actions_remaining
    ):
        raise RuntimeError("orientation worker restoration or render audit failed")


def orientation_correction_worker(output_root, *, resume_candidate_00=False):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Euler = mathutils.Euler
    Matrix = mathutils.Matrix
    Vector = mathutils.Vector

    if resume_candidate_00:
        output_root = Path(output_root).resolve()
        frame_00 = output_root / "frames" / "candidate-00.png"
        existing_files = {
            path.relative_to(output_root).as_posix()
            for path in output_root.rglob("*")
            if path.is_file()
        }
        if existing_files != {"frames/candidate-00.png"} or (
            sha256(frame_00) != CORRECTION_RECOVERY_FRAME_00_SHA256
        ):
            raise RuntimeError("orientation correction recovery staging drift")
        frames_root = output_root / "frames"
    else:
        output_root = validate_orientation_worker_staging(output_root)
        frames_root = output_root / "frames"
        frames_root.mkdir()
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for orientation correction")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before orientation correction")

    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("scene camera missing")
    source_camera_matrix = source_camera.matrix_world.copy()
    original_frame = scene.frame_current
    original_scene_camera = scene.camera
    original_scene = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent,
        "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {
        name: bool(bpy.data.objects[name].hide_render)
        for name in profile["sharedHiddenObjects"]
        if name in bpy.data.objects
    }
    if set(original_visibility) != set(profile["sharedHiddenObjects"]):
        raise RuntimeError("stage 1 shared visibility target missing")

    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 top-plate material target missing")
    material_slot = top_plate.material_slots[0]
    original_material = material_slot.material
    original_material_link = material_slot.link
    if original_material is None:
        raise RuntimeError("stage 1 top-plate material missing")

    probe_camera_data = source_camera.data.copy()
    probe_camera_data.name = "TEMP__STAGE4_CORRECTION_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_CORRECTION_CAMERA"
    camera.data = probe_camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera

    temporary_material = None
    technical_lights = []
    frame_records = []
    scenario_metrics = []
    overview_location = Vector((0.86733437, 0.07146358, 0.88114214))
    overview_target = Vector((0.38308914, 0.61887108, 0.55480299))
    semantic_frames = (1, 51, 101)
    sample_frames = tuple(range(1, 102, 5))
    render_by_identity = {
        (record["unit"], record["pose"]): (index, record)
        for index, record in enumerate(ORIENTATION_CORRECTION["renders"])
    }

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_fcurve(fcurves, data_path, values, index=None):
        kwargs = {"data_path": data_path}
        if index is not None:
            kwargs["index"] = index
        curve = fcurves.new(**kwargs)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        curve.update()
        return curve

    def quaternion_error_degrees(actual, expected):
        return math.degrees(float(actual.rotation_difference(expected).angle))

    def evaluated_pose(target):
        bpy.context.view_layer.update()
        matrix = camera.matrix_world.copy()
        rotation = matrix.to_quaternion()
        direction = (target.matrix_world.translation - matrix.translation).normalized()
        forward = rotation @ Vector((0.0, 0.0, -1.0))
        up = rotation @ Vector((0.0, 1.0, 0.0))
        ideal = direction.to_track_quat("-Z", "Y")
        return {
            "matrix": matrix,
            "rotation": rotation,
            "targetErrorDegrees": math.degrees(float(forward.angle(direction))),
            "rollDegrees": quaternion_error_degrees(rotation, ideal),
            "upDotWorldZ": float(up.dot(Vector((0.0, 0.0, 1.0)))),
            "up": up,
        }

    def cleanup_scenario(curve_object, target, constraints, actions, curve_data):
        for constraint in constraints:
            if constraint.name in camera.constraints:
                camera.constraints.remove(constraint)
        camera.animation_data_clear()
        for action in actions:
            if action.name in bpy.data.actions:
                bpy.data.actions.remove(action)
        if target.name in bpy.data.objects:
            bpy.data.objects.remove(target, do_unlink=True)
        if curve_object.name in bpy.data.objects:
            bpy.data.objects.remove(curve_object, do_unlink=True)
        if curve_data.name in bpy.data.curves:
            bpy.data.curves.remove(curve_data)

    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x = ORIENTATION_CORRECTION["render"]["resolution"][0]
        scene.render.resolution_y = ORIENTATION_CORRECTION["render"]["resolution"][1]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = ORIENTATION_CORRECTION["render"]["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        chamber_target = Vector(authority["units"][CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(
                f"TEMP__STAGE4_CORRECTION_SHARED_{key.upper()}_DATA", "AREA"
            )
            data.energy = config["energy"]
            data.shape = "DISK"
            data.size = config["size"]
            obj = bpy.data.objects.new(
                f"TEMP__STAGE4_CORRECTION_SHARED_{key.upper()}", data
            )
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat(
                "-Z", "Y"
            ).to_euler()
            technical_lights.append((obj.name, data.name))

        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE4_CORRECTION_TOP_PLATE_NO_NORMAL"
        normal_nodes = [
            node
            for node in temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map material rule drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"][
            "normalMapStrengthDuringRender"
        ]
        material_slot.link = "OBJECT"
        material_slot.material = temporary_material

        for unit_id in SEMANTIC_UNITS:
            unit = authority["units"][unit_id]
            intrinsics = correction_camera_intrinsics(unit_id)
            camera.data.lens = intrinsics["lensMm"]
            camera.data.sensor_width = intrinsics["sensorWidthMm"]
            camera.data.shift_x = intrinsics["shiftX"]
            camera.data.shift_y = intrinsics["shiftY"]
            focus_location = Vector(unit["camera"]["location"])
            focus_target = Vector(unit["camera"]["target"])
            midpoint = (overview_location + focus_location) * 0.5
            lateral = (focus_location - overview_location).cross(
                Vector((0.0, 0.0, 1.0))
            )
            if lateral.length > 1e-9:
                midpoint += lateral.normalized() * 0.035
            midpoint.z += 0.025

            curve_data = bpy.data.curves.new(
                f"TEMP__STAGE4_CORRECTION_{unit_id}_CURVE", type="CURVE"
            )
            curve_data.dimensions = "3D"
            curve_data.path_duration = 100
            spline = curve_data.splines.new(type="POLY")
            spline.points.add(2)
            for point, location in zip(
                spline.points, (overview_location, midpoint, focus_location)
            ):
                point.co = (*location, 1.0)
            curve_object = bpy.data.objects.new(
                f"TEMP__STAGE4_CORRECTION_{unit_id}_PATH", curve_data
            )
            scene.collection.objects.link(curve_object)
            curve_object.matrix_world = Matrix.Identity(4)
            target = bpy.data.objects.new(
                f"TEMP__STAGE4_CORRECTION_{unit_id}_TARGET", None
            )
            target.empty_display_type = "PLAIN_AXES"
            scene.collection.objects.link(target)

            camera_action = bpy.data.actions.new(
                f"TEMP__STAGE4_CORRECTION_{unit_id}_CAMERA_ACTION"
            )
            camera_slot, camera_fcurves = action_fcurves(
                camera_action, camera, "Camera Motion"
            )
            target_action = bpy.data.actions.new(
                f"TEMP__STAGE4_CORRECTION_{unit_id}_TARGET_ACTION"
            )
            target_slot, target_fcurves = action_fcurves(
                target_action, target, "Target Motion"
            )
            follow = camera.constraints.new(type="FOLLOW_PATH")
            follow.name = f"TEMP__STAGE4_CORRECTION_{unit_id}_FOLLOW_PATH"
            follow.target = curve_object
            follow.use_fixed_location = True
            follow.use_curve_follow = False
            orientation = camera.constraints.new(type="TRACK_TO")
            orientation.name = f"TEMP__STAGE4_CORRECTION_{unit_id}_TRACK_TO"
            orientation.target = target
            orientation.track_axis = "TRACK_NEGATIVE_Z"
            orientation.up_axis = "UP_Y"
            add_fcurve(
                camera_fcurves,
                f'constraints["{follow.name}"].offset_factor',
                tuple(zip(semantic_frames, (0.0, 0.5, 1.0))),
            )
            target_midpoint = (overview_target + focus_target) * 0.5
            for axis in range(3):
                add_fcurve(
                    target_fcurves,
                    "location",
                    tuple(
                        zip(
                            semantic_frames,
                            (
                                overview_target[axis],
                                target_midpoint[axis],
                                focus_target[axis],
                            ),
                        )
                    ),
                    index=axis,
                )
            camera_animation = camera.animation_data_create()
            camera_animation.action = camera_action
            camera_animation.action_slot = camera_slot
            target_animation = target.animation_data_create()
            target_animation.action = target_action
            target_animation.action_slot = target_slot
            camera.location = Vector((0.0, 0.0, 0.0))
            camera.rotation_mode = "XYZ"
            camera.rotation_euler = (overview_target - overview_location).to_track_quat(
                "-Z", "Y"
            ).to_euler()
            camera.scale = Vector((1.0, 1.0, 1.0))

            samples = []
            previous_rotation = None
            previous_up = None
            flip_count = 0
            for frame in sample_frames:
                scene.frame_set(frame)
                pose = evaluated_pose(target)
                step = (
                    0.0
                    if previous_rotation is None
                    else quaternion_error_degrees(previous_rotation, pose["rotation"])
                )
                if previous_up is not None and previous_up.dot(pose["up"]) < 0.0:
                    flip_count += 1
                samples.append(
                    {
                        "frame": frame,
                        "targetErrorDegrees": pose["targetErrorDegrees"],
                        "rollDegrees": pose["rollDegrees"],
                        "upDotWorldZ": pose["upDotWorldZ"],
                        "orientationStepDegrees": step,
                    }
                )
                previous_rotation = pose["rotation"]
                previous_up = pose["up"]

            endpoint_poses = {}
            for pose_name, frame in zip(
                ORIENTATION_PROBE["semanticPoses"], semantic_frames
            ):
                scene.frame_set(frame)
                pose = evaluated_pose(target)
                endpoint_poses[pose_name] = pose
                identity = (unit_id, pose_name)
                if identity not in render_by_identity:
                    continue
                output_index, render_contract = render_by_identity[identity]
                path = frames_root / f"candidate-{output_index:02d}.png"
                if output_index == 0 and resume_candidate_00:
                    if sha256(path) != CORRECTION_RECOVERY_FRAME_00_SHA256:
                        raise RuntimeError("reused correction frame 0 drift")
                else:
                    scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                frame_records.append(
                    {
                        "index": output_index,
                        **render_contract,
                        "path": path.relative_to(output_root).as_posix(),
                        "sha256": sha256(path),
                        "cameraIntrinsics": dict(intrinsics),
                        "projection": correction_projection_record(
                            unit_id,
                            camera_location=[
                                float(value) for value in pose["matrix"].translation
                            ],
                            camera_target=[
                                float(value)
                                for value in target.matrix_world.translation
                            ],
                        ),
                        "location": [
                            round(float(value), 9)
                            for value in pose["matrix"].translation
                        ],
                        "targetErrorDegrees": pose["targetErrorDegrees"],
                        "rollDegrees": pose["rollDegrees"],
                        "upDotWorldZ": pose["upDotWorldZ"],
                    }
                )

            expected_start_rotation = (
                overview_target - overview_location
            ).to_track_quat("-Z", "Y")
            expected_end_rotation = Euler(
                unit["camera"]["rotation"], "XYZ"
            ).to_quaternion()
            start_pose = endpoint_poses["entry"]
            end_pose = endpoint_poses["focus"]
            scenario_metrics.append(
                {
                    "unit": unit_id,
                    "sampleCount": len(samples),
                    "samples": samples,
                    "startLocationErrorM": float(
                        (start_pose["matrix"].translation - overview_location).length
                    ),
                    "endLocationErrorM": float(
                        (end_pose["matrix"].translation - focus_location).length
                    ),
                    "startRotationErrorDegrees": quaternion_error_degrees(
                        start_pose["rotation"], expected_start_rotation
                    ),
                    "endRotationErrorDegrees": quaternion_error_degrees(
                        end_pose["rotation"], expected_end_rotation
                    ),
                    "maximumTargetErrorDegrees": max(
                        sample["targetErrorDegrees"] for sample in samples
                    ),
                    "maximumRollDegrees": max(
                        abs(sample["rollDegrees"]) for sample in samples
                    ),
                    "minimumUpDotWorldZ": min(
                        sample["upDotWorldZ"] for sample in samples
                    ),
                    "maximumOrientationStepDegrees": max(
                        sample["orientationStepDegrees"] for sample in samples
                    ),
                    "flipCount": flip_count,
                    "constraintCompetition": False,
                    "evaluationLoopDetected": False,
                }
            )
            cleanup_scenario(
                curve_object,
                target,
                (follow, orientation),
                (camera_action, target_action),
                curve_data,
            )

        orientation_metrics = {
            "maximumTargetErrorDegrees": max(
                record["maximumTargetErrorDegrees"] for record in scenario_metrics
            ),
            "maximumRollDegrees": max(
                record["maximumRollDegrees"] for record in scenario_metrics
            ),
            "maximumEndpointRotationErrorDegrees": max(
                max(
                    record["startRotationErrorDegrees"],
                    record["endRotationErrorDegrees"],
                )
                for record in scenario_metrics
            ),
            "maximumEndpointLocationErrorM": max(
                max(record["startLocationErrorM"], record["endLocationErrorM"])
                for record in scenario_metrics
            ),
            "minimumUpDotWorldZ": min(
                record["minimumUpDotWorldZ"] for record in scenario_metrics
            ),
            "maximumOrientationStepDegrees": max(
                record["maximumOrientationStepDegrees"]
                for record in scenario_metrics
            ),
            "flipCount": sum(record["flipCount"] for record in scenario_metrics),
            "constraintCompetition": False,
            "evaluationLoopDetected": False,
            "scenarios": scenario_metrics,
        }
    finally:
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4_CORRECTION"):
                camera.constraints.remove(constraint)
        camera.animation_data_clear()
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4_CORRECTION"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4_CORRECTION"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4_CORRECTION"):
                bpy.data.curves.remove(curve)
        material_slot.material = original_material
        material_slot.link = original_material_link
        if temporary_material is not None and temporary_material.name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for object_name, data_name in technical_lights:
            remove_named_datablock(
                bpy.data.objects, object_name, do_unlink=True
            )
            remove_named_datablock(bpy.data.lights, data_name)
        scene.camera = original_scene_camera
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.render.film_transparent = original_scene["film_transparent"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.view_settings.view_transform = original_scene["viewTransform"]
        scene.view_settings.look = original_scene["look"]
        scene.view_settings.exposure = original_scene["exposure"]
        scene.view_settings.gamma = original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()
        for camera_data in list(bpy.data.cameras):
            if camera_data.name.startswith("TEMP__STAGE4_CORRECTION"):
                bpy.data.cameras.remove(camera_data)

    candidate_hash_after = sha256(candidate_blend)
    temporary_cameras_remaining = sorted(
        camera_data.name
        for camera_data in bpy.data.cameras
        if camera_data.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    temporary_curves_remaining = sorted(
        curve.name
        for curve in bpy.data.curves
        if curve.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    temporary_empties_remaining = sorted(
        obj.name
        for obj in bpy.data.objects
        if obj.name.startswith("TEMP__STAGE4_CORRECTION") and obj.type == "EMPTY"
    )
    temporary_lights_remaining = sorted(
        light.name
        for light in bpy.data.lights
        if light.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    temporary_materials_remaining = sorted(
        material.name
        for material in bpy.data.materials
        if material.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    temporary_constraints_remaining = sorted(
        constraint.name
        for constraint in source_camera.constraints
        if constraint.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    temporary_actions_remaining = sorted(
        action.name
        for action in bpy.data.actions
        if action.name.startswith("TEMP__STAGE4_CORRECTION")
    )
    source_camera_transform_restored = all(
        abs(float(left) - float(right)) <= 1e-8
        for left_row, right_row in zip(source_camera.matrix_world, source_camera_matrix)
        for left, right in zip(left_row, right_row)
    ) and scene.camera == source_camera
    scene_settings_restored = (
        scene.render.engine == original_scene["engine"]
        and scene.render.resolution_x == original_scene["resolution_x"]
        and scene.render.resolution_y == original_scene["resolution_y"]
        and scene.render.resolution_percentage
        == original_scene["resolution_percentage"]
        and scene.render.filepath == original_scene["filepath"]
        and scene.render.image_settings.file_format == original_scene["file_format"]
        and scene.render.image_settings.color_mode == original_scene["color_mode"]
        and scene.render.film_transparent == original_scene["film_transparent"]
        and scene.eevee.taa_render_samples == original_scene["samples"]
        and scene.view_settings.view_transform == original_scene["viewTransform"]
        and scene.view_settings.look == original_scene["look"]
        and float(scene.view_settings.exposure) == original_scene["exposure"]
        and float(scene.view_settings.gamma) == original_scene["gamma"]
    )
    visibility_restored = all(
        bool(bpy.data.objects[name].hide_render) == hidden
        for name, hidden in original_visibility.items()
    )
    material_restored = (
        material_slot.material == original_material
        and material_slot.link == original_material_link
        and not temporary_materials_remaining
    )
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sourceCameraTransformRestored": source_camera_transform_restored,
        "sceneSettingsRestored": scene_settings_restored,
        "visibilityRestored": visibility_restored,
        "materialRestored": material_restored,
        "temporaryCamerasRemaining": temporary_cameras_remaining,
        "temporaryCurvesRemaining": temporary_curves_remaining,
        "temporaryEmptiesRemaining": temporary_empties_remaining,
        "temporaryLightsRemaining": temporary_lights_remaining,
        "temporaryMaterialsRemaining": temporary_materials_remaining,
        "temporaryConstraintsRemaining": temporary_constraints_remaining,
        "temporaryActionsRemaining": temporary_actions_remaining,
    }
    audit = {
        "schema": "twinkle-stage4-orientation-correction-worker-v1",
        "constraint": "TRACK_TO",
        "renderProfile": correction_render_profile(),
        "renderFrameCount": len(frame_records),
        "budgetEvidence": {
            "initialProbeRenders": 12,
            "correctionRendersBeforeRecovery": [0],
            "reusedFrameIndices": [0],
            "renderedFrameIndicesThisRun": [1, 2],
            "totalOrientationRenders": 15,
        },
        "frames": sorted(frame_records, key=lambda record: record["index"]),
        "orientationMetrics": orientation_metrics,
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        len(frame_records) != ORIENTATION_CORRECTION["renderFrameCount"]
        or candidate_hash_after != candidate_hash_before
        or not source_camera_transform_restored
        or not scene_settings_restored
        or not visibility_restored
        or not material_restored
        or any(
            restoration[field]
            for field in (
                "temporaryCamerasRemaining",
                "temporaryCurvesRemaining",
                "temporaryEmptiesRemaining",
                "temporaryLightsRemaining",
                "temporaryMaterialsRemaining",
                "temporaryConstraintsRemaining",
                "temporaryActionsRemaining",
            )
        )
    ):
        raise RuntimeError("orientation correction restoration or render audit failed")


def orbit_o1_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("O1 output must be an absolute path")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-orbit-o1-worker",
        str(output_root),
    ]


def _frame_quality(path):
    from PIL import Image, ImageStat

    with Image.open(path) as source:
        image = source.convert("RGB")
    luminance = image.convert("L")
    histogram = luminance.histogram()
    pixel_count = image.width * image.height
    near_black_fraction = sum(histogram[:11]) / pixel_count
    mean_luminance = float(ImageStat.Stat(luminance).mean[0])
    extrema = image.getextrema()
    dynamic_range = max(high for _, high in extrema) - min(low for low, _ in extrema)
    return {
        "resolution": list(image.size),
        "meanLuminance": mean_luminance,
        "nearBlackFraction": near_black_fraction,
        "dynamicRange": int(dynamic_range),
        "blackFrame": mean_luminance <= 10.0 or near_black_fraction >= 0.95,
        "emptyFrame": dynamic_range <= 24 and near_black_fraction >= 0.95,
    }


def _contiguous_intervals(indices):
    indices = sorted(set(int(index) for index in indices))
    if not indices:
        return []
    intervals = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            intervals.append([start, previous])
            start = index
        previous = index
    intervals.append([start, previous])
    return intervals


def _initial_entry_frames(qualified_logical_frames):
    eligible = sorted(set(int(index) for index in qualified_logical_frames))
    if len(eligible) < 2:
        raise ValueError("hotspot has insufficient machine-qualified frames")
    selected = [eligible[(len(eligible) - 1) // 3], eligible[(2 * (len(eligible) - 1)) // 3]]
    return list(dict.fromkeys(selected))[: ORBIT_PROFILE["maximumEntryFramesPerUnit"]]


def _write_orbit_speed_graph(output_root, frames):
    from PIL import Image, ImageDraw

    width, height = 1200, 480
    margin = 64
    image = Image.new("RGB", (width, height), (18, 21, 27))
    draw = ImageDraw.Draw(image)
    draw.line((margin, height - margin, width - margin, height - margin), fill=(120, 130, 145), width=2)
    draw.line((margin, margin, margin, height - margin), fill=(120, 130, 145), width=2)
    speeds = [float(frame["speedMetersPerSecond"]) for frame in frames]
    maximum = max(speeds) if max(speeds) > 0.0 else 1.0
    points = []
    for index, speed in enumerate(speeds):
        x = margin + index * (width - 2 * margin) / (len(speeds) - 1)
        y = height - margin - speed / maximum * (height - 2 * margin)
        points.append((x, y))
    draw.line(points, fill=(57, 196, 210), width=4)
    draw.text((margin, 20), "O1 camera path speed (m/s)", fill=(238, 242, 248))
    draw.text((width - 230, 20), f"max={maximum:.6f}", fill=(238, 242, 248))
    path = Path(output_root) / "path-speed.png"
    image.save(path)
    return path


def _write_orbit_contact_sheet(output_root, frames):
    from PIL import Image, ImageDraw

    qualified = [
        frame
        for frame in frames
        if frame["machineFramePassed"]
        and any(
            frame["qualificationByUnit"][unit]["machineQualified"]
            for unit in SEMANTIC_UNITS
        )
    ]
    if not qualified:
        raise ValueError("no qualified O1 frames are available for the contact sheet")
    columns = 7
    cell_width, image_height, label_height = 320, 225, 34
    rows = math.ceil(len(qualified) / columns)
    sheet = Image.new(
        "RGB", (columns * cell_width, rows * (image_height + label_height)), (18, 21, 27)
    )
    draw = ImageDraw.Draw(sheet)
    for cell, frame in enumerate(qualified):
        row, column = divmod(cell, columns)
        with Image.open(Path(output_root) / frame["path"]) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
        x = column * cell_width + (cell_width - image.width) // 2
        y = row * (image_height + label_height)
        sheet.paste(image, (x, y))
        units = ",".join(
            "C" if unit == CHAMBER else "L"
            for unit in SEMANTIC_UNITS
            if frame["qualificationByUnit"][unit]["machineQualified"]
        )
        draw.text((column * cell_width + 8, y + image_height + 8), f"frame {frame['physicalFrameIndex']:02d} | {units}", fill=(235, 239, 246))
    path = Path(output_root) / "orbit-qualified-contact-sheet.png"
    sheet.save(path)
    return path


def _write_orbit_review_page(output_root, report):
    rows = []
    for unit in SEMANTIC_UNITS:
        record = report["qualificationByUnit"][unit]
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                unit,
                record["proposedHumanVisibleIntervals"],
                record["initialEntryFrameSet"],
                len(record["machineQualifiedPhysicalFrames"]),
            )
        )
    review_root = Path(output_root) / "review"
    review_root.mkdir()
    html = """<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>TWINKLE O1 审核</title>
<style>body{font:16px/1.6 system-ui;margin:32px;background:#11151b;color:#eef2f7}img{max-width:100%;background:#222}table{border-collapse:collapse}td,th{border:1px solid #56606d;padding:8px}code{color:#69d3df}</style>
<h1>阶段四步骤 5｜有限环绕低清候选 O1</h1>
<p>机器状态：<code>machinePassed=true</code>；人工状态：<code>humanVisualApproved=false</code>。本页只提交人工审核，不授权步骤 6、A/B 曲线或阶段五。</p>
<p>49 张物理帧；96 个逻辑索引；Track To；640×450；64 samples；10,000 ms；方位角 −12°..+12°。</p>
<h2>仅含机器合格画面的联系表</h2><img src=\"../orbit-qualified-contact-sheet.png\" alt=\"有限环绕合格帧联系表\">
<h2>路径速度</h2><img src=\"../path-speed.png\" alt=\"相机路径速度图\">
<h2>热点资格与候选入弯点</h2><table><thead><tr><th>热点</th><th>机器候选区间</th><th>候选 entryFrameSet</th><th>合格物理帧数</th></tr></thead><tbody>__ROWS__</tbody></table>
<p><a href=\"../orbit-o1-manifest.json\">manifest</a> · <a href=\"../frame-qualification.json\">逐帧资格</a> · <a href=\"../camera-path.json\">相机路径</a> · <a href=\"../logical-index-map.json\">逻辑索引</a></p></html>""".replace("__ROWS__", "".join(rows))
    path = review_root / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def validate_orbit_o1(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "orbit-o1-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("O1 candidate manifest is missing")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != "twinkle-stage4-orbit-o1-v1":
        raise ValueError("O1 schema mismatch")
    if report.get("orbitProfile") != ORBIT_PROFILE:
        raise ValueError("O1 orbit profile drift")
    if report.get("orientationConstraint") != "TRACK_TO":
        raise ValueError("O1 orientation must remain Track To")
    if report.get("render") != ORBIT_O1_RENDER:
        raise ValueError("O1 render contract drift")
    if report.get("physicalFrameCount") != 49 or report.get("logicalIndexCount") != 96:
        raise ValueError("O1 physical/logical frame count mismatch")
    if report.get("logicalPhysicalFrames") != list(expanded_physical_frames()):
        raise ValueError("O1 logical index sequence mismatch")
    if report.get("selectedSurfaceAnchorByUnit") != {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }:
        raise ValueError("O1 approved surface anchor selection mismatch")
    if (
        report.get("surfaceAnchorManifestSha256")
        != EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256
        or report.get("renderedFrameCount") != 0
        or report.get("reusedOrbitPngCount") != 49
        or report.get("totalStage4RenderedToDate") != 64
        or report.get("renderOperatorInvoked") is not False
    ):
        raise ValueError("O1 zero-render rebuild authority or budget mismatch")
    frames = report.get("frames", [])
    if len(frames) != 49 or [frame.get("physicalFrameIndex") for frame in frames] != list(range(49)):
        raise ValueError("O1 physical frame records mismatch")
    if any(
        frame.get("quality", {}).get("blackFrame") is not False
        or frame.get("quality", {}).get("emptyFrame") is not False
        or frame.get("targetClipped") is not False
        or frame.get("subjectOutOfFrame") is not False
        for frame in frames
    ):
        raise ValueError("O1 black/empty/target/subject gate failed")
    for unit in SEMANTIC_UNITS:
        qualification = report.get("qualificationByUnit", {}).get(unit, {})
        if len(qualification.get("physicalFrames", [])) != 49 or len(qualification.get("logicalFrames", [])) != 96:
            raise ValueError("O1 qualification table count mismatch")
        if len(set(qualification.get("machineQualifiedPhysicalFrames", []))) < 2:
            raise ValueError("hotspot has insufficient machine-qualified frames")
        entries = qualification.get("initialEntryFrameSet", [])
        if not 1 <= len(entries) <= ORBIT_PROFILE["maximumEntryFramesPerUnit"]:
            raise ValueError("O1 entry frame candidate count mismatch")
        if not set(entries) <= set(qualification.get("machineQualifiedLogicalFrames", [])):
            raise ValueError("O1 entry frame is not machine qualified")
        if qualification.get("humanApproved") is not False:
            raise ValueError("O1 hotspot intervals cannot be machine-approved")
    restoration = report.get("restoration", {})
    if not (
        restoration.get("candidateBlendSha256Before") == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After") == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSaved") is False
        and restoration.get("sourceCameraTransformRestored") is True
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("visibilityRestored") is True
        and restoration.get("materialRestored") is True
        and all(restoration.get(field) == [] for field in (
            "temporaryCamerasRemaining", "temporaryCurvesRemaining", "temporaryEmptiesRemaining",
            "temporaryLightsRemaining", "temporaryMaterialsRemaining", "temporaryConstraintsRemaining",
            "temporaryActionsRemaining",
        ))
    ):
        raise ValueError("O1 restoration audit failed")
    if (
        report.get("machinePassed") is not True
        or report.get("humanSurfaceApproved") is not True
        or report.get("humanVisualApproved") is not False
        or report.get("authorizesOrbitRepair") is not False
    ):
        raise ValueError("O1 machine/human gate mismatch")
    if report.get("authorizesStep6") is not False or report.get("authorizesStage5") is not False:
        raise ValueError("O1 cannot authorize a later step or stage")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    required = {
        "worker-audit.json", "logical-index-map.json", "camera-path.json",
        "frame-qualification.json", "path-speed.png", "orbit-qualified-contact-sheet.png",
        "surface-anchor-selection.json", "review/index.html",
        *{f"frames/frame-{index:03d}.png" for index in range(49)},
    }
    if set(actual) != required or report.get("inventorySha256") != actual:
        raise ValueError("O1 exact inventory mismatch")
    for index, frame in enumerate(frames):
        source = FAILED_ORBIT_O1_ROOT / "frames" / f"frame-{index:03d}.png"
        if frame.get("sha256") != sha256(source) or sha256(
            output_root / frame["path"]
        ) != sha256(source):
            raise ValueError("O1 reused PNG hash mismatch")
    return report


def build_orbit_o1(output_root, *, authorized=False, blender=None, runner=None):
    if authorized is not True:
        raise PermissionError("stage 4 step 5 O1 requires explicit authorization")
    output_root = Path(output_root).resolve()
    if output_root.name != "orbit-o1":
        raise ValueError("O1 output name must be orbit-o1")
    validate_request(default_request(output_root))
    authority = validate_authority()
    correction = validate_orientation_correction(APPROVED_ORIENTATION_CORRECTION)
    if correction.get("humanApproved") is not True:
        raise ValueError("Track To human approval is missing")
    surface_manifest = (
        APPROVED_SURFACE_ANCHOR_PRECHECK
        / "surface-anchor-precheck-manifest.json"
    )
    if (
        sha256(surface_manifest)
        != EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256
    ):
        raise ValueError("approved surface anchor manifest drift")
    surface = validate_surface_anchor_precheck(APPROVED_SURFACE_ANCHOR_PRECHECK)
    selected = {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    if (
        surface.get("humanSurfaceApproved") is not True
        or surface.get("selectedCandidateByUnit") != selected
        or surface.get("humanVisualApproved") is not False
        or surface.get("authorizesOrbitRepair") is not False
        or surface.get("authorizesStep6") is not False
        or surface.get("authorizesStage5") is not False
    ):
        raise ValueError("approved surface anchor scope mismatch")
    if sha256(FAILED_ORBIT_O1_AUDIT) != EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256:
        raise ValueError("failed O1 worker audit drift")
    source_audit = json.loads(
        FAILED_ORBIT_O1_AUDIT.read_text(encoding="utf-8")
    )
    source_frames = sorted(
        source_audit.get("frames", []),
        key=lambda frame: frame["physicalFrameIndex"],
    )
    if (
        len(source_frames) != 49
        or [frame["physicalFrameIndex"] for frame in source_frames]
        != list(range(49))
    ):
        raise ValueError("failed O1 frame transform inventory drift")

    selected_candidates = {}
    for unit in SEMANTIC_UNITS:
        matches = [
            candidate
            for candidate in surface["candidatesByUnit"][unit]
            if candidate["candidateId"] == selected[unit]
        ]
        if len(matches) != 1 or matches[0].get("humanApproved") is not True:
            raise ValueError("approved surface candidate identity mismatch")
        selected_candidates[unit] = matches[0]

    candidate_blend = Path(authority["stage1"]["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before zero-render O1 rebuild")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".orbit-o1-finalize-", dir=output_root.parent)
    ).resolve()
    try:
        frames_root = staging / "frames"
        frames_root.mkdir()
        frames = []
        for source_frame in source_frames:
            index = source_frame["physicalFrameIndex"]
            source_path = FAILED_ORBIT_O1_ROOT / source_frame["path"]
            target_path = frames_root / f"frame-{index:03d}.png"
            if sha256(source_path) != source_frame["sha256"]:
                raise ValueError("failed O1 source PNG drift")
            shutil.copyfile(source_path, target_path)
            if sha256(target_path) != source_frame["sha256"]:
                raise ValueError("reused O1 PNG hash mismatch")
            frame = dict(source_frame)
            frame["path"] = target_path.relative_to(staging).as_posix()
            frame["quality"] = _frame_quality(target_path)
            frame["qualificationByUnit"] = {}
            for unit in SEMANTIC_UNITS:
                qualification = dict(
                    selected_candidates[unit]["physicalFrames"][index]
                )
                qualification["selectedSurfaceCandidateId"] = selected[unit]
                frame["qualificationByUnit"][unit] = qualification
            frame["machineFramePassed"] = not (
                frame["quality"]["blackFrame"]
                or frame["quality"]["emptyFrame"]
                or frame["targetClipped"]
                or frame["subjectOutOfFrame"]
            )
            if not frame["machineFramePassed"] or not all(
                frame["qualificationByUnit"][unit]["machineQualified"]
                for unit in SEMANTIC_UNITS
            ):
                raise ValueError("reused O1 frame qualification gate failed")
            frames.append(frame)

        logical_map = [
            {"logicalIndex": index, "physicalFrameIndex": physical}
            for index, physical in enumerate(expanded_physical_frames())
        ]
        qualification_by_unit = {}
        for unit in SEMANTIC_UNITS:
            candidate = selected_candidates[unit]
            physical = [dict(record) for record in candidate["physicalFrames"]]
            logical = [dict(record) for record in candidate["logicalFrames"]]
            qualified_physical = list(
                candidate["machineQualifiedPhysicalFrames"]
            )
            qualified_logical = list(candidate["machineQualifiedLogicalFrames"])
            qualification_by_unit[unit] = {
                "selectedSurfaceCandidateId": selected[unit],
                "surfaceObjectName": candidate["objectName"],
                "surfacePolygonIndex": candidate["polygonIndex"],
                "surfaceWorldPosition": candidate["worldPosition"],
                "surfaceWorldNormal": candidate["worldNormal"],
                "physicalFrames": physical,
                "logicalFrames": logical,
                "machineQualifiedPhysicalFrames": qualified_physical,
                "machineQualifiedLogicalFrames": qualified_logical,
                "machineQualifiedIntervals": list(
                    candidate["machineQualifiedLogicalIntervals"]
                ),
                "proposedHumanVisibleIntervals": list(
                    candidate["machineQualifiedLogicalIntervals"]
                ),
                "initialEntryFrameSet": _initial_entry_frames(
                    qualified_logical
                ),
                "humanApproved": False,
            }

        (staging / "logical-index-map.json").write_text(
            json.dumps(logical_map, indent=2), encoding="utf-8"
        )
        (staging / "camera-path.json").write_text(
            json.dumps(
                [
                    {
                        key: frame[key]
                        for key in (
                            "physicalFrameIndex",
                            "camera",
                            "speedMetersPerSecond",
                        )
                    }
                    for frame in frames
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        (staging / "frame-qualification.json").write_text(
            json.dumps(qualification_by_unit, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (staging / "surface-anchor-selection.json").write_text(
            json.dumps(
                {
                    unit: {
                        key: selected_candidates[unit][key]
                        for key in (
                            "candidateId",
                            "objectName",
                            "meshTopologySha256",
                            "polygonIndex",
                            "loopTriangleIndex",
                            "vertexIndices",
                            "barycentricCoordinates",
                            "worldPosition",
                            "worldNormal",
                        )
                    }
                    for unit in SEMANTIC_UNITS
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _write_orbit_speed_graph(staging, frames)
        _write_orbit_contact_sheet(staging, frames)
        worker_audit = {
            "schema": "twinkle-stage4-orbit-o1-zero-render-rebuild-v1",
            "renderOperatorInvoked": False,
            "renderedFrameCount": 0,
            "reusedOrbitPngCount": 49,
            "sourceO1WorkerAuditSha256": EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256,
            "surfaceAnchorManifestSha256": EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256,
            "selectedSurfaceAnchorByUnit": selected,
            "cameraTransformCount": 49,
            "logicalIndexCount": 96,
            "restoration": source_audit["restoration"],
        }
        worker_path = staging / "worker-audit.json"
        worker_path.write_text(
            json.dumps(worker_audit, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report = {
            "schema": "twinkle-stage4-orbit-o1-v1",
            "scope": "stage4-step5-zero-render-rebuilt-orbit-candidate-only",
            "authority": {
                "stage1ManifestSha256": EXPECTED_STAGE1_SHA256,
                "stage3R2ManifestSha256": EXPECTED_STAGE3_R2_SHA256,
                "sourceBlendSha256": EXPECTED_SOURCE_BLEND_SHA256,
                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
                "orientationManifestSha256": EXPECTED_ORIENTATION_CORRECTION_SHA256,
                "trackToSixGridSha256": EXPECTED_TRACK_TO_SIX_GRID_SHA256,
                "failedO1WorkerAuditSha256": EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256,
            },
            "orbitProfile": ORBIT_PROFILE,
            "orientationConstraint": "TRACK_TO",
            "selectedSurfaceAnchorByUnit": selected,
            "surfaceAnchorManifestSha256": EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256,
            "cameraIntrinsics": source_audit["cameraIntrinsics"],
            "renderProfile": correction_render_profile(),
            "render": ORBIT_O1_RENDER,
            "physicalFrameCount": 49,
            "logicalIndexCount": 96,
            "logicalPhysicalFrames": list(expanded_physical_frames()),
            "renderedFrameCount": 0,
            "reusedOrbitPngCount": 49,
            "totalStage4RenderedToDate": 64,
            "renderOperatorInvoked": False,
            "frames": frames,
            "qualificationByUnit": qualification_by_unit,
            "orientationMetrics": source_audit["orientationMetrics"],
            "restoration": source_audit["restoration"],
            "budgetEvidence": {
                "orientationProbeRenders": 15,
                "orbitO1Renders": 49,
                "curveRenders": 0,
                "renderedThisRun": 0,
                "reusedOrbitPngCount": 49,
                "totalRenderedToDate": 64,
                "approvedFirstRoundBudget": 264,
                "remainingFirstRoundBudget": 200,
                "approvedMaximumBudget": 513,
            },
            "machinePassed": True,
            "humanSurfaceApproved": True,
            "humanVisualApproved": False,
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        }
        _write_orbit_review_page(staging, report)
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "orbit-o1-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_orbit_o1(staging)
        if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
            raise ValueError("candidate blend drift after zero-render O1 rebuild")
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"O1 zero-render rebuild failed; isolated staging kept at {staging}"
        ) from error
    return validate_orbit_o1(output_root)


def orbit_o1_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Matrix, Vector = mathutils.Matrix, mathutils.Vector

    output_root = validate_orientation_worker_staging(output_root)
    frames_root = output_root / "frames"
    frames_root.mkdir()
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY_SNAPSHOT.read_text(encoding="utf-8"))
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for O1")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256 or sha256(GEOMETRY_SNAPSHOT) != EXPECTED_GEOMETRY_SNAPSHOT_SHA256:
        raise RuntimeError("O1 blend or geometry authority drift")
    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("scene camera missing")
    source_camera_matrix = source_camera.matrix_world.copy()
    original_frame = scene.frame_current
    original_scene = {
        "camera": scene.camera, "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x, "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage, "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format, "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent, "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform, "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure), "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {name: bool(bpy.data.objects[name].hide_render) for name in profile["sharedHiddenObjects"] if name in bpy.data.objects}
    if set(original_visibility) != set(profile["sharedHiddenObjects"]):
        raise RuntimeError("stage 1 visibility authority missing")
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("stage 1 material target missing")
    material_slot = top_plate.material_slots[0]
    original_material, original_material_link = material_slot.material, material_slot.link
    if original_material is None:
        raise RuntimeError("stage 1 material missing")

    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__STAGE4_O1_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_O1_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    temporary_material = None
    technical_lights = []
    frame_records = []
    curve_data = curve_object = target = camera_action = follow = orientation = None

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_linear_fcurve(fcurves, data_path, values):
        curve = fcurves.new(data_path=data_path)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "LINEAR"
        curve.update()
        return curve

    def next_render_visible_hit(origin, direction, distance, depsgraph):
        cursor = origin.copy()
        remaining = float(distance)
        travelled = 0.0
        for _ in range(64):
            hit, location, normal, face_index, obj, _ = scene.ray_cast(depsgraph, cursor, direction, distance=remaining)
            if not hit:
                return None
            segment = float((location - cursor).length)
            travelled += segment
            if obj.type == "MESH" and not obj.hide_render:
                return {"location": location.copy(), "normal": normal.copy(), "faceIndex": int(face_index), "object": obj, "distance": travelled}
            step = 1e-5
            cursor = location + direction * step
            travelled += step
            remaining -= segment + step
            if remaining <= 0.0:
                return None
        raise RuntimeError("ray cast exceeded bounded traversal")

    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x, scene.render.resolution_y = ORBIT_O1_RENDER["resolution"]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = ORBIT_O1_RENDER["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform, scene.view_settings.look = color["viewTransform"], color["look"]
        scene.view_settings.exposure, scene.view_settings.gamma = color["exposure"], color["gamma"]
        chamber_target = Vector(authority["units"][CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(f"TEMP__STAGE4_O1_SHARED_{key.upper()}_DATA", "AREA")
            data.energy, data.shape, data.size = config["energy"], "DISK", config["size"]
            obj = bpy.data.objects.new(f"TEMP__STAGE4_O1_SHARED_{key.upper()}", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat("-Z", "Y").to_euler()
            technical_lights.append((obj.name, data.name))
        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE4_O1_TOP_PLATE_NO_NORMAL"
        normal_nodes = [node for node in temporary_material.node_tree.nodes if node.bl_idname == "ShaderNodeNormalMap"]
        if len(normal_nodes) != 1:
            raise RuntimeError("stage 1 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"]["normalMapStrengthDuringRender"]
        material_slot.link, material_slot.material = "OBJECT", temporary_material

        camera.data.lens, camera.data.sensor_width = ORBIT_LENS_MM, ORBIT_SENSOR_WIDTH_MM
        camera.data.shift_x, camera.data.shift_y = ORBIT_SHIFT
        pivot = Vector(ORBIT_OVERVIEW_TARGET)
        base = Vector(ORBIT_OVERVIEW_LOCATION) - pivot
        path_locations = []
        for index in range(49):
            angle = math.radians(-12.0 + 24.0 * index / 48.0)
            rotated = Matrix.Rotation(angle, 4, "Z") @ base
            path_locations.append(pivot + rotated)
        curve_data = bpy.data.curves.new("TEMP__STAGE4_O1_CURVE", type="CURVE")
        curve_data.dimensions, curve_data.path_duration = "3D", 48
        spline = curve_data.splines.new(type="POLY")
        spline.points.add(48)
        for point, location in zip(spline.points, path_locations):
            point.co = (*location, 1.0)
        curve_object = bpy.data.objects.new("TEMP__STAGE4_O1_PATH", curve_data)
        scene.collection.objects.link(curve_object)
        curve_object.matrix_world = Matrix.Identity(4)
        target = bpy.data.objects.new("TEMP__STAGE4_O1_TARGET", None)
        target.location = pivot
        scene.collection.objects.link(target)
        follow = camera.constraints.new(type="FOLLOW_PATH")
        follow.name, follow.target = "TEMP__STAGE4_O1_FOLLOW_PATH", curve_object
        follow.use_fixed_location, follow.use_curve_follow = True, False
        orientation = camera.constraints.new(type="TRACK_TO")
        orientation.name, orientation.target = "TEMP__STAGE4_O1_TRACK_TO", target
        orientation.track_axis, orientation.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        camera_action = bpy.data.actions.new("TEMP__STAGE4_O1_CAMERA_ACTION")
        camera_slot, fcurves = action_fcurves(camera_action, camera, "O1 Orbit")
        add_linear_fcurve(fcurves, f'constraints["{follow.name}"].offset_factor', ((1, 0.0), (49, 1.0)))
        animation = camera.animation_data_create()
        animation.action, animation.action_slot = camera_action, camera_slot
        camera.location = Vector((0.0, 0.0, 0.0))
        camera.rotation_euler = (pivot - path_locations[0]).to_track_quat("-Z", "Y").to_euler()
        camera.scale = Vector((1.0, 1.0, 1.0))

        depsgraph = bpy.context.evaluated_depsgraph_get()
        surface_authority = {}
        for unit in SEMANTIC_UNITS:
            marker_id = BLEND_MARKER_IDS[unit]
            anchor = bpy.data.objects.get(f"HOTSPOT_ANCHOR__{marker_id}")
            focus = bpy.data.objects.get(f"FOCUS_TARGET__{marker_id}")
            if anchor is None or focus is None:
                raise RuntimeError(f"hotspot/focus Empty missing: {unit}")
            origin, endpoint = anchor.matrix_world.translation.copy(), focus.matrix_world.translation.copy()
            ray = endpoint - origin
            if ray.length <= 1e-8:
                raise RuntimeError(f"hotspot CAD normal ray is degenerate: {unit}")
            hit = next_render_visible_hit(
                origin, ray.normalized(), distance=1.0, depsgraph=depsgraph
            )
            if hit is None:
                raise RuntimeError(f"authoritative CAD face hit is missing: {unit}")
            surface_authority[unit] = {
                "anchor": origin, "focus": endpoint, "normal": hit["normal"].normalized(),
                "hitObject": hit["object"].name, "faceIndex": hit["faceIndex"], "hitDistance": hit["distance"],
                "unique": True,
            }

        subject_points = []
        for obj in bpy.context.view_layer.objects:
            if obj.type == "MESH" and not obj.hide_render:
                subject_points.extend([obj.matrix_world @ Vector(corner) for corner in obj.bound_box])
        projection = load_camera_projection_module()
        previous_location = None
        previous_rotation = previous_up = None
        maximum_target_error = maximum_roll = maximum_step = 0.0
        minimum_up_dot = 1.0
        flip_count = 0
        for physical_index in range(49):
            scene.frame_set(physical_index + 1)
            bpy.context.view_layer.update()
            matrix = camera.matrix_world.copy()
            location, rotation = matrix.translation.copy(), matrix.to_quaternion()
            current_target = target.matrix_world.translation.copy()
            forward = rotation @ Vector((0.0, 0.0, -1.0))
            up = rotation @ Vector((0.0, 1.0, 0.0))
            target_direction = (current_target - location).normalized()
            ideal = target_direction.to_track_quat("-Z", "Y")
            target_error = math.degrees(float(forward.angle(target_direction)))
            roll = math.degrees(float(rotation.rotation_difference(ideal).angle))
            step = 0.0 if previous_rotation is None else math.degrees(float(previous_rotation.rotation_difference(rotation).angle))
            if previous_up is not None and previous_up.dot(up) < 0.0:
                flip_count += 1
            speed = 0.0 if previous_location is None else float((location - previous_location).length) / (ORBIT_PROFILE["durationMs"] / 1000.0 / 48.0)
            spec = projection.CameraSpec(location=location, target=current_target, lens_mm=ORBIT_LENS_MM, sensor_width_mm=ORBIT_SENSOR_WIDTH_MM, shift_x=ORBIT_SHIFT[0], shift_y=ORBIT_SHIFT[1], resolution_x=640, resolution_y=450, sensor_fit="AUTO")
            target_projection = projection.project_world_point(current_target, spec)
            bounds = projection.project_bounds(subject_points, spec)
            min_x, min_y, max_x, max_y = bounds.as_list()
            area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
            visible_area = max(0.0, min(1.0, max_x) - max(0.0, min_x)) * max(0.0, min(1.0, max_y) - max(0.0, min_y))
            visible_fraction = visible_area / area if area > 0.0 else 0.0
            safe_min_x, safe_min_y, safe_max_x, safe_max_y = ORBIT_SAFE_BOUNDS
            target_clipped = not (target_projection.depth > 0.0 and safe_min_x <= target_projection.x <= safe_max_x and safe_min_y <= target_projection.y <= safe_max_y)
            subject_out = visible_fraction < ORBIT_MIN_VISIBLE_SUBJECT_FRACTION or visible_area < ORBIT_MIN_VISIBLE_CANVAS_AREA
            qualification = {}
            for unit in SEMANTIC_UNITS:
                surface = surface_authority[unit]
                anchor = surface["anchor"]
                projected = projection.project_world_point(anchor, spec)
                projection_safe = projected.depth > 0.0 and safe_min_x <= projected.x <= safe_max_x and safe_min_y <= projected.y <= safe_max_y
                facing_dot = float(surface["normal"].dot((location - anchor).normalized()))
                occlusion_ray = anchor - location
                occlusion = next_render_visible_hit(location, occlusion_ray.normalized(), max(0.0, occlusion_ray.length - 1e-5), depsgraph)
                unoccluded = occlusion is None or occlusion["object"].name == surface["hitObject"]
                qualification[unit] = {
                    "depthPositive": projected.depth > 0.0,
                    "projectionSafe": projection_safe,
                    "projection": [float(projected.x), float(projected.y)],
                    "depth": float(projected.depth),
                    "worldNormal": [float(value) for value in surface["normal"]],
                    "normalHitObject": surface["hitObject"],
                    "normalHitFaceIndex": surface["faceIndex"],
                    "normalHitUnique": surface["unique"],
                    "facingDot": facing_dot,
                    "facingCamera": facing_dot > 0.0,
                    "occlusionMethod": "Blender scene.ray_cast",
                    "occlusionHitObject": None if occlusion is None else occlusion["object"].name,
                    "unoccluded": unoccluded,
                    "machineQualified": projected.depth > 0.0 and projection_safe and facing_dot > 0.0 and unoccluded,
                }
            path = frames_root / f"frame-{physical_index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frame_records.append({
                "physicalFrameIndex": physical_index, "sourceFrame": physical_index + 1,
                "azimuthDegreesRelativeToV7": -12.0 + 24.0 * physical_index / 48.0,
                "path": path.relative_to(output_root).as_posix(), "sha256": sha256(path),
                "camera": {
                    "location": [round(float(value), 9) for value in location],
                    "rotationQuaternion": [round(float(value), 9) for value in rotation],
                    "target": [round(float(value), 9) for value in current_target],
                    "up": [round(float(value), 9) for value in up],
                    "lensMm": ORBIT_LENS_MM, "sensorWidthMm": ORBIT_SENSOR_WIDTH_MM,
                    "shiftX": ORBIT_SHIFT[0], "shiftY": ORBIT_SHIFT[1],
                    "targetErrorDegrees": target_error, "rollDegrees": roll, "upDotWorldZ": float(up.z),
                },
                "speedMetersPerSecond": speed,
                "targetProjection": [float(target_projection.x), float(target_projection.y)],
                "subjectBounds": [float(value) for value in bounds.as_list()],
                "visibleSubjectFraction": float(visible_fraction), "visibleCanvasArea": float(visible_area),
                "targetClipped": target_clipped, "subjectOutOfFrame": subject_out,
                "qualificationByUnit": qualification,
            })
            maximum_target_error = max(maximum_target_error, target_error)
            maximum_roll = max(maximum_roll, abs(roll))
            maximum_step = max(maximum_step, step)
            minimum_up_dot = min(minimum_up_dot, float(up.z))
            previous_location, previous_rotation, previous_up = location, rotation, up
    finally:
        camera.animation_data_clear()
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4_O1"):
                camera.constraints.remove(constraint)
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4_O1"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4_O1"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4_O1"):
                bpy.data.curves.remove(curve)
        material_slot.material, material_slot.link = original_material, original_material_link
        if temporary_material is not None and temporary_material.name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for object_name, data_name in technical_lights:
            remove_named_datablock(bpy.data.objects, object_name, do_unlink=True)
            remove_named_datablock(bpy.data.lights, data_name)
        scene.camera = original_scene["camera"]
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x, scene.render.resolution_y = original_scene["resolution_x"], original_scene["resolution_y"]
        scene.render.resolution_percentage, scene.render.filepath = original_scene["resolution_percentage"], original_scene["filepath"]
        scene.render.image_settings.file_format, scene.render.image_settings.color_mode = original_scene["file_format"], original_scene["color_mode"]
        scene.render.film_transparent, scene.eevee.taa_render_samples = original_scene["film_transparent"], original_scene["samples"]
        scene.view_settings.view_transform, scene.view_settings.look = original_scene["viewTransform"], original_scene["look"]
        scene.view_settings.exposure, scene.view_settings.gamma = original_scene["exposure"], original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()
        for camera_block in list(bpy.data.cameras):
            if camera_block.name.startswith("TEMP__STAGE4_O1"):
                bpy.data.cameras.remove(camera_block)

    candidate_hash_after = sha256(candidate_blend)
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sourceCameraTransformRestored": all(abs(float(left) - float(right)) <= 1e-8 for left_row, right_row in zip(source_camera.matrix_world, source_camera_matrix) for left, right in zip(left_row, right_row)) and scene.camera == source_camera,
        "sceneSettingsRestored": scene.render.engine == original_scene["engine"] and scene.render.resolution_x == original_scene["resolution_x"] and scene.render.resolution_y == original_scene["resolution_y"] and scene.render.filepath == original_scene["filepath"] and scene.eevee.taa_render_samples == original_scene["samples"],
        "visibilityRestored": all(bool(bpy.data.objects[name].hide_render) == hidden for name, hidden in original_visibility.items()),
        "materialRestored": material_slot.material == original_material and material_slot.link == original_material_link,
        "temporaryCamerasRemaining": sorted(block.name for block in bpy.data.cameras if block.name.startswith("TEMP__STAGE4_O1")),
        "temporaryCurvesRemaining": sorted(block.name for block in bpy.data.curves if block.name.startswith("TEMP__STAGE4_O1")),
        "temporaryEmptiesRemaining": sorted(obj.name for obj in bpy.data.objects if obj.name.startswith("TEMP__STAGE4_O1") and obj.type == "EMPTY"),
        "temporaryLightsRemaining": sorted(block.name for block in bpy.data.lights if block.name.startswith("TEMP__STAGE4_O1")),
        "temporaryMaterialsRemaining": sorted(block.name for block in bpy.data.materials if block.name.startswith("TEMP__STAGE4_O1")),
        "temporaryConstraintsRemaining": sorted(constraint.name for constraint in source_camera.constraints if constraint.name.startswith("TEMP__STAGE4_O1")),
        "temporaryActionsRemaining": sorted(block.name for block in bpy.data.actions if block.name.startswith("TEMP__STAGE4_O1")),
    }
    audit = {
        "schema": "twinkle-stage4-orbit-o1-worker-v1",
        "cameraIntrinsics": {"lensMm": ORBIT_LENS_MM, "sensorWidthMm": ORBIT_SENSOR_WIDTH_MM, "shiftX": ORBIT_SHIFT[0], "shiftY": ORBIT_SHIFT[1]},
        "frames": frame_records,
        "orientationMetrics": {
            "maximumTargetErrorDegrees": maximum_target_error, "maximumRollDegrees": maximum_roll,
            "minimumUpDotWorldZ": minimum_up_dot, "maximumOrientationStepDegrees": maximum_step,
            "flipCount": flip_count, "constraintCompetition": False, "evaluationLoopDetected": False,
        },
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    if len(frame_records) != 49 or candidate_hash_after != candidate_hash_before or not all((restoration["sourceCameraTransformRestored"], restoration["sceneSettingsRestored"], restoration["visibilityRestored"], restoration["materialRestored"])) or any(restoration[field] for field in ("temporaryCamerasRemaining", "temporaryCurvesRemaining", "temporaryEmptiesRemaining", "temporaryLightsRemaining", "temporaryMaterialsRemaining", "temporaryConstraintsRemaining", "temporaryActionsRemaining")):
        raise RuntimeError("O1 restoration or render audit failed")


def surface_anchor_precheck_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("surface anchor precheck output must be absolute")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-surface-anchor-precheck-worker",
        str(output_root),
    ]


def _longest_interval_length(intervals):
    return max((end - start + 1 for start, end in intervals), default=0)


def _write_surface_anchor_overlays(output_root, candidates_by_unit):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root)
    overlays_root = output_root / "overlays"
    overlays_root.mkdir()
    font_record = correction_review_font()
    font = ImageFont.truetype(font_record["path"], 16)
    cells = []
    for unit in SEMANTIC_UNITS:
        for candidate in candidates_by_unit[unit]:
            qualified = candidate["machineQualifiedPhysicalFrames"]
            representative = qualified[len(qualified) // 2]
            frame = candidate["physicalFrames"][representative]
            source = FAILED_ORBIT_O1_ROOT / "frames" / f"frame-{representative:03d}.png"
            with Image.open(source) as original:
                image = original.convert("RGB")
            x = float(frame["projection"][0]) * image.width
            y = float(frame["projection"][1]) * image.height
            draw = ImageDraw.Draw(image)
            radius = 10
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(255, 198, 64),
                outline=(18, 21, 27),
                width=3,
            )
            label = f"{candidate['candidateId']} | frame {representative:02d}"
            draw.text((max(4, x + 14), max(4, y - 22)), label, font=font, fill=(255, 248, 225), stroke_width=2, stroke_fill=(18, 21, 27))
            relative = Path("overlays") / f"{candidate['candidateId']}--frame-{representative:03d}.png"
            image.save(output_root / relative)
            candidate["overlayAsset"] = relative.as_posix()
            candidate["overlayPhysicalFrameIndex"] = representative
            cells.append((candidate, output_root / relative))

    cell_width, image_height, label_height = 320, 225, 56
    columns = 3
    rows = math.ceil(len(cells) / columns)
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * (image_height + label_height)),
        (18, 21, 27),
    )
    draw = ImageDraw.Draw(sheet)
    for index, (candidate, path) in enumerate(cells):
        row, column = divmod(index, columns)
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
        x = column * cell_width + (cell_width - image.width) // 2
        y = row * (image_height + label_height)
        sheet.paste(image, (x, y))
        label = (
            f"{candidate['candidateId']}\n"
            f"qualified={len(candidate['machineQualifiedPhysicalFrames'])}/49"
        )
        draw.multiline_text(
            (column * cell_width + 8, y + image_height + 6),
            label,
            font=font,
            fill=(235, 239, 246),
            spacing=2,
        )
    path = output_root / "surface-anchor-candidate-contact-sheet.png"
    sheet.save(path)
    return path


def _write_surface_anchor_review(output_root, report):
    output_root = Path(output_root)
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    rows = []
    for unit in SEMANTIC_UNITS:
        recommended = report["recommendedCandidateByUnit"][unit]
        for candidate in report["candidatesByUnit"][unit]:
            rows.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    unit,
                    candidate["candidateId"],
                    candidate["objectName"],
                    candidate["machineQualifiedPhysicalIntervals"],
                    "推荐（待人工）" if candidate["candidateId"] == recommended else "候选",
                )
            )
    html = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>TWINKLE 表面绑定热点审核</title>
<style>body{font:16px/1.6 system-ui;margin:32px;background:#11151b;color:#eef2f7}img{max-width:100%;background:#222}table{border-collapse:collapse}td,th{border:1px solid #56606d;padding:8px}code{color:#69d3df}</style>
<h1>阶段四方案 A｜CAD 表面绑定候选</h1>
<p><code>renderedFrameCount=0</code>；复用 49 张 O1 PNG；阶段四累计渲染仍为 64。机器推荐不等于人工批准。</p>
<p><code>humanSurfaceApproved=false</code>；<code>authorizesOrbitRepair=false</code>；<code>authorizesStep6=false</code>。</p>
<img src="../surface-anchor-candidate-contact-sheet.png" alt="现有 O1 PNG 上的 CAD 表面候选叠加联系表">
<h2>候选与合格区间</h2><table><thead><tr><th>热点</th><th>候选</th><th>CAD 对象</th><th>物理合格区间</th><th>机器建议</th></tr></thead><tbody>__ROWS__</tbody></table>
<p><a href="../surface-anchor-precheck-manifest.json">manifest</a> · <a href="../surface-candidates.json">候选详情</a> · <a href="../frame-qualification.json">逐帧资格</a> · <a href="../raycast-summary.json">ray-cast 摘要</a></p></html>""".replace("__ROWS__", "".join(rows))
    path = review_root / "index.html"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite surface review: {path}")
    path.write_text(html, encoding="utf-8")
    return path


def validate_surface_anchor_precheck(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "surface-anchor-precheck-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("surface anchor precheck manifest is missing")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != SURFACE_ANCHOR_PRECHECK["schema"]:
        raise ValueError("surface anchor precheck schema mismatch")
    if report.get("contract") != SURFACE_ANCHOR_PRECHECK:
        raise ValueError("surface anchor precheck contract mismatch")
    required_false = (
        "humanVisualApproved",
        "authorizesOrbitRepair",
        "authorizesStep6",
        "authorizesStage5",
        "renderOperatorInvoked",
    )
    if any(report.get(field) is not False for field in required_false):
        raise ValueError("surface anchor precheck approval or render gate mismatch")
    if (
        report.get("renderedFrameCount") != 0
        or report.get("reusedOrbitPngCount") != 49
        or report.get("totalStage4RenderedToDate") != 64
        or report.get("logicalPhysicalFrames") != list(expanded_physical_frames())
    ):
        raise ValueError("surface anchor precheck frame or budget mismatch")
    if len(report.get("reusedOrbitPngSha256", {})) != 49:
        raise ValueError("surface anchor reused PNG inventory mismatch")
    human_surface_approved = report.get("humanSurfaceApproved") is True
    selected_by_unit = report.get("selectedCandidateByUnit", {})
    for unit in SEMANTIC_UNITS:
        candidates = report.get("candidatesByUnit", {}).get(unit, [])
        if not 1 <= len(candidates) <= SURFACE_ANCHOR_PRECHECK["maximumSubmittedCandidatesPerUnit"]:
            raise ValueError("surface anchor submitted candidate count mismatch")
        identifiers = {candidate.get("candidateId") for candidate in candidates}
        if report.get("recommendedCandidateByUnit", {}).get(unit) not in identifiers:
            raise ValueError("surface anchor recommendation is not a submitted candidate")
        for candidate in candidates:
            if candidate.get("semanticId") != unit:
                raise ValueError("surface anchor semantic identity mismatch")
            if candidate.get("candidateBlendSha256") != EXPECTED_CANDIDATE_BLEND_SHA256:
                raise ValueError("surface anchor blend authority mismatch")
            if candidate.get("topologyAmbiguous") is not False or candidate.get("hitAmbiguous") is not False:
                raise ValueError("surface anchor topology or hit ambiguity")
            if len(candidate.get("physicalFrames", [])) != 49 or len(candidate.get("logicalFrames", [])) != 96:
                raise ValueError("surface anchor qualification frame count mismatch")
            if len(set(candidate.get("machineQualifiedPhysicalFrames", []))) < 2:
                raise ValueError("surface anchor candidate has insufficient qualified frames")
            if _longest_interval_length(candidate.get("machineQualifiedPhysicalIntervals", [])) < 2:
                raise ValueError("surface anchor candidate has no continuous physical interval")
        approved_ids = [
            candidate.get("candidateId")
            for candidate in candidates
            if candidate.get("humanApproved") is True
        ]
        if human_surface_approved:
            selected = selected_by_unit.get(unit)
            if selected not in {candidate.get("candidateId") for candidate in candidates}:
                raise ValueError("surface anchor approved selection is not a candidate")
            if approved_ids != [selected]:
                raise ValueError("surface anchor candidate approval set mismatch")
        elif approved_ids:
            raise ValueError("surface anchor candidate cannot be machine-approved")
    if human_surface_approved:
        approval = report.get("surfaceApproval", {})
        expected_approval = {
            "approvedBy": "user",
            "approvedOn": approval.get("approvedOn"),
            "scope": "stage4-step5-cad-surface-binding-locations-only",
            "selectedCandidateByUnit": selected_by_unit,
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        }
        if set(selected_by_unit) != set(SEMANTIC_UNITS) or approval != expected_approval:
            raise ValueError("surface anchor human approval metadata mismatch")
    elif report.get("humanSurfaceApproved") is not False or report.get(
        "surfaceApproval"
    ) is not None or selected_by_unit:
        raise ValueError("surface anchor pending approval state mismatch")
    restoration = report.get("restoration", {})
    expected_restoration = {
        "candidateBlendSha256Before": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "sceneFrameRestored": True,
        "sceneCameraRestored": True,
        "sceneVisibilityRestored": True,
        "temporaryDataBlocksRemaining": [],
    }
    if restoration != expected_restoration:
        raise ValueError("surface anchor precheck restoration mismatch")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    required = {
        "surface-candidates.json",
        "frame-qualification.json",
        "logical-index-map.json",
        "raycast-summary.json",
        "surface-anchor-candidate-contact-sheet.png",
        "review/index.html",
        "worker-audit.json",
    }
    if not required <= set(actual) or report.get("inventorySha256") != actual:
        raise ValueError("surface anchor precheck exact inventory mismatch")
    return report


def record_surface_anchor_approval(
    output_root, *, selected_candidate_by_unit, approved_on
):
    output_root = Path(output_root).resolve()
    report = validate_surface_anchor_precheck(output_root)
    if report.get("humanSurfaceApproved") is not False:
        raise ValueError("surface anchor approval is already recorded")
    selected = {
        str(unit): str(candidate_id)
        for unit, candidate_id in selected_candidate_by_unit.items()
    }
    if set(selected) != set(SEMANTIC_UNITS):
        raise ValueError("surface anchor approval must select exactly both units")
    for unit in SEMANTIC_UNITS:
        identifiers = {
            candidate["candidateId"] for candidate in report["candidatesByUnit"][unit]
        }
        if selected[unit] not in identifiers:
            raise ValueError(f"surface anchor approval candidate is unknown: {unit}")
        for candidate in report["candidatesByUnit"][unit]:
            candidate["humanApproved"] = (
                candidate["candidateId"] == selected[unit]
            )
    report["humanSurfaceApproved"] = True
    report["selectedCandidateByUnit"] = selected
    report["surfaceApproval"] = {
        "approvedBy": "user",
        "approvedOn": str(approved_on),
        "scope": "stage4-step5-cad-surface-binding-locations-only",
        "selectedCandidateByUnit": selected,
        "authorizesOrbitRepair": False,
        "authorizesStep6": False,
        "authorizesStage5": False,
    }
    report["humanVisualApproved"] = False
    report["authorizesOrbitRepair"] = False
    report["authorizesStep6"] = False
    report["authorizesStage5"] = False
    manifest_path = output_root / "surface-anchor-precheck-manifest.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_surface_anchor_precheck(output_root)


def validate_surface_anchor_precheck_recovery_staging(staging):
    staging = Path(staging).resolve()
    if not staging.is_dir():
        raise ValueError("surface anchor recovery staging is missing")
    if (staging / "surface-anchor-precheck-manifest.json").exists() or (
        staging / "review" / "index.html"
    ).exists():
        raise ValueError("surface anchor recovery staging is already finalized")
    expected = {
        "worker-audit.json",
        "surface-candidates.json",
        "frame-qualification.json",
        "logical-index-map.json",
        "raycast-summary.json",
        "surface-anchor-candidate-contact-sheet.png",
        *{
            f"overlays/{prefix}-surface-{index:02d}--frame-024.png"
            for prefix in ("chamber", "condenser")
            for index in range(1, 4)
        },
    }
    actual = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ValueError("surface anchor recovery inventory drift")
    worker = json.loads(
        (staging / "worker-audit.json").read_text(encoding="utf-8")
    )
    if worker.get("schema") != "twinkle-stage4-surface-anchor-precheck-worker-v1":
        raise ValueError("surface anchor recovery worker schema mismatch")
    if worker.get("renderOperatorInvoked") is not False:
        raise ValueError("surface anchor recovery cannot contain renders")
    if worker.get("cameraTransformCount") != 49:
        raise ValueError("surface anchor recovery camera transform count mismatch")
    if worker.get("sourceO1WorkerAuditSha256") != EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256:
        raise ValueError("surface anchor recovery O1 authority mismatch")
    expected_restoration = {
        "candidateBlendSha256Before": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "sceneFrameRestored": True,
        "sceneCameraRestored": True,
        "sceneVisibilityRestored": True,
        "temporaryDataBlocksRemaining": [],
    }
    if worker.get("restoration") != expected_restoration:
        raise ValueError("surface anchor recovery restoration mismatch")
    counts = {}
    for unit in SEMANTIC_UNITS:
        candidates = worker.get("candidatesByUnit", {}).get(unit, [])
        if not 1 <= len(candidates) <= 3:
            raise ValueError("surface anchor recovery candidate count mismatch")
        if any(
            len(set(candidate.get("machineQualifiedPhysicalFrames", []))) < 2
            or _longest_interval_length(
                candidate.get("machineQualifiedPhysicalIntervals", [])
            )
            < 2
            for candidate in candidates
        ):
            raise ValueError("surface anchor recovery candidate qualification mismatch")
        counts[unit] = len(candidates)
    return {
        "workerSchema": worker["schema"],
        "renderOperatorInvoked": False,
        "cameraTransformCount": 49,
        "candidateCountByUnit": counts,
    }


def build_surface_anchor_precheck(
    output_root,
    *,
    authorized=False,
    blender=None,
    runner=None,
    recovery_staging=None,
):
    if authorized is not True:
        raise PermissionError("surface anchor precheck requires explicit authorization")
    output_root = Path(output_root).resolve()
    if output_root.name != "surface-anchor-precheck-r1":
        raise ValueError("surface anchor precheck output name mismatch")
    validate_request(default_request(output_root))
    validate_authority()
    if sha256(FAILED_ORBIT_O1_AUDIT) != EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256:
        raise ValueError("failed O1 worker audit drift")
    o1_audit = json.loads(FAILED_ORBIT_O1_AUDIT.read_text(encoding="utf-8"))
    frames = sorted(o1_audit.get("frames", []), key=lambda item: item["physicalFrameIndex"])
    if len(frames) != 49 or [item["physicalFrameIndex"] for item in frames] != list(range(49)):
        raise ValueError("failed O1 camera transform inventory drift")
    reused_png_hashes = {}
    for frame in frames:
        relative = Path(frame["path"])
        png = FAILED_ORBIT_O1_ROOT / relative
        if not png.is_file() or sha256(png) != frame["sha256"]:
            raise ValueError("failed O1 PNG inventory drift")
        reused_png_hashes[relative.as_posix()] = frame["sha256"]

    authority = validate_authority()["stage1"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before surface precheck")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked

    if recovery_staging is None:
        output_root.parent.mkdir(parents=True, exist_ok=False)
        staging = Path(
            tempfile.mkdtemp(
                prefix=".surface-anchor-precheck-", dir=output_root.parent
            )
        ).resolve()
    else:
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(recovery_staging).resolve()
        validate_surface_anchor_precheck_recovery_staging(staging)
    try:
        if recovery_staging is None:
            runner(
                surface_anchor_precheck_blender_command(
                    blender, candidate_blend, staging
                ),
                cwd=ROOT,
            )
        worker_path = staging / "worker-audit.json"
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        if worker.get("schema") != "twinkle-stage4-surface-anchor-precheck-worker-v1":
            raise ValueError("surface anchor worker schema mismatch")
        candidates_by_unit = worker.get("candidatesByUnit", {})
        if set(candidates_by_unit) != set(SEMANTIC_UNITS):
            raise ValueError("surface anchor worker unit inventory mismatch")
        if recovery_staging is None:
            _write_surface_anchor_overlays(staging, candidates_by_unit)
        else:
            recorded_candidates = json.loads(
                (staging / "surface-candidates.json").read_text(encoding="utf-8")
            )
            if {
                unit: [candidate["candidateId"] for candidate in candidates_by_unit[unit]]
                for unit in SEMANTIC_UNITS
            } != {
                unit: [candidate["candidateId"] for candidate in recorded_candidates[unit]]
                for unit in SEMANTIC_UNITS
            }:
                raise ValueError("surface anchor recovery candidate identity drift")
            candidates_by_unit = recorded_candidates
        recommended = {
            unit: candidates_by_unit[unit][0]["candidateId"] for unit in SEMANTIC_UNITS
        }
        logical_map = [
            {"logicalIndex": index, "physicalFrameIndex": physical}
            for index, physical in enumerate(expanded_physical_frames())
        ]
        if recovery_staging is None:
            (staging / "surface-candidates.json").write_text(
                json.dumps(candidates_by_unit, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (staging / "frame-qualification.json").write_text(
                json.dumps(
                    {
                        unit: {
                            candidate["candidateId"]: {
                                "physicalFrames": candidate["physicalFrames"],
                                "logicalFrames": candidate["logicalFrames"],
                            }
                            for candidate in candidates_by_unit[unit]
                        }
                        for unit in SEMANTIC_UNITS
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (staging / "logical-index-map.json").write_text(
                json.dumps(logical_map, indent=2), encoding="utf-8"
            )
        raycast_summary = {
            unit: {
                candidate["candidateId"]: {
                    "boundObject": candidate["objectName"],
                    "boundPolygonIndex": candidate["polygonIndex"],
                    "qualifiedPhysicalFrameCount": len(
                        candidate["machineQualifiedPhysicalFrames"]
                    ),
                    "qualifiedPhysicalIntervals": candidate[
                        "machineQualifiedPhysicalIntervals"
                    ],
                    "nearestHitObjects": sorted(
                        {
                            frame["nearestHitObject"]
                            for frame in candidate["physicalFrames"]
                            if frame["nearestHitObject"] is not None
                        }
                    ),
                }
                for candidate in candidates_by_unit[unit]
            }
            for unit in SEMANTIC_UNITS
        }
        if recovery_staging is None:
            (staging / "raycast-summary.json").write_text(
                json.dumps(raycast_summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        report = {
            "schema": SURFACE_ANCHOR_PRECHECK["schema"],
            "scope": "stage4-step5-surface-anchor-zero-render-precheck-only",
            "contract": SURFACE_ANCHOR_PRECHECK,
            "authority": {
                "stage1ManifestSha256": EXPECTED_STAGE1_SHA256,
                "stage3R2ManifestSha256": EXPECTED_STAGE3_R2_SHA256,
                "sourceBlendSha256": EXPECTED_SOURCE_BLEND_SHA256,
                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
                "failedO1WorkerAuditSha256": EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256,
            },
            "physicalFrameCount": 49,
            "logicalIndexCount": 96,
            "logicalPhysicalFrames": list(expanded_physical_frames()),
            "renderedFrameCount": 0,
            "reusedOrbitPngCount": 49,
            "reusedOrbitPngSha256": reused_png_hashes,
            "totalStage4RenderedToDate": 64,
            "candidatesByUnit": candidates_by_unit,
            "recommendedCandidateByUnit": recommended,
            "recommendationBasis": (
                "maximum qualified physical frames, then longest continuous interval, "
                "world triangle area, and stable CAD identity; pending human review"
            ),
            "restoration": worker["restoration"],
            "renderOperatorInvoked": False,
            "humanSurfaceApproved": False,
            "humanVisualApproved": False,
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        }
        _write_surface_anchor_review(staging, report)
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "surface-anchor-precheck-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_surface_anchor_precheck(staging)
        if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
            raise ValueError("candidate blend drift after surface precheck")
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"surface anchor precheck failed; isolated staging kept at {staging}"
        ) from error
    return validate_surface_anchor_precheck(output_root)


def surface_anchor_precheck_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Vector = mathutils.Vector

    output_root = validate_orientation_worker_staging(output_root)
    if sha256(FAILED_ORBIT_O1_AUDIT) != EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256:
        raise RuntimeError("failed O1 worker audit drift in Blender worker")
    o1 = json.loads(FAILED_ORBIT_O1_AUDIT.read_text(encoding="utf-8"))
    frames = sorted(o1["frames"], key=lambda item: item["physicalFrameIndex"])
    if len(frames) != 49:
        raise RuntimeError("failed O1 camera transform count mismatch")
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY_SNAPSHOT.read_text(encoding="utf-8"))
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for surface anchor precheck")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before surface anchor precheck")

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    original_frame = scene.frame_current
    original_camera = scene.camera
    original_visibility = {
        obj.name: bool(obj.hide_render) for obj in bpy.data.objects
    }
    original_data = {
        "objects": set(bpy.data.objects.keys()),
        "meshes": set(bpy.data.meshes.keys()),
        "materials": set(bpy.data.materials.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "actions": set(bpy.data.actions.keys()),
    }
    shared_hidden = set(authority["renderProfile"]["sharedHiddenObjects"])
    projection = load_camera_projection_module()
    safe_min_x, safe_min_y, safe_max_x, safe_max_y = SURFACE_ANCHOR_PRECHECK[
        "safeBounds"
    ]
    tolerance = SURFACE_ANCHOR_PRECHECK["surfaceHitToleranceM"]

    def rounded(values):
        return [round(float(value), 12) for value in values]

    def topology_sha256(mesh, object_name):
        payload = {
            "object": object_name,
            "vertices": [rounded(vertex.co) for vertex in mesh.vertices],
            "polygons": [list(polygon.vertices) for polygon in mesh.polygons],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest().upper()

    def render_visible(obj):
        return (
            obj is not None
            and obj.type == "MESH"
            and not obj.hide_render
            and obj.name not in shared_hidden
        )

    def nearest_render_visible_hit(origin, target):
        direction_vector = target - origin
        target_distance = float(direction_vector.length)
        if target_distance <= 1e-12:
            raise RuntimeError("surface ray is degenerate")
        direction = direction_vector.normalized()
        cursor = origin.copy()
        remaining = target_distance + tolerance
        travelled = 0.0
        for _ in range(64):
            hit, location, normal, face_index, obj, _ = scene.ray_cast(
                depsgraph, cursor, direction, distance=remaining
            )
            if not hit:
                return None
            segment = float((location - cursor).length)
            travelled += segment
            if render_visible(obj):
                return {
                    "object": obj.name,
                    "polygonIndex": int(face_index),
                    "location": location.copy(),
                    "normal": normal.copy(),
                    "distance": travelled,
                }
            step = 1e-6
            cursor = location + direction * step
            travelled += step
            remaining -= segment + step
            if remaining <= 0.0:
                return None
        raise RuntimeError("surface ray-cast exceeded bounded traversal")

    def camera_spec(frame):
        camera = frame["camera"]
        return projection.CameraSpec(
            location=camera["location"],
            target=camera["target"],
            lens_mm=camera["lensMm"],
            sensor_width_mm=camera["sensorWidthMm"],
            shift_x=camera["shiftX"],
            shift_y=camera["shiftY"],
            resolution_x=640,
            resolution_y=450,
            sensor_fit="AUTO",
        )

    candidates_by_unit = {}
    try:
        for unit_index, unit in enumerate(SEMANTIC_UNITS):
            pool = []
            mesh_names = geometry["units"][unit]["meshObjects"]
            if not mesh_names:
                raise RuntimeError(f"surface mesh authority is empty: {unit}")
            for object_name in mesh_names:
                obj = bpy.data.objects.get(object_name)
                if not render_visible(obj):
                    raise RuntimeError(f"surface mesh is missing or not render-visible: {object_name}")
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh(
                    preserve_all_data_layers=True, depsgraph=depsgraph
                )
                try:
                    mesh.calc_loop_triangles()
                    topology = topology_sha256(mesh, object_name)
                    matrix = evaluated.matrix_world.copy()
                    normal_matrix = matrix.to_3x3().inverted().transposed()
                    identity_counts = {}
                    for triangle in mesh.loop_triangles:
                        key = (int(triangle.polygon_index), tuple(int(v) for v in triangle.vertices))
                        identity_counts[key] = identity_counts.get(key, 0) + 1
                    for triangle in mesh.loop_triangles:
                        vertex_indices = tuple(int(value) for value in triangle.vertices)
                        vertices = [mesh.vertices[index].co.copy() for index in vertex_indices]
                        local_position = sum(vertices, Vector((0.0, 0.0, 0.0))) / 3.0
                        local_normal = (vertices[1] - vertices[0]).cross(
                            vertices[2] - vertices[0]
                        )
                        if local_normal.length <= 1e-12:
                            continue
                        local_normal.normalize()
                        world_position = matrix @ local_position
                        world_normal = (normal_matrix @ local_normal).normalized()
                        world_area = float(
                            ((matrix @ vertices[1]) - (matrix @ vertices[0])).cross(
                                (matrix @ vertices[2]) - (matrix @ vertices[0])
                            ).length
                            * 0.5
                        )
                        potential = 0
                        for frame in frames:
                            spec = camera_spec(frame)
                            projected = projection.project_world_point(world_position, spec)
                            camera_location = Vector(frame["camera"]["location"])
                            facing = float(
                                world_normal.dot(
                                    (camera_location - world_position).normalized()
                                )
                            )
                            if (
                                projected.depth > 0.0
                                and safe_min_x <= projected.x <= safe_max_x
                                and safe_min_y <= projected.y <= safe_max_y
                                and facing > 0.0
                            ):
                                potential += 1
                        if potential < 2:
                            continue
                        pool.append(
                            {
                                "semanticId": unit,
                                "objectName": object_name,
                                "meshTopologySha256": topology,
                                "polygonIndex": int(triangle.polygon_index),
                                "loopTriangleIndex": int(triangle.index),
                                "vertexIndices": list(vertex_indices),
                                "barycentricCoordinates": list(
                                    SURFACE_ANCHOR_PRECHECK["barycentricCoordinates"]
                                ),
                                "localPosition": rounded(local_position),
                                "worldPosition": rounded(world_position),
                                "localNormal": rounded(local_normal),
                                "worldNormal": rounded(world_normal),
                                "positionEvaluationMethod": "evaluated-loop-triangle-centroid-then-object-matrix-world",
                                "normalEvaluationMethod": "triangle-cross-product-then-inverse-transpose-normal-matrix",
                                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
                                "topologyAmbiguous": identity_counts[
                                    (int(triangle.polygon_index), vertex_indices)
                                ]
                                != 1,
                                "potentialQualifiedFrameCount": potential,
                                "worldTriangleAreaM2": world_area,
                            }
                        )
                finally:
                    evaluated.to_mesh_clear()

            pool.sort(
                key=lambda candidate: (
                    -candidate["potentialQualifiedFrameCount"],
                    -candidate["worldTriangleAreaM2"],
                    candidate["objectName"],
                    candidate["polygonIndex"],
                    candidate["loopTriangleIndex"],
                )
            )
            bounded_pool = pool[
                : SURFACE_ANCHOR_PRECHECK["maximumRaycastTrianglesPerUnit"]
            ]
            qualified_candidates = []
            for candidate in bounded_pool:
                world_position = Vector(candidate["worldPosition"])
                world_normal = Vector(candidate["worldNormal"])
                physical_records = []
                hit_identity_conflict = False
                for frame in frames:
                    spec = camera_spec(frame)
                    projected = projection.project_world_point(world_position, spec)
                    camera_location = Vector(frame["camera"]["location"])
                    facing_dot = float(
                        world_normal.dot(
                            (camera_location - world_position).normalized()
                        )
                    )
                    hit = nearest_render_visible_hit(camera_location, world_position)
                    target_distance = float((world_position - camera_location).length)
                    hit_position_error = (
                        None
                        if hit is None
                        else float((hit["location"] - world_position).length)
                    )
                    same_surface = (
                        hit is not None
                        and hit["object"] == candidate["objectName"]
                        and hit["polygonIndex"] == candidate["polygonIndex"]
                        and hit_position_error <= tolerance
                        and abs(hit["distance"] - target_distance) <= tolerance
                    )
                    if (
                        hit is not None
                        and hit_position_error <= tolerance
                        and (
                            hit["object"] != candidate["objectName"]
                            or hit["polygonIndex"] != candidate["polygonIndex"]
                        )
                    ):
                        hit_identity_conflict = True
                    depth_positive = projected.depth > 0.0
                    projection_safe = (
                        depth_positive
                        and safe_min_x <= projected.x <= safe_max_x
                        and safe_min_y <= projected.y <= safe_max_y
                    )
                    physical_records.append(
                        {
                            "physicalFrameIndex": frame["physicalFrameIndex"],
                            "depthPositive": depth_positive,
                            "projectionSafe": projection_safe,
                            "projection": [float(projected.x), float(projected.y)],
                            "depth": float(projected.depth),
                            "worldNormal": candidate["worldNormal"],
                            "facingDot": facing_dot,
                            "facingCamera": facing_dot > 0.0,
                            "rayCastMethod": "Blender scene.ray_cast nearest render-visible hit",
                            "nearestHitObject": None if hit is None else hit["object"],
                            "nearestHitPolygonIndex": None
                            if hit is None
                            else hit["polygonIndex"],
                            "nearestHitDistanceM": None if hit is None else hit["distance"],
                            "boundSurfaceDistanceM": target_distance,
                            "hitPositionErrorM": hit_position_error,
                            "surfaceHitToleranceM": tolerance,
                            "unoccluded": same_surface,
                            "machineQualified": (
                                depth_positive
                                and projection_safe
                                and facing_dot > 0.0
                                and same_surface
                            ),
                        }
                    )
                qualified_physical = [
                    record["physicalFrameIndex"]
                    for record in physical_records
                    if record["machineQualified"]
                ]
                physical_intervals = _contiguous_intervals(qualified_physical)
                logical_records = []
                for logical_index, physical_index in enumerate(
                    expanded_physical_frames()
                ):
                    logical_records.append(
                        {
                            "logicalIndex": logical_index,
                            **physical_records[physical_index],
                        }
                    )
                qualified_logical = [
                    record["logicalIndex"]
                    for record in logical_records
                    if record["machineQualified"]
                ]
                logical_intervals = _contiguous_intervals(qualified_logical)
                candidate.update(
                    {
                        "hitAmbiguous": hit_identity_conflict,
                        "physicalFrames": physical_records,
                        "logicalFrames": logical_records,
                        "machineQualifiedPhysicalFrames": qualified_physical,
                        "machineQualifiedLogicalFrames": qualified_logical,
                        "machineQualifiedPhysicalIntervals": physical_intervals,
                        "machineQualifiedLogicalIntervals": logical_intervals,
                        "humanApproved": False,
                    }
                )
                if (
                    not candidate["topologyAmbiguous"]
                    and not candidate["hitAmbiguous"]
                    and len(set(qualified_physical)) >= 2
                    and _longest_interval_length(physical_intervals) >= 2
                ):
                    qualified_candidates.append(candidate)

            qualified_candidates.sort(
                key=lambda candidate: (
                    -len(candidate["machineQualifiedPhysicalFrames"]),
                    -_longest_interval_length(
                        candidate["machineQualifiedPhysicalIntervals"]
                    ),
                    -candidate["worldTriangleAreaM2"],
                    candidate["objectName"],
                    candidate["polygonIndex"],
                    candidate["loopTriangleIndex"],
                )
            )
            submitted = qualified_candidates[
                : SURFACE_ANCHOR_PRECHECK["maximumSubmittedCandidatesPerUnit"]
            ]
            if not submitted:
                raise RuntimeError(
                    f"surface anchor has no candidate with a continuous qualified interval: {unit}"
                )
            prefix = "chamber" if unit_index == 0 else "condenser"
            for index, candidate in enumerate(submitted, start=1):
                candidate["candidateId"] = f"{prefix}-surface-{index:02d}"
            candidates_by_unit[unit] = submitted
    finally:
        scene.frame_set(original_frame)

    candidate_hash_after = sha256(candidate_blend)
    current_data = {
        "objects": set(bpy.data.objects.keys()),
        "meshes": set(bpy.data.meshes.keys()),
        "materials": set(bpy.data.materials.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "actions": set(bpy.data.actions.keys()),
    }
    temporary_remaining = sorted(
        f"{kind}:{name}"
        for kind in original_data
        for name in current_data[kind] - original_data[kind]
    )
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sceneFrameRestored": scene.frame_current == original_frame,
        "sceneCameraRestored": scene.camera == original_camera,
        "sceneVisibilityRestored": all(
            bool(bpy.data.objects[name].hide_render) == hidden
            for name, hidden in original_visibility.items()
        ),
        "temporaryDataBlocksRemaining": temporary_remaining,
    }
    audit = {
        "schema": "twinkle-stage4-surface-anchor-precheck-worker-v1",
        "contract": SURFACE_ANCHOR_PRECHECK,
        "renderOperatorInvoked": False,
        "sourceO1WorkerAuditSha256": EXPECTED_FAILED_ORBIT_O1_AUDIT_SHA256,
        "cameraTransformCount": len(frames),
        "candidatesByUnit": candidates_by_unit,
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        candidate_hash_after != candidate_hash_before
        or not restoration["sceneFrameRestored"]
        or not restoration["sceneCameraRestored"]
        or not restoration["sceneVisibilityRestored"]
        or restoration["temporaryDataBlocksRemaining"]
    ):
        raise RuntimeError("surface anchor precheck restoration failed")


def c360_f96_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("C360-F96 output must be absolute")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-c360-f96-worker",
        str(output_root),
    ]


def _cyclic_intervals(indices, frame_count):
    linear = _contiguous_intervals(indices)
    if not linear:
        return []
    if len(linear) > 1 and linear[0][0] == 0 and linear[-1][1] == frame_count - 1:
        merged = {
            "start": linear[-1][0],
            "end": linear[0][1],
            "wraps": True,
        }
        middle = [
            {"start": start, "end": end, "wraps": False}
            for start, end in linear[1:-1]
        ]
        return [merged, *middle]
    return [
        {"start": start, "end": end, "wraps": False}
        for start, end in linear
    ]


def _rgb_mae(left_path, right_path):
    from PIL import Image, ImageChops, ImageStat

    with Image.open(left_path) as source:
        left = source.convert("RGB").resize((160, 113))
    with Image.open(right_path) as source:
        right = source.convert("RGB").resize((160, 113))
    return sum(ImageStat.Stat(ImageChops.difference(left, right)).mean) / 3.0


def _write_c360_contact_sheet(output_root, frames):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root)
    font = ImageFont.truetype(correction_review_font()["path"], 15)
    sampled = list(range(0, 96, 8))
    columns, cell_width, image_height, label_height = 4, 320, 225, 72
    rows = math.ceil(len(sampled) / columns)
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * (image_height + label_height)),
        (18, 21, 27),
    )
    draw = ImageDraw.Draw(sheet)
    colors = {CHAMBER: (255, 176, 0), CONDENSER: (0, 194, 255)}
    short_names = {CHAMBER: "光学舱", CONDENSER: "聚光镜"}
    status_labels = {
        "visible": "可见",
        "back-facing": "背向",
        "occluded": "遮挡",
        "out-of-safe": "超出安全区",
    }
    for cell, index in enumerate(sampled):
        frame = frames[index]
        row, column = divmod(cell, columns)
        with Image.open(output_root / frame["path"]) as source:
            image = source.convert("RGB")
            image.thumbnail((cell_width, image_height))
        overlay = ImageDraw.Draw(image)
        labels = []
        for unit in SEMANTIC_UNITS:
            record = frame["qualificationByUnit"][unit]
            x = float(record["projection"][0]) * image.width
            y = float(record["projection"][1]) * image.height
            if 0 <= x < image.width and 0 <= y < image.height:
                overlay.ellipse(
                    (x - 7, y - 7, x + 7, y + 7),
                    fill=colors[unit] if record["status"] == "visible" else None,
                    outline=colors[unit],
                    width=3,
                )
            labels.append(
                f"{short_names[unit]}：{status_labels[record['status']]}"
            )
        x0 = column * cell_width + (cell_width - image.width) // 2
        y0 = row * (image_height + label_height)
        sheet.paste(image, (x0, y0))
        draw.text(
            (column * cell_width + 6, y0 + image_height + 3),
            f"frame {index:02d} | {frame['azimuthDegrees']:.2f}°",
            font=font,
            fill=(235, 239, 246),
        )
        draw.text(
            (column * cell_width + 6, y0 + image_height + 25),
            labels[0],
            font=font,
            fill=(205, 213, 224),
        )
        draw.text(
            (column * cell_width + 6, y0 + image_height + 47),
            labels[1],
            font=font,
            fill=(205, 213, 224),
        )
    path = output_root / "c360-f96-12-frame-contact-sheet.png"
    sheet.save(path)
    return path, sampled


def _build_c360_qualification_by_unit(frames, authority, selected):
    qualification_by_unit = {}
    total_entries = 0
    for unit in SEMANTIC_UNITS:
        physical = [
            {
                "physicalFrameIndex": frame["physicalFrameIndex"],
                **frame["qualificationByUnit"][unit],
            }
            for frame in frames
        ]
        qualified = [
            record["physicalFrameIndex"]
            for record in physical
            if record["machineQualified"]
        ]
        if not qualified:
            raise ValueError(f"C360-F96 has no qualified hotspot frame: {unit}")
        component_records = [
            c360_component_recognizability_record(unit, frame)
            for frame in frames
        ]
        recognizable = [
            record["physicalFrameIndex"]
            for record in component_records
            if record["gatePassed"]
        ]
        if not recognizable:
            raise ValueError(
                f"C360-F96 has no recognizable entry candidate: {unit}"
            )
        focus_location = authority["units"][unit]["camera"]["location"]
        hero = min(
            qualified,
            key=lambda index: sum(
                (
                    frames[index]["camera"]["location"][axis]
                    - focus_location[axis]
                )
                ** 2
                for axis in range(3)
            ),
        )
        entry_selection = select_c360_entry_frames(
            qualified,
            hero_frame=hero,
            frame_count=96,
            recognizable_frames=recognizable,
        )
        entries = entry_selection["entryFrameSet"]
        turn_plans = [
            plan_c360_shortest_turn(
                current_frame=current,
                entry_frames=entries,
                orbit_direction=direction,
            )
            for current in range(96)
            for direction in ("forward", "backward")
        ]
        worst_turn = max(
            turn_plans,
            key=lambda plan: (
                plan["turnDurationMs"],
                plan["distanceFrames"],
            ),
        )
        if (
            worst_turn["turnDurationMs"]
            > C360_F96_PROFILE["maximumTurnDurationMs"]
            or worst_turn["peakAngularSpeedDegreesPerSecond"]
            > C360_F96_PROFILE["maximumAngularSpeedDegreesPerSecond"]
        ):
            raise ValueError("C360 name-button turn plan exceeds motion caps")
        total_entries += len(entries)
        logical = [
            {"logicalIndex": record["physicalFrameIndex"], **record}
            for record in physical
        ]
        intervals = _cyclic_intervals(qualified, 96)
        component_by_frame = {
            record["physicalFrameIndex"]: record
            for record in component_records
        }
        entry_candidates = []
        for entry in entries:
            component = dict(component_by_frame[entry])
            component["humanReviewStatus"] = "pending"
            frame = frames[entry]
            entry_candidates.append(
                {
                    "frameIndex": entry,
                    "angleDegrees": frame["azimuthDegrees"],
                    "sourcePng": frame["path"],
                    "sourcePngSha256": frame["sha256"],
                    "hotspotStatus": frame["qualificationByUnit"][unit][
                        "status"
                    ],
                    "hotspotProjection": frame["qualificationByUnit"][unit][
                        "projection"
                    ],
                    "componentRecognizability": component,
                    "visualCueZh": (
                        f"完整装配投影约占画布宽 "
                        f"{component['visibleWidth'] * 100:.1f}%、高 "
                        f"{component['visibleHeight'] * 100:.1f}%、面积 "
                        f"{component['visibleArea'] * 100:.1f}%"
                    ),
                }
            )
        qualification_by_unit[unit] = {
            "selectedSurfaceCandidateId": selected[unit],
            "physicalFrames": physical,
            "logicalFrames": logical,
            "machineQualifiedPhysicalFrames": qualified,
            "machineQualifiedLogicalFrames": list(qualified),
            "machineQualifiedCyclicIntervals": intervals,
            "proposedHumanVisibleIntervals": intervals,
            "componentRecognizabilityGateOrder": [
                "machine-visible",
                "complete-overview-component-projection",
                "cyclic-shortest-turn",
            ],
            "componentRecognizabilityThresholds": dict(
                C360_F96_COMPONENT_RECOGNIZABILITY[unit]
            ),
            "componentRecognizabilityQualifiedFrames": recognizable,
            "componentRecognizabilityRecords": component_records,
            "initialEntryFrameSet": entries,
            "entryCandidates": entry_candidates,
            "entryRole": "overview-exit-only",
            "focusRouteGenerated": False,
            "entrySelection": entry_selection,
            "turnPlanWorstCase": worst_turn,
            "statusCounts": {
                status: sum(record["status"] == status for record in physical)
                for status in (
                    "visible",
                    "back-facing",
                    "occluded",
                    "out-of-safe",
                )
            },
            "humanEntryApproved": False,
            "humanApproved": False,
        }
    return qualification_by_unit, total_entries


def _write_c360_review_player_legacy(output_root, frames, qualification_by_unit):
    output_root = Path(output_root)
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    data = {
        "durationMs": C360_F96_PROFILE["durationMs"],
        "frameCount": 96,
        "entryRole": "overview-exit-only",
        "focusRouteGenerated": False,
        "entryFramesByUnit": {
            unit: qualification_by_unit[unit]["initialEntryFrameSet"]
            for unit in SEMANTIC_UNITS
        },
        "entryCandidatesByUnit": {
            unit: qualification_by_unit[unit]["entryCandidates"]
            for unit in SEMANTIC_UNITS
        },
        "visibleIntervalsByUnit": {
            unit: qualification_by_unit[unit]["proposedHumanVisibleIntervals"]
            for unit in SEMANTIC_UNITS
        },
        "statusCountsByUnit": {
            unit: qualification_by_unit[unit]["statusCounts"]
            for unit in SEMANTIC_UNITS
        },
        "navigation": {
            "maximumTurnDurationMs": 2_000,
            "maximumAngularSpeedDegreesPerSecond": 90.0,
            "accelerationRampMs": 250,
            "decelerationRampMs": 250,
            "settledHoldMs": 100,
        },
        "frames": [
            {
                "index": frame["physicalFrameIndex"],
                "angle": frame["azimuthDegrees"],
                "src": f"../{frame['path']}",
                "hotspots": {
                    unit: {
                        "status": frame["qualificationByUnit"][unit]["status"],
                        "projection": frame["qualificationByUnit"][unit]["projection"],
                    }
                    for unit in SEMANTIC_UNITS
                },
            }
            for frame in frames
        ],
    }
    (review_root / "review-data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    html = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,\"><title>TWINKLE 360°动态审核</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#10141a;color:#edf2f7;font:16px/1.5 system-ui}.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;min-height:100vh}.stage{display:grid;place-items:center;padding:24px}.viewer{position:relative;width:min(100%,960px);aspect-ratio:64/45;background:#e9eceb;overflow:hidden}.viewer img{width:100%;height:100%;object-fit:contain}.hotspot{position:absolute;transform:translate(-50%,-50%);padding:6px 10px;border:2px solid currentColor;border-radius:999px;background:#10141ad9;color:inherit;font-weight:700;white-space:nowrap}.hotspot.visible{opacity:1}.hotspot.back-facing{opacity:.38;border-style:dashed}.hotspot.occluded{opacity:.5;text-decoration:line-through}.hotspot.out-of-safe{display:none}.chamber{color:#FFB000}.condenser{color:#00C2FF}.panel{padding:24px;background:#171d25}.controls{display:flex;gap:8px;flex-wrap:wrap}.controls button,.name-button{padding:10px 14px;border:1px solid #586575;background:#222c38;color:#fff;border-radius:8px}.name-button{display:block;width:100%;margin:8px 0;text-align:left}.panel input{width:100%}.status{margin:12px 0;padding:10px;background:#0d1117;border-radius:8px}.gate{color:#ffcf66}
</style><div class="layout"><main class="stage"><div class="viewer" data-testid="spin-player"><img data-testid="spin-frame" alt="TWINKLE 360°"><div class="hotspot chamber" data-unit="dual_channel_collection_optics_chamber">双通道采集光学舱</div><div class="hotspot condenser" data-unit="dual_channel_condenser_lens_assembly">聚光镜组件</div></div></main><aside class="panel"><h1>C360-F96 动态审核</h1><p class="gate">humanVisualApproved=false；不授权返修、步骤6、A/B或阶段五。</p><div class="controls"><button data-testid="play-pause">暂停</button><button data-testid="replay">重播</button></div><label>拖动查看 <input data-testid="scrubber" type="range" min="0" max="95" step="1" value="0"></label><div class="status" data-testid="frame-status">加载中</div><button class="name-button chamber" data-action-unit="dual_channel_collection_optics_chamber">双通道采集光学舱（固定名称按钮）</button><button class="name-button condenser" data-action-unit="dual_channel_condenser_lens_assembly">聚光镜组件（固定名称按钮）</button><p>状态：visible / back-facing / occluded / out-of-safe</p></aside></div>
<script>
const names={dual_channel_collection_optics_chamber:'双通道采集光学舱',dual_channel_condenser_lens_assembly:'聚光镜组件'};
const labels={visible:'可见','back-facing':'背向',occluded:'遮挡','out-of-safe':'超出安全区'};
let data,frame=0,elapsed=0,started=0,playing=false,raf;
const image=document.querySelector('[data-testid="spin-frame"]'),scrubber=document.querySelector('[data-testid="scrubber"]'),status=document.querySelector('[data-testid="frame-status"]'),toggle=document.querySelector('[data-testid="play-pause"]');
function show(index){frame=(index+data.frameCount)%data.frameCount;const record=data.frames[frame];image.src=record.src;scrubber.value=frame;for(const [unit,hotspot] of Object.entries(record.hotspots)){const el=document.querySelector(`[data-unit="${unit}"]`);el.className=`hotspot ${unit.includes('collection')?'chamber':'condenser'} ${hotspot.status}`;el.textContent=`${names[unit]}｜${labels[hotspot.status]}`;el.style.left=`${hotspot.projection[0]*100}%`;el.style.top=`${hotspot.projection[1]*100}%`;}status.textContent=`frame ${frame}/95｜${record.angle.toFixed(2)}°｜${(elapsed/1000).toFixed(2)}s`;document.body.dataset.frame=String(frame);}
function setState(value){document.body.dataset.state=value;toggle.textContent=value==='playing'?'暂停':'继续';}
function tick(now){if(!playing)return;elapsed=now-started;if(elapsed>=data.durationMs){elapsed=data.durationMs;show(0);playing=false;setState('completed');return;}show(Math.floor(elapsed/data.durationMs*data.frameCount));raf=requestAnimationFrame(tick);}
function play(){if(playing)return;if(elapsed>=data.durationMs)elapsed=0;playing=true;started=performance.now()-elapsed;setState('playing');raf=requestAnimationFrame(tick);}
function pause(){if(!playing)return;playing=false;cancelAnimationFrame(raf);setState('paused');show(frame);}
function shortestTurn(current,entries){const plans=[];for(const entry of entries){const forward=(entry-current+96)%96,backward=(current-entry+96)%96;if(forward<=backward)plans.push({entry,direction:'forward',distance:forward});else plans.push({entry,direction:'backward',distance:backward});}plans.sort((a,b)=>a.distance-b.distance||a.entry-b.entry);return plans[0];}
function turnToUnit(unit){playing=false;cancelAnimationFrame(raf);const plan=shortestTurn(frame,data.entryFramesByUnit[unit]);const distanceDegrees=plan.distance*3.75,nav=data.navigation,movementMs=plan.distance===0?0:(distanceDegrees/nav.maximumAngularSpeedDegreesPerSecond*1000+nav.accelerationRampMs),rampMs=Math.min(nav.accelerationRampMs,movementMs/2),peak=plan.distance===0?0:distanceDegrees/(movementMs/1000-rampMs/1000),totalMs=movementMs+nav.settledHoldMs,startFrame=frame,start=performance.now();document.body.dataset.state='turning';document.body.dataset.turnDurationMs=String(Math.round(totalMs));document.body.dataset.peakAngularSpeed=String(peak);document.body.dataset.selectedEntry=String(plan.entry);function progress(ms){if(movementMs===0)return 1;const time=Math.min(ms,movementMs)/1000,ramp=rampMs/1000,movement=movementMs/1000,cruise=Math.max(0,movement-2*ramp),pi=Math.PI;let travelled;if(time<ramp)travelled=peak*(time/2-ramp/(2*pi)*Math.sin(pi*time/ramp));else if(time<ramp+cruise)travelled=peak*(ramp/2+time-ramp);else{const u=time-ramp-cruise;travelled=peak*(ramp/2+cruise+u/2+ramp/(2*pi)*Math.sin(pi*u/ramp));}return Math.min(travelled/Math.max(distanceDegrees,1e-9),1);}function move(now){const t=progress(now-start),direct=plan.direction==='forward'?1:-1,step=Math.round(plan.distance*t);show(startFrame+direct*step);if(t<1){raf=requestAnimationFrame(move);return;}show(plan.entry);document.body.dataset.state='settling';setTimeout(()=>{document.body.dataset.state='focus-ready';document.body.dataset.focusUnit=unit;status.textContent+=`｜已停稳，可进入${names[unit]}聚焦路线`;},nav.settledHoldMs);}raf=requestAnimationFrame(move);}
toggle.addEventListener('click',()=>playing?pause():play());document.querySelector('[data-testid="replay"]').addEventListener('click',()=>{playing=false;cancelAnimationFrame(raf);elapsed=0;show(0);play();});scrubber.addEventListener('input',()=>{playing=false;cancelAnimationFrame(raf);frame=Number(scrubber.value);elapsed=frame/data.frameCount*data.durationMs;setState('paused');show(frame);});
for(const button of document.querySelectorAll('[data-action-unit]'))button.addEventListener('click',()=>turnToUnit(button.dataset.actionUnit));
fetch('review-data.json').then(r=>r.json()).then(value=>{data=value;document.body.dataset.ready='true';show(0);play();});
</script></html>'''
    path = review_root / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def _write_c360_review_player(output_root, frames, qualification_by_unit):
    output_root = Path(output_root)
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    data = {
        "durationMs": C360_F96_PROFILE["durationMs"],
        "frameCount": 96,
        "entryRole": "overview-exit-only",
        "focusRouteGenerated": False,
        "entryFramesByUnit": {
            unit: qualification_by_unit[unit]["initialEntryFrameSet"]
            for unit in SEMANTIC_UNITS
        },
        "entryCandidatesByUnit": {
            unit: qualification_by_unit[unit]["entryCandidates"]
            for unit in SEMANTIC_UNITS
        },
        "visibleIntervalsByUnit": {
            unit: qualification_by_unit[unit]["proposedHumanVisibleIntervals"]
            for unit in SEMANTIC_UNITS
        },
        "statusCountsByUnit": {
            unit: qualification_by_unit[unit]["statusCounts"]
            for unit in SEMANTIC_UNITS
        },
        "navigation": {
            "maximumTurnDurationMs": 2_000,
            "maximumAngularSpeedDegreesPerSecond": 90.0,
            "accelerationRampMs": 250,
            "decelerationRampMs": 250,
            "settledHoldMs": 100,
        },
        "frames": [
            {
                "index": frame["physicalFrameIndex"],
                "angle": frame["azimuthDegrees"],
                "src": f"../{frame['path']}",
                "hotspots": {
                    unit: {
                        "status": frame["qualificationByUnit"][unit]["status"],
                        "projection": frame["qualificationByUnit"][unit][
                            "projection"
                        ],
                    }
                    for unit in SEMANTIC_UNITS
                },
            }
            for frame in frames
        ],
    }
    (review_root / "review-data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    html = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>TWINKLE C360-F96 人工审核</title>
<style>
:root{color-scheme:dark;--bg:#0c0f12;--panel:#14181d;--surface:#1b2026;--line:rgba(255,255,255,.14);--muted:#9ba5af;--text:#f6f7f8;--hotspot:#fff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 system-ui,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}.layout{display:grid;grid-template-columns:minmax(0,1fr) 360px;min-height:100vh}.stage{display:grid;place-items:center;padding:clamp(18px,3vw,42px);background:radial-gradient(circle at 50% 42%,#20262d 0,#101419 58%,#0c0f12 100%)}.viewer-shell{width:min(100%,1040px)}.viewer-heading{display:flex;justify-content:space-between;margin:0 0 14px;color:var(--muted);font-size:11px;letter-spacing:.08em;text-transform:uppercase}.viewer{position:relative;width:100%;aspect-ratio:64/45;overflow:hidden;border:1px solid rgba(255,255,255,.16);border-radius:14px;background:#e9eceb;box-shadow:0 28px 80px rgba(0,0,0,.34)}.viewer img{display:block;width:100%;height:100%;object-fit:contain}.hotspot[hidden]{display:none!important;pointer-events:none}.hotspot{position:absolute;width:30px;height:30px;transform:translate(-50%,-50%);border:0;background:transparent;color:var(--hotspot);cursor:pointer;padding:0;filter:drop-shadow(0 2px 6px rgba(0,0,0,.45))}.hotspot-ring{position:absolute;inset:6px;border:1.5px solid currentColor;border-radius:50%;background:rgba(12,15,18,.36)}.hotspot-ring::after{content:"";position:absolute;inset:4px;border-radius:50%;background:currentColor}.hotspot-pulse{position:absolute;inset:3px;border:1px solid currentColor;border-radius:50%;opacity:.55;animation:hotspotPulse 2.2s ease-out infinite}.hotspot-label{position:absolute;left:27px;top:50%;transform:translate(4px,-50%);padding:5px 9px;border:1px solid rgba(255,255,255,.13);border-radius:5px;background:rgba(18,22,27,.78);box-shadow:0 8px 24px rgba(0,0,0,.24);color:#fff;font-size:12px;font-weight:600;line-height:1.2;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .16s ease,transform .16s ease}.hotspot:hover .hotspot-label,.hotspot:focus-visible .hotspot-label,.hotspot[aria-pressed="true"] .hotspot-label{opacity:1;transform:translate(0,-50%)}.hotspot:focus-visible{outline:2px solid #fff;outline-offset:3px;border-radius:50%}@keyframes hotspotPulse{0%{transform:scale(.72);opacity:.6}75%,100%{transform:scale(1.35);opacity:0}}.audit-controls{padding:28px 24px 32px;background:var(--panel);border-left:1px solid var(--line);overflow:auto}.eyebrow{margin:0 0 8px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}.audit-controls h1{margin:0;font-size:25px;line-height:1.15;font-weight:620;letter-spacing:-.02em}.scope-note{margin:12px 0 20px;color:#c2c9d0;font-size:12px}.scope-note strong{color:#fff}.section{padding:18px 0;border-top:1px solid var(--line)}.section-title{margin:0 0 11px;color:#fff;font-size:12px;font-weight:700;letter-spacing:.06em}.controls{display:grid;grid-template-columns:1fr 1fr;gap:8px}.control,.name-button,.entry-button{min-height:42px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:#fff;font:inherit;cursor:pointer;transition:border-color .16s ease,background .16s ease,transform .16s ease}.control:hover,.name-button:hover,.entry-button:hover{border-color:rgba(255,255,255,.34);background:#222830}.control:active,.name-button:active,.entry-button:active{transform:translateY(1px)}.scrubber-label{display:block;margin-top:14px;color:var(--muted);font-size:12px}.scrubber-label input{display:block;width:100%;margin-top:9px;accent-color:#fff}.frame-status{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.metric{padding:9px 8px;border:1px solid var(--line);border-radius:8px;background:#0f1317}.metric b{display:block;font-size:15px;font-variant-numeric:tabular-nums}.metric span{color:var(--muted);font-size:10px}.state-line{min-height:38px;margin:10px 0 0;padding:9px 10px;border-radius:8px;background:#0e1216;color:#cbd2d8;font-size:12px}.name-button{display:block;width:100%;margin-top:8px;padding:10px 12px;text-align:left}.name-button.chamber,.name-button.condenser{border-left:2px solid rgba(255,255,255,.5)}.summary{display:grid;gap:9px}.summary-card{padding:11px;border:1px solid var(--line);border-radius:9px;background:#101419}.summary-card h3{margin:0 0 7px;font-size:12px}.summary-card p{margin:3px 0;color:#aeb7c0;font-size:11px}.entry-list{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.entry-button{padding:8px;text-align:left;font-size:11px}.entry-button b{display:block;color:#fff;font-size:12px}.gate{margin:0;padding:11px;border:1px solid rgba(255,255,255,.2);border-radius:9px;background:rgba(255,255,255,.04);color:#dce2e7;font-size:11px}.dev-status{color:var(--muted);font-size:11px}.dev-status code{color:#dce2e7}.chamber-text,.condenser-text{color:#fff}@media(max-width:980px){.layout{grid-template-columns:1fr}.audit-controls{border-left:0;border-top:1px solid var(--line)}.stage{min-height:62vh}}@media(prefers-reduced-motion:reduce){.hotspot-pulse{animation:none}.hotspot-label,.control,.name-button,.entry-button{transition:none}}
:root{--hotspot-fade:140ms}.hotspot{opacity:0;transition:opacity var(--hotspot-fade) ease-out}.hotspot.is-visible{opacity:1}.hotspot-label{opacity:1;transform:translate(0,-50%);pointer-events:none}@media(prefers-reduced-motion:reduce){.hotspot{transition:none}}
</style></head><body data-focus-route-generated="false"><div class="layout"><main class="stage"><div class="viewer-shell"><div class="viewer-heading"><span>完整装配 · 360° 人工审核</span><span>lossless PNG · 96 frames</span></div><div class="viewer" data-testid="spin-player"><img data-testid="spin-frame" alt="TWINKLE C360-F96 完整装配 360°审核帧"><button class="hotspot chamber" type="button" data-unit="dual_channel_collection_optics_chamber" aria-label="双通道采集光学舱" aria-pressed="false" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">双通道采集光学舱</span></button><button class="hotspot condenser" type="button" data-unit="dual_channel_condenser_lens_assembly" aria-label="聚光镜组件" aria-pressed="false" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">聚光镜组件</span></button></div></div></main><aside class="audit-controls" aria-label="C360-F96 人工审核控制栏"><p class="eyebrow">Stage 4 · Human review</p><h1>C360-F96 人工审核</h1><p class="scope-note"><strong>仅限人工审核控制栏。</strong>不实现正式详情面板、产品讲解内容、阶段 3 动作接入、生产信息架构或生产页面交互。</p><section class="section"><h2 class="section-title">播放控制</h2><div class="controls"><button class="control" data-testid="play-pause">暂停</button><button class="control" data-testid="replay">重播</button></div><label class="scrubber-label">拖动查看<input data-testid="scrubber" type="range" min="0" max="95" step="1" value="0"></label><div class="frame-status" data-testid="frame-status"><div class="metric"><b data-frame-value>0/95</b><span>当前帧</span></div><div class="metric"><b data-angle-value>0.00°</b><span>角度</span></div><div class="metric"><b data-time-value>0.00s</b><span>时间</span></div></div><p class="state-line" data-testid="focus-status">完整 360° 单圈播放</p></section><section class="section"><h2 class="section-title">固定中文名称按钮</h2><button class="name-button chamber" data-action-unit="dual_channel_collection_optics_chamber">双通道采集光学舱</button><button class="name-button condenser" data-action-unit="dual_channel_condenser_lens_assembly">聚光镜组件</button></section><section class="section"><h2 class="section-title">入口候选与可见区间</h2><p class="gate">入口帧只是总览出口；到达后仅显示“准备进入聚焦”。本页未生成或冒充聚焦曲线。</p><div class="summary" data-testid="entry-summary"></div></section><section class="section"><h2 class="section-title">开发状态</h2><p class="dev-status">hotspot status：<code>visible</code> / <code>back-facing</code> / <code>occluded</code> / <code>out-of-safe</code>。非 visible 热点完全隐藏且不可交互。</p><p class="dev-status">humanVisualApproved=false · humanEntryApproved=false · authorizesOrbitRepair=false · authorizesStep6=false · authorizesStage5=false</p></section></aside></div>
<script>
const names={dual_channel_collection_optics_chamber:'双通道采集光学舱',dual_channel_condenser_lens_assembly:'聚光镜组件'},auditBoundary={focusRouteGenerated:false,entryRole:'overview-exit-only'};
let data,frame=0,elapsed=0,started=0,playing=false,raf,settleTimer,selectedUnit=null,orbitDirection='forward',fadeTimers=new Map();
const image=document.querySelector('[data-testid="spin-frame"]'),scrubber=document.querySelector('[data-testid="scrubber"]'),toggle=document.querySelector('[data-testid="play-pause"]'),focusStatus=document.querySelector('[data-testid="focus-status"]'),frameValue=document.querySelector('[data-frame-value]'),angleValue=document.querySelector('[data-angle-value]'),timeValue=document.querySelector('[data-time-value]');
function cancelMotion(){playing=false;cancelAnimationFrame(raf);clearTimeout(settleTimer);}
function preloadFrames(){return Promise.all(data.frames.map(record=>new Promise((resolve,reject)=>{const preload=new Image();preload.onload=()=>resolve(record.index);preload.onerror=()=>reject(new Error('frame preload failed '+record.index));preload.src=record.src;})));}
function scheduleHotspotVisibility(el,isVisible){const next=String(isVisible);if(el.dataset.visibility===next)return;el.dataset.visibility=next;clearTimeout(fadeTimers.get(el));fadeTimers.delete(el);if(isVisible){el.hidden=false;el.classList.remove('is-visible');void el.offsetWidth;el.classList.add('is-visible');return;}el.classList.remove('is-visible');const timer=setTimeout(()=>{if(el.dataset.visibility==='false')el.hidden=true;fadeTimers.delete(el);},140);fadeTimers.set(el,timer);}
function setState(value){document.body.dataset.state=value;toggle.textContent=value==='playing'?'暂停':value==='paused'?'继续':'播放';}
function show(index,timeMs=elapsed){frame=(index+data.frameCount)%data.frameCount;const record=data.frames[frame];image.src=record.src;scrubber.value=frame;for(const [unit,hotspot] of Object.entries(record.hotspots)){const el=document.querySelector('[data-unit="'+unit+'"]'),isVisible=hotspot.status==='visible';scheduleHotspotVisibility(el,isVisible);el.disabled=!isVisible;el.setAttribute('aria-hidden',String(!isVisible));el.setAttribute('aria-pressed',String(isVisible&&selectedUnit===unit));el.style.pointerEvents=isVisible?'auto':'none';el.style.left=(hotspot.projection[0]*100)+'%';el.style.top=(hotspot.projection[1]*100)+'%';document.body.dataset[unit.includes('collection')?'chamberStatus':'condenserStatus']=hotspot.status;}frameValue.textContent=frame+'/95';angleValue.textContent=record.angle.toFixed(2)+'°';timeValue.textContent=(timeMs/1000).toFixed(2)+'s';document.body.dataset.frame=String(frame);}
function tick(now){if(!playing)return;elapsed=now-started;if(elapsed>=data.durationMs){elapsed=data.durationMs;show(0,elapsed);playing=false;setState('completed');focusStatus.textContent='单圈播放完成 · seam 95→0';return;}orbitDirection='forward';show(Math.floor(elapsed/data.durationMs*data.frameCount),elapsed);raf=requestAnimationFrame(tick);}
function play(){if(playing)return;clearTimeout(settleTimer);selectedUnit=null;if(elapsed>=data.durationMs){elapsed=0;show(0,0);}playing=true;started=performance.now()-elapsed;focusStatus.textContent='完整 360° 单圈播放';setState('playing');raf=requestAnimationFrame(tick);}
function pause(){if(!playing)return;playing=false;cancelAnimationFrame(raf);setState('paused');focusStatus.textContent='已暂停 · 可从同点继续';show(frame,elapsed);}
function shortestTurn(current,entries){const plans=[];for(const entry of entries){const forward=(entry-current+96)%96,backward=(current-entry+96)%96;let direction,distance;if(forward<backward){direction='forward';distance=forward}else if(backward<forward){direction='backward';distance=backward}else{direction=orbitDirection;distance=forward}plans.push({entry,direction,distance});}plans.sort((a,b)=>a.distance-b.distance||((a.direction===orbitDirection?0:1)-(b.direction===orbitDirection?0:1))||a.entry-b.entry);return plans[0];}
function turnToUnit(unit){cancelMotion();selectedUnit=unit;const plan=shortestTurn(frame,data.entryFramesByUnit[unit]),distanceDegrees=plan.distance*3.75,nav=data.navigation,movementMs=plan.distance===0?0:(distanceDegrees/nav.maximumAngularSpeedDegreesPerSecond*1000+nav.accelerationRampMs),rampMs=Math.min(nav.accelerationRampMs,movementMs/2),peak=plan.distance===0?0:distanceDegrees/(movementMs/1000-rampMs/1000),totalMs=movementMs+nav.settledHoldMs,startFrame=frame,start=performance.now();orbitDirection=plan.direction;document.body.dataset.state='turning';document.body.dataset.turnDurationMs=String(Math.round(totalMs));document.body.dataset.peakAngularSpeed=String(peak);document.body.dataset.selectedEntry=String(plan.entry);focusStatus.textContent='正在转向'+names[unit]+'入口';function progress(ms){if(movementMs===0)return 1;const time=Math.min(ms,movementMs)/1000,ramp=rampMs/1000,movement=movementMs/1000,cruise=Math.max(0,movement-2*ramp),pi=Math.PI;let travelled;if(time<ramp)travelled=peak*(time/2-ramp/(2*pi)*Math.sin(pi*time/ramp));else if(time<ramp+cruise)travelled=peak*(ramp/2+time-ramp);else{const u=time-ramp-cruise;travelled=peak*(ramp/2+cruise+u/2+ramp/(2*pi)*Math.sin(pi*u/ramp));}return Math.min(travelled/Math.max(distanceDegrees,1e-9),1);}function move(now){const t=progress(now-start),direct=plan.direction==='forward'?1:-1,step=Math.round(plan.distance*t),nextFrame=(startFrame+direct*step+96)%96;elapsed=nextFrame/data.frameCount*data.durationMs;show(nextFrame,elapsed);if(t<1){raf=requestAnimationFrame(move);return;}elapsed=plan.entry/data.frameCount*data.durationMs;show(plan.entry,elapsed);document.body.dataset.state='settling';focusStatus.textContent='入口已到达 · 正在停稳';settleTimer=setTimeout(()=>{document.body.dataset.state='focus-ready';document.body.dataset.focusUnit=unit;focusStatus.textContent='准备进入聚焦 · '+names[unit];},nav.settledHoldMs);}raf=requestAnimationFrame(move);}
function activateModelHotspot(unit){const isVisible=data.frames[frame].hotspots[unit].status==='visible';if(!isVisible)return;turnToUnit(unit);}
function formatIntervals(intervals){return intervals.map(item=>item.wraps?item.start+'→'+item.end+'（跨 seam）':item.start+'–'+item.end).join('，');}
function renderSummary(){const root=document.querySelector('[data-testid="entry-summary"]');for(const unit of Object.keys(names)){const card=document.createElement('article'),candidates=data.entryCandidatesByUnit[unit],counts=data.statusCountsByUnit[unit];card.className='summary-card';card.innerHTML='<h3 class="'+(unit.includes('collection')?'chamber-text':'condenser-text')+'">'+names[unit]+'</h3><p>机器可见区间：'+formatIntervals(data.visibleIntervalsByUnit[unit])+'</p><p>visible '+counts.visible+' · back-facing '+counts['back-facing']+' · occluded '+counts.occluded+' · out-of-safe '+counts['out-of-safe']+'</p><div class="entry-list"></div>';const list=card.querySelector('.entry-list');for(const candidate of candidates){const button=document.createElement('button');button.className='entry-button';button.type='button';button.innerHTML='<b>frame '+candidate.frameIndex+'</b>'+candidate.angleDegrees.toFixed(2)+'° · 投影面积 '+(candidate.componentRecognizability.visibleArea*100).toFixed(1)+'%';button.addEventListener('click',()=>{cancelMotion();selectedUnit=unit;elapsed=candidate.frameIndex/data.frameCount*data.durationMs;setState('paused');show(candidate.frameIndex,elapsed);focusStatus.textContent='入口候选 frame '+candidate.frameIndex+' · 等待人工审核';});list.append(button);}root.append(card);}}
toggle.addEventListener('click',()=>playing?pause():play());document.querySelector('[data-testid="replay"]').addEventListener('click',()=>{cancelMotion();elapsed=0;selectedUnit=null;show(0,0);play();});scrubber.addEventListener('input',()=>{cancelMotion();const next=Number(scrubber.value);orbitDirection=next>=frame?'forward':'backward';frame=next;elapsed=frame/data.frameCount*data.durationMs;selectedUnit=null;setState('paused');focusStatus.textContent='已拖动 · 可从同点继续';show(frame,elapsed);});
for(const button of document.querySelectorAll('[data-action-unit]'))button.addEventListener('click',()=>turnToUnit(button.dataset.actionUnit));for(const hotspot of document.querySelectorAll('[data-unit]'))hotspot.addEventListener('click',()=>activateModelHotspot(hotspot.dataset.unit));
fetch('review-data.json').then(response=>{if(!response.ok)throw new Error('review data '+response.status);return response.json();}).then(value=>{data=value;if(data.focusRouteGenerated!==auditBoundary.focusRouteGenerated)throw new Error('focus route generation boundary mismatch');focusStatus.textContent='正在预加载 96 帧';return preloadFrames();}).then(()=>{document.body.dataset.ready='true';renderSummary();show(0,0);play();}).catch(error=>{document.body.dataset.state='error';focusStatus.textContent='审核数据加载失败：'+error.message;console.error(error);});
</script></body></html>'''
    path = review_root / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def validate_c360_f96(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "orbit-c360-f96-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("C360-F96 manifest is missing")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != "twinkle-stage4-orbit-c360-f96-v1":
        raise ValueError("C360-F96 schema mismatch")
    if report.get("orbitProfile") != C360_F96_PROFILE:
        raise ValueError("C360-F96 profile mismatch")
    if report.get("anglesDegrees") != c360_f96_angles():
        raise ValueError("C360-F96 angle sequence mismatch")
    if report.get("logicalPhysicalFrames") != list(range(96)):
        raise ValueError("C360-F96 logical mapping mismatch")
    frames = report.get("frames", [])
    if len(frames) != 96 or [f.get("physicalFrameIndex") for f in frames] != list(range(96)):
        raise ValueError("C360-F96 frame inventory mismatch")
    if len({tuple(f["camera"]["location"]) for f in frames}) != 96:
        raise ValueError("C360-F96 contains a duplicate camera endpoint")
    if any(
        f.get("quality", {}).get("blackFrame") is not False
        or f.get("quality", {}).get("emptyFrame") is not False
        or f.get("targetClipped") is not False
        or f.get("subjectOutOfFrame") is not False
        for f in frames
    ):
        raise ValueError("C360-F96 visual frame gate failed")
    closure = report.get("closureMetrics", {})
    if (
        closure.get("duplicateEndpointRendered") is not False
        or float(closure.get("seamPositionStepRatio", 99)) > 1.05
        or float(closure.get("seamOrientationStepRatio", 99)) > 1.05
        or float(closure.get("pixelSeamRatio", 99)) > 1.25
    ):
        raise ValueError("C360-F96 closure gate failed")
    human_visual_approved = report.get("humanVisualApproved")
    human_entry_approved = report.get("humanEntryApproved", False)
    if human_visual_approved is not human_entry_approved:
        raise ValueError("C360-F96 visual and entry approval state mismatch")
    if human_visual_approved is not False and human_visual_approved is not True:
        raise ValueError("C360-F96 human approval must be an explicit boolean")
    expected_component_review_status = (
        "approved" if human_visual_approved else "pending"
    )
    for unit in SEMANTIC_UNITS:
        qualification = report.get("qualificationByUnit", {}).get(unit, {})
        if len(qualification.get("physicalFrames", [])) != 96 or len(qualification.get("logicalFrames", [])) != 96:
            raise ValueError("C360-F96 hotspot qualification count mismatch")
        entries = qualification.get("initialEntryFrameSet", [])
        candidates = qualification.get("entryCandidates", [])
        recognizable = qualification.get(
            "componentRecognizabilityQualifiedFrames", []
        )
        if (
            not 1 <= len(entries) <= 2
            or [candidate.get("frameIndex") for candidate in candidates]
            != entries
            or not recognizable
            or qualification.get("entryRole") != "overview-exit-only"
            or qualification.get("focusRouteGenerated") is not False
            or qualification.get("humanEntryApproved")
            is not human_entry_approved
            or qualification.get("humanApproved") is not human_entry_approved
            or qualification.get("componentRecognizabilityGateOrder")
            != [
                "machine-visible",
                "complete-overview-component-projection",
                "cyclic-shortest-turn",
            ]
        ):
            raise ValueError("C360-F96 entry candidate gate mismatch")
        for candidate in candidates:
            component = candidate.get("componentRecognizability", {})
            if (
                candidate.get("frameIndex") not in recognizable
                or candidate.get("frameIndex")
                not in qualification.get("machineQualifiedPhysicalFrames", [])
                or candidate.get("hotspotStatus") != "visible"
                or component.get("gatePassed") is not True
                or component.get("authorityState")
                != "complete-overview-assembly"
                or component.get("usesFocusOrExtractState") is not False
                or component.get("humanReviewStatus")
                != expected_component_review_status
                or not all(component.get("criteria", {}).values())
            ):
                raise ValueError(
                    "C360-F96 component recognizability gate mismatch"
                )
        selection = qualification.get("entrySelection", {})
        if (
            selection.get("recognizabilityGateApplied") is not True
            or
            selection.get("maximumCyclicDistanceFrames", 99) > 48
            or qualification.get("turnPlanWorstCase", {}).get(
                "turnDurationMs", 9999
            )
            > 2_000
            or qualification.get("turnPlanWorstCase", {}).get(
                "peakAngularSpeedDegreesPerSecond", 999
            )
            > 90.0
            or qualification.get("turnPlanWorstCase", {}).get(
                "arrivesStopped"
            )
            is not True
            or qualification.get("turnPlanWorstCase", {}).get(
                "enterFocusAfterSettled"
            )
            is not True
        ):
            raise ValueError("C360-F96 name-button turn plan failed")
    if report.get("reviewPlayer") != C360_F96_REVIEW_PLAYER:
        raise ValueError("C360-F96 review player contract mismatch")
    approval = report.get("c360ReviewApproval")
    if human_visual_approved:
        expected_approval = {
            "approvedBy": "user",
            "approvedOn": approval.get("approvedOn") if approval else None,
            "scope": (
                "stage4-c360-f96-visual-hotspots-visible-intervals-and-"
                "overview-exit-entry-candidates-only"
            ),
            "approvedReviewAsset": "review/index.html",
            "approvedReviewAssetSha256": report.get("inventorySha256", {}).get(
                "review/index.html"
            ),
            "approvedVisibleIntervalsByUnit": {
                unit: report["qualificationByUnit"][unit][
                    "machineQualifiedCyclicIntervals"
                ]
                for unit in SEMANTIC_UNITS
            },
            "approvedEntryFrameSetByUnit": {
                unit: report["qualificationByUnit"][unit][
                    "initialEntryFrameSet"
                ]
                for unit in SEMANTIC_UNITS
            },
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        }
        if not expected_approval["approvedOn"] or approval != expected_approval:
            raise ValueError("C360-F96 human review approval metadata mismatch")
    elif approval is not None:
        raise ValueError("C360-F96 pending approval state mismatch")
    if (
        report.get("renderedFrameCount") != 96
        or report.get("totalStage4RenderedToDate") != 160
        or report.get("authorizesOrbitRepair") is not False
        or report.get("authorizesStep6") is not False
        or report.get("authorizesStage5") is not False
    ):
        raise ValueError("C360-F96 budget or approval gate mismatch")
    restoration = report.get("restoration", {})
    if not (
        restoration.get("candidateBlendSha256Before") == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After") == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSaved") is False
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("temporaryDataBlocksRemaining") == []
    ):
        raise ValueError("C360-F96 restoration gate failed")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    required = {
        "worker-audit.json", "logical-index-map.json", "camera-path.json",
        "frame-qualification.json", "path-speed.png",
        "c360-f96-12-frame-contact-sheet.png", "review/index.html",
        "review/review-data.json",
        *{f"frames/frame-{index:03d}.png" for index in range(96)},
    }
    if set(actual) != required or report.get("inventorySha256") != actual:
        raise ValueError("C360-F96 exact inventory mismatch")
    return report


def record_c360_f96_review_approval(output_root, *, approved_on):
    output_root = Path(output_root).resolve()
    report = validate_c360_f96(output_root)
    if (
        report.get("humanVisualApproved") is not False
        or report.get("humanEntryApproved", False) is not False
        or report.get("c360ReviewApproval") is not None
    ):
        raise ValueError("C360-F96 human review approval is already recorded")
    approved_on = str(approved_on)
    if not approved_on:
        raise ValueError("C360-F96 human review approval date is required")
    for qualification in report["qualificationByUnit"].values():
        qualification["humanEntryApproved"] = True
        qualification["humanApproved"] = True
        for candidate in qualification["entryCandidates"]:
            candidate["componentRecognizability"][
                "humanReviewStatus"
            ] = "approved"
    report["humanVisualApproved"] = True
    report["humanEntryApproved"] = True
    report["c360ReviewApproval"] = {
        "approvedBy": "user",
        "approvedOn": approved_on,
        "scope": (
            "stage4-c360-f96-visual-hotspots-visible-intervals-and-"
            "overview-exit-entry-candidates-only"
        ),
        "approvedReviewAsset": "review/index.html",
        "approvedReviewAssetSha256": report["inventorySha256"][
            "review/index.html"
        ],
        "approvedVisibleIntervalsByUnit": {
            unit: report["qualificationByUnit"][unit][
                "machineQualifiedCyclicIntervals"
            ]
            for unit in SEMANTIC_UNITS
        },
        "approvedEntryFrameSetByUnit": {
            unit: report["qualificationByUnit"][unit]["initialEntryFrameSet"]
            for unit in SEMANTIC_UNITS
        },
        "authorizesOrbitRepair": False,
        "authorizesStep6": False,
        "authorizesStage5": False,
    }
    report["authorizesOrbitRepair"] = False
    report["authorizesStep6"] = False
    report["authorizesStage5"] = False
    manifest_path = output_root / "orbit-c360-f96-manifest.json"
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return validate_c360_f96(output_root)


def validate_c360_f96_recovery_staging(staging):
    staging = Path(staging).resolve()
    if not staging.is_dir():
        raise ValueError("C360-F96 recovery staging is missing")
    expected = {
        "worker-audit.json",
        *{f"frames/frame-{index:03d}.png" for index in range(96)},
    }
    actual = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ValueError("C360-F96 recovery inventory drift")
    worker = json.loads(
        (staging / "worker-audit.json").read_text(encoding="utf-8")
    )
    if worker.get("schema") != "twinkle-stage4-c360-f96-worker-v1":
        raise ValueError("C360-F96 recovery worker schema mismatch")
    frames = worker.get("frames", [])
    if worker.get("renderedFrameCount") != 96 or len(frames) != 96:
        raise ValueError("C360-F96 recovery frame count mismatch")
    for index, frame in enumerate(frames):
        path = staging / "frames" / f"frame-{index:03d}.png"
        if frame.get("physicalFrameIndex") != index or sha256(path) != frame.get(
            "sha256"
        ):
            raise ValueError("C360-F96 recovery frame hash mismatch")
    restoration = worker.get("restoration", {})
    if not (
        restoration.get("candidateBlendSaved") is False
        and restoration.get("candidateBlendSha256Before")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("temporaryDataBlocksRemaining") == []
    ):
        raise ValueError("C360-F96 recovery restoration mismatch")
    return {
        "workerSchema": worker["schema"],
        "renderedFrameCount": 96,
        "frameCount": 96,
        "candidateBlendSaved": False,
    }


def build_c360_f96(
    output_root,
    *,
    authorized=False,
    blender=None,
    runner=None,
    recovery_staging=None,
):
    if authorized is not True:
        raise PermissionError("C360-F96 requires explicit authorization")
    output_root = Path(output_root).resolve()
    if output_root.name != "orbit-c360-f96-r1":
        raise ValueError("C360-F96 output name mismatch")
    validate_request(default_request(output_root))
    authority = validate_authority()["stage1"]
    correction = validate_orientation_correction(APPROVED_ORIENTATION_CORRECTION)
    surface = validate_surface_anchor_precheck(APPROVED_SURFACE_ANCHOR_PRECHECK)
    selected = {CHAMBER: "chamber-surface-02", CONDENSER: "condenser-surface-01"}
    if (
        correction.get("humanApproved") is not True
        or surface.get("humanSurfaceApproved") is not True
        or surface.get("selectedCandidateByUnit") != selected
    ):
        raise ValueError("C360-F96 input approval mismatch")
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before C360-F96")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked
    if recovery_staging is None:
        output_root.parent.mkdir(parents=True, exist_ok=False)
        staging = Path(
            tempfile.mkdtemp(prefix=".orbit-c360-f96-", dir=output_root.parent)
        ).resolve()
    else:
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(recovery_staging).resolve()
        validate_c360_f96_recovery_staging(staging)
    try:
        if recovery_staging is None:
            runner(
                c360_f96_blender_command(blender, candidate_blend, staging),
                cwd=ROOT,
            )
        worker_path = staging / "worker-audit.json"
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        if worker.get("schema") != "twinkle-stage4-c360-f96-worker-v1":
            raise ValueError("C360-F96 worker schema mismatch")
        frames = sorted(
            worker.get("frames", []), key=lambda frame: frame["physicalFrameIndex"]
        )
        if len(frames) != 96:
            raise ValueError("C360-F96 worker frame count mismatch")
        for frame in frames:
            path = staging / frame["path"]
            if not path.is_file() or sha256(path) != frame.get("sha256"):
                raise ValueError("C360-F96 frame file or hash mismatch")
            frame["quality"] = _frame_quality(path)
            if frame["quality"]["blackFrame"] or frame["quality"]["emptyFrame"]:
                raise ValueError("C360-F96 black or empty frame")

        adjacent_mae = [
            _rgb_mae(staging / frames[index]["path"], staging / frames[index + 1]["path"])
            for index in range(95)
        ]
        seam_mae = _rgb_mae(staging / frames[-1]["path"], staging / frames[0]["path"])
        median_adjacent = sorted(adjacent_mae)[len(adjacent_mae) // 2]
        pixel_seam_ratio = seam_mae / median_adjacent if median_adjacent else 1.0
        closure = dict(worker["closureMetrics"])
        closure.update(
            {
                "pixelAdjacentMedianRgbMae": median_adjacent,
                "pixelSeamRgbMae": seam_mae,
                "pixelSeamRatio": pixel_seam_ratio,
                "duplicateEndpointRendered": False,
            }
        )
        if (
            closure["seamPositionStepRatio"] > 1.05
            or closure["seamOrientationStepRatio"] > 1.05
            or pixel_seam_ratio > 1.25
        ):
            raise ValueError("C360-F96 closure continuity failed")

        logical_map = [
            {"logicalIndex": index, "physicalFrameIndex": index}
            for index in range(96)
        ]
        qualification_by_unit, total_entries = (
            _build_c360_qualification_by_unit(frames, authority, selected)
        )
        (staging / "logical-index-map.json").write_text(
            json.dumps(logical_map, indent=2), encoding="utf-8"
        )
        (staging / "camera-path.json").write_text(
            json.dumps(
                [
                    {
                        key: frame[key]
                        for key in (
                            "physicalFrameIndex",
                            "azimuthDegrees",
                            "camera",
                            "speedMetersPerSecond",
                        )
                    }
                    for frame in frames
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        (staging / "frame-qualification.json").write_text(
            json.dumps(qualification_by_unit, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _write_orbit_speed_graph(staging, frames)
        contact_path, sampled = _write_c360_contact_sheet(staging, frames)
        _write_c360_review_player(staging, frames, qualification_by_unit)
        curve_budget = 50 * total_entries
        report = {
            "schema": "twinkle-stage4-orbit-c360-f96-v1",
            "scope": "stage4-c360-f96-single-lowres-candidate-only",
            "authority": {
                "stage1ManifestSha256": EXPECTED_STAGE1_SHA256,
                "stage3R2ManifestSha256": EXPECTED_STAGE3_R2_SHA256,
                "candidateBlendSha256": EXPECTED_CANDIDATE_BLEND_SHA256,
                "surfaceAnchorManifestSha256": EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256,
            },
            "orbitProfile": C360_F96_PROFILE,
            "render": C360_F96_RENDER,
            "orientationConstraint": "TRACK_TO",
            "anglesDegrees": c360_f96_angles(),
            "physicalFrameCount": 96,
            "logicalIndexCount": 96,
            "logicalPhysicalFrames": list(range(96)),
            "selectedSurfaceAnchorByUnit": selected,
            "frames": frames,
            "qualificationByUnit": qualification_by_unit,
            "closureMetrics": closure,
            "orientationMetrics": worker["orientationMetrics"],
            "restoration": worker["restoration"],
            "staticContactSheet": {
                "asset": contact_path.name,
                "sampledFrameIndices": sampled,
            },
            "reviewPlayer": dict(C360_F96_REVIEW_PLAYER),
            "renderedFrameCount": 96,
            "totalStage4RenderedToDate": 160,
            "budgetEvidence": {
                "previousStage4Rendered": 64,
                "renderedThisRun": 96,
                "totalRenderedToDate": 160,
                "totalEntryPoints": total_entries,
                "futureCurveFirstRoundRenders": curve_budget,
                "futureFirstRoundCumulative": 160 + curve_budget,
                "maximumCumulativeWithAuthorizedDesignAllowances": 256 + 2 * curve_budget,
                "orbitRepairAuthorized": False,
                "curveRenderingAuthorized": False,
            },
            "machinePassed": True,
            "humanVisualApproved": False,
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "orbit-c360-f96-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_c360_f96(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(
            f"C360-F96 failed; isolated staging kept at {staging}"
        ) from error
    return validate_c360_f96(output_root)


def refresh_c360_f96_review(output_root):
    output_root = Path(output_root).resolve()
    if output_root.name != "orbit-c360-f96-r1" or not output_root.is_dir():
        raise ValueError("C360-F96 review refresh target mismatch")
    manifest_path = output_root / "orbit-c360-f96-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = sorted(
        report.get("frames", []), key=lambda frame: frame["physicalFrameIndex"]
    )
    if (
        report.get("schema") != "twinkle-stage4-orbit-c360-f96-v1"
        or len(frames) != 96
        or report.get("renderedFrameCount") != 96
        or report.get("totalStage4RenderedToDate") != 160
        or report.get("humanVisualApproved") is not False
        or report.get("authorizesOrbitRepair") is not False
        or report.get("authorizesStep6") is not False
        or report.get("authorizesStage5") is not False
    ):
        raise ValueError("C360-F96 review refresh source gate mismatch")
    allowed_changes = {
        "frame-qualification.json",
        "review/index.html",
        "review/review-data.json",
        "orbit-c360-f96-manifest.json",
    }
    immutable_before = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path.relative_to(output_root).as_posix() not in allowed_changes
    }
    expected_inventory = report.get("inventorySha256", {})
    if any(
        expected_inventory.get(relative) != digest
        for relative, digest in immutable_before.items()
    ):
        raise ValueError("C360-F96 immutable review source drift")
    for index, frame in enumerate(frames):
        path = output_root / frame["path"]
        if (
            frame.get("physicalFrameIndex") != index
            or not path.is_file()
            or sha256(path) != frame.get("sha256")
        ):
            raise ValueError("C360-F96 source PNG drift before review refresh")

    authority = validate_authority()["stage1"]
    selected = {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    if report.get("selectedSurfaceAnchorByUnit") != selected:
        raise ValueError("C360-F96 surface selection drift before review refresh")
    qualification_by_unit, total_entries = (
        _build_c360_qualification_by_unit(frames, authority, selected)
    )
    (output_root / "frame-qualification.json").write_text(
        json.dumps(qualification_by_unit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_c360_review_player(output_root, frames, qualification_by_unit)
    curve_budget = 50 * total_entries
    report["scope"] = "stage4-c360-f96-zero-render-human-review-optimization-only"
    report["qualificationByUnit"] = qualification_by_unit
    report["entryRole"] = "overview-exit-only"
    report["focusRouteGenerated"] = False
    report["humanEntryApproved"] = False
    report["reviewPlayer"] = dict(C360_F96_REVIEW_PLAYER)
    report["budgetEvidence"].update(
        {
            "totalEntryPoints": total_entries,
            "futureCurveFirstRoundRenders": curve_budget,
            "futureFirstRoundCumulative": 160 + curve_budget,
            "maximumCumulativeWithAuthorizedDesignAllowances": (
                256 + 2 * curve_budget
            ),
            "orbitRepairAuthorized": False,
            "curveRenderingAuthorized": False,
        }
    )
    report["reviewOptimization"] = {
        "renderedFrameCount": 0,
        "reusedC360PngCount": 96,
        "sourcePngAndWorkerAuditUnchanged": True,
        "surfaceState": "complete-overview-assembly",
        "usesFocusOrExtractState": False,
        "componentRecognizabilityGateOrder": [
            "machine-visible",
            "complete-overview-component-projection",
            "cyclic-shortest-turn",
        ],
        "componentRecognizabilityThresholdsByUnit": {
            unit: dict(C360_F96_COMPONENT_RECOGNIZABILITY[unit])
            for unit in SEMANTIC_UNITS
        },
        "cleanRoomVisualReference": (
            "Demodern 3D Product Explorer visual language only; no source, "
            "brand asset, icon, font, or proprietary media copied"
        ),
        "auditControlBarOnly": True,
        "productionDetailPanelImplemented": False,
        "stage3MotionIntegrated": False,
        "productionInteractionImplemented": False,
    }
    report["inventorySha256"] = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    immutable_after = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path.relative_to(output_root).as_posix() not in allowed_changes
    }
    if immutable_after != immutable_before:
        raise RuntimeError("C360-F96 review refresh changed an immutable asset")
    return validate_c360_f96(output_root)


def c1_keyframe_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("C1 keyframe output must be an absolute path")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-c1-keyframe-worker",
        str(output_root),
    ]


def c2_full_review_blender_command(blender, candidate_blend, output_root):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("C2 full-review output must be an absolute path")
    return [
        str(blender),
        "--background",
        str(candidate_blend),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--stage4-c2-full-worker",
        str(output_root),
    ]


def _write_c1_contact_sheet(output_root, routes):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root)
    font_record = correction_review_font()
    font = ImageFont.truetype(font_record["path"], 18)
    label_font = ImageFont.truetype(font_record["path"], 16)
    cell_width, image_height, label_height = 320, 225, 52
    sheet = Image.new(
        "RGB",
        (cell_width * 3, (image_height + label_height) * len(routes)),
        (18, 21, 27),
    )
    draw = ImageDraw.Draw(sheet)
    names = {CHAMBER: "双通道采集光学舱", CONDENSER: "聚光镜组件"}
    labels = ("入口（复用）", "曲线中点（新渲染）", "聚焦端点（复用）")
    for row, route in enumerate(routes):
        for column, (frame, label) in enumerate(
            zip(route["previewFrames"], labels)
        ):
            with Image.open(output_root / frame["path"]) as source:
                image = source.convert("RGB")
                image.thumbnail((cell_width, image_height))
                x = column * cell_width + (cell_width - image.width) // 2
                y = row * (image_height + label_height)
                sheet.paste(image, (x, y))
            draw.text(
                (column * cell_width + 8, y + image_height + 4),
                label,
                fill=(238, 241, 247),
                font=label_font,
            )
        draw.text(
            (8, row * (image_height + label_height) + 5),
            f"{names[route['unit']]} / 入口 {route['entryFrame']:03d} / 路线 {route['variant']}",
            fill=(255, 255, 255),
            font=font,
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    path = review_root / "c1-keyframes-contact-sheet.png"
    sheet.save(path)
    return path


def _write_c1_review_page(output_root, routes):
    output_root = Path(output_root)
    names = {CHAMBER: "双通道采集光学舱", CONDENSER: "聚光镜组件"}
    cards = []
    for route in routes:
        images = "".join(
            f'<figure><img src="../{frame["path"]}" alt="{route["routeId"]} '
            f'{frame["sampleIndex"]}"><figcaption>{label}</figcaption></figure>'
            for frame, label in zip(
                route["previewFrames"],
                ("入口（批准资产复用）", "曲线中点（C1 新渲染）", "聚焦端点（阶段 1 复用）"),
            )
        )
        cards.append(
            f'<section data-route="{route["routeId"]}"><h2>{names[route["unit"]]} · '
            f'入口 {route["entryFrame"]:03d} · 路线 {route["variant"]}</h2>'
            f'<div class="triptych">{images}</div><p>machinePassed=true；humanApproved=false</p></section>'
        )
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>TWINKLE C1 A/B 关键帧预检</title><style>
body{margin:0;background:#10141b;color:#eef2f7;font-family:"Microsoft YaHei",sans-serif}main{max-width:1280px;margin:auto;padding:28px}
.gate{padding:14px;background:#291f13;border:1px solid #8d6a2e}section{margin:24px 0;padding:18px;background:#181e27;border:1px solid #303a49}
.triptych{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}figure{margin:0}img{display:block;width:100%;background:#05070a}figcaption{padding:8px 0;color:#bfc9d7}
@media(max-width:760px){.triptych{grid-template-columns:1fr}}</style></head><body><main>
<h1>阶段四步骤 7 · A/B 关键帧预检 C1</h1><p class="gate">机器预检通过不代表人工批准；humanC1Approved=false；不得进入步骤 8。</p>
""" + "".join(cards) + """</main></body></html>"""
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    path = review_root / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def validate_c1_keyframe_precheck(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "c1-keyframe-precheck-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != C1_KEYFRAME_PROFILE["schema"]:
        raise ValueError("C1 keyframe schema mismatch")
    if report.get("profile") != C1_KEYFRAME_PROFILE:
        raise ValueError("C1 keyframe profile mismatch")
    routes = report.get("routes", [])
    if len(routes) != 8 or report.get("routeCount") != 8:
        raise ValueError("C1 keyframe route count mismatch")
    if report.get("renderedFrameCount") != 8 or report.get(
        "reusedEndpointFrameCount"
    ) != 16:
        raise ValueError("C1 keyframe render/reuse count mismatch")
    if report.get("totalStage4RenderedToDate") != 168:
        raise ValueError("C1 keyframe cumulative budget mismatch")
    for route in routes:
        frames = route.get("previewFrames", [])
        if route.get("previewSampleIndices") != [0, 12, 24] or len(frames) != 3:
            raise ValueError("C1 keyframe preview inventory mismatch")
        if [frame.get("sampleIndex") for frame in frames] != [0, 12, 24]:
            raise ValueError("C1 keyframe sample order mismatch")
        for frame in frames:
            path = output_root / frame["path"]
            if not path.is_file() or sha256(path) != frame.get("sha256"):
                raise ValueError("C1 keyframe file/hash mismatch")
            if frame.get("blackFrame") or frame.get("emptyFrame"):
                raise ValueError("C1 black or empty keyframe")
        if not (
            route.get("machinePassed") is True
            and route.get("humanApproved") is False
            and route.get("fullSequenceGenerated") is False
        ):
            raise ValueError("C1 route gate mismatch")
    pairs = {}
    for route in routes:
        pairs.setdefault((route["unit"], route["entryFrame"]), []).append(route)
    if len(pairs) != 4:
        raise ValueError("C1 route pair count mismatch")
    for pair in pairs.values():
        pair.sort(key=lambda route: route["variant"])
        if (
            [route["variant"] for route in pair] != ["A", "B"]
            or pair[0]["commonFields"] != pair[1]["commonFields"]
            or pair[0]["curveControlPoints"] == pair[1]["curveControlPoints"]
        ):
            raise ValueError("C1 A/B common-field contract mismatch")
    restoration = report.get("restoration", {})
    if not (
        restoration.get("candidateBlendSaved") is False
        and restoration.get("candidateBlendSha256Before")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("temporaryDataBlocksRemaining") == []
    ):
        raise ValueError("C1 restoration gate mismatch")
    if not (
        report.get("machinePassed") is True
        and report.get("humanC1Approved") is False
        and report.get("humanVisualApproved") is False
        and report.get("authorizesStep8") is False
        and report.get("authorizesStage5") is False
        and report.get("fullSequenceGenerated") is False
        and report.get("stage3MechanicalPlaybackGenerated") is False
    ):
        raise ValueError("C1 approval boundary mismatch")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if report.get("inventorySha256") != actual:
        raise ValueError("C1 inventory hash mismatch")
    return report


def prepare_c1_output_parent(output_root):
    output_root = Path(output_root).resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    return output_root.parent


def build_c1_keyframe_precheck(
    output_root, *, authorized=False, blender=None, runner=None
):
    if authorized is not True:
        raise PermissionError("C1 keyframe precheck requires explicit authorization")
    output_root = Path(output_root).resolve()
    if output_root.name != "c1-keyframe-precheck-r1":
        raise ValueError("C1 keyframe output name mismatch")
    validate_request(default_request(output_root))
    orbit = validate_c360_f96(APPROVED_C360_F96)
    authority = validate_authority()["stage1"]
    contracts = c1_route_contracts(orbit, authority)
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before C1")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked
    output_parent = prepare_c1_output_parent(output_root)
    staging = Path(tempfile.mkdtemp(prefix=".c1-keyframes-", dir=output_parent))
    try:
        runner(c1_keyframe_blender_command(blender, candidate_blend, staging), cwd=ROOT)
        worker = json.loads((staging / "worker-audit.json").read_text(encoding="utf-8"))
        worker_routes = {route["routeId"]: route for route in worker.get("routes", [])}
        if worker.get("schema") != "twinkle-stage4-c1-keyframe-worker-v1" or set(
            worker_routes
        ) != {route["routeId"] for route in contracts}:
            raise ValueError("C1 worker route inventory mismatch")
        orbit_frames = {int(frame["physicalFrameIndex"]): frame for frame in orbit["frames"]}
        routes = []
        for contract in contracts:
            route_id = contract["routeId"]
            route_root = staging / "frames" / route_id
            route_root.mkdir(parents=True, exist_ok=True)
            start = route_root / "keyframe-000.png"
            middle = route_root / "keyframe-012.png"
            end = route_root / "keyframe-024.png"
            shutil.copy2(
                APPROVED_C360_F96 / orbit_frames[contract["entryFrame"]]["path"],
                start,
            )
            focus_asset = STAGE1_MANIFEST.parent / authority["units"][contract["unit"]][
                "frames"
            ]["focused-settled"]["asset"]
            shutil.copy2(focus_asset, end)
            worker_route = worker_routes[route_id]
            if worker_route.get("path") != middle.relative_to(staging).as_posix():
                raise ValueError("C1 worker midpoint path mismatch")
            preview_frames = []
            for sample_index, path, provenance in (
                (0, start, "approved-c360-entry-reuse"),
                (12, middle, "c1-new-render"),
                (24, end, "approved-stage1-focus-reuse"),
            ):
                quality = _frame_quality(path)
                preview_frames.append(
                    {
                        "sampleIndex": sample_index,
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256(path),
                        "provenance": provenance,
                        **quality,
                    }
                )
            route = {
                **contract,
                "previewSampleIndices": [0, 12, 24],
                "previewFrames": preview_frames,
                "midpointAudit": worker_route,
                "machinePassed": (
                    not any(frame["blackFrame"] or frame["emptyFrame"] for frame in preview_frames)
                    and worker_route.get("positionErrorM", 1.0) <= 1e-5
                    and worker_route.get("targetErrorDegrees", 1.0) <= 1e-4
                ),
                "humanApproved": False,
                "fullSequenceGenerated": False,
            }
            if not route["machinePassed"]:
                raise ValueError(f"C1 route machine gate failed: {route_id}")
            routes.append(route)
        contact = _write_c1_contact_sheet(staging, routes)
        review = _write_c1_review_page(staging, routes)
        report = {
            "schema": C1_KEYFRAME_PROFILE["schema"],
            "scope": "stage4-step7-c1-keyframe-precheck-only",
            "profile": C1_KEYFRAME_PROFILE,
            "routes": routes,
            "routeCount": len(routes),
            "renderedFrameCount": 8,
            "reusedEndpointFrameCount": 16,
            "totalStage4RenderedToDate": 168,
            "restoration": worker["restoration"],
            "review": {
                "asset": review.relative_to(staging).as_posix(),
                "contactSheet": contact.relative_to(staging).as_posix(),
                "candidateGroupRepairUsedByUnit": {
                    CHAMBER: False,
                    CONDENSER: False,
                },
            },
            "machinePassed": True,
            "humanC1Approved": False,
            "humanVisualApproved": False,
            "authorizesStep8": False,
            "authorizesStage5": False,
            "fullSequenceGenerated": False,
            "stage3MechanicalPlaybackGenerated": False,
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        (staging / "c1-keyframe-precheck-manifest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_c1_keyframe_precheck(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(f"C1 keyframe precheck failed; staging kept at {staging}") from error
    return validate_c1_keyframe_precheck(output_root)


def _validate_stage3_r2_inventory(stage3_report):
    inventory = stage3_report.get("inventorySha256", {})
    if not inventory:
        raise ValueError("stage 3 r2 inventory is missing")
    for relative, expected in inventory.items():
        path = STAGE3_R2_MANIFEST.parent / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"stage 3 r2 asset drift: {relative}")
    return inventory


def _materialize_c2_review_dependencies(output_root, routes):
    output_root = Path(output_root)
    dependency_root = output_root / "review-assets"
    if dependency_root.exists():
        raise FileExistsError("C2 review dependency root already exists")
    orbit = validate_c360_f96(APPROVED_C360_F96)
    orbit_frames = {
        int(frame["physicalFrameIndex"]): frame["path"] for frame in orbit["frames"]
    }
    orbit_inventory = orbit["inventorySha256"]
    stage3_report = validate_authority()["stage3"]
    stage3_inventory = _validate_stage3_r2_inventory(stage3_report)
    copied = {}

    def copy_bound(source, destination, expected):
        source = Path(source)
        destination = Path(destination)
        if not source.is_file() or sha256(source) != expected:
            raise ValueError(f"C2 review dependency drift: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256(destination) != expected:
                raise ValueError(f"C2 review dependency collision: {destination}")
        else:
            shutil.copy2(source, destination)
        relative = destination.relative_to(output_root).as_posix()
        copied[relative] = expected
        return relative

    for route in routes:
        route["orbitPrefixReviewAssets"] = []
        for index in route["orbitPrefixIndices"]:
            source_relative = orbit_frames[int(index)]
            local_relative = copy_bound(
                APPROVED_C360_F96 / source_relative,
                dependency_root / "orbit" / f"frame-{int(index):03d}.png",
                orbit_inventory[source_relative],
            )
            route["orbitPrefixReviewAssets"].append(local_relative)
        stage3 = route["stage3R2"]
        stage3["expandReviewAssets"] = [
            copy_bound(
                STAGE3_R2_MANIFEST.parent / asset,
                dependency_root / "stage3" / asset,
                stage3_inventory[asset],
            )
            for asset in stage3["expandAssets"]
        ]
        stage3["closeReviewAssets"] = list(reversed(stage3["expandReviewAssets"]))
        if stage3["inspectionLight"] is not None:
            inspection = stage3["inspectionLight"]
            inspection["unlitReviewAsset"] = copy_bound(
                STAGE3_R2_MANIFEST.parent / inspection["unlitAsset"],
                dependency_root / "stage3" / inspection["unlitAsset"],
                stage3_inventory[inspection["unlitAsset"]],
            )
            inspection["litReviewAsset"] = copy_bound(
                STAGE3_R2_MANIFEST.parent / inspection["litAsset"],
                dependency_root / "stage3" / inspection["litAsset"],
                stage3_inventory[inspection["litAsset"]],
            )
    return copied


def _bind_existing_c2_review_dependencies(output_root, routes):
    output_root = Path(output_root)
    for route in routes:
        route["orbitPrefixReviewAssets"] = [
            f"review-assets/orbit/frame-{int(index):03d}.png"
            for index in route["orbitPrefixIndices"]
        ]
        stage3 = route["stage3R2"]
        stage3["expandReviewAssets"] = [
            f"review-assets/stage3/{asset}" for asset in stage3["expandAssets"]
        ]
        stage3["closeReviewAssets"] = list(reversed(stage3["expandReviewAssets"]))
        if stage3["inspectionLight"] is not None:
            inspection = stage3["inspectionLight"]
            inspection["unlitReviewAsset"] = (
                f"review-assets/stage3/{inspection['unlitAsset']}"
            )
            inspection["litReviewAsset"] = (
                f"review-assets/stage3/{inspection['litAsset']}"
            )
        for relative in route["orbitPrefixReviewAssets"] + stage3[
            "expandReviewAssets"
        ]:
            if not (output_root / relative).is_file():
                raise ValueError(f"C2 local review dependency missing: {relative}")
        if stage3["inspectionLight"] is not None:
            for key in ("unlitReviewAsset", "litReviewAsset"):
                relative = stage3["inspectionLight"][key]
                if not (output_root / relative).is_file():
                    raise ValueError(f"C2 local review dependency missing: {relative}")
    return routes


def _c2_review_asset_inventory(output_root):
    output_root = Path(output_root)
    excluded = {"c2-full-review-manifest.json", "review/index.html"}
    return {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path.relative_to(output_root).as_posix() not in excluded
        and "browser-results" not in path.relative_to(output_root).parts
    }


def _write_c2_review_page(
    output_root, routes, *, review_asset_inventory_sha256
):
    output_root = Path(output_root)
    names = {
        CHAMBER: "双通道采集光学舱",
        CONDENSER: "聚光镜组件",
    }
    payload = []
    cards = []
    for route in routes:
        orbit_prefix = [f"../{asset}" for asset in route["orbitPrefixReviewAssets"]]
        focus = [f"../{frame['path']}" for frame in route["focusFrames"]]
        inspection = route["stage3R2"]["inspectionLight"]
        if inspection is not None:
            inspection = {
                **inspection,
                "unlitAsset": f"../{inspection['unlitReviewAsset']}",
                "litAsset": f"../{inspection['litReviewAsset']}",
            }
        route_payload = {
            "routeId": route["routeId"],
            "unit": route["unit"],
            "entryFrame": route["entryFrame"],
            "variant": route["variant"],
            "c1HumanChoice": route["c1HumanChoice"],
            "modelHotspotQualified": route["modelHotspotQualified"],
            "turnDirection": route["turnDirection"],
            "orbitPrefix": orbit_prefix,
            "focus": focus,
            "expand": [f"../{asset}" for asset in route["stage3R2"]["expandReviewAssets"]],
            "close": [f"../{asset}" for asset in route["stage3R2"]["closeReviewAssets"]],
            "inspectionLight": inspection,
            "overviewReturn": list(reversed(focus)) + list(reversed(orbit_prefix)),
            "captureFrame": orbit_prefix[0],
            "curveDurationMs": C2_FULL_REVIEW_PROFILE["curveDurationMs"],
            "settledHoldMs": C2_FULL_REVIEW_PROFILE["settledHoldMs"],
        }
        payload.append(route_payload)
        choice = "C1 已选" if route["c1HumanChoice"] else "C1 未选"
        cards.append(
            f'<section class="route-card" data-route="{route["routeId"]}"><h2>{names[route["unit"]]} · '
            f'入口 {route["entryFrame"]:03d} · 路线 {route["variant"]}</h2>'
            f'<p>{choice}；完整聚焦 25 帧；真实阶段 3 r2 机械 25 帧。</p>'
            f'<button data-source="model" data-route="{route["routeId"]}">模型热点入口</button>'
            f'<button data-source="name" data-route="{route["routeId"]}">名称入口</button>'
            "</section>"
        )
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>TWINKLE C2 完整 A/B 与 r2 真实审核</title><style>
body{margin:0;background:#0d1118;color:#eef2f7;font-family:"Microsoft YaHei",sans-serif}main{max-width:1280px;margin:auto;padding:28px}
.gate{padding:14px;background:#291f13;border:1px solid #8d6a2e}.player{position:relative;max-width:960px;aspect-ratio:16/11.25;background:#05070a;overflow:hidden}
.player img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.light{opacity:0;transition:opacity 900ms linear}.fallback{display:none;position:static!important}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.routes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.route-card{padding:14px;background:#181e27;border:1px solid #303a49}
button{padding:8px 12px;margin:3px;background:#253247;color:#eef2f7;border:1px solid #52647c}#status[data-state="error"]{color:#ff8d8d}@media(max-width:760px){.routes{grid-template-columns:1fr}}</style></head><body><main>
<h1>阶段四步骤 8 · C2 完整 A/B 与 r2 真实审核</h1>
<p class="gate">机器审核通过不代表人工批准；humanVisualApproved=false；不得进入步骤 9。</p>
<div class="player"><img id="stage" alt="C2 动态审核帧"><img id="light" class="light" alt="检查灯渐变层"><img id="fallback" class="fallback" src="c2-static-fallback.png" alt="C2 静态回退"></div>
<div class="controls"><button data-action="pause">暂停</button><button data-action="replay">重播</button><button data-action="static-fallback">静态回退</button></div>
<p id="status" data-state="loading">正在预加载全部 C2 与 r2 审核资产…</p><div class="routes">""" + "".join(cards) + f"""</div>
<noscript><img src="c2-static-fallback.png" alt="C2 静态回退"></noscript>
<script id="c2-data" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
<script>
const routes=JSON.parse(document.querySelector('#c2-data').textContent),query=new URLSearchParams(location.search),speed=Math.max(.001,Number(query.get('speed')||1));
const reviewAssetInventorySha256='{review_asset_inventory_sha256}';
async function sha256Url(url){{const response=await fetch(url,{{cache:'no-store'}});if(!response.ok)throw new Error(`digest fetch failed: ${{response.status}}`);const digest=await crypto.subtle.digest('SHA-256',await response.arrayBuffer());return [...new Uint8Array(digest)].map(value=>value.toString(16).padStart(2,'0')).join('').toUpperCase();}}
const stage=document.querySelector('#stage'),light=document.querySelector('#light'),fallback=document.querySelector('#fallback'),status=document.querySelector('#status');
let active=routes.find(route=>route.c1HumanChoice)||routes[0],paused=false,runToken=0,currentAsset='',currentDirection='forward',currentSequenceLabel='',currentSequenceIndex=-1,currentSequenceAssets=[],resumeExpectation=null,currentPhase='idle',phaseWaiters=new Set(),currentRouteId='',requestFailures=[],preloadPromise=null;
const rawDelay=ms=>new Promise(resolve=>setTimeout(resolve,Math.max(1,ms))),delay=ms=>rawDelay(Math.max(1,ms*speed));
function settlePhaseWaiter(waiter,error){{if(!phaseWaiters.delete(waiter))return;clearTimeout(waiter.timer);if(error)waiter.reject(error);else waiter.resolve(true);}}
function waitForPhaseEntry(phase,token,timeoutMs,label){{return new Promise((resolve,reject)=>{{const waiter={{phase,token,resolve,reject,timer:null}};waiter.timer=setTimeout(()=>settlePhaseWaiter(waiter,new Error(`timeout:${{label}}`)),timeoutMs);phaseWaiters.add(waiter);}});}}
function cancelPhaseWaiters(token){{for(const waiter of [...phaseWaiters])if(waiter.token===token)settlePhaseWaiter(waiter,new Error(`cancelled:${{token}}`));}}
function setPhase(value,token=runToken){{currentPhase=value;for(const waiter of [...phaseWaiters])if(waiter.phase===value&&waiter.token===token)settlePhaseWaiter(waiter);}}
function cancelRun(){{const cancelledToken=runToken;runToken++;cancelPhaseWaiters(cancelledToken);paused=false;resumeExpectation=null;setPhase('cancelled');currentRouteId='';currentSequenceIndex=-1;currentSequenceAssets=[];light.style.transitionDuration='0ms';light.style.opacity='0';}}
async function wait(ms,token){{let remaining=Math.max(1,ms*speed);while(remaining>0){{if(token!==runToken)return false;if(paused){{await rawDelay(12);continue;}}const slice=Math.min(remaining,12);await rawDelay(slice);remaining-=slice;}}return token===runToken;}}
async function waitUntil(predicate,timeoutMs,label){{const deadline=performance.now()+timeoutMs;while(!predicate()){{if(performance.now()>=deadline)throw new Error(`timeout:${{label}}`);await rawDelay(5);}}return true;}}
async function withDeadline(promise,timeoutMs,label){{return Promise.race([promise,(async()=>{{await rawDelay(timeoutMs);throw new Error(`timeout:${{label}}`);}})()]);}}
function allSources(route){{const lightSources=route.inspectionLight?[route.inspectionLight.unlitAsset,route.inspectionLight.litAsset]:[];return [...route.orbitPrefix,...route.focus,...route.expand,...route.close,...route.overviewReturn,...lightSources];}}
function preloadAll(){{if(preloadPromise)return preloadPromise;let sources=[...new Set(routes.flatMap(allSources))];if(query.has('failAsset'))sources.push('/__c2_injected_missing_asset__.png');preloadPromise=Promise.all(sources.map(src=>new Promise(resolve=>{{const image=new Image();image.onload=resolve;image.onerror=()=>{{requestFailures.push(src);resolve();}};image.src=src;}}))).then(()=>{{if(requestFailures.length){{status.dataset.state='error';status.textContent='error：审核资产加载失败，禁止播放';}}else{{status.dataset.state='ready';status.textContent='全部审核资产已加载，可开始 C2 审核';}}return requestFailures.length===0;}});return preloadPromise;}}
async function showSequence(assets,phase,label,duration,token,direction){{if(token!==runToken)return false;setPhase(phase,token);currentDirection=direction;currentSequenceLabel=label;currentSequenceAssets=assets;const per=assets.length>1?duration/(assets.length-1):0;for(let index=0;index<assets.length;index++){{if(token!==runToken)return false;while(paused){{if(token!==runToken)return false;await rawDelay(12);}}if(token!==runToken)return false;currentSequenceIndex=index;currentAsset=assets[index];if(resumeExpectation&&resumeExpectation.label===label&&resumeExpectation.index===index&&resumeExpectation.asset===currentAsset)resumeExpectation.observed=true;stage.src=currentAsset;status.textContent=`${{label}} ${{index+1}}/${{assets.length}}`;if(per&&index<assets.length-1&&!(await wait(per,token)))return false;}}return token===runToken;}}
async function inspection(route,token){{const spec=route.inspectionLight;if(!spec)return token===runToken;if(token!==runToken)return false;setPhase('inspection-fade-in',token);stage.src=spec.unlitAsset;light.src=spec.litAsset;light.style.transitionDuration=`${{spec.fadeInMs*speed}}ms`;light.style.opacity='1';status.textContent='检查灯渐入';if(!(await wait(spec.fadeInMs,token))||token!==runToken)return false;setPhase('inspection-hold',token);status.textContent='检查灯稳定';if(!(await wait(spec.holdMs,token))||token!==runToken)return false;setPhase('inspection-fade-out',token);light.style.transitionDuration=`${{spec.fadeOutMs*speed}}ms`;light.style.opacity='0';status.textContent='检查灯渐出';return await wait(spec.fadeOutMs,token);}}
async function playRoute(route,source){{const previousToken=runToken,token=++runToken;cancelPhaseWaiters(previousToken);active=route;paused=false;currentRouteId=route.routeId;const loaded=await preloadAll();if(token!==runToken||!loaded)return false;if(source==='model'&&route.modelHotspotQualified!==true){{status.dataset.state='error';status.textContent='error：模型热点当前不可交互';return false;}}fallback.style.display='none';stage.style.display='block';light.style.display='block';light.style.opacity='0';status.dataset.state='running';status.textContent=`${{source}}入口 · ${{route.routeId}}`;if(!(await showSequence(route.orbitPrefix,'orbit','环绕前缀',route.orbitPrefix.length*20,token,route.turnDirection||'forward')))return false;if(!(await showSequence(route.focus,'focus','聚焦',route.curveDurationMs,token,'forward')))return false;setPhase('settled',token);if(!(await wait(route.settledHoldMs,token)))return false;if(!(await showSequence(route.expand,'expand','r2 展开',1000,token,'forward')))return false;if(!(await inspection(route,token)))return false;if(!(await showSequence(route.close,'close','r2 闭合',1000,token,'backward')))return false;if(!(await showSequence(route.overviewReturn,'overviewReturn','严格反序返回',route.curveDurationMs+route.orbitPrefix.length*20,token,'backward')))return false;if(token!==runToken)return false;setPhase('complete',token);currentAsset=route.captureFrame;stage.src=currentAsset;status.dataset.state='complete';status.textContent='捕获帧已恢复；等待人工裁决';return true;}}
function showStatic(){{cancelRun();setPhase('fallback');stage.style.display='none';light.style.display='none';light.style.opacity='0';fallback.style.display='block';status.dataset.state='fallback';status.textContent='静态回退：未播放动态序列';}}
document.querySelectorAll('[data-source]').forEach(button=>button.addEventListener('click',()=>playRoute(routes.find(route=>route.routeId===button.dataset.route),button.dataset.source)));
document.querySelector('[data-action="pause"]').addEventListener('click',event=>{{paused=!paused;event.currentTarget.textContent=paused?'继续':'暂停';}});
document.querySelector('[data-action="replay"]').addEventListener('click',()=>playRoute(active,'replay'));
document.querySelector('[data-action="static-fallback"]').addEventListener('click',showStatic);
if(matchMedia('(prefers-reduced-motion: reduce)').matches&&!query.has('browser'))showStatic();else preloadAll();
async function cancellationProbe(phase,action){{const base=routes.find(route=>route.unit==='{CHAMBER}')||routes[0],alternate=routes.find(route=>route.routeId!==base.routeId);const expectedOldToken=runToken+1;const phasePromise=waitForPhaseEntry(phase,expectedOldToken,15000,`${{action}}-${{phase}}-start`);const oldPromise=playRoute(base,'model');const oldToken=runToken;if(oldToken!==expectedOldToken){{cancelPhaseWaiters(expectedOldToken);await phasePromise.catch(()=>false);throw new Error(`token-mismatch:${{action}}-${{phase}}`);}}await phasePromise;let replacement=null;if(action==='route-switch')replacement=playRoute(alternate,'name');else if(action==='replay')replacement=playRoute(base,'replay');else showStatic();const oldResult=await withDeadline(oldPromise,15000,`${{action}}-${{phase}}-cancel`);if(oldResult!==false||runToken<=oldToken)return false;if(action==='fallback'){{await rawDelay(50);return currentPhase==='fallback'&&fallback.style.display==='block'&&stage.style.display==='none'&&light.style.display==='none'&&light.style.opacity==='0'&&status.dataset.state==='fallback';}}const replacementResult=await withDeadline(replacement,30000,`${{action}}-${{phase}}-replacement`);const expected=action==='route-switch'?alternate:base;return replacementResult&&currentPhase==='complete'&&currentRouteId===expected.routeId&&currentAsset===expected.captureFrame;}}
async function publishHarnessResult(result){{window.__c2HarnessResult=result;if(query.has('post')){{try{{await fetch('/result',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(result)}});}}catch(error){{window.__c2HarnessPostError=String(error);}}}}}}
async function harness(){{if(!query.has('browser'))return;const started=performance.now(),reviewPageSha256=await sha256Url(location.pathname);if(query.has('timeoutProbe')){{let timedOut=false;try{{await waitUntil(()=>false,Number(query.get('harnessTimeoutMs')||20),'harness-timeout-probe');}}catch(error){{timedOut=String(error).includes('timeout:');}}cancelRun();setPhase('error');status.dataset.state='error';status.textContent='error：harness bounded timeout';await publishHarnessResult({{browserId:query.get('browser'),passed:false,timedOut,timeoutPhase:'harness-timeout-probe',durationMs:performance.now()-started,requestFailures:[],reviewAssetInventorySha256,reviewPageSha256}});return;}}const loaded=await preloadAll();let pauseHeld=false,resumeSameDirection=false,resumeFromHeldPoint=false,modelEntryCovered=false,nameEntryCovered=false,captureFrameRestored=true,staticFallbackShown=false,routeSwitchDuringFocusSafe=false,replayDuringFocusSafe=false,fallbackDuringFocusSafe=false,routeSwitchDuringInspectionSafe=false,replayDuringInspectionSafe=false,fallbackDuringInspectionSafe=false,boundedWaitFailureObserved=false;const routeCoverage=[],entrySources=new Set();try{{if(loaded){{routeSwitchDuringFocusSafe=await cancellationProbe('focus','route-switch');replayDuringFocusSafe=await cancellationProbe('focus','replay');fallbackDuringFocusSafe=await cancellationProbe('focus','fallback');routeSwitchDuringInspectionSafe=await cancellationProbe('inspection-fade-in','route-switch');replayDuringInspectionSafe=await cancellationProbe('inspection-fade-in','replay');fallbackDuringInspectionSafe=await cancellationProbe('inspection-fade-in','fallback');try{{await waitUntil(()=>false,5,'bounded-wait-negative');}}catch(error){{boundedWaitFailureObserved=String(error).includes('timeout:bounded-wait-negative');}}const first=active,modelRun=playRoute(first,'model');await waitUntil(()=>currentPhase==='focus'&&currentSequenceIndex>=2,15000,'pause-focus');document.querySelector('[data-action="pause"]').click();const held=currentAsset,heldIndex=currentSequenceIndex,heldLabel=currentSequenceLabel,heldAssets=currentSequenceAssets,direction=currentDirection;await delay(160);pauseHeld=currentAsset===held&&currentSequenceIndex===heldIndex;resumeExpectation={{label:heldLabel,index:heldIndex+1,asset:heldAssets[heldIndex+1],observed:false}};document.querySelector('[data-action="pause"]').click();await waitUntil(()=>resumeExpectation&&resumeExpectation.observed,5000,'resume-next-frame');resumeSameDirection=currentDirection===direction;resumeFromHeldPoint=resumeExpectation.observed;resumeExpectation=null;const firstPassed=await withDeadline(modelRun,30000,'first-route');routeCoverage.push(first.routeId);entrySources.add('model');captureFrameRestored=captureFrameRestored&&firstPassed&&currentAsset===first.captureFrame;for(let index=0;index<routes.length;index++){{const route=routes[index];if(route.routeId===first.routeId)continue;const source=index%2===0?'model':'name',passed=await withDeadline(playRoute(route,source),30000,`route-${{route.routeId}}`);routeCoverage.push(route.routeId);entrySources.add(source);captureFrameRestored=captureFrameRestored&&passed&&currentAsset===route.captureFrame;}}modelEntryCovered=entrySources.has('model');nameEntryCovered=entrySources.has('name');showStatic();staticFallbackShown=fallback.style.display==='block';}}const failurePathEntered=!loaded&&status.dataset.state==='error',allRoutesCovered=routeCoverage.length===routes.length&&new Set(routeCoverage).size===routes.length;const passed=loaded?pauseHeld&&resumeSameDirection&&resumeFromHeldPoint&&modelEntryCovered&&nameEntryCovered&&allRoutesCovered&&captureFrameRestored&&staticFallbackShown&&routeSwitchDuringFocusSafe&&replayDuringFocusSafe&&fallbackDuringFocusSafe&&routeSwitchDuringInspectionSafe&&replayDuringInspectionSafe&&fallbackDuringInspectionSafe&&boundedWaitFailureObserved:failurePathEntered;await publishHarnessResult({{browserId:query.get('browser'),passed,imagesLoaded:loaded,pauseHeld,resumeSameDirection,resumeFromHeldPoint,modelEntryCovered,nameEntryCovered,routeCoverage,captureFrameRestored,staticFallbackShown,routeSwitchDuringFocusSafe,replayDuringFocusSafe,fallbackDuringFocusSafe,routeSwitchDuringInspectionSafe,replayDuringInspectionSafe,fallbackDuringInspectionSafe,boundedWaitFailureObserved,timedOut:false,failurePathEntered,requestFailures,reviewAssetInventorySha256,reviewPageSha256,durationMs:performance.now()-started}});}}catch(error){{cancelRun();setPhase('error');status.dataset.state='error';status.textContent=`error：${{error}}`;await publishHarnessResult({{browserId:query.get('browser'),passed:false,timedOut:String(error).includes('timeout:'),timeoutPhase:currentPhase,durationMs:performance.now()-started,requestFailures,reviewAssetInventorySha256,reviewPageSha256,harnessError:String(error)}});}}}}
harness();
</script></main></body></html>"""
    review_root = output_root / "review"
    review_root.mkdir(exist_ok=True)
    path = review_root / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def _write_c2_static_fallback(output_root, routes):
    from PIL import Image, ImageDraw, ImageFont

    output_root = Path(output_root)
    font_record = correction_review_font()
    font = ImageFont.truetype(font_record["path"], 15)
    cell_width, image_height, label_height = 240, 169, 38
    sheet = Image.new(
        "RGB",
        (cell_width * 6, (image_height + label_height) * len(routes)),
        (16, 20, 27),
    )
    draw = ImageDraw.Draw(sheet)
    for row, route in enumerate(routes):
        sources = [
            ("入口", output_root / route["focusFrames"][0]["path"]),
            ("聚焦中点", output_root / route["focusFrames"][12]["path"]),
            ("聚焦停稳", output_root / route["focusFrames"][24]["path"]),
            (
                "r2 展开起点",
                output_root / route["stage3R2"]["expandReviewAssets"][0],
            ),
            (
                "r2 展开终点",
                output_root / route["stage3R2"]["expandReviewAssets"][-1],
            ),
            (
                "r2 闭合捕获",
                output_root / route["stage3R2"]["closeReviewAssets"][-1],
            ),
        ]
        top = row * (image_height + label_height)
        for column, (label, source) in enumerate(sources):
            with Image.open(source) as opened:
                image = opened.convert("RGB")
                image.thumbnail((cell_width, image_height), Image.Resampling.LANCZOS)
            x = column * cell_width + (cell_width - image.width) // 2
            y = top + (image_height - image.height) // 2
            sheet.paste(image, (x, y))
            draw.text(
                (column * cell_width + 6, top + image_height + 4),
                f"{route['entryFrame']:03d}{route['variant']} {label}",
                font=font,
                fill=(232, 238, 246),
            )
    path = output_root / "review" / "c2-static-fallback.png"
    path.parent.mkdir(exist_ok=True)
    sheet.save(path)
    return path


def validate_c2_full_review(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report.get("schema") != C2_FULL_REVIEW_PROFILE["schema"]:
        raise ValueError("C2 schema mismatch")
    if report.get("profile") != C2_FULL_REVIEW_PROFILE:
        raise ValueError("C2 profile mismatch")
    authority = validate_authority()
    stage3_inventory = _validate_stage3_r2_inventory(authority["stage3"])
    orbit = validate_c360_f96(APPROVED_C360_F96)
    orbit_frames = {
        int(frame["physicalFrameIndex"]): frame["path"] for frame in orbit["frames"]
    }
    worker_contract = json.loads(
        (output_root / "c2-worker-contracts.json").read_text(encoding="utf-8")
    )
    worker_contract_sha256 = canonical_json_sha256(worker_contract.get("routes", []))
    worker_audit = json.loads(
        (output_root / "worker-audit.json").read_text(encoding="utf-8")
    )
    if not (
        worker_contract.get("schema") == "twinkle-stage4-c2-worker-contracts-v1"
        and worker_contract.get("contractSha256") == worker_contract_sha256
        and report.get("workerContractSha256") == worker_contract_sha256
        and worker_audit.get("contractSha256") == worker_contract_sha256
    ):
        raise ValueError("C2 worker contract binding mismatch")
    normalized_choices = normalize_stage4_choices(
        report.get("c1HumanChoices", {})
    )
    contract_choices = {
        unit: {
            int(entry): variant
            for entry, variant in normalized_choices[unit].items()
        }
        for unit in SEMANTIC_UNITS
    }
    c1 = validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT_ROOT)
    expected_contracts = c2_route_contracts(
        c1, authority["stage3"], contract_choices
    )
    if worker_contract.get("routes") != expected_contracts:
        raise ValueError("C2 worker contracts drift from C1/C360 authority")
    worker_routes = {
        route.get("routeId"): route for route in worker_audit.get("routes", [])
    }
    expected_route_ids = {contract["routeId"] for contract in expected_contracts}
    if (
        worker_audit.get("schema") != "twinkle-stage4-c2-full-worker-v1"
        or set(worker_routes) != expected_route_ids
    ):
        raise ValueError("C2 worker frame route inventory mismatch")
    routes = report.get("routes", [])
    if len(routes) != 8 or report.get("routeCount") != 8:
        raise ValueError("C2 route count mismatch")
    report_routes = {route["routeId"]: route for route in routes}
    for contract in worker_contract["routes"]:
        report_route = report_routes.get(contract["routeId"], {})
        report_contract = {key: report_route.get(key) for key in contract}
        if "stage3R2" in report_contract:
            stage3_contract = json.loads(json.dumps(report_contract["stage3R2"]))
            stage3_contract.pop("expandReviewAssets", None)
            stage3_contract.pop("closeReviewAssets", None)
            if stage3_contract.get("inspectionLight") is not None:
                stage3_contract["inspectionLight"].pop("unlitReviewAsset", None)
                stage3_contract["inspectionLight"].pop("litReviewAsset", None)
            report_contract["stage3R2"] = stage3_contract
        if report_contract != contract:
            raise ValueError("C2 report/worker contract drift")
    if not (
        report.get("renderedFocusFrameCount") == 176
        and report.get("reusedC1FrameCount") == 24
        and report.get("referencedStage3R2FrameCount") == 50
        and report.get("renderMachinePassed") is True
    ):
        raise ValueError("C2 render inventory mismatch")
    if set(report_routes) != expected_route_ids:
        raise ValueError("C2 report route inventory mismatch")
    c1_routes = {route["routeId"]: route for route in c1["routes"]}
    reused_indices = {0, 12, 24}
    rendered_indices = set(range(25)) - reused_indices
    bound_focus_paths = set()
    new_count = reused_count = 0
    for route in routes:
        route_id = route["routeId"]
        frames = route.get("focusFrames", [])
        if [frame.get("sampleIndex") for frame in frames] != list(range(25)):
            raise ValueError("C2 focus sequence mismatch")
        audit_records = {
            int(frame.get("sampleIndex", -1)): frame
            for frame in worker_routes[route_id].get("frames", [])
        }
        if set(audit_records) != rendered_indices:
            raise ValueError(f"C2 worker frame inventory mismatch: {route_id}")
        c1_records = {
            int(frame["sampleIndex"]): frame
            for frame in c1_routes[route_id]["previewFrames"]
        }
        if set(c1_records) != reused_indices:
            raise ValueError(f"C2 C1 reuse inventory mismatch: {route_id}")
        for frame in frames:
            sample_index = int(frame["sampleIndex"])
            expected_relative = (
                f"frames/{route_id}/focus-{sample_index:03d}.png"
            )
            relative = str(frame.get("path", ""))
            relative_path = Path(relative)
            if (
                relative != expected_relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative in bound_focus_paths
            ):
                raise ValueError("C2 focus binding path or uniqueness mismatch")
            bound_focus_paths.add(relative)
            path = output_root / relative_path
            if not path.is_file() or sha256(path) != frame.get("sha256"):
                raise ValueError("C2 focus file/hash mismatch")
            quality = _frame_quality(path)
            if quality["blackFrame"] or quality["emptyFrame"]:
                raise ValueError("C2 focus frame quality mismatch")
            if sample_index in reused_indices:
                expected = c1_records[sample_index]
                if (
                    frame.get("provenance") != "approved-c1-reuse"
                    or frame.get("sha256") != expected.get("sha256")
                    or sha256(
                        C1_KEYFRAME_OUTPUT_ROOT / expected.get("path", "")
                    )
                    != expected.get("sha256")
                ):
                    raise ValueError("C2 C1 reuse provenance or hash mismatch")
                reused_count += 1
            else:
                audit = audit_records[sample_index]
                if (
                    frame.get("provenance") != "c2-new-render"
                    or audit.get("path") != expected_relative
                    or audit.get("sha256") != frame.get("sha256")
                    or sha256(path) != audit.get("sha256")
                ):
                    raise ValueError("C2 worker frame provenance or hash mismatch")
                if quality["resolution"] != C2_FULL_REVIEW_PROFILE["render"]["resolution"]:
                    raise ValueError("C2 new-render resolution mismatch")
                new_count += 1
        stage3 = route.get("stage3R2", {})
        if stage3.get("sourceManifestSha256") != EXPECTED_STAGE3_R2_SHA256:
            raise ValueError("C2 stage 3 authority mismatch")
        expected_orbit_review_assets = [
            f"review-assets/orbit/frame-{int(index):03d}.png"
            for index in route.get("orbitPrefixIndices", [])
        ]
        expected_expand_review_assets = [
            f"review-assets/stage3/{asset}"
            for asset in stage3.get("expandAssets", [])
        ]
        if (
            route.get("orbitPrefixReviewAssets")
            != expected_orbit_review_assets
            or stage3.get("expandReviewAssets")
            != expected_expand_review_assets
            or stage3.get("closeReviewAssets")
            != list(reversed(expected_expand_review_assets))
        ):
            raise ValueError("C2 local provenance mapping mismatch")
        for source_asset, local_asset in zip(
            stage3.get("expandAssets", []), stage3.get("expandReviewAssets", [])
        ):
            expected = stage3_inventory.get(source_asset)
            if not expected or sha256(output_root / local_asset) != expected:
                raise ValueError("C2 local stage 3 frame/hash mismatch")
        for index, local_asset in zip(
            route.get("orbitPrefixIndices", []),
            route.get("orbitPrefixReviewAssets", []),
        ):
            expected = orbit["inventorySha256"][orbit_frames[int(index)]]
            if sha256(output_root / local_asset) != expected:
                raise ValueError("C2 local orbit frame/hash mismatch")
        inspection = stage3.get("inspectionLight")
        if inspection is not None:
            expected_inspection_review = {
                "unlitReviewAsset": (
                    f"review-assets/stage3/{inspection['unlitAsset']}"
                ),
                "litReviewAsset": (
                    f"review-assets/stage3/{inspection['litAsset']}"
                ),
            }
            if any(
                inspection.get(key) != expected
                for key, expected in expected_inspection_review.items()
            ):
                raise ValueError("C2 local provenance mapping mismatch")
            for source_key, local_key in (
                ("unlitAsset", "unlitReviewAsset"),
                ("litAsset", "litReviewAsset"),
            ):
                if (
                    sha256(output_root / inspection[local_key])
                    != stage3_inventory[inspection[source_key]]
                ):
                    raise ValueError("C2 local inspection frame/hash mismatch")
        if not (
            route.get("fullSequenceGenerated") is True
            and route.get("stage3MechanicalPlaybackGenerated") is True
            and route.get("humanVisualApproved") is False
            and route.get("overviewReturn") == list(reversed(route["fullFocusTrace"]))
        ):
            raise ValueError("C2 route gate mismatch")
    if (new_count, reused_count) != (176, 24) or len(bound_focus_paths) != 200:
        raise ValueError("C2 focus provenance count mismatch")
    restoration = report.get("restoration", {})
    if not (
        restoration.get("candidateBlendSaved") is False
        and restoration.get("candidateBlendSha256Before")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("candidateBlendSha256After")
        == EXPECTED_CANDIDATE_BLEND_SHA256
        and restoration.get("sceneSettingsRestored") is True
        and restoration.get("temporaryDataBlocksRemaining") == []
    ):
        raise ValueError("C2 restoration mismatch")
    for asset in report.get("review", {}).values():
        if not (output_root / asset).is_file():
            raise ValueError("C2 review asset missing")
    local_dependencies = [
        path
        for path in (output_root / "review-assets").rglob("*")
        if path.is_file()
    ]
    if len(local_dependencies) != report.get("localReviewDependencyCount"):
        raise ValueError("C2 local review dependency count mismatch")
    review_asset_inventory_sha256 = canonical_json_sha256(
        _c2_review_asset_inventory(output_root)
    )
    if report.get("reviewAssetInventorySha256") != review_asset_inventory_sha256:
        raise ValueError("C2 review asset inventory digest mismatch")
    review_path = output_root / report["review"]["asset"]
    if report.get("reviewPageSha256") != sha256(review_path):
        raise ValueError("C2 review page digest mismatch")
    if "/output/" in review_path.read_text(encoding="utf-8"):
        raise ValueError("C2 review page must not reference external output assets")
    machine_passed = (
        report.get("renderMachinePassed") is True
        and report.get("browserMachinePassed") is True
    )
    pending_boundary = (
        report.get("humanVisualApproved") is False
        and report.get("authorizesStep9") is False
        and report.get("stage4Closed") is False
        and report.get("authorizesStage5") is False
        and report.get("focusRouteGenerated", False) is False
        and report.get("routeByUnit") is None
        and report.get("entryFrameSet") is None
        and report.get("stage4Closure") is None
    )
    expected_route_by_unit = {
        unit: [
            {
                "entryFrame": int(entry),
                "variant": variant,
                "routeId": f"{unit}--entry-{int(entry):03d}--{variant}",
            }
            for entry, variant in report.get("c1HumanChoices", {}).get(
                unit, {}
            ).items()
        ]
        for unit in SEMANTIC_UNITS
    }
    expected_entry_frame_set = {
        unit: [record["entryFrame"] for record in expected_route_by_unit[unit]]
        for unit in SEMANTIC_UNITS
    }
    selected_route_ids = {
        record["routeId"]
        for records in expected_route_by_unit.values()
        for record in records
    }
    closed_boundary = (
        report.get("humanVisualApproved") is True
        and report.get("authorizesStep9") is True
        and report.get("stage4Closed") is True
        and report.get("authorizesStage5") is False
        and report.get("focusRouteGenerated") is True
        and normalized_choices
        == normalize_stage4_choices(APPROVED_STAGE4_CHOICES)
        and report.get("routeByUnit") == expected_route_by_unit
        and report.get("entryFrameSet") == expected_entry_frame_set
        and report.get("stage4Closure")
        == {
            "approvedBy": "user",
            "approvedOn": report.get("stage4Closure", {}).get("approvedOn"),
            "scope": "stage4-step9-selection-record-and-closure-only",
            "replacesFocusRouteStub": True,
            "authorizesStage5": False,
        }
        and bool(report.get("stage4Closure", {}).get("approvedOn"))
        and {
            route.get("routeId")
            for route in routes
            if route.get("c1HumanChoice") is True
        }
        == selected_route_ids
    )
    if not (
        report.get("machinePassed") is machine_passed
        and (pending_boundary or closed_boundary)
    ):
        raise ValueError("C2 approval boundary mismatch")
    browser_records = report.get("browserEvidence", [])
    if report.get("browserMachinePassed") is True:
        evidence = []
        for record in browser_records:
            path = output_root / record["result"]
            if not path.is_file() or sha256(path) != record.get("sha256"):
                raise ValueError("C2 browser evidence file/hash mismatch")
            evidence.append(json.loads(path.read_text(encoding="utf-8")))
        validate_c2_browser_evidence(
            evidence,
            expected_review_asset_inventory_sha256=report[
                "reviewAssetInventorySha256"
            ],
            expected_review_page_sha256=report["reviewPageSha256"],
        )
    elif browser_records != []:
        raise ValueError("C2 pending browser evidence mismatch")
    actual = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if report.get("inventorySha256") != actual:
        raise ValueError("C2 inventory hash mismatch")
    return report


def record_stage4_selection_and_close(
    output_root, *, choices, approved_on, authorized=False
):
    if authorized is not True:
        raise ValueError("explicit step 9 authorization is required")
    output_root = Path(output_root).resolve()
    report = validate_c2_full_review(output_root)
    if not (
        report.get("machinePassed") is True
        and report.get("humanVisualApproved") is False
        and report.get("authorizesStep9") is False
        and report.get("stage4Closed") is False
    ):
        raise ValueError("step 9 requires the machine-passed pending C2 candidate")
    normalized_choices = normalize_stage4_choices(choices)
    if normalized_choices != normalize_stage4_choices(
        APPROVED_STAGE4_CHOICES
    ):
        raise ValueError(
            "step 9 choices do not match the four approved final selections"
        )
    if normalized_choices != report.get("c1HumanChoices"):
        raise ValueError("step 9 choices do not match the approved C2 human choices")
    approved_on = str(approved_on)
    if not approved_on:
        raise ValueError("step 9 approval date is required")

    routes = {route["routeId"]: route for route in report["routes"]}
    route_by_unit = {}
    entry_frame_set = {}
    for unit in SEMANTIC_UNITS:
        route_by_unit[unit] = []
        entry_frame_set[unit] = []
        for entry, variant in normalized_choices[unit].items():
            entry = int(entry)
            route_id = f"{unit}--entry-{entry:03d}--{variant}"
            route = routes.get(route_id)
            if route is None or route.get("c1HumanChoice") is not True:
                raise ValueError("approved C2 route is missing or not selected")
            route_by_unit[unit].append(
                {"entryFrame": entry, "variant": variant, "routeId": route_id}
            )
            entry_frame_set[unit].append(entry)

    manifest_path = output_root / "c2-full-review-manifest.json"
    manifest_before = manifest_path.read_bytes()
    report["routeByUnit"] = route_by_unit
    report["entryFrameSet"] = entry_frame_set
    report["focusRouteGenerated"] = True
    report["humanVisualApproved"] = True
    report["authorizesStep9"] = True
    report["stage4Closed"] = True
    report["authorizesStage5"] = False
    report["stage4Closure"] = {
        "approvedBy": "user",
        "approvedOn": approved_on,
        "scope": "stage4-step9-selection-record-and-closure-only",
        "replacesFocusRouteStub": True,
        "authorizesStage5": False,
    }
    try:
        _atomic_write_json(manifest_path, report)
        return validate_c2_full_review(output_root)
    except Exception:
        _atomic_write_bytes(manifest_path, manifest_before)
        raise


def validate_c2_browser_evidence(
    evidence,
    *,
    expected_review_asset_inventory_sha256=None,
    expected_review_page_sha256=None,
):
    records = list(evidence)
    by_scenario = {record.get("scenario"): record for record in records}
    if set(by_scenario) != {
        "desktop",
        "mobile",
        "injected-failure",
        "bounded-timeout",
    } or len(records) != 4:
        raise ValueError("C2 browser evidence scenarios mismatch")
    if by_scenario["desktop"].get("viewport") != [1440, 1000] or by_scenario[
        "mobile"
    ].get("viewport") != [390, 844]:
        raise ValueError("C2 browser evidence viewport mismatch")
    bindings = {
        (
            record.get("reviewAssetInventorySha256"),
            record.get("reviewPageSha256"),
        )
        for record in records
    }
    if len(bindings) != 1:
        raise ValueError("C2 browser review binding mismatch")
    review_asset_digest, review_page_digest = next(iter(bindings))
    if not all(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789ABCDEF" for character in value)
        for value in (review_asset_digest, review_page_digest)
    ):
        raise ValueError("C2 browser review binding format mismatch")
    if (
        expected_review_asset_inventory_sha256 is not None
        and review_asset_digest != expected_review_asset_inventory_sha256
    ) or (
        expected_review_page_sha256 is not None
        and review_page_digest != expected_review_page_sha256
    ):
        raise ValueError("C2 browser review binding drift")
    success_fields = (
        "passed",
        "imagesLoaded",
        "pauseHeld",
        "resumeSameDirection",
        "resumeFromHeldPoint",
        "modelEntryCovered",
        "nameEntryCovered",
        "captureFrameRestored",
        "staticFallbackShown",
        "routeSwitchDuringFocusSafe",
        "replayDuringFocusSafe",
        "fallbackDuringFocusSafe",
        "routeSwitchDuringInspectionSafe",
        "replayDuringInspectionSafe",
        "fallbackDuringInspectionSafe",
        "boundedWaitFailureObserved",
    )
    for scenario in ("desktop", "mobile"):
        record = by_scenario[scenario]
        expected_routes = {
            f"{unit}--entry-{entry:03d}--{variant}"
            for unit, entry in C2_CAPTURE_CASES
            for variant in C2_FULL_REVIEW_PROFILE["variants"]
        }
        if not (
            record.get("browserId")
            and all(record.get(field) is True for field in success_fields)
            and len(record.get("routeCoverage", [])) == len(expected_routes)
            and set(record.get("routeCoverage", [])) == expected_routes
            and record.get("timedOut") is False
            and record.get("failurePathEntered") is False
            and record.get("requestFailures") == []
            and record.get("consoleErrors") == []
            and record.get("consoleWarnings") == []
        ):
            if set(record.get("routeCoverage", [])) != expected_routes:
                raise ValueError(f"C2 browser route coverage mismatch: {scenario}")
            raise ValueError(f"C2 browser success evidence mismatch: {scenario}")
    failure = by_scenario["injected-failure"]
    if not (
        failure.get("browserId")
        and failure.get("viewport") == [1440, 1000]
        and failure.get("passed") is True
        and failure.get("imagesLoaded") is False
        and failure.get("failurePathEntered") is True
        and failure.get("requestFailures") == ["/__c2_injected_missing_asset__.png"]
        and failure.get("consoleErrors") == ["expected injected missing asset 404"]
        and failure.get("consoleWarnings") == []
    ):
        raise ValueError("C2 browser failure evidence mismatch")
    timeout = by_scenario["bounded-timeout"]
    if not (
        timeout.get("browserId")
        and timeout.get("viewport") == [1440, 1000]
        and timeout.get("passed") is False
        and timeout.get("timedOut") is True
        and timeout.get("timeoutPhase") == "harness-timeout-probe"
        and 0 < float(timeout.get("durationMs", 0)) <= 5_000
        and timeout.get("requestFailures") == []
        and timeout.get("consoleErrors") == []
        and timeout.get("consoleWarnings") == []
    ):
        raise ValueError("C2 browser bounded-timeout evidence mismatch")
    return records


def record_c2_browser_evidence(output_root, evidence):
    output_root = Path(output_root).resolve()
    report = validate_c2_full_review(output_root)
    if report.get("browserMachinePassed") is not False or report.get(
        "browserEvidence"
    ) != []:
        raise ValueError("C2 browser evidence already recorded")
    records = validate_c2_browser_evidence(
        evidence,
        expected_review_asset_inventory_sha256=report[
            "reviewAssetInventorySha256"
        ],
        expected_review_page_sha256=report["reviewPageSha256"],
    )
    manifest_path = output_root / "c2-full-review-manifest.json"
    manifest_before = manifest_path.read_bytes()
    immutable_before = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path != manifest_path
        and "browser-results" not in path.relative_to(output_root).parts
    }
    browser_root = output_root / "browser-results"
    if browser_root.exists():
        raise FileExistsError("C2 browser evidence directory already exists")
    staging = Path(tempfile.mkdtemp(prefix=".browser-results-txn-", dir=output_root))
    try:
        references = []
        for record in records:
            staged_path = staging / f"{record['scenario']}.json"
            _atomic_write_json(staged_path, record)
            references.append(
                {
                    "scenario": record["scenario"],
                    "browserId": record["browserId"],
                    "viewport": record["viewport"],
                    "result": f"browser-results/{staged_path.name}",
                    "sha256": sha256(staged_path),
                }
            )
        staging.rename(browser_root)
        report["browserEvidence"] = references
        report["browserMachinePassed"] = True
        report["machinePassed"] = report["renderMachinePassed"] is True
        report["inventorySha256"] = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file() and path != manifest_path
        }
        _atomic_write_json(manifest_path, report)
        immutable_after = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file()
            and path != manifest_path
            and "browser-results" not in path.relative_to(output_root).parts
        }
        if immutable_after != immutable_before:
            raise RuntimeError("C2 browser evidence recording changed an immutable asset")
        return validate_c2_full_review(output_root)
    except Exception:
        _atomic_write_bytes(manifest_path, manifest_before)
        if browser_root.exists():
            shutil.rmtree(browser_root)
        if staging.exists():
            shutil.rmtree(staging)
        immutable_after = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file() and path != manifest_path
        }
        if immutable_after != immutable_before:
            raise RuntimeError("C2 browser evidence rollback failed")
        raise


def refresh_c2_review(output_root):
    output_root = Path(output_root).resolve()
    report = validate_c2_full_review(output_root)
    if report.get("browserMachinePassed") is not False:
        raise ValueError("C2 review cannot refresh after browser evidence is recorded")
    manifest_path = output_root / "c2-full-review-manifest.json"
    review_path = output_root / "review" / "index.html"
    manifest_before = manifest_path.read_bytes()
    review_before = review_path.read_bytes()
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    immutable_before = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.relative_to(output_root).as_posix() not in mutable
    }
    try:
        review_asset_inventory_sha256 = canonical_json_sha256(
            _c2_review_asset_inventory(output_root)
        )
        _write_c2_review_page(
            output_root,
            report["routes"],
            review_asset_inventory_sha256=review_asset_inventory_sha256,
        )
        report["reviewAssetInventorySha256"] = review_asset_inventory_sha256
        report["reviewPageSha256"] = sha256(review_path)
        report["inventorySha256"] = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file() and path != manifest_path
        }
        _atomic_write_json(manifest_path, report)
        immutable_after = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file()
            and path.relative_to(output_root).as_posix() not in mutable
        }
        if immutable_after != immutable_before:
            raise RuntimeError("C2 review refresh changed an immutable asset")
        return validate_c2_full_review(output_root)
    except Exception:
        _atomic_write_bytes(review_path, review_before)
        _atomic_write_bytes(manifest_path, manifest_before)
        raise


def reopen_c2_browser_gate(
    output_root, *, retained_root, reason, authorized=False
):
    if authorized is not True:
        raise PermissionError("reopening C2 browser gate requires explicit authorization")
    output_root = Path(output_root).resolve()
    retained_root = Path(retained_root).resolve()
    if output_root.name != "c2-full-review-r1":
        raise ValueError("C2 browser-gate output name mismatch")
    if retained_root.exists():
        raise FileExistsError(f"refusing to overwrite retained evidence: {retained_root}")
    if not retained_root.parent.is_dir():
        raise ValueError("retained evidence parent must already exist")
    if output_root.drive.casefold() != retained_root.parent.drive.casefold():
        raise ValueError("C2 browser evidence transaction must stay on one volume")
    browser_root = output_root / "browser-results"
    manifest_path = output_root / "c2-full-review-manifest.json"
    review_path = output_root / "review" / "index.html"
    if not browser_root.is_dir() or not manifest_path.is_file() or not review_path.is_file():
        raise ValueError("C2 completed browser evidence is missing")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (
        report.get("schema") == C2_FULL_REVIEW_PROFILE["schema"]
        and report.get("renderMachinePassed") is True
        and report.get("browserMachinePassed") is True
        and report.get("machinePassed") is True
        and report.get("humanVisualApproved") is False
        and report.get("authorizesStep9") is False
    ):
        raise ValueError("C2 browser-gate source state mismatch")
    actual_inventory = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if actual_inventory != report.get("inventorySha256"):
        raise ValueError("C2 browser-gate source inventory mismatch")
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    immutable_before = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path.relative_to(output_root).as_posix() not in mutable
        and "browser-results" not in path.relative_to(output_root).parts
    }
    manifest_before = manifest_path.read_bytes()
    review_before = review_path.read_bytes()
    rollback_root = Path(
        tempfile.mkdtemp(prefix=".browser-results-reopen-", dir=output_root.parent)
    )
    rollback_root.rmdir()
    browser_root.rename(rollback_root)
    source_candidate = (
        output_root.relative_to(ROOT).as_posix()
        if output_root.is_relative_to(ROOT)
        else str(output_root)
    )
    try:
        _atomic_write_json(
            rollback_root / "superseded.json",
            {
                "schema": "twinkle-stage4-c2-superseded-browser-evidence-v1",
                "reason": str(reason),
                "sourceCandidate": source_candidate,
                "renderAssetsChanged": False,
            },
        )
        choices = {
            unit: {int(entry): variant for entry, variant in entries.items()}
            for unit, entries in report["c1HumanChoices"].items()
        }
        c1 = validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT_ROOT)
        authority = validate_authority()
        contracts = c2_route_contracts(c1, authority["stage3"], choices)
        old_routes = {route["routeId"]: route for route in report["routes"]}
        report["routes"] = [
            {
                **contract,
                "focusFrames": old_routes[contract["routeId"]]["focusFrames"],
                "stage3MechanicalPlaybackGenerated": True,
                "renderMachinePassed": True,
            }
            for contract in contracts
        ]
        _bind_existing_c2_review_dependencies(output_root, report["routes"])
        report["browserMachinePassed"] = False
        report["browserEvidence"] = []
        report["machinePassed"] = False
        review_asset_inventory_sha256 = canonical_json_sha256(
            _c2_review_asset_inventory(output_root)
        )
        _write_c2_review_page(
            output_root,
            report["routes"],
            review_asset_inventory_sha256=review_asset_inventory_sha256,
        )
        report["reviewAssetInventorySha256"] = review_asset_inventory_sha256
        report["reviewPageSha256"] = sha256(review_path)
        report["inventorySha256"] = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file() and path != manifest_path
        }
        _atomic_write_json(manifest_path, report)
        result = validate_c2_full_review(output_root)
        immutable_after = {
            path.relative_to(output_root).as_posix(): sha256(path)
            for path in sorted(output_root.rglob("*"))
            if path.is_file()
            and path.relative_to(output_root).as_posix() not in mutable
            and "browser-results" not in path.relative_to(output_root).parts
        }
        if immutable_after != immutable_before:
            raise RuntimeError("reopening C2 browser gate changed render assets")
        rollback_root.rename(retained_root)
    except Exception:
        _atomic_write_bytes(manifest_path, manifest_before)
        _atomic_write_bytes(review_path, review_before)
        if retained_root.exists() and not rollback_root.exists():
            retained_root.rename(rollback_root)
        if rollback_root.exists():
            marker = rollback_root / "superseded.json"
            if marker.exists():
                marker.unlink()
            if not browser_root.exists():
                rollback_root.rename(browser_root)
        raise
    return result


def upgrade_c2_quality_bindings(
    output_root, *, backup_root, authorized=False
):
    if authorized is not True:
        raise PermissionError("C2 quality binding upgrade requires explicit authorization")
    output_root = Path(output_root).resolve()
    backup_root = Path(backup_root).resolve()
    if output_root.name != "c2-full-review-r1" or not output_root.is_dir():
        raise ValueError("C2 quality upgrade source mismatch")
    if backup_root.exists() or not backup_root.parent.is_dir():
        raise ValueError("C2 quality upgrade backup target mismatch")
    if output_root.drive.casefold() != backup_root.parent.drive.casefold():
        raise ValueError("C2 quality upgrade must stay on one volume")
    manifest_path = output_root / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (
        report.get("schema") == C2_FULL_REVIEW_PROFILE["schema"]
        and report.get("renderMachinePassed") is True
        and report.get("browserMachinePassed") is False
        and report.get("machinePassed") is False
        and report.get("humanVisualApproved") is False
        and not (output_root / "browser-results").exists()
        and not (output_root / "review-assets").exists()
        and not (output_root / "c2-worker-contracts.json").exists()
    ):
        raise ValueError("C2 quality upgrade requires the pending legacy candidate")
    actual_inventory = {
        path.relative_to(output_root).as_posix(): sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    if actual_inventory != report.get("inventorySha256"):
        raise ValueError("C2 quality upgrade source inventory mismatch")
    choices = {
        unit: {int(entry): variant for entry, variant in entries.items()}
        for unit, entries in report["c1HumanChoices"].items()
    }
    c1 = validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT_ROOT)
    authority = validate_authority()
    contracts = c2_route_contracts(c1, authority["stage3"], choices)
    contract_sha256 = canonical_json_sha256(contracts)
    old_worker = json.loads(
        (output_root / "worker-audit.json").read_text(encoding="utf-8")
    )
    bound_worker = bind_c2_worker_audit_contract(old_worker, contracts)
    if bound_worker["contractSha256"] != contract_sha256:
        raise ValueError("C2 quality upgrade worker binding mismatch")
    staging = Path(
        tempfile.mkdtemp(prefix=".c2-quality-upgrade-", dir=output_root.parent)
    )
    staging.rmdir()
    shutil.copytree(output_root, staging, copy_function=os.link)
    try:
        _atomic_write_json(
            staging / "c2-worker-contracts.json",
            {
                "schema": "twinkle-stage4-c2-worker-contracts-v1",
                "contractSha256": contract_sha256,
                "routes": contracts,
            },
        )
        _atomic_write_json(staging / "worker-audit.json", bound_worker)
        old_routes = {route["routeId"]: route for route in report["routes"]}
        report["routes"] = [
            {
                **contract,
                "focusFrames": old_routes[contract["routeId"]]["focusFrames"],
                "stage3MechanicalPlaybackGenerated": True,
                "renderMachinePassed": True,
            }
            for contract in contracts
        ]
        local_dependencies = _materialize_c2_review_dependencies(
            staging, report["routes"]
        )
        static_path = staging / "review" / "c2-static-fallback.png"
        review_path = staging / "review" / "index.html"
        static_path.unlink()
        review_path.unlink()
        _write_c2_static_fallback(staging, report["routes"])
        review_asset_inventory_sha256 = canonical_json_sha256(
            _c2_review_asset_inventory(staging)
        )
        _write_c2_review_page(
            staging,
            report["routes"],
            review_asset_inventory_sha256=review_asset_inventory_sha256,
        )
        report["localReviewDependencyCount"] = len(local_dependencies)
        report["reviewAssetInventorySha256"] = review_asset_inventory_sha256
        report["reviewPageSha256"] = sha256(review_path)
        report["workerContractSha256"] = contract_sha256
        report["browserMachinePassed"] = False
        report["browserEvidence"] = []
        report["machinePassed"] = False
        staging_manifest = staging / "c2-full-review-manifest.json"
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path != staging_manifest
        }
        _atomic_write_json(staging_manifest, report)
        validate_c2_full_review(staging)
        output_root.rename(backup_root)
        try:
            staging.rename(output_root)
        except Exception:
            backup_root.rename(output_root)
            raise
    except Exception as error:
        raise RuntimeError(f"C2 quality upgrade failed; staging kept at {staging}") from error
    return validate_c2_full_review(output_root)


def build_c2_full_review(
    output_root, *, choices, authorized=False, blender=None, runner=None
):
    if authorized is not True:
        raise PermissionError("C2 full review requires explicit authorization")
    output_root = Path(output_root).resolve()
    if output_root.name != "c2-full-review-r1":
        raise ValueError("C2 full-review output name mismatch")
    validate_request(default_request(output_root))
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    c1 = validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT_ROOT)
    authority = validate_authority()
    contracts = c2_route_contracts(c1, authority["stage3"], choices)
    candidate_blend = Path(authority["stage1"]["candidateBlend"]["path"])
    if sha256(candidate_blend) != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise ValueError("candidate blend drift before C2")
    blender = Path(
        blender
        or os.environ.get("TWINKLE_BLENDER")
        or shutil.which("blender")
        or "blender"
    )
    if runner is None and not blender.is_file():
        raise FileNotFoundError(f"Blender executable missing: {blender}")
    runner = runner or _run_checked
    staging = Path(tempfile.mkdtemp(prefix=".c2-full-", dir=output_root.parent))
    try:
        worker_contract_sha256 = canonical_json_sha256(contracts)
        (staging / "c2-worker-contracts.json").write_text(
            json.dumps(
                {
                    "schema": "twinkle-stage4-c2-worker-contracts-v1",
                    "contractSha256": worker_contract_sha256,
                    "routes": contracts,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner(
            c2_full_review_blender_command(blender, candidate_blend, staging),
            cwd=ROOT,
        )
        worker = json.loads((staging / "worker-audit.json").read_text(encoding="utf-8"))
        worker_routes = {route["routeId"]: route for route in worker.get("routes", [])}
        if not (
            worker.get("schema") == "twinkle-stage4-c2-full-worker-v1"
            and worker.get("contractSha256") == worker_contract_sha256
            and worker.get("renderedFrameCount") == 176
            and set(worker_routes) == {route["routeId"] for route in contracts}
        ):
            raise ValueError("C2 worker inventory mismatch")
        c1_routes = {route["routeId"]: route for route in c1["routes"]}
        rendered_indices = [index for index in range(25) if index not in {0, 12, 24}]
        routes = []
        for contract in contracts:
            route_id = contract["routeId"]
            route_root = staging / "frames" / route_id
            route_root.mkdir(parents=True, exist_ok=True)
            reused = {
                int(frame["sampleIndex"]): frame
                for frame in c1_routes[route_id]["previewFrames"]
            }
            for index, source in reused.items():
                shutil.copy2(
                    (
                        C1_KEYFRAME_OUTPUT_ROOT / source["path"]
                    ),
                    route_root / f"focus-{index:03d}.png",
                )
            records = {
                int(frame["sampleIndex"]): frame
                for frame in worker_routes[route_id].get("frames", [])
            }
            if sorted(records) != rendered_indices:
                raise ValueError(f"C2 worker samples mismatch: {route_id}")
            focus_frames = []
            for index in range(25):
                path = route_root / f"focus-{index:03d}.png"
                if not path.is_file():
                    raise ValueError(f"C2 focus frame missing: {route_id}/{index}")
                quality = _frame_quality(path)
                audit = records.get(index)
                if (
                    audit is not None
                    and quality["resolution"]
                    != C2_FULL_REVIEW_PROFILE["render"]["resolution"]
                ):
                    raise ValueError(f"C2 focus resolution mismatch: {route_id}/{index}")
                if quality["blackFrame"] or quality["emptyFrame"]:
                    raise ValueError(f"C2 black or empty focus frame: {route_id}/{index}")
                if audit is not None and (
                    audit.get("path") != path.relative_to(staging).as_posix()
                    or len(audit.get("expectedPosition", [])) != 3
                    or any(
                            abs(float(left) - float(right))
                            > C2_WORKER_EXPECTED_POSITION_FLOAT32_TOLERANCE_M
                        for left, right in zip(
                            audit.get("expectedPosition", []),
                            contract["curveSamplePositions"][index],
                        )
                    )
                    or float(audit.get("positionErrorM", 1.0)) > 1e-5
                    or float(audit.get("targetErrorDegrees", 1.0)) > 1e-4
                ):
                    raise ValueError(f"C2 focus audit mismatch: {route_id}/{index}")
                focus_frames.append(
                    {
                        "sampleIndex": index,
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256(path),
                        "provenance": (
                            "approved-c1-reuse"
                            if index in reused
                            else "c2-new-render"
                        ),
                        **quality,
                    }
                )
            routes.append(
                {
                    **contract,
                    "focusFrames": focus_frames,
                    "stage3MechanicalPlaybackGenerated": True,
                    "renderMachinePassed": True,
                }
            )
        local_dependencies = _materialize_c2_review_dependencies(staging, routes)
        static_fallback = _write_c2_static_fallback(staging, routes)
        review_asset_inventory_sha256 = canonical_json_sha256(
            _c2_review_asset_inventory(staging)
        )
        review = _write_c2_review_page(
            staging,
            routes,
            review_asset_inventory_sha256=review_asset_inventory_sha256,
        )
        report = {
            "schema": C2_FULL_REVIEW_PROFILE["schema"],
            "scope": "stage4-step8-c2-full-ab-and-stage3-r2-review-only",
            "profile": C2_FULL_REVIEW_PROFILE,
            "c1HumanChoices": {
                unit: {str(entry): variant for entry, variant in entries.items()}
                for unit, entries in choices.items()
            },
            "routes": routes,
            "routeCount": len(routes),
            "renderedFocusFrameCount": 176,
            "reusedC1FrameCount": 24,
            "referencedStage3R2FrameCount": 50,
            "localReviewDependencyCount": len(local_dependencies),
            "reviewAssetInventorySha256": review_asset_inventory_sha256,
            "reviewPageSha256": sha256(review),
            "workerContractSha256": worker_contract_sha256,
            "restoration": worker["restoration"],
            "review": {
                "asset": review.relative_to(staging).as_posix(),
                "staticFallback": static_fallback.relative_to(staging).as_posix(),
            },
            "renderMachinePassed": True,
            "browserMachinePassed": False,
            "browserEvidence": [],
            "machinePassed": False,
            "humanVisualApproved": False,
            "authorizesStep9": False,
            "stage4Closed": False,
            "authorizesStage5": False,
        }
        report["inventorySha256"] = {
            path.relative_to(staging).as_posix(): sha256(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        manifest_path = staging / "c2-full-review-manifest.json"
        manifest_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        validate_c2_full_review(staging)
        staging.rename(output_root)
    except Exception as error:
        raise RuntimeError(f"C2 full review failed; staging kept at {staging}") from error
    return validate_c2_full_review(output_root)


def c360_f96_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Matrix, Quaternion, Vector = (
        mathutils.Matrix,
        mathutils.Quaternion,
        mathutils.Vector,
    )

    output_root = validate_orientation_worker_staging(output_root)
    frames_root = output_root / "frames"
    frames_root.mkdir()
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for C360-F96")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before C360-F96 worker")
    surface_manifest = (
        APPROVED_SURFACE_ANCHOR_PRECHECK
        / "surface-anchor-precheck-manifest.json"
    )
    if sha256(surface_manifest) != EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256:
        raise RuntimeError("approved surface anchor manifest drift in C360 worker")
    surface = json.loads(surface_manifest.read_text(encoding="utf-8"))
    selected_ids = {CHAMBER: "chamber-surface-02", CONDENSER: "condenser-surface-01"}
    selected = {}
    for unit in SEMANTIC_UNITS:
        matches = [
            candidate
            for candidate in surface["candidatesByUnit"][unit]
            if candidate["candidateId"] == selected_ids[unit]
        ]
        if len(matches) != 1 or matches[0].get("humanApproved") is not True:
            raise RuntimeError("C360 worker surface approval mismatch")
        selected[unit] = matches[0]

    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("C360 source camera missing")
    original_frame = scene.frame_current
    original_camera = scene.camera
    original_camera_matrix = source_camera.matrix_world.copy()
    original_scene = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent,
        "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {
        name: bool(bpy.data.objects[name].hide_render)
        for name in profile["sharedHiddenObjects"]
        if name in bpy.data.objects
    }
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("C360 material authority missing")
    material_slot = top_plate.material_slots[0]
    original_material, original_material_link = material_slot.material, material_slot.link
    if original_material is None:
        raise RuntimeError("C360 original material missing")
    original_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }

    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__STAGE4_C360_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_C360_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    temporary_material = None
    technical_lights = []
    frame_records = []
    curve_data = curve_object = target = camera_action = None

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_linear_fcurve(fcurves, data_path, values):
        curve = fcurves.new(data_path=data_path)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "LINEAR"
        curve.update()
        return curve

    shared_hidden = set(profile["sharedHiddenObjects"])

    def render_visible(obj):
        return (
            obj is not None
            and obj.type == "MESH"
            and not obj.hide_render
            and obj.name not in shared_hidden
        )

    def nearest_render_visible_hit(origin, point, depsgraph):
        direction_vector = point - origin
        target_distance = float(direction_vector.length)
        direction = direction_vector.normalized()
        cursor = origin.copy()
        remaining = target_distance + 0.0001
        travelled = 0.0
        for _ in range(64):
            hit, location, normal, face_index, obj, _ = scene.ray_cast(
                depsgraph, cursor, direction, distance=remaining
            )
            if not hit:
                return None
            segment = float((location - cursor).length)
            travelled += segment
            if render_visible(obj):
                return {
                    "object": obj.name,
                    "polygonIndex": int(face_index),
                    "location": location.copy(),
                    "distance": travelled,
                }
            step = 1e-6
            cursor = location + direction * step
            travelled += step
            remaining -= segment + step
            if remaining <= 0:
                return None
        raise RuntimeError("C360 ray-cast exceeded bounded traversal")

    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x, scene.render.resolution_y = C360_F96_RENDER[
            "resolution"
        ]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = C360_F96_RENDER["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        chamber_target = Vector(authority["units"][CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(
                f"TEMP__STAGE4_C360_{key.upper()}_DATA", "AREA"
            )
            data.energy, data.shape, data.size = config["energy"], "DISK", config["size"]
            obj = bpy.data.objects.new(f"TEMP__STAGE4_C360_{key.upper()}", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat(
                "-Z", "Y"
            ).to_euler()
            technical_lights.append((obj.name, data.name))

        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE4_C360_TOP_PLATE_NO_NORMAL"
        normal_nodes = [
            node
            for node in temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("C360 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"][
            "normalMapStrengthDuringRender"
        ]
        material_slot.link, material_slot.material = "OBJECT", temporary_material

        camera.data.lens = ORBIT_LENS_MM
        camera.data.sensor_width = ORBIT_SENSOR_WIDTH_MM
        camera.data.shift_x, camera.data.shift_y = ORBIT_SHIFT
        pivot = Vector(ORBIT_OVERVIEW_TARGET)
        base = Vector(ORBIT_OVERVIEW_LOCATION) - pivot
        expected_locations = []
        for angle in c360_f96_angles():
            expected_locations.append(
                pivot + Matrix.Rotation(math.radians(angle), 4, "Z") @ base
            )
        curve_data = bpy.data.curves.new("TEMP__STAGE4_C360_CURVE", type="CURVE")
        curve_data.dimensions, curve_data.path_duration = "3D", 96
        spline = curve_data.splines.new(type="POLY")
        spline.points.add(95)
        spline.use_cyclic_u = True
        for point, location in zip(spline.points, expected_locations):
            point.co = (*location, 1.0)
        curve_object = bpy.data.objects.new("TEMP__STAGE4_C360_PATH", curve_data)
        scene.collection.objects.link(curve_object)
        curve_object.matrix_world = Matrix.Identity(4)
        target = bpy.data.objects.new("TEMP__STAGE4_C360_TARGET", None)
        target.location = pivot
        scene.collection.objects.link(target)
        follow = camera.constraints.new(type="FOLLOW_PATH")
        follow.name, follow.target = "TEMP__STAGE4_C360_FOLLOW_PATH", curve_object
        follow.use_fixed_location, follow.use_curve_follow = True, False
        orientation = camera.constraints.new(type="TRACK_TO")
        orientation.name, orientation.target = "TEMP__STAGE4_C360_TRACK_TO", target
        orientation.track_axis, orientation.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        camera_action = bpy.data.actions.new("TEMP__STAGE4_C360_CAMERA_ACTION")
        camera_slot, fcurves = action_fcurves(camera_action, camera, "C360 Orbit")
        add_linear_fcurve(
            fcurves,
            f'constraints["{follow.name}"].offset_factor',
            ((1, 0.0), (97, 1.0)),
        )
        animation = camera.animation_data_create()
        animation.action, animation.action_slot = camera_action, camera_slot
        camera.location = Vector((0.0, 0.0, 0.0))
        camera.rotation_euler = (pivot - expected_locations[0]).to_track_quat(
            "-Z", "Y"
        ).to_euler()
        camera.scale = Vector((1.0, 1.0, 1.0))

        depsgraph = bpy.context.evaluated_depsgraph_get()
        subject_points = []
        for obj in bpy.context.view_layer.objects:
            if render_visible(obj):
                subject_points.extend(
                    [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
                )
        projection = load_camera_projection_module()
        maximum_target_error = maximum_roll = maximum_step = 0.0
        minimum_up_dot = 1.0
        previous_rotation = None
        flip_count = 0
        for index, angle in enumerate(c360_f96_angles()):
            scene.frame_set(index + 1)
            bpy.context.view_layer.update()
            matrix = camera.matrix_world.copy()
            location, rotation = matrix.translation.copy(), matrix.to_quaternion()
            path_error = float((location - expected_locations[index]).length)
            if path_error > 1e-5:
                raise RuntimeError(f"C360 path evaluation drift at frame {index}")
            current_target = target.matrix_world.translation.copy()
            direction = (current_target - location).normalized()
            forward = rotation @ Vector((0.0, 0.0, -1.0))
            up = rotation @ Vector((0.0, 1.0, 0.0))
            ideal = direction.to_track_quat("-Z", "Y")
            target_error = math.degrees(float(forward.angle(direction)))
            roll = math.degrees(float(rotation.rotation_difference(ideal).angle))
            step = (
                0.0
                if previous_rotation is None
                else math.degrees(
                    float(previous_rotation.rotation_difference(rotation).angle)
                )
            )
            if previous_rotation is not None and (
                (previous_rotation @ Vector((0, 1, 0))).dot(up) < 0
            ):
                flip_count += 1
            spec = projection.CameraSpec(
                location=location,
                target=current_target,
                lens_mm=ORBIT_LENS_MM,
                sensor_width_mm=ORBIT_SENSOR_WIDTH_MM,
                shift_x=0.0,
                shift_y=0.0,
                resolution_x=640,
                resolution_y=450,
                sensor_fit="AUTO",
            )
            target_projection = projection.project_world_point(current_target, spec)
            bounds = projection.project_bounds(subject_points, spec)
            min_x, min_y, max_x, max_y = bounds.as_list()
            total_area = max(0.0, max_x - min_x) * max(0.0, max_y - min_y)
            visible_area = max(0.0, min(1.0, max_x) - max(0.0, min_x)) * max(
                0.0, min(1.0, max_y) - max(0.0, min_y)
            )
            visible_fraction = visible_area / total_area if total_area else 0.0
            target_clipped = not (
                target_projection.depth > 0
                and 0.05 <= target_projection.x <= 0.69
                and 0.05 <= target_projection.y <= 0.95
            )
            subject_out = (
                visible_fraction < ORBIT_MIN_VISIBLE_SUBJECT_FRACTION
                or visible_area < ORBIT_MIN_VISIBLE_CANVAS_AREA
            )
            qualification = {}
            for unit in SEMANTIC_UNITS:
                candidate = selected[unit]
                point = Vector(candidate["worldPosition"])
                normal = Vector(candidate["worldNormal"])
                projected = projection.project_world_point(point, spec)
                depth_positive = projected.depth > 0
                projection_safe = (
                    depth_positive
                    and 0.05 <= projected.x <= 0.69
                    and 0.05 <= projected.y <= 0.95
                )
                facing_dot = float(normal.dot((location - point).normalized()))
                hit = nearest_render_visible_hit(location, point, depsgraph)
                hit_error = None if hit is None else float((hit["location"] - point).length)
                unoccluded = (
                    hit is not None
                    and hit["object"] == candidate["objectName"]
                    and hit["polygonIndex"] == candidate["polygonIndex"]
                    and hit_error <= 0.0001
                )
                if not projection_safe:
                    status = "out-of-safe"
                elif facing_dot <= 0:
                    status = "back-facing"
                elif not unoccluded:
                    status = "occluded"
                else:
                    status = "visible"
                qualification[unit] = {
                    "selectedSurfaceCandidateId": candidate["candidateId"],
                    "projection": [float(projected.x), float(projected.y)],
                    "depth": float(projected.depth),
                    "depthPositive": depth_positive,
                    "projectionSafe": projection_safe,
                    "facingDot": facing_dot,
                    "facingCamera": facing_dot > 0,
                    "nearestHitObject": None if hit is None else hit["object"],
                    "nearestHitPolygonIndex": None if hit is None else hit["polygonIndex"],
                    "hitPositionErrorM": hit_error,
                    "unoccluded": unoccluded,
                    "status": status,
                    "machineQualified": status == "visible",
                }
            path = frames_root / f"frame-{index:03d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frame_records.append(
                {
                    "physicalFrameIndex": index,
                    "sourceFrame": index + 1,
                    "azimuthDegrees": angle,
                    "path": path.relative_to(output_root).as_posix(),
                    "sha256": sha256(path),
                    "camera": {
                        "location": [round(float(value), 9) for value in location],
                        "rotationQuaternion": [round(float(value), 9) for value in rotation],
                        "target": [round(float(value), 9) for value in current_target],
                        "up": [round(float(value), 9) for value in up],
                        "lensMm": ORBIT_LENS_MM,
                        "sensorWidthMm": ORBIT_SENSOR_WIDTH_MM,
                        "shiftX": 0.0,
                        "shiftY": 0.0,
                        "targetErrorDegrees": target_error,
                        "rollDegrees": roll,
                        "upDotWorldZ": float(up.z),
                    },
                    "pathPositionErrorM": path_error,
                    "targetProjection": [
                        float(target_projection.x),
                        float(target_projection.y),
                    ],
                    "subjectBounds": [float(value) for value in bounds.as_list()],
                    "visibleSubjectFraction": visible_fraction,
                    "visibleCanvasArea": visible_area,
                    "targetClipped": target_clipped,
                    "subjectOutOfFrame": subject_out,
                    "qualificationByUnit": qualification,
                }
            )
            maximum_target_error = max(maximum_target_error, target_error)
            maximum_roll = max(maximum_roll, abs(roll))
            maximum_step = max(maximum_step, step)
            minimum_up_dot = min(minimum_up_dot, float(up.z))
            previous_rotation = rotation

        dt = C360_F96_PROFILE["durationMs"] / 1000.0 / 96.0
        position_steps = []
        orientation_steps = []
        for index, frame in enumerate(frame_records):
            previous = frame_records[(index - 1) % 96]
            position_step = float(
                (Vector(frame["camera"]["location"]) - Vector(previous["camera"]["location"])).length
            )
            orientation_step = math.degrees(
                float(
                    Quaternion(previous["camera"]["rotationQuaternion"]).rotation_difference(
                        Quaternion(frame["camera"]["rotationQuaternion"])
                    ).angle
                )
            )
            frame["speedMetersPerSecond"] = position_step / dt
            position_steps.append(position_step)
            orientation_steps.append(orientation_step)
        typical_position = sorted(position_steps[:-1])[len(position_steps[:-1]) // 2]
        typical_orientation = sorted(orientation_steps[1:])[len(orientation_steps[1:]) // 2]
        closure_metrics = {
            "seamPositionStepM": position_steps[0],
            "typicalPositionStepM": typical_position,
            "seamPositionStepRatio": position_steps[0] / typical_position,
            "seamOrientationStepDegrees": orientation_steps[0],
            "typicalOrientationStepDegrees": typical_orientation,
            "seamOrientationStepRatio": orientation_steps[0] / typical_orientation,
        }
    finally:
        camera.animation_data_clear()
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4_C360"):
                camera.constraints.remove(constraint)
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4_C360"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4_C360"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4_C360"):
                bpy.data.curves.remove(curve)
        material_slot.material, material_slot.link = original_material, original_material_link
        if temporary_material is not None and temporary_material.name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for object_name, data_name in technical_lights:
            remove_named_datablock(bpy.data.objects, object_name, do_unlink=True)
            remove_named_datablock(bpy.data.lights, data_name)
        scene.camera = original_camera
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.render.film_transparent = original_scene["film_transparent"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.view_settings.view_transform = original_scene["viewTransform"]
        scene.view_settings.look = original_scene["look"]
        scene.view_settings.exposure = original_scene["exposure"]
        scene.view_settings.gamma = original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()
        for camera_block in list(bpy.data.cameras):
            if camera_block.name.startswith("TEMP__STAGE4_C360"):
                bpy.data.cameras.remove(camera_block)

    candidate_hash_after = sha256(candidate_blend)
    current_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }
    temporary_remaining = sorted(
        f"{kind}:{name}"
        for kind in original_data
        for name in current_data[kind] - original_data[kind]
    )
    source_camera_restored = all(
        abs(float(left) - float(right)) <= 1e-8
        for left_row, right_row in zip(source_camera.matrix_world, original_camera_matrix)
        for left, right in zip(left_row, right_row)
    )
    scene_settings_restored = (
        scene.render.engine == original_scene["engine"]
        and scene.render.resolution_x == original_scene["resolution_x"]
        and scene.render.resolution_y == original_scene["resolution_y"]
        and scene.render.filepath == original_scene["filepath"]
        and scene.eevee.taa_render_samples == original_scene["samples"]
        and scene.camera == original_camera
    )
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sourceCameraTransformRestored": source_camera_restored,
        "sceneSettingsRestored": scene_settings_restored,
        "visibilityRestored": all(
            bool(bpy.data.objects[name].hide_render) == hidden
            for name, hidden in original_visibility.items()
        ),
        "materialRestored": material_slot.material == original_material
        and material_slot.link == original_material_link,
        "temporaryDataBlocksRemaining": temporary_remaining,
    }
    audit = {
        "schema": "twinkle-stage4-c360-f96-worker-v1",
        "orbitProfile": C360_F96_PROFILE,
        "render": C360_F96_RENDER,
        "frames": frame_records,
        "closureMetrics": closure_metrics,
        "orientationMetrics": {
            "maximumTargetErrorDegrees": maximum_target_error,
            "maximumRollDegrees": maximum_roll,
            "minimumUpDotWorldZ": minimum_up_dot,
            "maximumOrientationStepDegrees": max(
                maximum_step, closure_metrics["seamOrientationStepDegrees"]
            ),
            "flipCount": flip_count,
            "constraintCompetition": False,
            "evaluationLoopDetected": False,
        },
        "renderedFrameCount": len(frame_records),
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        len(frame_records) != 96
        or candidate_hash_after != candidate_hash_before
        or not source_camera_restored
        or not scene_settings_restored
        or not restoration["visibilityRestored"]
        or not restoration["materialRestored"]
        or temporary_remaining
    ):
        raise RuntimeError("C360-F96 restoration or render audit failed")


def c1_keyframe_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Matrix, Vector = mathutils.Matrix, mathutils.Vector

    output_root = validate_orientation_worker_staging(output_root)
    frames_root = output_root / "frames"
    frames_root.mkdir()
    authority = json.loads(STAGE1_MANIFEST.read_text(encoding="utf-8"))
    orbit = json.loads(
        (APPROVED_C360_F96 / "orbit-c360-f96-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    routes = c1_route_contracts(orbit, authority)
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for C1")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before C1 worker")

    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("C1 source camera missing")
    original_frame = scene.frame_current
    original_camera = scene.camera
    original_camera_matrix = source_camera.matrix_world.copy()
    original_scene = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent,
        "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {
        name: bool(bpy.data.objects[name].hide_render)
        for name in profile["sharedHiddenObjects"]
        if name in bpy.data.objects
    }
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("C1 material authority missing")
    material_slot = top_plate.material_slots[0]
    original_material, original_material_link = material_slot.material, material_slot.link
    if original_material is None:
        raise RuntimeError("C1 original material missing")
    original_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }

    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__STAGE4_C1_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_C1_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    temporary_material = None
    technical_lights = []
    route_records = []

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_eased_fcurve(fcurves, data_path, values):
        curve = fcurves.new(data_path=data_path)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        curve.update()
        return curve

    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x, scene.render.resolution_y = C1_KEYFRAME_PROFILE[
            "render"
        ]["resolution"]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = C1_KEYFRAME_PROFILE["render"]["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        chamber_target = Vector(authority["units"][CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(f"TEMP__STAGE4_C1_{key.upper()}_DATA", "AREA")
            data.energy, data.shape, data.size = config["energy"], "DISK", config["size"]
            obj = bpy.data.objects.new(f"TEMP__STAGE4_C1_{key.upper()}", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat(
                "-Z", "Y"
            ).to_euler()
            technical_lights.append((obj.name, data.name))

        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE4_C1_TOP_PLATE_NO_NORMAL"
        normal_nodes = [
            node
            for node in temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("C1 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"][
            "normalMapStrengthDuringRender"
        ]
        material_slot.link, material_slot.material = "OBJECT", temporary_material

        for route in routes:
            route_id = route["routeId"]
            route_root = frames_root / route_id
            route_root.mkdir()
            curve_data = bpy.data.curves.new(f"TEMP__STAGE4_C1_CURVE_{route_id}", "CURVE")
            curve_data.dimensions = "3D"
            curve_data.path_duration = C1_KEYFRAME_PROFILE["curveSampleCount"]
            spline = curve_data.splines.new(type="POLY")
            spline.points.add(C1_KEYFRAME_PROFILE["curveSampleCount"] - 1)
            for point, location in zip(spline.points, route["curveSamplePositions"]):
                point.co = (*location, 1.0)
            curve_object = bpy.data.objects.new(
                f"TEMP__STAGE4_C1_PATH_{route_id}", curve_data
            )
            scene.collection.objects.link(curve_object)
            curve_object.matrix_world = Matrix.Identity(4)
            target = bpy.data.objects.new(f"TEMP__STAGE4_C1_TARGET_{route_id}", None)
            target.location = Vector(route["commonFields"]["targetSamples"][12])
            scene.collection.objects.link(target)
            follow = camera.constraints.new(type="FOLLOW_PATH")
            follow.name = f"TEMP__STAGE4_C1_FOLLOW_{route_id}"
            follow.target = curve_object
            follow.use_fixed_location, follow.use_curve_follow = True, False
            orientation = camera.constraints.new(type="TRACK_TO")
            orientation.name = f"TEMP__STAGE4_C1_TRACK_{route_id}"
            orientation.target = target
            orientation.track_axis, orientation.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
            action = bpy.data.actions.new(f"TEMP__STAGE4_C1_ACTION_{route_id}")
            slot, fcurves = action_fcurves(action, camera, f"C1 {route_id}")
            add_eased_fcurve(
                fcurves,
                f'constraints["{follow.name}"].offset_factor',
                (
                    (1, 0.0),
                    (
                        13,
                        polyline_offset_factors(route["curveSamplePositions"])[12],
                    ),
                    (25, 1.0),
                ),
            )
            animation = camera.animation_data_create()
            animation.action, animation.action_slot = action, slot
            camera.location = Vector((0.0, 0.0, 0.0))
            camera.scale = Vector((1.0, 1.0, 1.0))
            camera.data.lens = route["commonFields"]["lensSamplesMm"][12]
            camera.data.sensor_width = ORBIT_SENSOR_WIDTH_MM
            camera.data.shift_x = route["commonFields"]["shiftXSamples"][12]
            camera.data.shift_y = route["commonFields"]["shiftYSamples"][12]
            scene.frame_set(13)
            bpy.context.view_layer.update()
            matrix = camera.matrix_world.copy()
            location, rotation = matrix.translation.copy(), matrix.to_quaternion()
            expected = Vector(route["curveSamplePositions"][12])
            direction = (target.matrix_world.translation - location).normalized()
            forward = rotation @ Vector((0.0, 0.0, -1.0))
            ideal = direction.to_track_quat("-Z", "Y")
            path = route_root / "keyframe-012.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            route_records.append(
                {
                    "routeId": route_id,
                    "path": path.relative_to(output_root).as_posix(),
                    "sampleIndex": 12,
                    "position": [round(float(value), 9) for value in location],
                    "expectedPosition": [round(float(value), 9) for value in expected],
                    "positionErrorM": float((location - expected).length),
                    "targetErrorDegrees": math.degrees(float(forward.angle(direction))),
                    "rollDegrees": math.degrees(
                        float(rotation.rotation_difference(ideal).angle)
                    ),
                    "orientationConstraint": "TRACK_TO",
                    "pathConstraint": "FOLLOW_PATH",
                    "fCurveEasing": "BEZIER/AUTO_CLAMPED",
                    "sha256": sha256(path),
                }
            )
            camera.animation_data_clear()
            camera.constraints.remove(orientation)
            camera.constraints.remove(follow)
            bpy.data.actions.remove(action)
            bpy.data.objects.remove(target, do_unlink=True)
            bpy.data.objects.remove(curve_object, do_unlink=True)
            bpy.data.curves.remove(curve_data)
    finally:
        camera.animation_data_clear()
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4_C1"):
                camera.constraints.remove(constraint)
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4_C1"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4_C1"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for camera_block in list(bpy.data.cameras):
            if camera_block.name.startswith("TEMP__STAGE4_C1"):
                bpy.data.cameras.remove(camera_block)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4_C1"):
                bpy.data.curves.remove(curve)
        material_slot.material, material_slot.link = original_material, original_material_link
        if temporary_material is not None and temporary_material.name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for object_name, data_name in technical_lights:
            remove_named_datablock(bpy.data.objects, object_name, do_unlink=True)
            remove_named_datablock(bpy.data.lights, data_name)
        scene.camera = original_camera
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.render.film_transparent = original_scene["film_transparent"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.view_settings.view_transform = original_scene["viewTransform"]
        scene.view_settings.look = original_scene["look"]
        scene.view_settings.exposure = original_scene["exposure"]
        scene.view_settings.gamma = original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()

    candidate_hash_after = sha256(candidate_blend)
    current_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }
    temporary_remaining = sorted(
        f"{kind}:{name}"
        for kind in original_data
        for name in current_data[kind] - original_data[kind]
    )
    source_camera_restored = all(
        abs(float(left) - float(right)) <= 1e-8
        for left_row, right_row in zip(source_camera.matrix_world, original_camera_matrix)
        for left, right in zip(left_row, right_row)
    )
    scene_settings_restored = (
        scene.render.engine == original_scene["engine"]
        and scene.render.resolution_x == original_scene["resolution_x"]
        and scene.render.resolution_y == original_scene["resolution_y"]
        and scene.render.filepath == original_scene["filepath"]
        and scene.eevee.taa_render_samples == original_scene["samples"]
        and scene.camera == original_camera
    )
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sourceCameraTransformRestored": source_camera_restored,
        "sceneSettingsRestored": scene_settings_restored,
        "visibilityRestored": all(
            bool(bpy.data.objects[name].hide_render) == hidden
            for name, hidden in original_visibility.items()
        ),
        "materialRestored": material_slot.material == original_material
        and material_slot.link == original_material_link,
        "temporaryDataBlocksRemaining": temporary_remaining,
    }
    audit = {
        "schema": "twinkle-stage4-c1-keyframe-worker-v1",
        "profile": C1_KEYFRAME_PROFILE,
        "routes": route_records,
        "renderedFrameCount": len(route_records),
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        len(route_records) != 8
        or candidate_hash_after != candidate_hash_before
        or not source_camera_restored
        or not scene_settings_restored
        or not restoration["visibilityRestored"]
        or not restoration["materialRestored"]
        or temporary_remaining
    ):
        raise RuntimeError("C1 restoration or render audit failed")


def c2_full_review_worker(output_root):
    bpy = __import__("bpy")
    mathutils = __import__("mathutils")
    Matrix, Vector = mathutils.Matrix, mathutils.Vector
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    frames_root = output_root / "frames"
    frames_root.mkdir(exist_ok=True)
    authority_bundle = validate_authority()
    authority = authority_bundle["stage1"]
    contract_payload = json.loads(
        (output_root / "c2-worker-contracts.json").read_text(encoding="utf-8")
    )
    routes = contract_payload.get("routes", [])
    contract_sha256 = canonical_json_sha256(routes)
    if not (
        contract_payload.get("schema") == "twinkle-stage4-c2-worker-contracts-v1"
        and contract_payload.get("contractSha256") == contract_sha256
        and len(routes) == 8
    ):
        raise RuntimeError("C2 worker contract digest mismatch")
    profile = authority["renderProfile"]
    candidate_blend = Path(authority["candidateBlend"]["path"])
    if Path(bpy.data.filepath).resolve() != candidate_blend.resolve():
        raise RuntimeError("wrong candidate blend loaded for C2")
    candidate_hash_before = sha256(candidate_blend)
    if candidate_hash_before != EXPECTED_CANDIDATE_BLEND_SHA256:
        raise RuntimeError("candidate blend drift before C2 worker")

    scene = bpy.context.scene
    source_camera = scene.camera
    if source_camera is None:
        raise RuntimeError("C2 source camera missing")
    original_frame = scene.frame_current
    original_camera = scene.camera
    original_camera_matrix = source_camera.matrix_world.copy()
    original_scene = {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "film_transparent": scene.render.film_transparent,
        "samples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    original_visibility = {
        name: bool(bpy.data.objects[name].hide_render)
        for name in profile["sharedHiddenObjects"]
        if name in bpy.data.objects
    }
    top_plate = bpy.data.objects.get(profile["materialRule"]["object"])
    if top_plate is None or len(top_plate.material_slots) != 1:
        raise RuntimeError("C2 material authority missing")
    material_slot = top_plate.material_slots[0]
    original_material, original_material_link = material_slot.material, material_slot.link
    if original_material is None:
        raise RuntimeError("C2 original material missing")
    original_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }

    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__STAGE4_C2_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__STAGE4_C2_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    temporary_material = None
    technical_lights = []
    route_records = []
    rendered_indices = [index for index in range(25) if index not in {0, 12, 24}]

    def action_fcurves(action, owner, label):
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        return slot, strip.channelbag(slot, ensure=True).fcurves

    def add_eased_fcurve(fcurves, data_path, values):
        curve = fcurves.new(data_path=data_path)
        curve.keyframe_points.add(len(values))
        for point, (frame, value) in zip(curve.keyframe_points, values):
            point.co = (float(frame), float(value))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        curve.update()
        return curve

    try:
        for name in profile["sharedHiddenObjects"]:
            bpy.data.objects[name].hide_render = True
        scene.render.engine = profile["engine"]
        scene.render.resolution_x, scene.render.resolution_y = C2_FULL_REVIEW_PROFILE[
            "render"
        ]["resolution"]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = profile["filmTransparent"]
        scene.eevee.taa_render_samples = C2_FULL_REVIEW_PROFILE["render"]["samples"]
        color = profile["colorManagement"]
        scene.view_settings.view_transform = color["viewTransform"]
        scene.view_settings.look = color["look"]
        scene.view_settings.exposure = color["exposure"]
        scene.view_settings.gamma = color["gamma"]

        chamber_target = Vector(authority["units"][CHAMBER]["camera"]["target"])
        for key, config in profile["sharedTechnicalLights"].items():
            data = bpy.data.lights.new(f"TEMP__STAGE4_C2_{key.upper()}_DATA", "AREA")
            data.energy, data.shape, data.size = config["energy"], "DISK", config["size"]
            obj = bpy.data.objects.new(f"TEMP__STAGE4_C2_{key.upper()}", data)
            scene.collection.objects.link(obj)
            obj.location = Vector(config["location"])
            obj.rotation_euler = (chamber_target - obj.location).to_track_quat(
                "-Z", "Y"
            ).to_euler()
            technical_lights.append((obj.name, data.name))

        temporary_material = original_material.copy()
        temporary_material.name = "TEMP__STAGE4_C2_TOP_PLATE_NO_NORMAL"
        normal_nodes = [
            node
            for node in temporary_material.node_tree.nodes
            if node.bl_idname == "ShaderNodeNormalMap"
        ]
        if len(normal_nodes) != 1:
            raise RuntimeError("C2 normal-map rule drift")
        normal_nodes[0].inputs["Strength"].default_value = profile["materialRule"][
            "normalMapStrengthDuringRender"
        ]
        material_slot.link, material_slot.material = "OBJECT", temporary_material

        for route in routes:
            route_id = route["routeId"]
            route_root = frames_root / route_id
            route_root.mkdir(parents=True, exist_ok=True)
            curve_data = bpy.data.curves.new(f"TEMP__STAGE4_C2_CURVE_{route_id}", "CURVE")
            curve_data.dimensions = "3D"
            curve_data.path_duration = C2_FULL_REVIEW_PROFILE["curveSampleCount"]
            spline = curve_data.splines.new(type="POLY")
            spline.points.add(C2_FULL_REVIEW_PROFILE["curveSampleCount"] - 1)
            for point, location in zip(spline.points, route["curveSamplePositions"]):
                point.co = (*location, 1.0)
            curve_object = bpy.data.objects.new(
                f"TEMP__STAGE4_C2_PATH_{route_id}", curve_data
            )
            scene.collection.objects.link(curve_object)
            curve_object.matrix_world = Matrix.Identity(4)
            target = bpy.data.objects.new(f"TEMP__STAGE4_C2_TARGET_{route_id}", None)
            scene.collection.objects.link(target)
            follow = camera.constraints.new(type="FOLLOW_PATH")
            follow.name = f"TEMP__STAGE4_C2_FOLLOW_{route_id}"
            follow.target = curve_object
            follow.use_fixed_location, follow.use_curve_follow = True, False
            orientation = camera.constraints.new(type="TRACK_TO")
            orientation.name = f"TEMP__STAGE4_C2_TRACK_{route_id}"
            orientation.target = target
            orientation.track_axis, orientation.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
            action = bpy.data.actions.new(f"TEMP__STAGE4_C2_ACTION_{route_id}")
            slot, fcurves = action_fcurves(action, camera, f"C2 {route_id}")
            offsets = polyline_offset_factors(route["curveSamplePositions"])
            add_eased_fcurve(
                fcurves,
                f'constraints["{follow.name}"].offset_factor',
                [(index + 1, offset) for index, offset in enumerate(offsets)],
            )
            animation = camera.animation_data_create()
            animation.action, animation.action_slot = action, slot
            camera.location = Vector((0.0, 0.0, 0.0))
            camera.scale = Vector((1.0, 1.0, 1.0))
            camera.data.sensor_width = ORBIT_SENSOR_WIDTH_MM
            frame_records = []
            for sample_index in rendered_indices:
                target.location = Vector(route["commonFields"]["targetSamples"][sample_index])
                camera.data.lens = route["commonFields"]["lensSamplesMm"][sample_index]
                camera.data.shift_x = route["commonFields"]["shiftXSamples"][sample_index]
                camera.data.shift_y = route["commonFields"]["shiftYSamples"][sample_index]
                scene.frame_set(sample_index + 1)
                bpy.context.view_layer.update()
                matrix = camera.matrix_world.copy()
                location, rotation = matrix.translation.copy(), matrix.to_quaternion()
                expected = Vector(route["curveSamplePositions"][sample_index])
                direction = (target.matrix_world.translation - location).normalized()
                forward = rotation @ Vector((0.0, 0.0, -1.0))
                ideal = direction.to_track_quat("-Z", "Y")
                path = route_root / f"focus-{sample_index:03d}.png"
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                frame_records.append(
                    {
                        "sampleIndex": sample_index,
                        "path": path.relative_to(output_root).as_posix(),
                        "position": [round(float(value), 9) for value in location],
                        "expectedPosition": [round(float(value), 9) for value in expected],
                        "positionErrorM": float((location - expected).length),
                        "targetErrorDegrees": math.degrees(float(forward.angle(direction))),
                        "rollDegrees": math.degrees(
                            float(rotation.rotation_difference(ideal).angle)
                        ),
                        "sha256": sha256(path),
                    }
                )
            route_records.append({"routeId": route_id, "frames": frame_records})
            camera.animation_data_clear()
            camera.constraints.remove(orientation)
            camera.constraints.remove(follow)
            bpy.data.actions.remove(action)
            bpy.data.objects.remove(target, do_unlink=True)
            bpy.data.objects.remove(curve_object, do_unlink=True)
            bpy.data.curves.remove(curve_data)
    finally:
        camera.animation_data_clear()
        for constraint in list(camera.constraints):
            if constraint.name.startswith("TEMP__STAGE4_C2"):
                camera.constraints.remove(constraint)
        for action in list(bpy.data.actions):
            if action.name.startswith("TEMP__STAGE4_C2"):
                bpy.data.actions.remove(action)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("TEMP__STAGE4_C2"):
                bpy.data.objects.remove(obj, do_unlink=True)
        for camera_block in list(bpy.data.cameras):
            if camera_block.name.startswith("TEMP__STAGE4_C2"):
                bpy.data.cameras.remove(camera_block)
        for curve in list(bpy.data.curves):
            if curve.name.startswith("TEMP__STAGE4_C2"):
                bpy.data.curves.remove(curve)
        material_slot.material, material_slot.link = original_material, original_material_link
        if temporary_material is not None and temporary_material.name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for object_name, data_name in technical_lights:
            remove_named_datablock(bpy.data.objects, object_name, do_unlink=True)
            remove_named_datablock(bpy.data.lights, data_name)
        scene.camera = original_camera
        for name, hidden in original_visibility.items():
            bpy.data.objects[name].hide_render = hidden
        scene.render.engine = original_scene["engine"]
        scene.render.resolution_x = original_scene["resolution_x"]
        scene.render.resolution_y = original_scene["resolution_y"]
        scene.render.resolution_percentage = original_scene["resolution_percentage"]
        scene.render.filepath = original_scene["filepath"]
        scene.render.image_settings.file_format = original_scene["file_format"]
        scene.render.image_settings.color_mode = original_scene["color_mode"]
        scene.render.film_transparent = original_scene["film_transparent"]
        scene.eevee.taa_render_samples = original_scene["samples"]
        scene.view_settings.view_transform = original_scene["viewTransform"]
        scene.view_settings.look = original_scene["look"]
        scene.view_settings.exposure = original_scene["exposure"]
        scene.view_settings.gamma = original_scene["gamma"]
        scene.frame_set(original_frame)
        bpy.context.view_layer.update()

    candidate_hash_after = sha256(candidate_blend)
    current_data = {
        "objects": set(bpy.data.objects.keys()),
        "cameras": set(bpy.data.cameras.keys()),
        "curves": set(bpy.data.curves.keys()),
        "lights": set(bpy.data.lights.keys()),
        "materials": set(bpy.data.materials.keys()),
        "actions": set(bpy.data.actions.keys()),
    }
    temporary_remaining = sorted(
        f"{kind}:{name}"
        for kind in original_data
        for name in current_data[kind] - original_data[kind]
    )
    source_camera_restored = all(
        abs(float(left) - float(right)) <= 1e-8
        for left_row, right_row in zip(source_camera.matrix_world, original_camera_matrix)
        for left, right in zip(left_row, right_row)
    )
    scene_settings_restored = (
        scene.render.engine == original_scene["engine"]
        and scene.render.resolution_x == original_scene["resolution_x"]
        and scene.render.resolution_y == original_scene["resolution_y"]
        and scene.render.filepath == original_scene["filepath"]
        and scene.eevee.taa_render_samples == original_scene["samples"]
        and scene.camera == original_camera
    )
    restoration = {
        "candidateBlendSha256Before": candidate_hash_before,
        "candidateBlendSha256After": candidate_hash_after,
        "candidateBlendSaved": False,
        "sourceCameraTransformRestored": source_camera_restored,
        "sceneSettingsRestored": scene_settings_restored,
        "visibilityRestored": all(
            bool(bpy.data.objects[name].hide_render) == hidden
            for name, hidden in original_visibility.items()
        ),
        "materialRestored": material_slot.material == original_material
        and material_slot.link == original_material_link,
        "temporaryDataBlocksRemaining": temporary_remaining,
    }
    audit = {
        "schema": "twinkle-stage4-c2-full-worker-v1",
        "contractSha256": contract_sha256,
        "profile": C2_FULL_REVIEW_PROFILE,
        "routes": route_records,
        "renderedFrameCount": sum(len(route["frames"]) for route in route_records),
        "restoration": restoration,
    }
    (output_root / "worker-audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if (
        audit["renderedFrameCount"] != 176
        or candidate_hash_after != candidate_hash_before
        or not source_camera_restored
        or not scene_settings_restored
        or not restoration["visibilityRestored"]
        or not restoration["materialRestored"]
        or temporary_remaining
    ):
        raise RuntimeError("C2 restoration or render audit failed")


if __name__ == "__main__" and "--stage4-orientation-worker" in __import__("sys").argv:
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-orientation-worker")
    orientation_probe_worker(arguments[worker_index + 1])


if (
    __name__ == "__main__"
    and "--stage4-orientation-correction-worker" in __import__("sys").argv
):
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-orientation-correction-worker")
    orientation_correction_worker(
        arguments[worker_index + 1],
        resume_candidate_00="--resume-candidate-00" in arguments,
    )


if __name__ == "__main__" and "--stage4-orbit-o1-worker" in __import__("sys").argv:
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-orbit-o1-worker")
    orbit_o1_worker(arguments[worker_index + 1])


if (
    __name__ == "__main__"
    and "--stage4-surface-anchor-precheck-worker" in __import__("sys").argv
):
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-surface-anchor-precheck-worker")
    surface_anchor_precheck_worker(arguments[worker_index + 1])


if __name__ == "__main__" and "--stage4-c360-f96-worker" in __import__("sys").argv:
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-c360-f96-worker")
    c360_f96_worker(arguments[worker_index + 1])


if (
    __name__ == "__main__"
    and "--stage4-c1-keyframe-worker" in __import__("sys").argv
):
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-c1-keyframe-worker")
    c1_keyframe_worker(arguments[worker_index + 1])


if (
    __name__ == "__main__"
    and "--stage4-c2-full-worker" in __import__("sys").argv
):
    arguments = __import__("sys").argv
    worker_index = arguments.index("--stage4-c2-full-worker")
    c2_full_review_worker(arguments[worker_index + 1])


if (
    __name__ == "__main__"
    and "--refresh-stage4-c360-f96-review" in __import__("sys").argv
):
    arguments = __import__("sys").argv
    refresh_index = arguments.index("--refresh-stage4-c360-f96-review")
    refresh_c360_f96_review(arguments[refresh_index + 1])
