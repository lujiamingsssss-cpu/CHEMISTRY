"""Build the isolated TWINKLE Stage 5 entry-count evaluation pilot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import statistics
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

UNITS = (
    "dual_channel_collection_optics_chamber",
    "dual_channel_condenser_lens_assembly",
)
UNIT_NAMES = {
    UNITS[0]: "双通道采集光学舱",
    UNITS[1]: "聚光镜组件",
}
ENTRY_COUNTS = (3, 4, 5)
AUTHORITY_FRAME_COUNT = 96
DISPLAY_FRAME_COUNT = 192
ORBIT_DURATION_MS = 8_000
AUTHORITY_ANGLE_STEP_DEGREES = 3.75
DISPLAY_ANGLE_STEP_DEGREES = 1.875
FIXED_FPS = 24
MAXIMUM_TURN_DURATION_MS = 2_000
MAXIMUM_ANGULAR_SPEED_DEGREES_PER_SECOND = 90.0
ACCELERATION_RAMP_MS = 250
DECELERATION_RAMP_MS = 250
SETTLED_HOLD_MS = 100
CLICK_DRAG_THRESHOLD_PX = 6
HOTSPOT_SPEED_FACTOR = 0.30
APPROVED_A192_MANIFEST_SHA256 = (
    "0AD45675F90BA19CE9F7D60AF6C1ECF6E5437BC559BF6BD4C34412AA8FFB53E4"
)


class EntryCountValidationError(ValueError):
    """Raised when an authority or isolated output violates the evaluation scope."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _json_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise EntryCountValidationError(f"cannot import authority module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_output_root(repo: Path, output_root: Path) -> Path:
    expected = (Path(repo).resolve() / "output/twinkle-stage5-entry-count-pilot").resolve()
    actual = Path(output_root).resolve()
    if actual != expected:
        raise EntryCountValidationError(
            f"entry-count pilot output must be exactly {expected}"
        )
    return actual


def load_authority(repo: Path) -> dict:
    repo = Path(repo).resolve()
    fixed = _load_module(
        repo / "scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py",
        "twinkle_entry_count_fixed_authority",
    )
    normalized = fixed.load_authority(repo)
    registry = json.loads(
        (repo / "registry/twinkle/stage5-runtime-assets.json").read_text(
            encoding="utf-8"
        )
    )
    c360_record = next(
        record for record in registry["authorities"] if record["id"] == "stage4-c360"
    )
    c360_path = repo / c360_record["copyPath"]
    if sha256(c360_path) != normalized["c360ManifestSha256"]:
        raise EntryCountValidationError("C360 authority hash drift")
    c360 = json.loads(c360_path.read_text(encoding="utf-8"))
    if c360["orbitProfile"] != normalized["orbitProfile"]:
        raise EntryCountValidationError("C360 navigation contract drift")

    summaries = c360["qualificationByUnit"]
    source_frames = {
        int(record["physicalFrameIndex"]): record for record in c360["frames"]
    }
    frames = {}
    for index in range(AUTHORITY_FRAME_COUNT):
        base = normalized["frames"][index]
        source = source_frames[index]
        unit_records = {}
        for unit in UNITS:
            qualification = dict(source["qualificationByUnit"][unit])
            recognizability = next(
                dict(record)
                for record in summaries[unit]["componentRecognizabilityRecords"]
                if int(record["physicalFrameIndex"]) == index
            )
            visible = qualification["status"] == "visible"
            unit_records[unit] = {
                "semanticId": unit,
                "status": qualification["status"],
                "visible": visible,
                "eligible": visible and qualification["machineQualified"] is True,
                "machineQualified": qualification["machineQualified"],
                "projection": [float(value) for value in qualification["projection"]],
                "facingDot": float(qualification["facingDot"]),
                "unoccluded": qualification["unoccluded"],
                "projectionSafe": qualification["projectionSafe"],
                "componentRecognizability": recognizability,
            }
        frames[index] = {
            "authorityFrameIndex": index,
            "sourceAuthorityIndex": index,
            "authorityKind": "stage4-integer",
            "angleDegrees": float(source["azimuthDegrees"]),
            "path": base["path"],
            "sha256": base["sha256"],
            "bytes": base["bytes"],
            "units": unit_records,
        }
    return {
        "repo": repo,
        "registrySha256": normalized["registrySha256"],
        "c360ManifestSha256": normalized["c360ManifestSha256"],
        "hotspotAuthority": "stage4-c360-f96-integer-frames-only",
        "orbitProfile": normalized["orbitProfile"],
        "frames": frames,
        "unitSummaries": summaries,
        "humanApprovedEntryFrames": {
            unit: [int(value) for value in summaries[unit]["initialEntryFrameSet"]]
            for unit in UNITS
        },
    }


def load_a192_display(repo: Path) -> dict:
    repo = Path(repo).resolve()
    path = repo / "output/twinkle-stage5-a192-full-sequence/a192-manifest.json"
    if not path.is_file():
        raise EntryCountValidationError("approved A/192 display manifest is missing")
    manifest_sha = sha256(path)
    if manifest_sha != APPROVED_A192_MANIFEST_SHA256:
        raise EntryCountValidationError("approved A/192 manifest hash drift")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    frames = manifest.get("frames", [])
    if (
        len(frames) != DISPLAY_FRAME_COUNT
        or manifest.get("hotspotRule")
        != "midpoint-holds-previous-authority-without-projection-interpolation"
        or manifest.get("homepageHotspotMappingAuthorized") is not False
    ):
        raise EntryCountValidationError("A/192 display-only contract drift")
    if [record.get("sequenceIndex") for record in frames] != list(
        range(DISPLAY_FRAME_COUNT)
    ):
        raise EntryCountValidationError("A/192 sequence index drift")
    authority_records = [record for record in frames if record.get("kind") == "authority"]
    if (
        len(authority_records) != AUTHORITY_FRAME_COUNT
        or [record.get("sourceAuthorityIndex") for record in authority_records]
        != list(range(AUTHORITY_FRAME_COUNT))
    ):
        raise EntryCountValidationError("A/192 authority interleave drift")
    output_root = path.parent
    for record in frames:
        frame_path = output_root / record["src"]
        if (
            not frame_path.is_file()
            or frame_path.stat().st_size != int(record["bytes"])
            or sha256(frame_path) != record["sha256"]
        ):
            raise EntryCountValidationError(
                f"approved A/192 frame drift: {record['sequenceIndex']:03d}"
            )
    return {"path": path, "sha256": manifest_sha, "manifest": manifest}


def cyclic_distance(left: int, right: int) -> int:
    distance = abs(int(left) - int(right))
    return min(distance, AUTHORITY_FRAME_COUNT - distance)


def shortest_turn(
    current_frame: int, entry_frames: list[int] | tuple[int, ...], orbit_direction: str
) -> dict:
    if orbit_direction not in {"forward", "backward"}:
        raise EntryCountValidationError("orbit direction must be forward or backward")
    plans = []
    for entry in sorted(int(value) for value in entry_frames):
        forward = (entry - int(current_frame)) % AUTHORITY_FRAME_COUNT
        backward = (int(current_frame) - entry) % AUTHORITY_FRAME_COUNT
        if forward < backward:
            direction, distance = "forward", forward
        elif backward < forward:
            direction, distance = "backward", backward
        else:
            direction, distance = orbit_direction, forward
        plans.append(
            (distance, 0 if direction == orbit_direction else 1, entry, direction)
        )
    if not plans:
        raise EntryCountValidationError("entry set cannot be empty")
    distance, _, entry, direction = min(plans)
    profile = motion_profile(distance)
    return {
        "startFrame": int(current_frame),
        "selectedEntryFrame": entry,
        "direction": direction,
        "distanceFrames": distance,
        "distanceDegrees": profile["distanceDegrees"],
        "movementMs": profile["movementMs"],
        "turnDurationMs": profile["turnDurationMs"],
        "peakAngularSpeedDegreesPerSecond": profile[
            "peakAngularSpeedDegreesPerSecond"
        ],
        "accelerationRampMs": profile["accelerationRampMs"],
        "decelerationRampMs": profile["decelerationRampMs"],
        "settledHoldMs": SETTLED_HOLD_MS,
        "arrivesStopped": True,
    }


def motion_profile(distance_frames: int) -> dict:
    distance_frames = int(distance_frames)
    if not 0 <= distance_frames <= AUTHORITY_FRAME_COUNT // 2:
        raise EntryCountValidationError("motion distance must be 0 through 48 frames")
    distance_degrees = distance_frames * AUTHORITY_ANGLE_STEP_DEGREES
    if distance_frames == 0:
        movement_ms = 0.0
        ramp_ms = 0.0
        peak = 0.0
    else:
        movement_ms = (
            distance_degrees
            / MAXIMUM_ANGULAR_SPEED_DEGREES_PER_SECOND
            * 1000
            + ACCELERATION_RAMP_MS
        )
        ramp_ms = min(float(ACCELERATION_RAMP_MS), movement_ms / 2)
        peak = min(
            MAXIMUM_ANGULAR_SPEED_DEGREES_PER_SECOND,
            distance_degrees / ((movement_ms - ramp_ms) / 1000),
        )
    return {
        "distanceFrames": distance_frames,
        "distanceDegrees": distance_degrees,
        "movementMs": movement_ms,
        "accelerationRampMs": ramp_ms,
        "decelerationRampMs": ramp_ms,
        "cruiseMs": max(0.0, movement_ms - 2 * ramp_ms),
        "peakAngularSpeedDegreesPerSecond": peak,
        "settledHoldMs": SETTLED_HOLD_MS,
        "turnDurationMs": int(round(movement_ms + SETTLED_HOLD_MS)),
    }


def motion_sample(profile: dict, elapsed_ms: float) -> dict:
    movement_ms = float(profile["movementMs"])
    distance_degrees = float(profile["distanceDegrees"])
    if movement_ms == 0:
        return {
            "elapsedMs": 0.0,
            "distanceDegrees": 0.0,
            "progress": 1.0,
            "speedDegreesPerSecond": 0.0,
        }
    elapsed_ms = min(movement_ms, max(0.0, float(elapsed_ms)))
    time_s = elapsed_ms / 1000
    ramp_s = float(profile["accelerationRampMs"]) / 1000
    movement_s = movement_ms / 1000
    cruise_s = float(profile["cruiseMs"]) / 1000
    peak = float(profile["peakAngularSpeedDegreesPerSecond"])
    if time_s < ramp_s:
        travelled = peak * (
            time_s / 2 - ramp_s / (2 * math.pi) * math.sin(math.pi * time_s / ramp_s)
        )
        speed = peak * (0.5 - 0.5 * math.cos(math.pi * time_s / ramp_s))
    elif time_s < ramp_s + cruise_s:
        travelled = peak * (ramp_s / 2 + time_s - ramp_s)
        speed = peak
    else:
        u = time_s - ramp_s - cruise_s
        travelled = peak * (
            ramp_s / 2
            + cruise_s
            + u / 2
            + ramp_s / (2 * math.pi) * math.sin(math.pi * u / ramp_s)
        )
        speed = peak * (0.5 + 0.5 * math.cos(math.pi * u / ramp_s))
    travelled = min(distance_degrees, max(0.0, travelled))
    return {
        "elapsedMs": elapsed_ms,
        "distanceDegrees": travelled,
        "progress": travelled / distance_degrees,
        "speedDegreesPerSecond": max(0.0, speed),
    }


def _wait_evaluation(entry_frames: tuple[int, ...]) -> tuple[list[dict], dict]:
    starts = [
        shortest_turn(current, entry_frames, "forward")
        for current in range(AUTHORITY_FRAME_COUNT)
    ]
    distances = [record["distanceFrames"] for record in starts]
    ordered = sorted(distances)
    worst = max(distances)
    worst_cases = [record for record in starts if record["distanceFrames"] == worst]
    metrics = {
        "sampleCount": AUTHORITY_FRAME_COUNT,
        "worstFrameDistance": worst,
        "averageFrameDistance": sum(distances) / AUTHORITY_FRAME_COUNT,
        "medianFrameDistance": statistics.median(distances),
        "p95FrameDistance": ordered[math.ceil(0.95 * AUTHORITY_FRAME_COUNT) - 1],
        "worstTurnAngleDegrees": worst * AUTHORITY_ANGLE_STEP_DEGREES,
        "worstTurnTimeMs": max(record["turnDurationMs"] for record in starts),
        "worstCases": worst_cases,
    }
    return starts, metrics


def _interval_contains(frame: int, interval: dict) -> bool:
    start, end = int(interval["start"]), int(interval["end"])
    if interval.get("wraps"):
        return frame >= start or frame <= end
    return start <= frame <= end


def _boundary_distance(frame: int, intervals: list[dict]) -> int:
    containing = [interval for interval in intervals if _interval_contains(frame, interval)]
    if not containing:
        raise EntryCountValidationError("candidate is outside visible interval")
    return min(
        min(cyclic_distance(frame, int(interval["start"])), cyclic_distance(frame, int(interval["end"])))
        for interval in containing
    )


def _normalize_intervals(value: object) -> list[dict]:
    if isinstance(value, dict):
        return [dict(value)]
    return [dict(item) for item in value]


def _ranking(
    entry_frames: tuple[int, ...], intervals: list[dict], authority: dict, unit: str
) -> tuple:
    _, metrics = _wait_evaluation(entry_frames)
    minimum_boundary = min(_boundary_distance(frame, intervals) for frame in entry_frames)
    facing_total = sum(
        authority["frames"][frame]["units"][unit]["facingDot"]
        for frame in entry_frames
    )
    return (
        metrics["worstFrameDistance"],
        metrics["p95FrameDistance"],
        metrics["averageFrameDistance"],
        metrics["medianFrameDistance"],
        -minimum_boundary,
        -facing_total,
        entry_frames,
    )


def _select_nested_candidates(authority: dict, unit: str) -> dict[int, tuple[int, ...]]:
    summary = authority["unitSummaries"][unit]
    intervals = _normalize_intervals(summary["machineQualifiedCyclicIntervals"])
    pool = tuple(int(value) for value in summary["componentRecognizabilityQualifiedFrames"])
    seed = tuple(sorted(authority["humanApprovedEntryFrames"][unit]))
    if any(frame not in pool for frame in seed):
        raise EntryCountValidationError("approved seed entry failed recognizability gate")
    selected = seed
    result = {}
    for count in ENTRY_COUNTS:
        additions = count - len(selected)
        if additions != 1:
            raise EntryCountValidationError("entry candidates must grow one frame at a time")
        options = [
            tuple(sorted(selected + addition))
            for addition in itertools.combinations(
                [frame for frame in pool if frame not in selected], additions
            )
        ]
        if not options:
            raise EntryCountValidationError(
                f"96-frame authority cannot supply {count} entries for {unit}"
            )
        selected = min(
            options,
            key=lambda entries: _ranking(entries, intervals, authority, unit),
        )
        result[count] = selected
    return result


def _spacing(entries: tuple[int, ...]) -> list[int]:
    ordered = sorted(entries)
    return [
        (ordered[(index + 1) % len(ordered)] - frame) % AUTHORITY_FRAME_COUNT
        for index, frame in enumerate(ordered)
    ]


def _entry_record(
    authority: dict, unit: str, frame: int, intervals: list[dict]
) -> dict:
    record = authority["frames"][frame]
    detail = record["units"][unit]
    boundary_distance = _boundary_distance(frame, intervals)
    if boundary_distance == 0:
        boundary_safety = "boundary"
    elif boundary_distance <= 2:
        boundary_safety = "near-boundary"
    else:
        boundary_safety = "interior"
    return {
        "semanticId": unit,
        "authorityFrameIndex": frame,
        "angleDegrees": record["angleDegrees"],
        "status": detail["status"],
        "visible": detail["visible"],
        "eligible": detail["eligible"],
        "machineQualified": detail["machineQualified"],
        "projection": detail["projection"],
        "facingDot": detail["facingDot"],
        "unoccluded": detail["unoccluded"],
        "projectionSafe": detail["projectionSafe"],
        "distanceToVisibleHiddenBoundaryFrames": boundary_distance,
        "distanceToVisibleHiddenBoundaryDegrees": (
            boundary_distance * AUTHORITY_ANGLE_STEP_DEGREES
        ),
        "boundarySafety": boundary_safety,
        "componentRecognizability": detail["componentRecognizability"],
    }


def _candidate_record(
    authority: dict, unit: str, count: int, entries: tuple[int, ...]
) -> dict:
    summary = authority["unitSummaries"][unit]
    intervals = _normalize_intervals(summary["machineQualifiedCyclicIntervals"])
    starts, metrics = _wait_evaluation(entries)
    entry_records = [_entry_record(authority, unit, frame, intervals) for frame in entries]
    passed = (
        metrics["worstTurnTimeMs"] <= MAXIMUM_TURN_DURATION_MS
        and all(record["eligible"] for record in entry_records)
        and all(
            record["componentRecognizability"]["gatePassed"]
            for record in entry_records
        )
    )
    return {
        "entryCount": count,
        "entryFrames": list(entries),
        "entries": entry_records,
        "starts": starts,
        "waitMetrics": metrics,
        "cyclicSpacingFrames": _spacing(entries),
        "cyclicSpacingDegrees": [
            value * AUTHORITY_ANGLE_STEP_DEGREES for value in _spacing(entries)
        ],
        "concentratedInSingleVisibleInterval": len(intervals) == 1,
        "boundaryEntryFrames": [
            record["authorityFrameIndex"]
            for record in entry_records
            if record["boundarySafety"] == "boundary"
        ],
        "nearBoundaryEntryFrames": [
            record["authorityFrameIndex"]
            for record in entry_records
            if record["boundarySafety"] == "near-boundary"
        ],
        "motionConstraintsPassed": passed,
        "reviewEligible": passed,
        "officiallySelected": False,
        "focusRouteGenerated": False,
    }


def _marginal(before: dict, after: dict) -> dict:
    left, right = before["waitMetrics"], after["waitMetrics"]
    return {
        "fromEntryCount": before["entryCount"],
        "toEntryCount": after["entryCount"],
        "addedEntryFrames": sorted(set(after["entryFrames"]) - set(before["entryFrames"])),
        "waitReductionsFrames": {
            "worst": left["worstFrameDistance"] - right["worstFrameDistance"],
            "average": left["averageFrameDistance"] - right["averageFrameDistance"],
            "median": left["medianFrameDistance"] - right["medianFrameDistance"],
            "p95": left["p95FrameDistance"] - right["p95FrameDistance"],
        },
        "worstTurnTimeReductionMs": (
            left["worstTurnTimeMs"] - right["worstTurnTimeMs"]
        ),
        "stateComplexityDelta": {
            "entryStates": 1,
            "entrySpecificTestCases": AUTHORITY_FRAME_COUNT,
            "futureFocusRoutes": 1,
        },
    }


def build_manifest(authority: dict, display: dict) -> dict:
    units = {}
    for unit in UNITS:
        summary = authority["unitSummaries"][unit]
        intervals = _normalize_intervals(summary["machineQualifiedCyclicIntervals"])
        nested = _select_nested_candidates(authority, unit)
        candidates = {
            str(count): _candidate_record(authority, unit, count, nested[count])
            for count in ENTRY_COUNTS
        }
        if not all(candidate["motionConstraintsPassed"] for candidate in candidates.values()):
            raise EntryCountValidationError(
                f"96-frame authority cannot satisfy fixed turn constraints for {unit}"
            )
        units[unit] = {
            "semanticId": unit,
            "displayNameZh": UNIT_NAMES[unit],
            "visibleIntervals": intervals,
            "statusCounts": summary["statusCounts"],
            "candidateAuthorityFrames": [
                int(value) for value in summary["componentRecognizabilityQualifiedFrames"]
            ],
            "recognizabilityThresholds": summary[
                "componentRecognizabilityThresholds"
            ],
            "stage4ApprovedSeedEntries": authority["humanApprovedEntryFrames"][unit],
            "candidates": candidates,
            "marginalBenefits": {
                "3to4": _marginal(candidates["3"], candidates["4"]),
                "4to5": _marginal(candidates["4"], candidates["5"]),
            },
        }
    return {
        "schema": "twinkle-stage5-entry-count-pilot-v1",
        "scope": "isolated-3-4-5-overview-entry-count-evaluation-only",
        "evaluationOnly": True,
        "authority": {
            "registrySha256": authority["registrySha256"],
            "c360ManifestSha256": authority["c360ManifestSha256"],
            "a192DisplayManifestSha256": display["sha256"],
        },
        "authorityPolicy": {
            "entryAuthorityFrameCount": AUTHORITY_FRAME_COUNT,
            "entryAuthorityKinds": ["stage4-integer"],
            "midpointEntryAuthorized": False,
            "hotspotStatusInterpolation": False,
            "hotspotProjectionInterpolation": False,
            "secondHotspotAuthorityCreated": False,
        },
        "selectionPolicy": {
            "method": "nested-stepwise-exhaustive-fixed-metric-search",
            "seed": "stage4-human-approved-overview-entry-candidates",
            "growth": "one-authority-frame-per-count-step",
            "globalOptimalWithinCount": False,
            "rankingOrder": [
                "worstFrameDistance",
                "p95FrameDistance",
                "averageFrameDistance",
                "medianFrameDistance",
                "maximumBoundarySafety",
                "maximumFacingDotTotal",
                "lowestFrameTuple",
            ],
            "subjectiveComplexityScore": False,
        },
        "navigation": {
            "topology": "cyclic",
            "selection": "cyclic-shortest-turn",
            "tieBreak": "current-orbit-direction-then-lowest-entry-frame",
            "maximumTurnDurationMs": MAXIMUM_TURN_DURATION_MS,
            "maximumAngularSpeedDegreesPerSecond": MAXIMUM_ANGULAR_SPEED_DEGREES_PER_SECOND,
            "accelerationRampMs": ACCELERATION_RAMP_MS,
            "decelerationRampMs": DECELERATION_RAMP_MS,
            "settledHoldMs": SETTLED_HOLD_MS,
            "entersFocusAfterSettled": False,
        },
        "display": {
            "sequence": "A/192",
            "frameCount": DISPLAY_FRAME_COUNT,
            "durationMs": ORBIT_DURATION_MS,
            "fixedFps": FIXED_FPS,
            "angleStepDegrees": DISPLAY_ANGLE_STEP_DEGREES,
            "manifestPath": "../twinkle-stage5-a192-full-sequence/a192-manifest.json",
            "role": "visual-density-only",
        },
        "units": units,
        "officialSelection": None,
        "formalEntryCountSelected": False,
        "formalEntryFramesSelected": False,
        "focusRouteGenerated": False,
        "homepageIntegrationAuthorized": False,
    }


PILOT_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>TWINKLE 3/4/5 入口隔离评审</title><link rel="stylesheet" href="pilot.css"></head>
<body><header class="review-header"><div><p class="eyebrow">TWINKLE H2 · 隔离评估</p><h1>双通道组件 3 / 4 / 5 入口比较</h1><p>入口仅绑定 Stage 4 的 96 个权威整数帧；A/192 只提高显示密度，不进入聚焦路线。</p></div><div class="unit-tabs" role="tablist"><button type="button" data-unit="dual_channel_collection_optics_chamber" aria-selected="true">双通道采集光学舱</button><button type="button" data-unit="dual_channel_condenser_lens_assembly" aria-selected="false">聚光镜组件</button></div></header>
<main><section class="stage-panel"><div id="orbit-viewport" class="orbit-viewport" data-held="false"><img id="orbit-frame" alt="TWINKLE A/192 总览"><div id="hotspot-layer"><button class="hotspot chamber" data-hotspot-unit="dual_channel_collection_optics_chamber" type="button" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">双通道采集光学舱</span></button><button class="hotspot condenser" data-hotspot-unit="dual_channel_condenser_lens_assembly" type="button" hidden><span class="hotspot-pulse"></span><span class="hotspot-ring"></span><span class="hotspot-label">聚光镜组件</span></button></div><div class="stage-badges"><span id="frame-status">frame-000 · 0.00°</span><span id="motion-status">等待资源</span></div></div><div class="orbit-strip" aria-label="visible-boundary"><div id="visible-band"></div><div id="entry-markers"></div></div><div class="controls"><label>权威起始帧 <output id="start-output">000</output><input id="start-frame" type="range" min="0" max="95" value="0"></label><button id="simulate-turn" type="button">模拟最近入口</button><button id="worst-case" type="button">复现最坏案例</button></div><p class="scope-note">只模拟 overview exit/entry 转向与 100 ms 停稳；不进入真实聚焦路线。</p></section>
<section class="comparison-panel"><div class="count-switch" aria-label="candidate-comparison"><button type="button" data-entry-count="3" aria-pressed="true">3 个入口</button><button type="button" data-entry-count="4" aria-pressed="false">4 个入口</button><button type="button" data-entry-count="5" aria-pressed="false">5 个入口</button></div><div id="candidate-summary"></div><div id="entry-list" class="entry-list"></div><div id="metrics" class="metrics"></div><div id="marginal" class="marginal"></div></section></main>
<script src="pilot.js"></script></body></html>
'''


PILOT_CSS = r''':root{color-scheme:dark;--bg:#090d12;--panel:#111820;--line:rgba(255,255,255,.13);--text:#f4f7fa;--muted:#a9b5c2;--accent:#58d6ff;--amber:#ffbd59}*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}body{min-height:100vh;background:radial-gradient(circle at 50% -20%,#193244 0,transparent 44%),var(--bg)}button,input{font:inherit}.review-header{display:flex;align-items:end;justify-content:space-between;gap:24px;padding:24px clamp(18px,4vw,52px) 18px;border-bottom:1px solid var(--line)}h1{margin:2px 0 6px;font-size:clamp(22px,3vw,36px);line-height:1.12}.eyebrow{margin:0;color:var(--accent);font-size:11px;letter-spacing:.14em;text-transform:uppercase}.review-header p:last-child{margin:0;color:var(--muted)}.unit-tabs,.count-switch,.controls{display:flex;gap:8px;flex-wrap:wrap}.unit-tabs button,.count-switch button,.controls button{border:1px solid var(--line);border-radius:999px;background:#15202a;color:var(--muted);padding:9px 14px;cursor:pointer}.unit-tabs button[aria-selected="true"],.count-switch button[aria-pressed="true"]{border-color:var(--accent);background:#143344;color:#fff}main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(360px,.8fr);gap:18px;padding:18px clamp(18px,4vw,52px) 36px}.stage-panel,.comparison-panel{border:1px solid var(--line);border-radius:18px;background:rgba(17,24,32,.88);box-shadow:0 24px 70px rgba(0,0,0,.24);overflow:hidden}.orbit-viewport{position:relative;aspect-ratio:16/10;min-height:390px;overflow:hidden;touch-action:pan-y;user-select:none;cursor:grab;background:radial-gradient(circle at 50% 45%,#dce2e7 0,#8f979e 68%,#626970 100%)}.orbit-viewport[data-held="true"]{cursor:grabbing}.orbit-viewport img{display:block;width:100%;height:100%;object-fit:contain;pointer-events:none}.stage-badges{position:absolute;inset:14px 14px auto;display:flex;justify-content:space-between;gap:8px;pointer-events:none}.stage-badges span{padding:6px 9px;border-radius:7px;background:rgba(8,12,17,.76);font-size:11px}.hotspot[hidden]{display:none!important}.hotspot{position:absolute;width:30px;height:30px;transform:translate(-50%,-50%);border:0;background:transparent;color:#fff;padding:0;cursor:pointer;filter:drop-shadow(0 2px 6px #0008)}.hotspot-ring{position:absolute;inset:6px;border:1.5px solid currentColor;border-radius:50%;background:#0c0f125c}.hotspot-ring:after{content:"";position:absolute;inset:4px;border-radius:50%;background:currentColor}.hotspot-pulse{position:absolute;inset:3px;border:1px solid currentColor;border-radius:50%;animation:pulse 2.2s ease-out infinite}.hotspot-label{position:absolute;left:27px;top:50%;transform:translateY(-50%);padding:5px 9px;border:1px solid var(--line);border-radius:5px;background:#12161bc7;color:#fff;font-size:12px;font-weight:600;white-space:nowrap;pointer-events:none}@keyframes pulse{0%{transform:scale(.72);opacity:.6}75%,100%{transform:scale(1.35);opacity:0}}.orbit-strip{position:relative;height:32px;margin:14px 18px 4px;border:1px solid var(--line);border-radius:8px;background:#080c10;overflow:hidden}.visible-segment{position:absolute;top:5px;height:20px;border-radius:5px;background:#1d6681}.boundary{position:absolute;top:0;width:2px;height:100%;background:var(--amber)}.entry-marker{position:absolute;top:8px;width:8px;height:16px;transform:translateX(-50%);border-radius:3px;background:#fff}.controls{align-items:center;padding:14px 18px}.controls label{display:grid;grid-template-columns:auto 34px minmax(140px,1fr);align-items:center;gap:8px;flex:1;color:var(--muted)}.controls input{width:100%}.scope-note{margin:0;padding:0 18px 18px;color:var(--muted);font-size:12px}.comparison-panel{padding:18px}.count-switch{margin-bottom:16px}.summary-card,.metric-card,.entry-card,.marginal{border:1px solid var(--line);border-radius:12px;background:#0c1218;padding:12px}.entry-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin:12px 0}.entry-card strong{display:block;font-size:18px}.entry-card small{display:block;color:var(--muted)}.entry-card[data-boundary="boundary"]{border-color:#a9693c}.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.metric-card span{display:block;color:var(--muted);font-size:11px}.metric-card strong{font-size:18px}.marginal{margin-top:12px;color:var(--muted)}@media(max-width:900px){.review-header{align-items:stretch;flex-direction:column}.review-header .unit-tabs button{flex:1}main{grid-template-columns:1fr}.orbit-viewport{min-height:340px}.comparison-panel{min-height:420px}}@media(max-width:480px){main{padding:10px}.review-header{padding:16px}.orbit-viewport{min-height:300px;aspect-ratio:1/1}.metrics{grid-template-columns:1fr 1fr}.hotspot-label{font-size:11px}.orbit-viewport:has(.chamber:not([hidden])):has(.condenser:not([hidden])) .chamber .hotspot-label{transform:translateY(calc(-50% - 15px))}.orbit-viewport:has(.chamber:not([hidden])):has(.condenser:not([hidden])) .condenser .hotspot-label{transform:translateY(calc(-50% + 5px))}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
'''


PILOT_JS = r'''"use strict";
const AUTHORITY_FRAME_COUNT=96,DISPLAY_FRAME_COUNT=192,CLICK_DRAG_THRESHOLD_PX=6,HOTSPOT_SPEED_FACTOR=0.3,SEAM_CASE="095→000";
const reducedMotion=matchMedia("(prefers-reduced-motion: reduce)");
const viewport=document.querySelector("#orbit-viewport"),frameImage=document.querySelector("#orbit-frame"),startInput=document.querySelector("#start-frame"),startOutput=document.querySelector("#start-output"),frameStatus=document.querySelector("#frame-status"),motionStatus=document.querySelector("#motion-status");
const hotspotElements=new Map([...document.querySelectorAll("[data-hotspot-unit]")].map(element=>[element.dataset.hotspotUnit,element]));
const frameCache=new Map();
const state={manifest:null,a192:null,unit:"dual_channel_collection_optics_chamber",count:3,authorityPosition:0,displayedIndex:-1,orbitDirection:"forward",playing:true,turning:false,lastTimestamp:null,currentSpeedFactor:1,pointer:{activeId:null,held:false,dragging:false,startX:0,startY:0,startPosition:0,viewportWidth:1},events:[]};
function wrap(value,size){return((value%size)+size)%size}function authorityFrame(){return Math.floor(wrap(state.authorityPosition,AUTHORITY_FRAME_COUNT))}function currentCandidate(){return state.manifest.units[state.unit].candidates[String(state.count)]}function log(type,detail={}){state.events.push({type,time:performance.now(),...detail});if(state.events.length>500)state.events.shift()}
function cyclicShortestTurn(current,entries,direction){const plans=[];for(const entry of entries){const forward=wrap(entry-current,96),backward=wrap(current-entry,96);let turnDirection,distance;if(forward<backward){turnDirection="forward";distance=forward}else if(backward<forward){turnDirection="backward";distance=backward}else{turnDirection=direction;distance=forward}plans.push({entry,direction:turnDirection,distance})}plans.sort((a,b)=>a.distance-b.distance||((a.direction===direction?0:1)-(b.direction===direction?0:1))||a.entry-b.entry);return plans[0]}
function contentBox(){const box=viewport.getBoundingClientRect(),ratio=640/450;let width=box.width,height=width/ratio;if(height>box.height){height=box.height;width=height*ratio}return{left:(box.width-width)/2,top:(box.height-height)/2,width,height}}
function positionHotspots(displayIndex){const record=state.a192.frames[displayIndex],box=contentBox();for(const [unit,element]of hotspotElements){const hotspot=record.hotspots[unit],visible=hotspot.status==="visible"&&hotspot.eligible===true;element.hidden=!visible;element.disabled=!visible;element.setAttribute("aria-hidden",String(!visible));element.style.pointerEvents=visible?"auto":"none";element.style.left=(box.left+hotspot.projection[0]*box.width)+"px";element.style.top=(box.top+hotspot.projection[1]*box.height)+"px"}}
function render(force=false){if(!state.a192)return;const displayIndex=wrap(Math.round(state.authorityPosition*2),DISPLAY_FRAME_COUNT);if(!force&&displayIndex===state.displayedIndex)return;const record=state.a192.frames[displayIndex],cached=frameCache.get(displayIndex);frameImage.src=cached?.src||("../twinkle-stage5-a192-full-sequence/"+record.src);state.displayedIndex=displayIndex;const index=authorityFrame();positionHotspots(displayIndex);frameStatus.textContent=`frame-${String(index).padStart(3,"0")} · ${(state.authorityPosition*3.75).toFixed(2)}°`;document.body.dataset.frame=String(index);document.body.dataset.displayFrame=String(displayIndex);document.body.dataset.state=state.turning?"turning":"overview"}
function desiredSpeed(){if(state.pointer.held)return 0;if([...hotspotElements.values()].some(element=>element.matches(":hover,:focus")))return HOTSPOT_SPEED_FACTOR;return 1}
function animationLoop(now){if(state.lastTimestamp===null)state.lastTimestamp=now;const delta=Math.min(100,Math.max(0,now-state.lastTimestamp));state.lastTimestamp=now;state.currentSpeedFactor=desiredSpeed();if(state.playing&&!state.turning&&!reducedMotion.matches){state.authorityPosition=wrap(state.authorityPosition+delta*AUTHORITY_FRAME_COUNT/8000*state.currentSpeedFactor,AUTHORITY_FRAME_COUNT);render()}viewport.dataset.held=String(state.pointer.held);document.body.dataset.speedFactor=state.currentSpeedFactor.toFixed(3);requestAnimationFrame(animationLoop)}
function setStartFrame(frame){state.playing=false;state.turning=false;state.authorityPosition=wrap(Number(frame),96);startInput.value=String(authorityFrame());startOutput.value=String(authorityFrame()).padStart(3,"0");motionStatus.textContent="起点已设置";render(true);renderReview()}
function renderBands(){const root=document.querySelector("#visible-band"),markers=document.querySelector("#entry-markers");root.replaceChildren();markers.replaceChildren();for(const interval of state.manifest.units[state.unit].visibleIntervals){const segments=interval.wraps?[[interval.start,95],[0,interval.end]]:[[interval.start,interval.end]];for(const [start,end]of segments){const band=document.createElement("span");band.className="visible-segment";band.style.left=(start/96*100)+"%";band.style.width=((end-start+1)/96*100)+"%";root.append(band)}for(const value of[interval.start,interval.end]){const boundary=document.createElement("span");boundary.className="boundary";boundary.style.left=(value/96*100)+"%";root.append(boundary)}}for(const entry of currentCandidate().entryFrames){const marker=document.createElement("span");marker.className="entry-marker";marker.dataset.frame=String(entry);marker.style.left=(entry/96*100)+"%";markers.append(marker)}}
function metric(label,value){return`<div class="metric-card"><span>${label}</span><strong>${value}</strong></div>`}
function renderReview(){if(!state.manifest)return;const candidate=currentCandidate(),m=candidate.waitMetrics;document.querySelector("#candidate-summary").innerHTML=`<div class="summary-card"><strong>${state.manifest.units[state.unit].displayNameZh} · ${state.count} 入口</strong><div>权威帧 ${candidate.entryFrames.map(value=>String(value).padStart(3,"0")).join(" / ")}</div><small>全部 visible / eligible / 完整可辨识；正式选择：未作出</small></div>`;document.querySelector("#entry-list").innerHTML=candidate.entries.map(entry=>`<button class="entry-card" type="button" data-entry-frame="${entry.authorityFrameIndex}" data-boundary="${entry.boundarySafety}"><strong>${String(entry.authorityFrameIndex).padStart(3,"0")}</strong><small>${entry.angleDegrees.toFixed(2)}° · ${entry.status}</small><small>投影 ${(entry.projection[0]*100).toFixed(1)}%, ${(entry.projection[1]*100).toFixed(1)}%</small><small>边界距离 ${entry.distanceToVisibleHiddenBoundaryFrames} 帧 · ${entry.boundarySafety}</small></button>`).join("");document.querySelector("#metrics").innerHTML=metric("最坏帧距离",m.worstFrameDistance)+metric("平均帧距离",m.averageFrameDistance.toFixed(2))+metric("中位帧距离",m.medianFrameDistance.toFixed(2))+metric("95 分位",m.p95FrameDistance)+metric("最坏角度",m.worstTurnAngleDegrees.toFixed(2)+"°")+metric("最坏转向时间",m.worstTurnTimeMs+" ms");const unit=state.manifest.units[state.unit],key=state.count===3?"3to4":state.count===4?"4to5":null,benefit=key?unit.marginalBenefits[key]:unit.marginalBenefits["4to5"],complexity=benefit.stateComplexityDelta;document.querySelector("#marginal").textContent=key?`${key.replace("to","→")}：新增 frame-${String(benefit.addedEntryFrames[0]).padStart(3,"0")}；平均等待减少 ${benefit.waitReductionsFrames.average.toFixed(2)} 帧，中位减少 ${benefit.waitReductionsFrames.median.toFixed(2)} 帧，最坏减少 ${benefit.waitReductionsFrames.worst} 帧；同时增加 ${complexity.entryStates} 个入口状态、${complexity.entrySpecificTestCases} 个入口专属起点案例及未来 ${complexity.futureFocusRoutes} 条聚焦路线。`:`4→5 已显示于上一档；5 入口额外增加 1 个状态、96 个入口专属起点案例及未来 1 条聚焦路线。`;renderBands();document.querySelectorAll("[data-entry-frame]").forEach(button=>button.addEventListener("click",()=>setStartFrame(Number(button.dataset.entryFrame))))}
function selectUnit(unit){state.unit=unit;document.querySelectorAll("[data-unit]").forEach(button=>button.setAttribute("aria-selected",String(button.dataset.unit===unit)));renderReview();log("unit-selected",{unit})}function selectCount(count){state.count=Number(count);document.querySelectorAll("[data-entry-count]").forEach(button=>button.setAttribute("aria-pressed",String(Number(button.dataset.entryCount)===state.count)));renderReview();log("count-selected",{count:state.count})}
function motionProfile(distanceFrames){const distanceDegrees=distanceFrames*3.75;if(distanceFrames===0)return{distanceFrames,distanceDegrees,movementMs:0,rampMs:0,cruiseMs:0,peakSpeed:0,totalMs:100};const movementMs=distanceDegrees/90*1000+250,rampMs=Math.min(250,movementMs/2),cruiseMs=Math.max(0,movementMs-2*rampMs),peakSpeed=Math.min(90,distanceDegrees/((movementMs-rampMs)/1000));return{distanceFrames,distanceDegrees,movementMs,rampMs,cruiseMs,peakSpeed,totalMs:Math.round(movementMs+100)}}
function motionProgress(profile,elapsedMs){if(profile.movementMs===0)return{progress:1,distanceDegrees:0,speedDegreesPerSecond:0};const elapsed=Math.min(profile.movementMs,Math.max(0,elapsedMs)),time=elapsed/1000,ramp=profile.rampMs/1000,cruise=profile.cruiseMs/1000,peak=profile.peakSpeed;let travelled,speed;if(time<ramp){travelled=peak*(time/2-ramp/(2*Math.PI)*Math.sin(Math.PI*time/ramp));speed=peak*(.5-.5*Math.cos(Math.PI*time/ramp))}else if(time<ramp+cruise){travelled=peak*(ramp/2+time-ramp);speed=peak}else{const u=time-ramp-cruise;travelled=peak*(ramp/2+cruise+u/2+ramp/(2*Math.PI)*Math.sin(Math.PI*u/ramp));speed=peak*(.5+.5*Math.cos(Math.PI*u/ramp))}travelled=Math.min(profile.distanceDegrees,Math.max(0,travelled));return{progress:travelled/profile.distanceDegrees,distanceDegrees:travelled,speedDegreesPerSecond:Math.max(0,speed)}}
function simulateTurn(startOverride=null){if(state.turning)return Promise.resolve(null);if(startOverride!==null)setStartFrame(startOverride);state.playing=false;const current=authorityFrame(),candidate=currentCandidate(),plan=cyclicShortestTurn(current,candidate.entryFrames,state.orbitDirection),profile=motionProfile(plan.distance),startPosition=state.authorityPosition,startTime=performance.now(),direction=plan.direction==="forward"?1:-1;state.turning=true;state.orbitDirection=plan.direction;motionStatus.textContent=`转向 frame-${String(plan.entry).padStart(3,"0")} · ${profile.totalMs} ms`;log("turn-start",{start:current,...plan,profile});return new Promise(resolve=>{function finish(){state.authorityPosition=plan.entry;render(true);document.body.dataset.state="settling";motionStatus.textContent="入口已到达 · 停稳 100 ms";setTimeout(()=>{state.turning=false;document.body.dataset.state="entry-ready";motionStatus.textContent=`入口 frame-${String(plan.entry).padStart(3,"0")} 已停稳 · 不进入聚焦`;const actualElapsedMs=performance.now()-startTime;log("turn-complete",{...plan,profile,actualElapsedMs});resolve({...plan,totalMs:profile.totalMs,profile,actualElapsedMs})},100)}function step(now){if(reducedMotion.matches||profile.movementMs===0){finish();return}const sample=motionProgress(profile,now-startTime);state.authorityPosition=wrap(startPosition+direction*sample.distanceDegrees/3.75,96);render(true);if(sample.progress<1){requestAnimationFrame(step)}else finish()}requestAnimationFrame(step)})}
function jumpToWorst(){const worst=currentCandidate().waitMetrics.worstCases[0];setStartFrame(worst.startFrame);motionStatus.textContent=`最坏案例 frame-${String(worst.startFrame).padStart(3,"0")} → ${String(worst.selectedEntryFrame).padStart(3,"0")}`;return worst}
function onPointerDown(event){if(event.button !== 0||event.isPrimary===false||state.pointer.activeId!==null)return;state.pointer.activeId=event.pointerId;state.pointer.held=true;state.pointer.dragging=false;state.pointer.startX=event.clientX;state.pointer.startY=event.clientY;state.pointer.startPosition=state.authorityPosition;state.pointer.viewportWidth=Math.max(1,viewport.getBoundingClientRect().width);viewport.setPointerCapture(event.pointerId);log("pointer-captured",{pointerId:event.pointerId})}function onPointerMove(event){if(event.pointerId!==state.pointer.activeId||!state.pointer.held)return;const dx=event.clientX-state.pointer.startX,dy=event.clientY-state.pointer.startY;if(!state.pointer.dragging&&Math.hypot(dx,dy)>CLICK_DRAG_THRESHOLD_PX){state.pointer.dragging=true;state.playing=false;log("drag-start",{dx,dy})}if(!state.pointer.dragging)return;event.preventDefault();state.authorityPosition=wrap(state.pointer.startPosition-dx/state.pointer.viewportWidth*96,96);render(true)}function finishPointer(event){if(event.pointerId!==state.pointer.activeId)return;const id=state.pointer.activeId;state.pointer.activeId=null;state.pointer.held=false;if(viewport.hasPointerCapture(id))viewport.releasePointerCapture(id);log("pointer-release",{pointerId:id,dragging:state.pointer.dragging});state.pointer.dragging=false}
viewport.addEventListener("pointerdown",onPointerDown);viewport.addEventListener("pointermove",onPointerMove);viewport.addEventListener("pointerup",finishPointer);viewport.addEventListener("pointercancel",finishPointer);viewport.addEventListener("lostpointercapture",event=>{if(event.pointerId===state.pointer.activeId){state.pointer.activeId=null;state.pointer.held=false;state.pointer.dragging=false}});startInput.addEventListener("input",()=>setStartFrame(startInput.value));document.querySelector("#simulate-turn").addEventListener("click",()=>simulateTurn());document.querySelector("#worst-case").addEventListener("click",jumpToWorst);document.querySelectorAll("[data-unit]").forEach(button=>button.addEventListener("click",()=>selectUnit(button.dataset.unit)));document.querySelectorAll("[data-entry-count]").forEach(button=>button.addEventListener("click",()=>selectCount(button.dataset.entryCount)));addEventListener("resize",()=>render(true));
function preloadFrame(record){return new Promise((resolve,reject)=>{const image=new Image();image.onload=async()=>{try{if(typeof image.decode==="function")await image.decode()}catch{}frameCache.set(record.sequenceIndex,image);resolve(image)};image.onerror=()=>reject(new Error("A/192 frame load failed: "+record.sequenceIndex));image.src="../twinkle-stage5-a192-full-sequence/"+record.src})}
Promise.all([fetch("entry-count-manifest.json").then(response=>{if(!response.ok)throw new Error("entry manifest "+response.status);return response.json()}),fetch("../twinkle-stage5-a192-full-sequence/a192-manifest.json").then(response=>{if(!response.ok)throw new Error("A/192 manifest "+response.status);return response.json()})]).then(async([manifest,a192])=>{if(manifest.officialSelection!==null||manifest.formalEntryCountSelected!==false||a192.frames.length!==192)throw new Error("evaluation boundary drift");state.manifest=manifest;state.a192=a192;motionStatus.textContent="正在解码 A/192";await Promise.all(a192.frames.map(preloadFrame));render(true);renderReview();motionStatus.textContent="A/192 已就绪 · 自动环绕";window.__twinkleEntryPilot={snapshot:()=>({unit:state.unit,count:state.count,authorityFrame:authorityFrame(),displayFrame:state.displayedIndex,speedFactor:state.currentSpeedFactor,held:state.pointer.held,dragging:state.pointer.dragging,turning:state.turning,bodyState:document.body.dataset.state,ready:Boolean(state.manifest&&state.a192&&frameCache.size===DISPLAY_FRAME_COUNT),decodedFrameCount:frameCache.size,displayedHotspots:state.a192.frames[state.displayedIndex]?.hotspots||null,candidateFrames:[...currentCandidate().entryFrames],motionText:motionStatus.textContent,seamCase:SEAM_CASE}),setStartFrame,selectUnit,selectCount,simulateTurn,jumpToWorst,cyclicShortestTurn,motionProfile,motionProgress,events:()=>state.events.map(record=>({...record}))};log("resources-ready",{displayFrames:a192.frames.length,decodedFrameCount:frameCache.size,seamCase:SEAM_CASE});requestAnimationFrame(animationLoop)}).catch(error=>{motionStatus.textContent="资源失败";console.error(error)});
'''


def assemble_pilot(output_root: Path, authority: dict, display: dict) -> dict:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(authority, display)
    manifest_path = output_root / "entry-count-manifest.json"
    _write_json(manifest_path, manifest)
    _write_text(output_root / "index.html", PILOT_HTML)
    _write_text(output_root / "pilot.css", PILOT_CSS)
    _write_text(output_root / "pilot.js", PILOT_JS)
    results = {
        "schema": "twinkle-stage5-entry-count-pilot-machine-results-v1",
        "manifestSha256": sha256(manifest_path),
        "manifestContractSha256": _json_sha(manifest),
        "unitCandidateFrames": {
            unit: {
                count: candidate["entryFrames"]
                for count, candidate in manifest["units"][unit]["candidates"].items()
            }
            for unit in UNITS
        },
        "allCandidatesReviewEligible": all(
            candidate["reviewEligible"]
            for unit in UNITS
            for candidate in manifest["units"][unit]["candidates"].values()
        ),
        "automaticSelectionMade": False,
        "formalWrites": 0,
        "generatedImageCount": 0,
        "blenderInvocations": 0,
        "ffmpegInvocations": 0,
        "focusRoutesGenerated": 0,
    }
    _write_json(output_root / "machine-results.json", results)
    return results


def build_pilot(repo: Path, output_root: Path) -> dict:
    repo = Path(repo).resolve()
    output_root = validate_output_root(repo, output_root)
    authority = load_authority(repo)
    display = load_a192_display(repo)
    return assemble_pilot(output_root, authority, display)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output_root = args.output_root or repo / "output/twinkle-stage5-entry-count-pilot"
    print(json.dumps(build_pilot(repo, output_root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
