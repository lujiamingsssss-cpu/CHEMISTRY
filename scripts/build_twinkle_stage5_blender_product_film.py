"""Build the isolated real-Blender TWINKLE product-film motion preview."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


EXPECTED_BLEND_SHA256 = "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
PREVIEW_FPS = 30
PREVIEW_RESOLUTION = (640, 450)
PREVIEW_FRAME_COUNT = 360
PREVIEW_DURATION_SECONDS = PREVIEW_FRAME_COUNT / PREVIEW_FPS
PREVIEW_SAMPLES = 16
PREVIEW_REVISION = "v2-from-scratch"
STORYBOARD_SAMPLES = 32
V2_EXPOSURE = -0.90
V2_FPS = 30
V2_FRAME_COUNT = 324
V2_DURATION_SECONDS = V2_FRAME_COUNT / V2_FPS
HERO_A192_CANDIDATES = (144, 148, 152)
HERO_A192_SELECTED = 148
HERO_LOCATION = (-0.096428074, 0.067317277, 0.881142139)
HERO_TARGET = (0.383089125, 0.618871093, 0.554803014)
FLOOR_BASE_COLOR = (0.002, 0.003, 0.005, 1.0)
FLOOR_ROUGHNESS = 0.78
FLOOR_IOR_LEVEL = 0.10
HIDE_STUDIO_FLOOR = True
STUDIO_LIGHTING = {
    "WS_Key_Softbox": (62.0, (0.88, 0.93, 1.0), "RECTANGLE", 0.44, 0.065, None),
    "WS_Fill_Softbox": (15.0, (0.68, 0.78, 1.0), "DISK", 0.36, 0.36, None),
    "WS_Rim_Light": (78.0, (0.55, 0.70, 1.0), "RECTANGLE", 0.48, 0.045, None),
    "WS_Front_Bounce": (1.8, (0.78, 0.84, 1.0), "DISK", 0.50, 0.50, None),
    "TEMP__TWINKLE_OPTIC_STRIP": (
        26.0,
        (0.78, 0.88, 1.0),
        "RECTANGLE",
        0.16,
        0.025,
        (0.055, 0.762, 0.712),
    ),
    "TEMP__TWINKLE_UNDERSIDE_STRIP": (
        48.0,
        (0.78, 0.86, 1.0),
        "RECTANGLE",
        0.25,
        0.040,
        (0.300, 0.500, 0.300),
    ),
}
V2_STUDIO_LIGHTING = {
    "WS_Key_Softbox": (9.0, (0.92, 0.95, 1.0), "RECTANGLE", 0.52, 0.12, None, 0.35),
    "WS_Fill_Softbox": (3.0, (0.78, 0.84, 0.92), "DISK", 0.48, 0.48, None, 1.0),
    "WS_Rim_Light": (58.0, (0.72, 0.82, 1.0), "RECTANGLE", 0.48, 0.045, None, 0.05),
    "WS_Front_Bounce": (1.0, (0.84, 0.88, 0.95), "DISK", 0.52, 0.52, None, 1.0),
    "TEMP__TWINKLE_V2_EDGE_STRIP": (64.0, (0.86, 0.92, 1.0), "RECTANGLE", 0.34, 0.028, (0.060, 0.770, 0.820), 0.0),
    "TEMP__TWINKLE_V2_UNDERSIDE": (18.0, (0.82, 0.88, 0.96), "RECTANGLE", 0.30, 0.065, (0.340, 0.470, 0.300), 0.0),
    "TEMP__TWINKLE_V2_BACKDROP_WASH": (0.5, (0.76, 0.84, 0.94), "RECTANGLE", 0.58, 0.34, (0.383, 0.730, 0.880), 1.0),
}
V2_BACKDROP = {
    "location": (0.383, 0.920, 0.650),
    "dimensions": (3.00, 2.00),
    "baseColor": (0.0012, 0.0018, 0.0026, 1.0),
    "emissionOnly": True,
    "emissionColor": (0.008, 0.012, 0.018, 1.0),
    "roughness": 0.78,
    "iorLevel": 0.12,
}


class FilmValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Shot:
    name: str
    start: int
    end_exclusive: int
    value: str


@dataclass(frozen=True)
class CameraState:
    location: tuple[float, float, float]
    target: tuple[float, float, float]
    lens_mm: float


@dataclass(frozen=True)
class StoryboardCandidate:
    name: str
    value: str
    match_to_next: str
    keyframes: tuple[CameraState, CameraState, CameraState]


@dataclass(frozen=True)
class HeroCandidate:
    state: CameraState
    subject_bounds: tuple[float, float, float, float]
    visible_subject_fraction: float


def _state(location, target, lens_mm):
    return CameraState(tuple(location), tuple(target), float(lens_mm))


STORYBOARD_CANDIDATES = (
    StoryboardCandidate(
        "shell-contour",
        "large outer silhouette, aperture identity, and grazing top edge",
        "rightward highlight travel and circular aperture",
        tuple(_state(p, (0.340, 0.620, 0.600), 58) for p in ((-0.019166659, 0.0297230875, 0.8655710695), (-0.018, 0.050, 0.850), (-0.016833341, 0.0702769125, 0.8344289305))),
    ),
    StoryboardCandidate(
        "front-cover-seam",
        "semicircular front cover, plate joint, and precision machining",
        "circular front cover echoes the next optical assembly",
        tuple(_state(p, (0.265, 0.645, 0.575), 75) for p in ((-0.120, 0.300, 0.680), (-0.105, 0.310, 0.685), (-0.090, 0.320, 0.690))),
    ),
    StoryboardCandidate(
        "top-optic-conditional",
        "authentic coated glass through the top aperture, only if readable",
        "centered circular form and matching highlight direction",
        tuple(_state(p, (0.285, 0.6223, 0.5854), 78) for p in ((0.100, 0.300, 0.880), (0.115, 0.310, 0.885), (0.130, 0.320, 0.890))),
    ),
    StoryboardCandidate(
        "underside-optic-conditional",
        "circular lower optical mount and layered precision structure",
        "circular form continues while scale remains stable",
        tuple(_state(p, (0.285227, 0.622304, 0.585193), 55) for p in ((0.390, 0.300, 0.360), (0.375, 0.285, 0.350), (0.360, 0.270, 0.340))),
    ),
    StoryboardCandidate(
        "dual-channel-interface",
        "two-channel connector geometry and central mounting interface",
        "rightward slide and long top edge lead into the hero",
        tuple(_state(p, (0.445, 0.620, 0.580), 55) for p in ((0.730, 0.156, 0.660), (0.720, 0.166, 0.665), (0.710, 0.176, 0.670))),
    ),
    StoryboardCandidate(
        "loop-bridge",
        "single readable medium silhouette returning to the opening pose",
        "identical target, lens, scale family, and motion direction at loop",
        (
            _state((-0.020333318, 0.009446175, 0.881142139), HERO_TARGET, 58),
            _state((-0.0197499885, 0.01958463125, 0.87335660425), (0.3615445625, 0.6194355465, 0.577401507), 58),
            _state((-0.019166659, 0.0297230875, 0.8655710695), (0.340, 0.620, 0.600), 58),
        ),
    ),
)


HERO_CANDIDATES = {
    144: HeroCandidate(
        _state((-0.164317831, 0.134625301, 0.881142139), HERO_TARGET, 58),
        (0.2160149609, 0.1506914841, 0.7825510969, 0.7131740266),
        1.0,
    ),
    148: HeroCandidate(
        _state((-0.096428074, 0.067317277, 0.881142139), HERO_TARGET, 58),
        (0.2065752012, 0.1585525735, 0.8122350490, 0.7054364893),
        1.0,
    ),
    152: HeroCandidate(
        _state((-0.020333318, 0.009446175, 0.881142139), HERO_TARGET, 58),
        (0.2027242749, 0.1684805287, 0.8383428926, 0.6962229988),
        1.0,
    ),
}


SELECTED_HERO_REVEAL = StoryboardCandidate(
    "hero-reveal-selected",
    "stable short dolly-out to the complete A/192 frame 152 hero",
    "same camera family continues into the single loop bridge",
    (
        _state((0.0119404774, 0.0582001684, 0.855035009), HERO_TARGET, 58),
        _state((-0.0041964203, 0.0338231717, 0.868088574), HERO_TARGET, 58),
        HERO_CANDIDATES[152].state,
    ),
)


V2_SHOTS = (
    Shot("shell-contour", 0, 72, "readable low-key silhouette and circular aperture"),
    Shot("underside-optic", 72, 144, "layered circular lower optical structure"),
    Shot("dual-channel-interface", 144, 207, "distinct two-channel connector geometry"),
    Shot("hero-reveal", 207, 288, "short dolly-out to complete A/192 frame 152"),
    Shot("loop-bridge", 288, 324, "single continuous bridge back to opening state"),
)


MICRO_CLIPS = (
    {
        "name": "edge-aperture",
        "value": "top circular aperture and authentic long machined edge",
        "frames": 45,
        "keyframes": (
            _state((0.070994134, 0.441450266, 0.716), (0.310, 0.642, 0.620), 110),
            _state((0.078494134, 0.435450266, 0.718), (0.310, 0.642, 0.620), 110),
            _state((0.085994134, 0.429450266, 0.720), (0.310, 0.642, 0.620), 110),
        ),
    },
    {
        "name": "machined-seam",
        "value": "real cover joint and machined edge without a plate-filling sweep",
        "frames": 45,
        "keyframes": (
            _state((0.089, 0.398, 0.708), (0.305, 0.650, 0.600), 115),
            _state((0.098, 0.398, 0.708), (0.314, 0.650, 0.600), 115),
            _state((0.107, 0.398, 0.708), (0.323, 0.650, 0.600), 115),
        ),
    },
    {
        "name": "underside-ring",
        "value": "layered circular lower optical-mechanical assembly",
        "frames": 48,
        "keyframes": (
            _state((0.37696595, 0.3609044, 0.35152105), (0.285227, 0.622304, 0.585193), 83),
            _state((0.38396595, 0.3659044, 0.35552105), (0.285227, 0.622304, 0.585193), 83),
            _state((0.39096595, 0.3709044, 0.35952105), (0.285227, 0.622304, 0.585193), 83),
        ),
    },
    {
        "name": "dual-interface",
        "value": "dual-channel connector region and its precision mounting boundary",
        "frames": 45,
        "keyframes": (
            _state((0.655696622, 0.415495562, 0.681639079), (0.435282414, 0.619698046, 0.58350977), 110),
            _state((0.665696622, 0.415495562, 0.681639079), (0.445282414, 0.619698046, 0.58350977), 110),
            _state((0.675696622, 0.415495562, 0.681639079), (0.455282414, 0.619698046, 0.58350977), 110),
        ),
    },
)


MOTION_REVISION_CLIPS = (
    {
        "name": "rolled-side-panel-surface-skimming-correction",
        "frames": 60,
        "lensMm": 100.0,
        "rollDegrees": -90.0,
        "pathPoints": (
            (0.080000000, 0.450000000, 0.585000000),
            (0.100000000, 0.450000000, 0.585000000),
            (0.120000000, 0.450000000, 0.585000000),
        ),
        "offsetKeys": ((1, 0.0), (60, 1.0)),
        "targetKeys": ((1, (0.380, 0.620, 0.580)), (60, (0.420, 0.620, 0.580))),
        "intent": "approved ninety-degree rolled full side-panel glide with fasteners",
    },
    {
        "name": "dual-interface-to-hero-continuous-correction",
        "frames": 150,
        "lensMm": 58.0,
        "pathPoints": (
            (0.551478952, 0.511995830, 0.635239806),
            HERO_CANDIDATES[152].state.location,
        ),
        "pathHandles": {
            "startRight": (0.525000000, 0.492000000, 0.648000000),
            "endLeft": (0.180000000, 0.150000000, 0.820000000),
        },
        "offsetKeys": ((1, 0.0), (150, 1.0)),
        "offsetBezierHandles": {
            "startRight": (110.0, 0.0),
            "endLeft": (140.0, 1.0),
        },
        "targetKeys": (
            (1, (0.435282414, 0.619698046, 0.583509770)),
            (150, HERO_TARGET),
        ),
        "targetBezierHandleFrames": (110.0, 140.0),
        "intent": "continuous dual-interface edge slide into paced pullback ending at A/192 frame 152",
    },
)

MOTION_REVISION_OUTPUT_DIR = "motion-correction-clips-v3"

DIP_TO_BLACK_OUTPUT_DIR = "dip-to-black-loop-v2"
DIP_TO_BLACK_LOOP = {
    "fadeInFrames": 12,
    "fadeOutFrames": 18,
    "heroFrameCount": 150,
    "fadeOutStartFrame": 132,
}
QUALITY_PREFLIGHT_CANDIDATES = (
    ("A", (640, 450), 64),
    ("B1", (1280, 900), 128),
    ("B2", (1280, 900), 256),
)
QUALITY_PREFLIGHT_FRAMES = (
    ("edge-aperture", 30, "micro"),
    ("rolled-side-panel-surface-skimming-correction", 30, "motion"),
    ("underside-ring", 24, "micro"),
    ("dual-interface-to-hero-continuous-correction", 60, "motion"),
)
QUALITY_B2_RESOLUTION = (1280, 900)
QUALITY_B2_SAMPLES = 256
QUALITY_B2_FULL_CLIPS = (
    ("edge-aperture", 45, "micro"),
    ("rolled-side-panel-surface-skimming-correction", 60, "motion"),
    ("underside-ring", 48, "micro"),
    ("dual-interface-to-hero-continuous-correction", 150, "motion"),
)
QUALITY_B2_REVIEW_VIDEO = "b2-dip-to-black-loop-review.mp4"
QUALITY_B2_REVIEW_CONTACT_FRAMES = (
    0, 6, 11, 12, 30, 44,
    45, 75, 104, 105, 129, 152,
    153, 200, 240, 284, 294, 302,
)


def quality_b2_review_contract(review_root: Path) -> dict:
    review_root = Path(review_root)
    clips = []
    start_frame = 0
    for name, frame_count, _ in QUALITY_B2_FULL_CLIPS:
        clips.append({
            "name": name,
            "video": review_root / f"{name}.mp4",
            "startFrame": start_frame,
            "frameCount": frame_count,
        })
        start_frame += frame_count
    fade_out_start = clips[-1]["startFrame"] + DIP_TO_BLACK_LOOP["fadeOutStartFrame"]
    return {
        "clips": clips,
        "combinedVideo": review_root / QUALITY_B2_REVIEW_VIDEO,
        "combinedFrameCount": start_frame,
        "fadeIn": {
            "startFrame": 0,
            "frameCount": DIP_TO_BLACK_LOOP["fadeInFrames"],
            "firstFullFrame": DIP_TO_BLACK_LOOP["fadeInFrames"],
        },
        "fadeOut": {
            "startFrame": fade_out_start,
            "frameCount": DIP_TO_BLACK_LOOP["fadeOutFrames"],
            "lastFrame": start_frame - 1,
        },
    }


def validate_quality_b2_review_probes(contract: dict, probes: dict) -> None:
    expected = {item["video"].name: item["frameCount"] for item in contract["clips"]}
    expected[contract["combinedVideo"].name] = contract["combinedFrameCount"]
    for name, frame_count in expected.items():
        probe = probes.get(name)
        if probe is None:
            raise FilmValidationError(f"missing video probe: {name}")
        if probe.get("nb_frames") != frame_count:
            label = "combined frame count" if name == contract["combinedVideo"].name else f"clip frame count: {name}"
            raise FilmValidationError(f"{label} drift")
        if (probe.get("width"), probe.get("height")) != QUALITY_B2_RESOLUTION:
            raise FilmValidationError(f"video resolution drift: {name}")
        if probe.get("r_frame_rate") != "30/1" or probe.get("avg_frame_rate") != "30/1":
            raise FilmValidationError(f"video frame rate drift: {name}")
        if probe.get("codec_name") != "h264" or probe.get("pix_fmt") != "yuv420p":
            raise FilmValidationError(f"video encoding drift: {name}")
        if abs(float(probe.get("duration", -1)) - frame_count / V2_FPS) > 0.001:
            raise FilmValidationError(f"video duration drift: {name}")


def quality_b2_review_sequence_checks(contract: dict) -> tuple:
    checks = []
    sample_frames = (30, 30, 24, 60)
    for item, local_frame in zip(contract["clips"], sample_frames):
        checks.append((item["name"], local_frame, item["startFrame"] + local_frame))
    checks.extend((
        ("fade-in-complete", contract["fadeIn"]["firstFullFrame"], contract["fadeIn"]["firstFullFrame"]),
        (
            "fade-out-start",
            DIP_TO_BLACK_LOOP["fadeOutStartFrame"],
            contract["fadeOut"]["startFrame"],
        ),
    ))
    return tuple(checks)


def parse_quality_b2_video_probe(output: str) -> dict:
    payload = json.loads(output)
    streams = payload.get("streams", [])
    if len(streams) != 1 or "format" not in payload:
        raise FilmValidationError("ffprobe did not return exactly one video stream")
    stream = streams[0]
    container = payload["format"]
    try:
        return {
            "codec_name": stream["codec_name"],
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "pix_fmt": stream["pix_fmt"],
            "r_frame_rate": stream["r_frame_rate"],
            "avg_frame_rate": stream["avg_frame_rate"],
            "nb_frames": int(stream["nb_frames"]),
            "duration": float(container["duration"]),
            "bytes": int(container["size"]),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise FilmValidationError("incomplete ffprobe result") from error


def parse_quality_b2_ssim(output: str) -> float:
    match = re.search(r"\bAll:([0-9]+(?:\.[0-9]+)?)", output)
    if match is None:
        raise FilmValidationError("missing FFmpeg SSIM result")
    return float(match.group(1))


def parse_quality_b2_signalstats(output: str) -> dict[int, float]:
    values = {}
    for match in re.finditer(
        r"pts_time:([0-9]+(?:\.[0-9]+)?).*?lavfi\.signalstats\.YAVG=([0-9]+(?:\.[0-9]+)?)",
        output,
        re.DOTALL,
    ):
        values[round(float(match.group(1)) * V2_FPS)] = float(match.group(2))
    if not values:
        raise FilmValidationError("missing FFmpeg signalstats result")
    return values


def parse_quality_b2_ssim(output: str) -> float:
    matches = re.findall(r"\bAll:([0-9.]+)", output)
    if len(matches) != 1:
        raise FilmValidationError("ffmpeg SSIM result missing or ambiguous")
    return float(matches[0])


def parse_quality_b2_signalstats(output: str) -> dict:
    result = {}
    current_frame = None
    for line in output.splitlines():
        pts_match = re.search(r"\bpts_time:([0-9.]+)", line)
        if pts_match:
            current_frame = round(float(pts_match.group(1)) * V2_FPS)
        yavg_match = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", line)
        if yavg_match and current_frame is not None:
            result[current_frame] = float(yavg_match.group(1))
            current_frame = None
    if not result:
        raise FilmValidationError("ffmpeg signalstats result missing")
    return result


def storyboard_items():
    labels = ("start", "mid", "end")
    items = []
    for candidate in STORYBOARD_CANDIDATES + (SELECTED_HERO_REVEAL,):
        items.extend((candidate.name, label, state) for label, state in zip(labels, candidate.keyframes))
    return items


def crop_safe(subject_bounds, source_aspect, target_aspect):
    min_x, min_y, max_x, max_y = (float(value) for value in subject_bounds)
    source_aspect = float(source_aspect)
    target_aspect = float(target_aspect)
    if target_aspect >= source_aspect:
        visible_height = source_aspect / target_aspect
        visible = (0.0, 0.5 - visible_height / 2.0, 1.0, 0.5 + visible_height / 2.0)
    else:
        visible_width = target_aspect / source_aspect
        visible = (0.5 - visible_width / 2.0, 0.0, 0.5 + visible_width / 2.0, 1.0)
    return min_x >= visible[0] and min_y >= visible[1] and max_x <= visible[2] and max_y <= visible[3]


def frame_metrics(path: Path, near_black_threshold: int = 20) -> dict:
    from PIL import Image
    import numpy as np

    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    luma = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    return {
        "nearBlackFraction": float((luma <= near_black_threshold).mean()),
        "meanLuma": float(luma.mean()),
        "p10Luma": float(np.percentile(luma, 10)),
        "p25Luma": float(np.percentile(luma, 25)),
    }


def sequence_metrics(frame_paths, cut_indices, near_black_threshold=20) -> dict:
    from PIL import Image
    import numpy as np

    rows = []
    arrays = []
    previous = None
    for index, path in enumerate(frame_paths):
        rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
        arrays.append(rgb)
        row = {"frame": index, **frame_metrics(path, near_black_threshold)}
        row["adjacentMeanAbsDiff"] = None if previous is None else float(np.abs(rgb - previous).mean())
        rows.append(row)
        previous = rgb
    cuts = []
    for index in cut_indices:
        before, after = rows[index - 1], rows[index]
        cuts.append({
            "frame": int(index),
            "meanLumaDelta": after["meanLuma"] - before["meanLuma"],
            "p10LumaDelta": after["p10Luma"] - before["p10Luma"],
            "p25LumaDelta": after["p25Luma"] - before["p25Luma"],
            "nearBlackDelta": after["nearBlackFraction"] - before["nearBlackFraction"],
            "meanAbsDiff": after["adjacentMeanAbsDiff"],
        })
    loop_diff = float(np.abs(arrays[0] - arrays[-1]).mean())
    adjacent = [row["adjacentMeanAbsDiff"] for row in rows[1:]]
    return {
        "nearBlackThreshold": int(near_black_threshold),
        "frames": rows,
        "cuts": cuts,
        "loop": {
            "meanLumaDelta": rows[0]["meanLuma"] - rows[-1]["meanLuma"],
            "p10LumaDelta": rows[0]["p10Luma"] - rows[-1]["p10Luma"],
            "p25LumaDelta": rows[0]["p25Luma"] - rows[-1]["p25Luma"],
            "nearBlackDelta": rows[0]["nearBlackFraction"] - rows[-1]["nearBlackFraction"],
            "meanAbsDiff": loop_diff,
        },
        "summary": {
            "frameCount": len(rows),
            "meanLumaRange": [min(row["meanLuma"] for row in rows), max(row["meanLuma"] for row in rows)],
            "nearBlackRange": [min(row["nearBlackFraction"] for row in rows), max(row["nearBlackFraction"] for row in rows)],
            "adjacentDiffP95": float(np.percentile(adjacent, 95)),
            "adjacentDiffMax": max(adjacent),
        },
    }


def require_blender_result(completed, result_path: Path, started_at_ns: int | None = None) -> dict:
    result_path = Path(result_path)
    if completed.returncode != 0:
        raise FilmValidationError(f"Blender worker failed with exit code {completed.returncode}")
    if not result_path.is_file():
        raise FilmValidationError("missing worker result despite Blender exit status")
    if started_at_ns is not None and result_path.stat().st_mtime_ns < started_at_ns:
        raise FilmValidationError("stale worker result despite Blender exit status")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("sourceRestored") is not True:
        raise FilmValidationError("Blender worker did not restore source state")
    return result


SHOTS = (
    Shot("dark-shell-loop", 0, 60, "near-black exterior silhouette and grazing edge"),
    Shot("machined-seam", 60, 120, "cover plate, joint, and machined face"),
    Shot("blue-optic", 120, 192, "circular optic and authentic coated surface"),
    Shot("dual-channel-interface", 192, 246, "distinct dual-channel connection region"),
    Shot("hero-reveal", 246, 324, "complete instrument arriving at A/192 frame 148"),
    Shot("dark-bridge-loop", 324, 360, "real-model dark bridge back to opening"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _lerp(left, right, amount):
    return tuple(float(a + (b - a) * amount) for a, b in zip(left, right))


def _smoothstep(value):
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def _shot_amount(frame, start, end_exclusive):
    return _smoothstep((frame - start) / (end_exclusive - start - 1))


def _quadratic_state(keyframes, amount):
    start, control, end = keyframes
    inverse = 1.0 - amount

    def curve(left, middle, right):
        return tuple(
            inverse * inverse * a + 2.0 * inverse * amount * b + amount * amount * c
            for a, b, c in zip(left, middle, right)
        )

    return CameraState(
        curve(start.location, control.location, end.location),
        curve(start.target, control.target, end.target),
        inverse * inverse * start.lens_mm + 2.0 * inverse * amount * control.lens_mm + amount * amount * end.lens_mm,
    )


def v2_camera_state(frame: int) -> CameraState:
    if frame == V2_FRAME_COUNT:
        return v2_camera_state(0)
    if not 0 <= frame < V2_FRAME_COUNT:
        raise FilmValidationError(f"frame outside V2 preview timeline: {frame}")
    candidates = {candidate.name: candidate for candidate in STORYBOARD_CANDIDATES}
    keyframes_by_shot = {
        "shell-contour": candidates["shell-contour"].keyframes,
        "underside-optic": candidates["underside-optic-conditional"].keyframes,
        "dual-channel-interface": candidates["dual-channel-interface"].keyframes,
        "hero-reveal": SELECTED_HERO_REVEAL.keyframes,
        "loop-bridge": candidates["loop-bridge"].keyframes,
    }
    shot = next(item for item in V2_SHOTS if item.start <= frame < item.end_exclusive)
    amount = (frame - shot.start) / (shot.end_exclusive - shot.start)
    if shot.name not in {"shell-contour", "loop-bridge"}:
        amount = _smoothstep(amount)
    return _quadratic_state(keyframes_by_shot[shot.name], amount)


def _dark_loop_state(phase_frame: int) -> CameraState:
    target = (0.310, 0.642, 0.620)
    radius = 0.260
    angle = math.radians(-140.0 + phase_frame * 0.35)
    location = (
        target[0] + radius * math.cos(angle),
        target[1] + radius * math.sin(angle),
        target[2] + 0.080,
    )
    return CameraState(location, target, 92.0)


def camera_state(frame: int) -> CameraState:
    if frame == PREVIEW_FRAME_COUNT:
        return camera_state(0)
    if not 0 <= frame < PREVIEW_FRAME_COUNT:
        raise FilmValidationError(f"frame outside preview timeline: {frame}")
    if frame < 60:
        return _dark_loop_state(frame)
    if frame < 120:
        amount = _shot_amount(frame, 60, 120)
        return CameraState(
            _lerp((0.070, 0.425, 0.665), (0.125, 0.440, 0.690), amount),
            _lerp((0.245, 0.650, 0.585), (0.305, 0.650, 0.600), amount),
            96.0,
        )
    if frame < 192:
        amount = _shot_amount(frame, 120, 192)
        target = (0.285227, 0.622304, 0.585193)
        return CameraState(
            _lerp((0.365, 0.395, 0.382), (0.452, 0.455, 0.405), amount),
            target,
            72.0,
        )
    if frame < 246:
        amount = _shot_amount(frame, 192, 246)
        return CameraState(
            _lerp((0.625, 0.445, 0.660), (0.585, 0.475, 0.695), amount),
            _lerp((0.438, 0.620, 0.582), (0.420, 0.618, 0.592), amount),
            92.0,
        )
    if frame < 324:
        amount = _shot_amount(frame, 246, 324)
        start = _lerp(HERO_TARGET, HERO_LOCATION, 0.64)
        return CameraState(_lerp(start, HERO_LOCATION, amount), HERO_TARGET, 58.0)
    return _dark_loop_state(frame - PREVIEW_FRAME_COUNT)


def validate_output_root(repo: Path, output_root: Path) -> Path:
    repo = Path(repo).resolve()
    output_root = Path(output_root).resolve()
    expected = repo / "output" / "twinkle-stage5-blender-product-film"
    if output_root != expected:
        raise FilmValidationError(f"output must be dedicated product-film directory: {expected}")
    return output_root


def blender_command(
    blender: Path,
    source_blend: Path,
    output_root: Path,
    representative_only: bool = False,
) -> list[str]:
    command = [
        str(blender),
        "--background",
        str(source_blend),
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--worker-output",
        str(output_root),
        "--preview",
        "true",
    ]
    if representative_only:
        command.append("--representative-only")
    return command


def storyboard_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender),
        "--background",
        str(source_blend),
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--worker-output",
        str(output_root),
        "--storyboard-only",
    ]


def v2_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender),
        "--background",
        str(source_blend),
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--worker-output",
        str(output_root),
        "--v2-preview",
    ]


def micro_clips_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender), "--background", str(source_blend), "--python", str(Path(__file__).resolve()), "--",
        "--worker-output", str(output_root), "--micro-clips",
    ]


def motion_revision_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender), "--background", str(source_blend), "--python", str(Path(__file__).resolve()), "--",
        "--worker-output", str(output_root), "--motion-revision-clips",
    ]


def quality_preflight_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender), "--background", str(source_blend), "--python", str(Path(__file__).resolve()), "--",
        "--worker-output", str(output_root), "--quality-preflight",
    ]


def quality_b2_full_blender_command(blender: Path, source_blend: Path, output_root: Path) -> list[str]:
    return [
        str(blender), "--background", str(source_blend), "--python", str(Path(__file__).resolve()), "--",
        "--worker-output", str(output_root), "--quality-b2-full-render",
    ]


def dip_to_black_loop_ffmpeg_command(
    ffmpeg: str,
    shot_1: Path,
    shot_2: Path,
    shot_3: Path,
    shot_4: Path,
    output: Path,
) -> list[str]:
    fade_in = DIP_TO_BLACK_LOOP["fadeInFrames"]
    fade_out = DIP_TO_BLACK_LOOP["fadeOutFrames"]
    fade_out_start = DIP_TO_BLACK_LOOP["fadeOutStartFrame"]
    graph = (
        f"[0:v]fade=t=in:s=0:n={fade_in}:color=black,setpts=PTS-STARTPTS[v0];"
        "[1:v]setpts=PTS-STARTPTS[v1];"
        "[2:v]setpts=PTS-STARTPTS[v2];"
        f"[3:v]fade=t=out:s={fade_out_start}:n={fade_out}:color=black,setpts=PTS-STARTPTS[v3];"
        "[v0][v1][v2][v3]concat=n=4:v=1:a=0[v]"
    )
    command = [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error"]
    for path in (shot_1, shot_2, shot_3, shot_4):
        command.extend(("-i", str(path)))
    command.extend((
        "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
        "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
        "-an", str(output),
    ))
    return command


def prepare_dip_to_black_review_root(preview_v2_root: Path) -> Path:
    review_root = Path(preview_v2_root) / DIP_TO_BLACK_OUTPUT_DIR
    review_root.mkdir(parents=True, exist_ok=True)
    return review_root


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _configure_dark_studio(scene):
    import bpy
    from mathutils import Vector

    world = bpy.data.worlds.new("TEMP__TWINKLE_FILM_WORLD")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.0015, 0.0020, 0.0030, 1.0)
    background.inputs["Strength"].default_value = 0.015
    scene.world = world

    floor = bpy.data.objects.get("WS_Studio_Floor")
    if floor is not None:
        floor.hide_render = HIDE_STUDIO_FLOOR
        material = bpy.data.materials.new("TEMP__TWINKLE_FILM_FLOOR")
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        principled.inputs["Base Color"].default_value = FLOOR_BASE_COLOR
        principled.inputs["Roughness"].default_value = FLOOR_ROUGHNESS
        if "IOR Level" in principled.inputs:
            principled.inputs["IOR Level"].default_value = FLOOR_IOR_LEVEL
        floor.data.materials.clear()
        floor.data.materials.append(material)

    aim = Vector((0.383, 0.619, 0.585))
    for name, (energy, color, shape, size, size_y, location) in STUDIO_LIGHTING.items():
        obj = bpy.data.objects.get(name)
        if obj is None and name.startswith("TEMP__"):
            data = bpy.data.lights.new(name + "_DATA", "AREA")
            obj = bpy.data.objects.new(name, data)
            scene.collection.objects.link(obj)
        if obj is None or obj.type != "LIGHT":
            raise RuntimeError(f"missing authority light: {name}")
        if location is not None:
            obj.location = location
        obj.data.energy = energy
        obj.data.color = color
        obj.data.shape = shape
        obj.data.size = size
        if shape == "RECTANGLE":
            obj.data.size_y = size_y
        light_aim = Vector((0.285, 0.6223, 0.5854)) if name == "TEMP__TWINKLE_OPTIC_STRIP" else aim
        obj.rotation_euler = (light_aim - obj.location).to_track_quat("-Z", "Y").to_euler()


def _configure_v2_studio(scene):
    import bpy
    import math as blender_math
    from mathutils import Vector

    world = bpy.data.worlds.new("TEMP__TWINKLE_V2_WORLD")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.0025, 0.0035, 0.0055, 1.0)
    background.inputs["Strength"].default_value = 0.035
    scene.world = world
    floor = bpy.data.objects.get("WS_Studio_Floor")
    if floor is not None:
        floor.hide_render = True

    bpy.ops.mesh.primitive_plane_add(
        size=2.0,
        location=V2_BACKDROP["location"],
        rotation=(blender_math.pi / 2.0, 0.0, 0.0),
    )
    backdrop = bpy.context.object
    backdrop.name = "TEMP__TWINKLE_V2_GRAPHITE_BACKDROP"
    backdrop.scale = (
        V2_BACKDROP["dimensions"][0] / 2.0,
        V2_BACKDROP["dimensions"][1] / 2.0,
        1.0,
    )
    backdrop_material = bpy.data.materials.new("TEMP__TWINKLE_V2_GRAPHITE_BACKDROP_MATERIAL")
    backdrop_material.use_nodes = True
    principled = backdrop_material.node_tree.nodes.get("Principled BSDF")
    if V2_BACKDROP["emissionOnly"]:
        principled.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        principled.inputs["Roughness"].default_value = 1.0
        if "IOR Level" in principled.inputs:
            principled.inputs["IOR Level"].default_value = 0.0
        principled.inputs["Emission Color"].default_value = V2_BACKDROP["emissionColor"]
        principled.inputs["Emission Strength"].default_value = 1.0
    else:
        principled.inputs["Base Color"].default_value = V2_BACKDROP["baseColor"]
        principled.inputs["Roughness"].default_value = V2_BACKDROP["roughness"]
        if "IOR Level" in principled.inputs:
            principled.inputs["IOR Level"].default_value = V2_BACKDROP["iorLevel"]
    backdrop.data.materials.append(backdrop_material)

    general_aim = Vector((0.383, 0.619, 0.585))
    for name, (energy, color, shape, size, size_y, location, diffuse_factor) in V2_STUDIO_LIGHTING.items():
        obj = bpy.data.objects.get(name)
        if obj is None and name.startswith("TEMP__"):
            data = bpy.data.lights.new(name + "_DATA", "AREA")
            obj = bpy.data.objects.new(name, data)
            scene.collection.objects.link(obj)
        if obj is None or obj.type != "LIGHT":
            raise RuntimeError(f"missing V2 studio light: {name}")
        if location is not None:
            obj.location = location
        obj.data.energy = energy
        obj.data.color = color
        obj.data.shape = shape
        obj.data.size = size
        if hasattr(obj.data, "diffuse_factor"):
            obj.data.diffuse_factor = diffuse_factor
        if shape == "RECTANGLE":
            obj.data.size_y = size_y
        if "UNDERSIDE" in name:
            aim = Vector((0.285, 0.622, 0.585))
        elif "BACKDROP_WASH" in name:
            aim = Vector(V2_BACKDROP["location"])
        else:
            aim = general_aim
        obj.rotation_euler = (aim - obj.location).to_track_quat("-Z", "Y").to_euler()


def _prepare_preview_scene(scene, samples, exposure=-0.35):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = PREVIEW_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.fps = PREVIEW_FPS
    scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = exposure
    scene.view_settings.gamma = 1.0


def _temporary_camera(scene, name):
    source_camera = scene.camera
    camera_data = source_camera.data.copy()
    camera_data.name = name + "_DATA"
    camera = source_camera.copy()
    camera.name = name
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def _apply_camera_state(camera, state):
    from mathutils import Vector

    camera.location = Vector(state.location)
    camera.rotation_euler = (Vector(state.target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = state.lens_mm
    camera.data.sensor_width = 36.0
    camera.data.shift_x = 0.0
    camera.data.shift_y = 0.0
    camera.data.dof.use_dof = False


def _render_storyboard(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    camera = _temporary_camera(scene, "TEMP__TWINKLE_V2_STORYBOARD_CAMERA")
    _prepare_preview_scene(scene, STORYBOARD_SAMPLES, V2_EXPOSURE)
    _configure_v2_studio(scene)
    storyboard_root = output_root / "preview-v2" / "storyboard"
    storyboard_root.mkdir(parents=True, exist_ok=True)
    records = []
    for candidate_name, label, state in storyboard_items():
        _apply_camera_state(camera, state)
        bpy.context.view_layer.update()
        destination = storyboard_root / f"{candidate_name}--{label}.png"
        scene.render.filepath = str(destination)
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        records.append({
            "candidate": candidate_name,
            "keyframe": label,
            "path": destination.relative_to(output_root).as_posix(),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "elapsedSeconds": round(time.perf_counter() - started, 4),
            "camera": {"location": state.location, "target": state.target, "lensMm": state.lens_mm},
        })
    for frame, candidate in HERO_CANDIDATES.items():
        _apply_camera_state(camera, candidate.state)
        bpy.context.view_layer.update()
        destination = storyboard_root / f"hero-a192-{frame}.png"
        scene.render.filepath = str(destination)
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        records.append({
            "candidate": f"hero-a192-{frame}",
            "keyframe": "static",
            "path": destination.relative_to(output_root).as_posix(),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "elapsedSeconds": round(time.perf_counter() - started, 4),
            "camera": {"location": candidate.state.location, "target": candidate.state.target, "lensMm": candidate.state.lens_mm},
            "cropSafe1280x800": crop_safe(candidate.subject_bounds, 64 / 45, 1280 / 800),
            "cropSafe900x700": crop_safe(candidate.subject_bounds, 64 / 45, 900 / 700),
        })
    after = sha256(source)
    result = {
        "schema": "twinkle-real-blender-product-film-storyboard-v2",
        "revision": PREVIEW_REVISION,
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "render": {"engine": scene.render.engine, "resolution": PREVIEW_RESOLUTION, "fps": PREVIEW_FPS, "samples": STORYBOARD_SAMPLES},
        "records": records,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "work" / "storyboard-v2-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during V2 storyboard")
    return 0


def _render_v2_preview(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    camera = _temporary_camera(scene, "TEMP__TWINKLE_V2_PREVIEW_CAMERA")
    _prepare_preview_scene(scene, PREVIEW_SAMPLES, V2_EXPOSURE)
    _configure_v2_studio(scene)
    frames_root = output_root / "preview-v2" / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    records = []
    for frame in range(V2_FRAME_COUNT):
        state = v2_camera_state(frame)
        shot = next(item for item in V2_SHOTS if item.start <= frame < item.end_exclusive)
        _apply_camera_state(camera, state)
        bpy.context.view_layer.update()
        destination = frames_root / f"frame-{frame:03d}.png"
        scene.render.filepath = str(destination)
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        records.append({
            "frame": frame,
            "shot": shot.name,
            "path": destination.relative_to(output_root).as_posix(),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "elapsedSeconds": round(time.perf_counter() - started, 4),
            "camera": {"location": state.location, "target": state.target, "lensMm": state.lens_mm},
        })
    after = sha256(source)
    result = {
        "schema": "twinkle-real-blender-product-film-preview-v2",
        "revision": PREVIEW_REVISION,
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "render": {"engine": scene.render.engine, "resolution": PREVIEW_RESOLUTION, "fps": V2_FPS, "samples": PREVIEW_SAMPLES},
        "frameCount": V2_FRAME_COUNT,
        "durationSeconds": V2_DURATION_SECONDS,
        "shots": [shot.__dict__ for shot in V2_SHOTS],
        "heroA192Frame": 152,
        "frames": records,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "work" / "preview-v2-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during V2 preview")
    return 0


def _render_micro_clips(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    camera = _temporary_camera(scene, "TEMP__TWINKLE_MICRO_CLIPS_CAMERA")
    _prepare_preview_scene(scene, 64, V2_EXPOSURE)
    _configure_v2_studio(scene)
    records = []
    for clip in MICRO_CLIPS:
        frames_root = output_root / "preview-v2" / "micro-clips" / clip["name"] / "frames"
        frames_root.mkdir(parents=True, exist_ok=True)
        for frame in range(clip["frames"]):
            amount = _smoothstep(frame / (clip["frames"] - 1))
            state = _quadratic_state(clip["keyframes"], amount)
            _apply_camera_state(camera, state)
            bpy.context.view_layer.update()
            destination = frames_root / f"frame-{frame:03d}.png"
            scene.render.filepath = str(destination)
            bpy.ops.render.render(write_still=True)
            records.append({
                "clip": clip["name"],
                "frame": frame,
                "path": destination.relative_to(output_root).as_posix(),
                "sha256": sha256(destination),
                "camera": {"location": state.location, "target": state.target, "lensMm": state.lens_mm},
            })
    after = sha256(source)
    result = {
        "schema": "twinkle-product-film-micro-clips-v1",
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "render": {"engine": scene.render.engine, "resolution": PREVIEW_RESOLUTION, "fps": 30, "samples": 64},
        "clips": [{"name": clip["name"], "value": clip["value"], "frameCount": clip["frames"]} for clip in MICRO_CLIPS],
        "frames": records,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "work" / "micro-clips-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during micro clips")
    return 0


def _create_native_motion_rig(scene, clip):
    import bpy

    camera = _temporary_camera(scene, f"TEMP__{clip['name']}_CAMERA")
    camera.parent = None
    camera.location = (0.0, 0.0, 0.0)
    camera.rotation_mode = "XYZ"
    camera.rotation_euler = (0.0, 0.0, 0.0)
    camera.data.lens = clip["lensMm"]
    camera.data.sensor_width = 36.0
    camera.data.dof.use_dof = False

    curve_data = bpy.data.curves.new(f"TEMP__{clip['name']}_CURVE_DATA", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 24
    curve_data.path_duration = clip["frames"]
    spline = curve_data.splines.new(type="BEZIER")
    spline.bezier_points.add(len(clip["pathPoints"]) - 1)
    for point, coordinate in zip(spline.bezier_points, clip["pathPoints"]):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    if "pathHandles" in clip:
        start = spline.bezier_points[0]
        end = spline.bezier_points[-1]
        start.handle_right_type = "FREE"
        start.handle_right = clip["pathHandles"]["startRight"]
        end.handle_left_type = "FREE"
        end.handle_left = clip["pathHandles"]["endLeft"]
    curve_object = bpy.data.objects.new(f"TEMP__{clip['name']}_CURVE", curve_data)
    scene.collection.objects.link(curve_object)

    target = bpy.data.objects.new(f"TEMP__{clip['name']}_TARGET", None)
    target.location = clip["targetKeys"][0][1]
    scene.collection.objects.link(target)
    motion_owner = camera
    if clip.get("rollDegrees"):
        motion_owner = bpy.data.objects.new(f"TEMP__{clip['name']}_ROLL_CARRIER", None)
        scene.collection.objects.link(motion_owner)
        camera.parent = motion_owner
        camera.location = (0.0, 0.0, 0.0)
        camera.rotation_euler = (0.0, 0.0, math.radians(float(clip["rollDegrees"])))
    follow = motion_owner.constraints.new(type="FOLLOW_PATH")
    follow.name = f"TEMP__{clip['name']}_FOLLOW_PATH"
    follow.target = curve_object
    follow.use_fixed_location = True
    follow.use_curve_follow = False
    orientation = motion_owner.constraints.new(type="TRACK_TO")
    orientation.name = f"TEMP__{clip['name']}_WORLD_UP_TRACK"
    orientation.target = target
    orientation.track_axis = "TRACK_NEGATIVE_Z"
    orientation.up_axis = "UP_Y"
    orientation.use_target_z = False

    def action_fcurves(owner, label):
        action = bpy.data.actions.new(f"TEMP__{clip['name']}_{label}_ACTION")
        slot = action.slots.new(owner.id_type, owner.name)
        strip = action.layers.new(label).strips.new(type="KEYFRAME")
        animation = owner.animation_data_create()
        animation.action = action
        animation.action_slot = slot
        return strip.channelbag(slot, ensure=True).fcurves

    camera_fcurves = action_fcurves(motion_owner, "Camera Path")
    offset_curve = camera_fcurves.new(data_path=f'constraints["{follow.name}"].offset_factor')
    offset_curve.keyframe_points.add(len(clip["offsetKeys"]))
    for point, (frame, value) in zip(offset_curve.keyframe_points, clip["offsetKeys"]):
        point.co = (float(frame), float(value))
        point.interpolation = "BEZIER"
        point.handle_left_type = "AUTO_CLAMPED"
        point.handle_right_type = "AUTO_CLAMPED"
    if "offsetBezierHandles" in clip:
        first = offset_curve.keyframe_points[0]
        last = offset_curve.keyframe_points[-1]
        first.handle_right_type = "FREE"
        first.handle_right = clip["offsetBezierHandles"]["startRight"]
        last.handle_left_type = "FREE"
        last.handle_left = clip["offsetBezierHandles"]["endLeft"]
    offset_curve.update()

    target_fcurves = action_fcurves(target, "Stable Target")
    for axis in range(3):
        curve = target_fcurves.new(data_path="location", index=axis)
        curve.keyframe_points.add(len(clip["targetKeys"]))
        for point, (frame, location) in zip(curve.keyframe_points, clip["targetKeys"]):
            point.co = (float(frame), float(location[axis]))
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
        if "targetBezierHandleFrames" in clip:
            first = curve.keyframe_points[0]
            last = curve.keyframe_points[-1]
            first.handle_right_type = "FREE"
            first.handle_right = (clip["targetBezierHandleFrames"][0], float(clip["targetKeys"][0][1][axis]))
            last.handle_left_type = "FREE"
            last.handle_left = (clip["targetBezierHandleFrames"][1], float(clip["targetKeys"][-1][1][axis]))
        curve.update()
    return camera, target, follow, orientation


def _render_motion_revision_clips(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    _prepare_preview_scene(scene, 64, V2_EXPOSURE)
    _configure_v2_studio(scene)
    clip_records = []
    for clip in MOTION_REVISION_CLIPS:
        camera, target, follow, orientation = _create_native_motion_rig(scene, clip)
        scene.camera = camera
        frames_root = output_root / "preview-v2" / MOTION_REVISION_OUTPUT_DIR / clip["name"] / "frames"
        frames_root.mkdir(parents=True, exist_ok=True)
        frame_records = []
        for frame in range(1, clip["frames"] + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            destination = frames_root / f"frame-{frame - 1:03d}.png"
            scene.render.filepath = str(destination)
            bpy.ops.render.render(write_still=True)
            frame_records.append({
                "frame": frame - 1,
                "path": destination.relative_to(output_root).as_posix(),
                "sha256": sha256(destination),
                "cameraLocation": tuple(float(value) for value in camera.matrix_world.translation),
                "cameraTarget": tuple(float(value) for value in target.location),
                "lensMm": float(camera.data.lens),
            })
        clip_records.append({
            "name": clip["name"],
            "intent": clip["intent"],
            "frameCount": clip["frames"],
            "lensMm": clip["lensMm"],
            "pathType": "native-bezier-follow-path",
            "orientationConstraint": orientation.type,
            "speedCurve": "BEZIER_AUTO_CLAMPED",
            "frames": frame_records,
        })
    after = sha256(source)
    result = {
        "schema": "twinkle-product-film-motion-correction-clips-v1",
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "render": {"engine": scene.render.engine, "resolution": PREVIEW_RESOLUTION, "fps": 30, "samples": 64},
        "frozen": False,
        "motionBlur": False,
        "productMaterialsModified": False,
        "clips": clip_records,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "work" / "motion-revision-clips-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during motion revision clips")
    return 0


def _render_quality_preflight(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    _prepare_preview_scene(scene, 64, V2_EXPOSURE)
    _configure_v2_studio(scene)

    micro_camera = _temporary_camera(scene, "TEMP__TWINKLE_QUALITY_PREFLIGHT_MICRO_CAMERA")
    micro_by_name = {clip["name"]: clip for clip in MICRO_CLIPS}
    motion_by_name = {clip["name"]: clip for clip in MOTION_REVISION_CLIPS}
    motion_rigs = {}
    for name, _, kind in QUALITY_PREFLIGHT_FRAMES:
        if kind == "motion" and name not in motion_rigs:
            camera, target, _, _ = _create_native_motion_rig(scene, motion_by_name[name])
            motion_rigs[name] = (camera, target)

    variants = []
    total_started = time.perf_counter()
    for variant, resolution, samples in QUALITY_PREFLIGHT_CANDIDATES:
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.eevee.taa_render_samples = samples
        variant_started = time.perf_counter()
        frames = []
        for name, frame, kind in QUALITY_PREFLIGHT_FRAMES:
            if kind == "micro":
                clip = micro_by_name[name]
                amount = _smoothstep(frame / (clip["frames"] - 1))
                state = _quadratic_state(clip["keyframes"], amount)
                scene.frame_set(1)
                scene.camera = micro_camera
                _apply_camera_state(micro_camera, state)
                target = state.target
                camera = micro_camera
            else:
                camera, target_object = motion_rigs[name]
                scene.frame_set(frame + 1)
                scene.camera = camera
                target = tuple(float(value) for value in target_object.location)
            bpy.context.view_layer.update()
            destination = output_root / variant / "full" / f"{name}--frame-{frame:03d}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(destination)
            started = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            elapsed = time.perf_counter() - started
            matrix = [[float(value) for value in row] for row in camera.matrix_world]
            frames.append({
                "clip": name,
                "frame": frame,
                "kind": kind,
                "path": destination.relative_to(output_root).as_posix(),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "elapsedSeconds": round(elapsed, 4),
                "camera": {
                    "object": camera.name,
                    "matrixWorld": matrix,
                    "location": tuple(float(value) for value in camera.matrix_world.translation),
                    "target": target,
                    "lensMm": float(camera.data.lens),
                },
            })
        variants.append({
            "name": variant,
            "resolution": resolution,
            "samples": samples,
            "elapsedSeconds": round(time.perf_counter() - variant_started, 4),
            "frames": frames,
        })
    after = sha256(source)
    result = {
        "schema": "twinkle-product-film-fixed-frame-quality-preflight-v1",
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "fixedState": "existing camera matrices, V2 studio lights, product materials, exposure, and AgX color management",
        "variants": variants,
        "totalElapsedSeconds": round(time.perf_counter() - total_started, 4),
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "render-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during quality preflight")
    return 0


def _render_quality_b2_full(output_root: Path) -> int:
    import bpy

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    _prepare_preview_scene(scene, QUALITY_B2_SAMPLES, V2_EXPOSURE)
    scene.render.resolution_x, scene.render.resolution_y = QUALITY_B2_RESOLUTION
    _configure_v2_studio(scene)

    micro_camera = _temporary_camera(scene, "TEMP__TWINKLE_QUALITY_B2_MICRO_CAMERA")
    micro_by_name = {clip["name"]: clip for clip in MICRO_CLIPS}
    motion_by_name = {clip["name"]: clip for clip in MOTION_REVISION_CLIPS}
    motion_rigs = {}
    for name, _, kind in QUALITY_B2_FULL_CLIPS:
        if kind == "motion":
            camera, target, _, _ = _create_native_motion_rig(scene, motion_by_name[name])
            motion_rigs[name] = (camera, target)

    total_frames = sum(frame_count for _, frame_count, _ in QUALITY_B2_FULL_CLIPS)
    completed_frames = 0
    clips = []
    total_started = time.perf_counter()
    for name, frame_count, kind in QUALITY_B2_FULL_CLIPS:
        clip_started = time.perf_counter()
        frames = []
        for frame in range(frame_count):
            if kind == "micro":
                clip = micro_by_name[name]
                amount = _smoothstep(frame / (clip["frames"] - 1))
                state = _quadratic_state(clip["keyframes"], amount)
                scene.frame_set(1)
                scene.camera = micro_camera
                _apply_camera_state(micro_camera, state)
                camera = micro_camera
                target = state.target
            else:
                camera, target_object = motion_rigs[name]
                scene.frame_set(frame + 1)
                scene.camera = camera
                target = tuple(float(value) for value in target_object.location)
            bpy.context.view_layer.update()
            destination = output_root / "frames" / name / f"frame-{frame:03d}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            scene.render.filepath = str(destination)
            started = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            elapsed = time.perf_counter() - started
            completed_frames += 1
            frames.append({
                "frame": frame,
                "path": destination.relative_to(output_root).as_posix(),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "elapsedSeconds": round(elapsed, 4),
                "camera": {
                    "matrixWorld": [[float(value) for value in row] for row in camera.matrix_world],
                    "location": tuple(float(value) for value in camera.matrix_world.translation),
                    "target": target,
                    "lensMm": float(camera.data.lens),
                },
            })
            _write_json(output_root / "render-progress.json", {
                "schema": "twinkle-product-film-quality-b2-render-progress-v1",
                "clip": name,
                "frame": frame,
                "completedFrames": completed_frames,
                "totalFrames": total_frames,
                "sourceBlendSha256": before,
            })
            print(f"B2_PROGRESS {completed_frames}/{total_frames} {name} frame-{frame:03d}", flush=True)
        clips.append({
            "name": name,
            "kind": kind,
            "frameCount": frame_count,
            "elapsedSeconds": round(time.perf_counter() - clip_started, 4),
            "frames": frames,
        })
    after = sha256(source)
    result = {
        "schema": "twinkle-product-film-quality-b2-full-render-v1",
        "blenderVersion": bpy.app.version_string,
        "render": {
            "engine": scene.render.engine,
            "resolution": QUALITY_B2_RESOLUTION,
            "samples": QUALITY_B2_SAMPLES,
            "fps": 30,
        },
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "fixedState": "approved existing cameras, motion curves, V2 studio, product materials, exposure, AgX, and edit contract",
        "frameCount": total_frames,
        "elapsedSeconds": round(time.perf_counter() - total_started, 4),
        "clips": clips,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "render-results.json", result)
    if before != after:
        raise RuntimeError("authority blend changed during B2 full render")
    return 0


def _render_worker(output_root: Path, representative_only: bool) -> int:
    import bpy
    from mathutils import Vector

    source = Path(bpy.data.filepath).resolve()
    before = sha256(source)
    if before != EXPECTED_BLEND_SHA256:
        raise RuntimeError("authority blend drift")
    scene = bpy.context.scene
    source_camera = scene.camera
    camera_data = source_camera.data.copy()
    camera_data.name = "TEMP__TWINKLE_FILM_CAMERA_DATA"
    camera = source_camera.copy()
    camera.name = "TEMP__TWINKLE_FILM_CAMERA"
    camera.data = camera_data
    camera.animation_data_clear()
    for constraint in list(camera.constraints):
        camera.constraints.remove(constraint)
    scene.collection.objects.link(camera)
    scene.camera = camera

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = PREVIEW_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.fps = PREVIEW_FPS
    scene.eevee.taa_render_samples = PREVIEW_SAMPLES
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -1.35
    scene.view_settings.gamma = 1.0
    _configure_dark_studio(scene)

    frames_root = output_root / "preview" / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    indices = [0, 59, 60, 119, 120, 191, 192, 245, 246, 323, 324, 359] if representative_only else list(range(PREVIEW_FRAME_COUNT))
    records = []
    for frame in indices:
        state = camera_state(frame)
        camera.location = Vector(state.location)
        camera.rotation_euler = (Vector(state.target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = state.lens_mm
        camera.data.sensor_width = 36.0
        camera.data.shift_x = 0.0
        camera.data.shift_y = 0.0
        camera.data.dof.use_dof = False
        bpy.context.view_layer.update()
        destination = frames_root / f"frame-{frame:03d}.png"
        scene.render.filepath = str(destination)
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        records.append(
            {
                "frame": frame,
                "shot": next(shot.name for shot in SHOTS if shot.start <= frame < shot.end_exclusive),
                "path": destination.relative_to(output_root).as_posix(),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "elapsedSeconds": round(time.perf_counter() - started, 4),
                "camera": {"location": state.location, "target": state.target, "lensMm": state.lens_mm},
            }
        )
    after = sha256(source)
    result = {
        "schema": "twinkle-real-blender-product-film-preview-v1",
        "representativeOnly": representative_only,
        "sourceBlend": {"path": str(source), "sha256Before": before, "sha256After": after},
        "render": {"engine": scene.render.engine, "resolution": PREVIEW_RESOLUTION, "fps": PREVIEW_FPS, "samples": PREVIEW_SAMPLES},
        "frames": records,
        "sourceRestored": before == after,
        "sceneSaved": False,
    }
    _write_json(output_root / "work" / ("representative-results.json" if representative_only else "preview-results.json"), result)
    if before != after:
        raise RuntimeError("authority blend changed during preview")
    return 0


def _encode_preview(output_root: Path, ffmpeg: str) -> dict:
    frames = output_root / "preview" / "frames" / "frame-%03d.png"
    video = output_root / "preview" / "twinkle-product-film-preview.mp4"
    poster = output_root / "preview" / "poster.png"
    shutil.copyfile(output_root / "preview" / "frames" / "frame-000.png", poster)
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(PREVIEW_FPS),
        "-i",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(PREVIEW_FPS),
        "-movflags",
        "+faststart",
        "-an",
        str(video),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise FilmValidationError(completed.stderr.strip() or "ffmpeg preview encoding failed")
    return {"path": str(video), "sha256": sha256(video), "bytes": video.stat().st_size, "command": command}


def build_preview(repo: Path, output_root: Path, blender: Path, source_blend: Path, ffmpeg: str, representative_only: bool) -> dict:
    output_root = validate_output_root(repo, output_root)
    if sha256(source_blend) != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    output_root.mkdir(parents=True, exist_ok=True)
    command = blender_command(blender, source_blend, output_root, representative_only)
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    _write_json(output_root / "evidence" / ("representative-blender-command.json" if representative_only else "preview-blender-command.json"), {
        "command": command,
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    })
    if completed.returncode != 0:
        raise FilmValidationError("Blender preview render failed")
    result = {"blenderExitCode": completed.returncode, "representativeOnly": representative_only}
    if not representative_only:
        result["video"] = _encode_preview(output_root, ffmpeg)
    return result


def build_storyboard(repo: Path, output_root: Path, blender: Path, source_blend: Path) -> dict:
    output_root = validate_output_root(repo, output_root)
    if sha256(source_blend) != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    output_root.mkdir(parents=True, exist_ok=True)
    command = storyboard_blender_command(blender, source_blend, output_root)
    started_at_ns = time.time_ns()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    _write_json(output_root / "evidence" / "storyboard-v2-blender-command.json", {
        "command": command,
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    })
    result_path = output_root / "work" / "storyboard-v2-results.json"
    worker_result = require_blender_result(completed, result_path, started_at_ns)
    for record in worker_result["records"]:
        record["metrics"] = frame_metrics(output_root / record["path"])
    _write_json(result_path, worker_result)
    return {"blenderExitCode": completed.returncode, "storyboardOnly": True}


def build_v2_preview(repo: Path, output_root: Path, blender: Path, source_blend: Path, ffmpeg: str) -> dict:
    output_root = validate_output_root(repo, output_root)
    if sha256(source_blend) != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    output_root.mkdir(parents=True, exist_ok=True)
    command = v2_blender_command(blender, source_blend, output_root)
    started_at_ns = time.time_ns()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    _write_json(output_root / "evidence" / "preview-v2-blender-command.json", {
        "command": command,
        "exitCode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    })
    result_path = output_root / "work" / "preview-v2-results.json"
    worker_result = require_blender_result(completed, result_path, started_at_ns)
    if len(worker_result.get("frames", [])) != V2_FRAME_COUNT:
        raise FilmValidationError("V2 worker frame count drift")
    frame_paths = [output_root / record["path"] for record in worker_result["frames"]]
    analysis = sequence_metrics(frame_paths, tuple(shot.start for shot in V2_SHOTS[1:]))
    for row, record in zip(analysis["frames"], worker_result["frames"]):
        row["shot"] = record["shot"]
    analysis["interpretationPolicy"] = "raw-curves-and-human-visual-review; no automatic artistic pass threshold"
    _write_json(output_root / "evidence" / "preview-v2-frame-analysis.json", analysis)

    video = output_root / "preview-v2" / "twinkle-product-film-preview-v2.mp4"
    poster = output_root / "preview-v2" / "poster-v2.png"
    shutil.copyfile(frame_paths[0], poster)
    encode = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(V2_FPS), "-i", str(output_root / "preview-v2" / "frames" / "frame-%03d.png"),
        "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
        "-r", str(V2_FPS), "-movflags", "+faststart", "-an", str(video),
    ]
    encoded = subprocess.run(encode, check=False, capture_output=True, text=True)
    if encoded.returncode != 0:
        raise FilmValidationError(encoded.stderr.strip() or "V2 preview encoding failed")
    manifest = {
        "schema": "twinkle-real-blender-product-film-preview-v2-delivery",
        "revision": PREVIEW_REVISION,
        "video": {"path": str(video), "sha256": sha256(video), "bytes": video.stat().st_size},
        "poster": {"path": str(poster), "sha256": sha256(poster), "bytes": poster.stat().st_size},
        "renderSource": str(result_path),
        "analysis": str(output_root / "evidence" / "preview-v2-frame-analysis.json"),
        "reviewStatus": "pending-first-human-visual-review",
    }
    _write_json(output_root / "preview-v2" / "preview-v2-manifest.json", manifest)
    return manifest


def build_micro_clips(repo: Path, output_root: Path, blender: Path, source_blend: Path, ffmpeg: str) -> dict:
    output_root = validate_output_root(repo, output_root)
    if sha256(source_blend) != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    command = micro_clips_blender_command(blender, source_blend, output_root)
    started_at_ns = time.time_ns()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    _write_json(output_root / "evidence" / "micro-clips-blender-command.json", {
        "command": command, "exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
    })
    result_path = output_root / "work" / "micro-clips-results.json"
    worker = require_blender_result(completed, result_path, started_at_ns)
    deliveries = []
    for clip in worker["clips"]:
        clip_root = output_root / "preview-v2" / "micro-clips" / clip["name"]
        video = clip_root / f"{clip['name']}.mp4"
        encode = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", "30",
            "-i", str(clip_root / "frames" / "frame-%03d.png"), "-c:v", "libx264",
            "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30",
            "-movflags", "+faststart", "-an", str(video),
        ]
        encoded = subprocess.run(encode, check=False, capture_output=True, text=True)
        if encoded.returncode != 0:
            raise FilmValidationError(encoded.stderr.strip() or f"micro clip encoding failed: {clip['name']}")
        deliveries.append({
            **clip, "video": str(video), "sha256": sha256(video), "bytes": video.stat().st_size,
            "durationSeconds": clip["frameCount"] / 30,
        })
    manifest = {
        "schema": "twinkle-product-film-micro-clips-delivery-v1",
        "materialPolicy": "authority product materials unchanged; route language only may derive from rejected preview",
        "clips": deliveries,
        "reviewStatus": "pending-quick-motion-feedback-before-samples-ab",
    }
    _write_json(output_root / "preview-v2" / "micro-clips" / "micro-clips-manifest.json", manifest)
    return manifest


def build_motion_revision_clips(repo: Path, output_root: Path, blender: Path, source_blend: Path, ffmpeg: str) -> dict:
    output_root = validate_output_root(repo, output_root)
    if sha256(source_blend) != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    command = motion_revision_blender_command(blender, source_blend, output_root)
    started_at_ns = time.time_ns()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    _write_json(output_root / "evidence" / "motion-revision-clips-blender-command.json", {
        "command": command, "exitCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
    })
    result_path = output_root / "work" / "motion-revision-clips-results.json"
    worker = require_blender_result(completed, result_path, started_at_ns)
    deliveries = []
    for clip in worker["clips"]:
        clip_root = output_root / "preview-v2" / MOTION_REVISION_OUTPUT_DIR / clip["name"]
        video = clip_root / f"{clip['name']}.mp4"
        encode = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-framerate", "30",
            "-i", str(clip_root / "frames" / "frame-%03d.png"), "-c:v", "libx264",
            "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-r", "30",
            "-movflags", "+faststart", "-an", str(video),
        ]
        encoded = subprocess.run(encode, check=False, capture_output=True, text=True)
        if encoded.returncode != 0:
            raise FilmValidationError(encoded.stderr.strip() or f"motion revision encoding failed: {clip['name']}")
        deliveries.append({
            "name": clip["name"], "intent": clip["intent"], "frameCount": clip["frameCount"],
            "durationSeconds": clip["frameCount"] / 30, "pathType": clip["pathType"],
            "orientationConstraint": clip["orientationConstraint"], "speedCurve": clip["speedCurve"],
            "video": str(video), "sha256": sha256(video), "bytes": video.stat().st_size,
        })
    manifest = {
        "schema": "twinkle-product-film-motion-correction-delivery-v1",
        "baselineV2Sha256": "25D9AACB336AA9ECB673E1AFB289C0EAA354428624F5438CF9742CA3D4698CF9",
        "frozenVisualState": "lighting, graphite backdrop, product materials, model structure, AgX",
        "heroTerminal": "shot 4 reaches A/192 frame 152 continuously with target and 58 mm lens unchanged",
        "shotNumbering": "1=edge-aperture unchanged; 2=ninety-degree rolled fastened-side-panel skim corrected; 3=underside-ring unchanged; 4=dual-interface continuous to hero corrected",
        "clips": deliveries,
        "reviewStatus": "pending-quick-motion-language-review",
    }
    _write_json(output_root / "preview-v2" / MOTION_REVISION_OUTPUT_DIR / "motion-correction-manifest.json", manifest)
    return manifest


def build_dip_to_black_loop_review(
    repo: Path, output_root: Path, blender: Path, source_blend: Path, ffmpeg: str
) -> dict:
    output_root = validate_output_root(repo, output_root)
    source_before = sha256(source_blend)
    if source_before != EXPECTED_BLEND_SHA256:
        raise FilmValidationError("authority blend drift")
    review_root = prepare_dip_to_black_review_root(output_root / "preview-v2")
    sources = (
        output_root / "preview-v2" / "micro-clips" / "edge-aperture" / "edge-aperture.mp4",
        output_root / "preview-v2" / MOTION_REVISION_OUTPUT_DIR / "rolled-side-panel-surface-skimming-correction" / "rolled-side-panel-surface-skimming-correction.mp4",
        output_root / "preview-v2" / "micro-clips" / "underside-ring" / "underside-ring.mp4",
        output_root / "preview-v2" / MOTION_REVISION_OUTPUT_DIR / "dual-interface-to-hero-continuous-correction" / "dual-interface-to-hero-continuous-correction.mp4",
    )
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FilmValidationError("missing locked source clips: " + ", ".join(missing))
    review_video = review_root / "dip-to-black-loop-review.mp4"
    assembled = subprocess.run(
        dip_to_black_loop_ffmpeg_command(ffmpeg, *sources, review_video),
        check=False,
        capture_output=True,
        text=True,
    )
    if assembled.returncode != 0:
        raise FilmValidationError(assembled.stderr.strip() or "dip-to-black loop assembly failed")
    manifest = {
        "schema": "twinkle-product-film-dip-to-black-loop-review-v2",
        "transition": {**DIP_TO_BLACK_LOOP, "color": "black", "boundary": "half-open virtual black"},
        "sequence": ["edge-aperture", "rolled-side-panel-surface-skimming-correction", "underside-ring", "dual-interface-to-hero-continuous-correction"],
        "lockedSourceSha256": {path.name: sha256(path) for path in sources},
        "delivery": {"video": str(review_video), "sha256": sha256(review_video), "bytes": review_video.stat().st_size},
        "sourceBlend": {"path": str(source_blend), "sha256Before": source_before, "sha256After": sha256(source_blend)},
        "sourceRestored": source_before == sha256(source_blend),
        "reviewStatus": "pending-human-review-before-full-quality-or-web-integration",
    }
    _write_json(review_root / "review-manifest.json", manifest)
    return manifest


def build_quality_b2_review_audit(repo: Path, output_root: Path, ffmpeg: str, ffprobe: str) -> dict:
    from PIL import Image, ImageDraw

    repo = Path(repo).resolve()
    output_root = Path(output_root).resolve()
    expected = (
        repo / "output" / "playwright" / "twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "film-quality-b2-full-render"
    )
    if output_root != expected:
        raise FilmValidationError(f"B2 review audit output must be isolated at: {expected}")
    render_results_path = output_root / "render-results.json"
    if not render_results_path.is_file():
        raise FilmValidationError("missing B2 render results")
    render_results = json.loads(render_results_path.read_text(encoding="utf-8"))
    if render_results.get("frameCount") != 303 or not render_results.get("sourceRestored"):
        raise FilmValidationError("B2 render results are not validated")

    review_root = output_root / "review"
    contract = quality_b2_review_contract(review_root)
    videos = [item["video"] for item in contract["clips"]] + [contract["combinedVideo"]]
    missing = [str(path) for path in videos if not path.is_file()]
    if missing:
        raise FilmValidationError("missing B2 review video: " + ", ".join(missing))

    def run(command: list[str]) -> subprocess.CompletedProcess:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise FilmValidationError(completed.stderr.strip() or "external review tool failed")
        return completed

    probes = {}
    for video in videos:
        completed = run([
            str(ffprobe), "-v", "error", "-select_streams", "v:0",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,pix_fmt:format=duration,size",
            "-of", "json", str(video),
        ])
        probes[video.name] = parse_quality_b2_video_probe(completed.stdout)
    validate_quality_b2_review_probes(contract, probes)

    clip_by_name = {item["name"]: item for item in contract["clips"]}
    sequence_checks = []
    for label, local_frame, combined_frame in quality_b2_review_sequence_checks(contract):
        source = clip_by_name[label]["video"] if label in clip_by_name else (
            contract["clips"][0]["video"] if label == "fade-in-complete" else contract["clips"][-1]["video"]
        )
        graph = (
            f"[0:v]select='eq(n\\,{combined_frame})',setpts=PTS-STARTPTS[a];"
            f"[1:v]select='eq(n\\,{local_frame})',setpts=PTS-STARTPTS[b];[a][b]ssim"
        )
        completed = run([
            str(ffmpeg), "-hide_banner", "-i", str(contract["combinedVideo"]), "-i", str(source),
            "-filter_complex", graph, "-frames:v", "1", "-f", "null", "-",
        ])
        similarity = parse_quality_b2_ssim(completed.stdout + completed.stderr)
        if similarity < 0.99:
            raise FilmValidationError(f"B2 review sequence mismatch at {label}: SSIM {similarity}")
        sequence_checks.append({
            "label": label,
            "sourceVideo": source.name,
            "sourceFrame": local_frame,
            "combinedFrame": combined_frame,
            "ssim": similarity,
        })

    signal_frames = (0, 6, 11, 12, 284, 285, 294, 302)
    selector = "+".join(f"eq(n\\,{frame})" for frame in signal_frames)
    completed = run([
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(contract["combinedVideo"]),
        "-vf", f"select='{selector}',signalstats,metadata=print:file=-", "-an", "-f", "null", "-",
    ])
    luma = parse_quality_b2_signalstats(completed.stdout + completed.stderr)
    if set(luma) != set(signal_frames):
        raise FilmValidationError("B2 fade signal sample set drift")
    if luma[0] > 16.5 or luma[12] <= luma[0] + 5:
        raise FilmValidationError("B2 fade-in contract failed")
    if luma[302] > 20 or luma[294] <= luma[302] + 5:
        raise FilmValidationError("B2 fade-out contract failed")

    contact_sheet_path = review_root / "b2-review-contact-sheet.png"
    with tempfile.TemporaryDirectory(prefix="twinkle-b2-review-") as temp_name:
        temp_root = Path(temp_name)
        selector = "+".join(f"eq(n\\,{frame})" for frame in QUALITY_B2_REVIEW_CONTACT_FRAMES)
        run([
            str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-i", str(contract["combinedVideo"]),
            "-vf", f"select='{selector}'", "-fps_mode", "vfr", str(temp_root / "frame-%03d.png"),
        ])
        extracted = sorted(temp_root.glob("frame-*.png"))
        if len(extracted) != len(QUALITY_B2_REVIEW_CONTACT_FRAMES):
            raise FilmValidationError("B2 contact-sheet extraction count drift")
        tile_size = (426, 300)
        label_height = 28
        columns = 6
        rows = math.ceil(len(extracted) / columns)
        sheet = Image.new("RGB", (columns * tile_size[0], rows * (tile_size[1] + label_height)), "#070b12")
        draw = ImageDraw.Draw(sheet)
        for index, (path, frame) in enumerate(zip(extracted, QUALITY_B2_REVIEW_CONTACT_FRAMES)):
            row, column = divmod(index, columns)
            x = column * tile_size[0]
            y = row * (tile_size[1] + label_height)
            with Image.open(path) as image:
                sheet.paste(image.convert("RGB").resize(tile_size, Image.Resampling.LANCZOS), (x, y))
            clip = next(item for item in reversed(contract["clips"]) if frame >= item["startFrame"])
            local_frame = frame - clip["startFrame"]
            draw.text(
                (x + 8, y + tile_size[1] + 7),
                f"F{frame:03d} {clip['name']} +{local_frame:03d}",
                fill="#e6edf7",
            )
        sheet.save(contact_sheet_path)

    ffmpeg_version = run([str(ffmpeg), "-version"]).stdout.splitlines()[0]
    ffprobe_version = run([str(ffprobe), "-version"]).stdout.splitlines()[0]
    manifest = {
        "schema": "twinkle-product-film-quality-b2-review-audit-v1",
        "reviewStatus": "pending-human-approval-before-formal-replacement",
        "tools": {"ffmpeg": ffmpeg_version, "ffprobe": ffprobe_version},
        "renderResults": {
            "path": str(render_results_path),
            "sha256": sha256(render_results_path),
            "blenderVersion": render_results.get("blenderVersion"),
            "render": render_results.get("render"),
            "sourceBlend": render_results.get("sourceBlend"),
        },
        "contract": {
            "sequence": [item["name"] for item in contract["clips"]],
            "combinedFrameCount": contract["combinedFrameCount"],
            "fadeIn": contract["fadeIn"],
            "fadeOut": contract["fadeOut"],
            "assemblyCommand": [str(value) for value in dip_to_black_loop_ffmpeg_command(
                ffmpeg, *(item["video"] for item in contract["clips"]), contract["combinedVideo"]
            )],
        },
        "videos": {
            video.name: {**probes[video.name], "sha256": sha256(video)} for video in videos
        },
        "contentChecks": {
            "minimumSsim": 0.99,
            "sequenceAndFadeBoundaries": sequence_checks,
            "sampledLumaYAvg": {str(frame): luma[frame] for frame in signal_frames},
        },
        "contactSheet": {
            "path": str(contact_sheet_path),
            "sha256": sha256(contact_sheet_path),
            "bytes": contact_sheet_path.stat().st_size,
            "frames": list(QUALITY_B2_REVIEW_CONTACT_FRAMES),
        },
    }
    _write_json(review_root / "review-manifest.json", manifest)
    return manifest


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--source-blend", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--representative-only", action="store_true")
    parser.add_argument("--storyboard-only", action="store_true")
    parser.add_argument("--v2-preview", action="store_true")
    parser.add_argument("--micro-clips", action="store_true")
    parser.add_argument("--motion-revision-clips", action="store_true")
    parser.add_argument("--dip-to-black-loop-review", action="store_true")
    parser.add_argument("--quality-preflight", action="store_true")
    parser.add_argument("--quality-b2-full-render", action="store_true")
    parser.add_argument("--quality-b2-review-audit", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--preview")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    worker_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else None
    args = parse_args(worker_args if worker_args is not None else argv)
    if args.worker_output is not None:
        if args.quality_b2_full_render:
            return _render_quality_b2_full(args.worker_output.resolve())
        if args.quality_preflight:
            return _render_quality_preflight(args.worker_output.resolve())
        if args.storyboard_only:
            return _render_storyboard(args.worker_output.resolve())
        if args.v2_preview:
            return _render_v2_preview(args.worker_output.resolve())
        if args.micro_clips:
            return _render_micro_clips(args.worker_output.resolve())
        if args.motion_revision_clips:
            return _render_motion_revision_clips(args.worker_output.resolve())
        return _render_worker(args.worker_output.resolve(), args.representative_only)
    if args.quality_b2_review_audit:
        if None in (args.repo, args.output_root):
            raise FilmValidationError("repo and output-root are required for B2 review audit")
        result = build_quality_b2_review_audit(args.repo, args.output_root, args.ffmpeg, args.ffprobe)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if None in (args.repo, args.output_root, args.blender, args.source_blend):
        raise FilmValidationError("repo, output-root, blender, and source-blend are required")
    if args.quality_b2_full_render:
        output_root = Path(args.output_root).resolve()
        expected = Path(args.repo).resolve() / "output" / "playwright" / "twinkle-stage5-h2-full-flow-review-candidate-20260912" / "film-quality-b2-full-render"
        if output_root != expected:
            raise FilmValidationError(f"B2 full render output must be isolated at: {expected}")
        source_before = sha256(args.source_blend)
        if source_before != EXPECTED_BLEND_SHA256:
            raise FilmValidationError("authority blend drift")
        command = quality_b2_full_blender_command(args.blender, args.source_blend, output_root)
        started_at_ns = time.time_ns()
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        _write_json(output_root / "blender-command.json", {
            "command": command, "exitCode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        })
        result = require_blender_result(completed, output_root / "render-results.json", started_at_ns)
        if result.get("frameCount") != 303:
            raise FilmValidationError("B2 full render frame count drift")
        if sha256(args.source_blend) != source_before:
            raise FilmValidationError("authority blend changed during B2 full render")
    elif args.quality_preflight:
        output_root = Path(args.output_root).resolve()
        expected = Path(args.repo).resolve() / "output" / "playwright" / "twinkle-stage5-h2-full-flow-review-candidate-20260912" / "film-quality-preflight"
        if output_root != expected:
            raise FilmValidationError(f"quality preflight output must be isolated at: {expected}")
        source_before = sha256(args.source_blend)
        if source_before != EXPECTED_BLEND_SHA256:
            raise FilmValidationError("authority blend drift")
        command = quality_preflight_blender_command(args.blender, args.source_blend, output_root)
        started_at_ns = time.time_ns()
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        _write_json(output_root / "blender-command.json", {
            "command": command, "exitCode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        })
        result = require_blender_result(completed, output_root / "render-results.json", started_at_ns)
        if sha256(args.source_blend) != source_before:
            raise FilmValidationError("authority blend changed during quality preflight")
    elif args.storyboard_only:
        result = build_storyboard(args.repo, args.output_root, args.blender, args.source_blend)
    elif args.v2_preview:
        result = build_v2_preview(args.repo, args.output_root, args.blender, args.source_blend, args.ffmpeg)
    elif args.micro_clips:
        result = build_micro_clips(args.repo, args.output_root, args.blender, args.source_blend, args.ffmpeg)
    elif args.motion_revision_clips:
        result = build_motion_revision_clips(args.repo, args.output_root, args.blender, args.source_blend, args.ffmpeg)
    elif args.dip_to_black_loop_review:
        result = build_dip_to_black_loop_review(args.repo, args.output_root, args.blender, args.source_blend, args.ffmpeg)
    else:
        result = build_preview(args.repo, args.output_root, args.blender, args.source_blend, args.ffmpeg, args.representative_only)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
