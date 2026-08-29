import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from twinkle_camera_projection import CameraSpec


BLENDER = (
    Path(os.environ["TWINKLE_BLENDER"]).expanduser()
    if os.environ.get("TWINKLE_BLENDER")
    else (Path(shutil.which("blender")) if shutil.which("blender") else None)
)
SOURCE_BLEND = (
    Path(os.environ["TWINKLE_SOURCE_BLEND"]).expanduser()
    if os.environ.get("TWINKLE_SOURCE_BLEND")
    else None
)
CANDIDATE_BLEND = (
    Path(os.environ["TWINKLE_CANDIDATE_BLEND"]).expanduser()
    if os.environ.get("TWINKLE_CANDIDATE_BLEND")
    else None
)
AUTHORITY_MANIFEST = (
    ROOT
    / "output"
    / "web-blender-page-coordinated-experiment-v7"
    / "experiment-manifest.json"
)
LEGACY_CONDENSER_REFERENCE = (
    ROOT / "scripts" / "assets" / "twinkle_condenser_legacy_reference.png"
)
LEGACY_CONDENSER_REFERENCE_SHA256 = (
    "12364CBBE6AA9F9AC0A382530506A5B16236AFDF55910D3EEB05A01481A8DC0A"
)
DEFAULT_OUTPUT_ROOT = ROOT / "output" / "twinkle-route1-camera-board-r1-1"
EXPECTED_SOURCE_SHA256 = (
    "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81"
)
EXPECTED_CANDIDATE_SHA256 = (
    "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
)

CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"
DISPLAY_NAMES_ZH = {
    CHAMBER: "双通道采集光学舱",
    CONDENSER: "聚光镜组件",
}
CJK_REVIEW_FONT = os.environ.get("TWINKLE_CJK_REVIEW_FONT", "msyh.ttc")
UNITS = {
    CHAMBER: {
        "rootObjects": (
            "DetectBox_Bottom_Mala2020:1",
            "Side2_optics:1",
        ),
        "fullOffsets": (
            (0.0, 0.0, -0.14),
            (0.0, -0.10, 0.0),
        ),
        "componentNames": ("bottomCover", "sidePanel"),
    },
    CONDENSER: {
        "rootObjects": ("SHOWCASE_GROUP__f_dual_acl_housing",),
        "fullOffsets": ((0.034, 0.012, -0.016),),
        "componentNames": ("condenserAssembly",),
        "legacySourceObjectId": "SHOWCASE_GROUP__f_dual_acl_housing",
    },
}
STATE_PROGRESS = {
    CHAMBER: {
        "focused-settled": 0.0,
        "fasteners-released-seam": 0.06,
        "extract-mid": 0.5,
        "extract-end": 1.0,
    },
    CONDENSER: {
        "focused-settled": 0.0,
        "extract-mid": 0.5,
        "extract-end": 1.0,
    },
}
AUTHORED_PRESETS = {
    CHAMBER: {
        "id": "collection-optics-chamber-side-underside",
        "location": (0.411294, 0.420016, 0.371682),
        "target": (0.285227, 0.622304, 0.585193),
        "lensMm": 55.0,
        "sensorWidthMm": 36.0,
        "shiftX": 0.0,
        "shiftY": 0.0,
    },
    CONDENSER: {
        "id": "condenser-lens-front-hero-right-15mm",
        "location": (0.43536043, 0.3241443, 0.56380999),
        "target": (0.45065495, 0.62336338, 0.57699472),
        "lensMm": 72.0,
        "sensorWidthMm": 36.0,
        "shiftX": 0.0,
        "shiftY": 0.02,
    },
}
CHAMBER_INSPECTION = {
    "state": "extract-end",
    "asset": "assets/dual-channel-collection-optics-chamber--inspection-lit.png",
    "rawAsset": ".chamber-inspection-raw.png",
    "enterMs": 900,
    "holdMs": 500,
    "exitMs": 700,
    "light": {
        "type": "AREA",
        "energy": 10.0,
        "size": 0.11,
        "cameraRelativeOffset": (-0.012, 0.008, 0.250),
        "aimDepth": 0.115,
    },
    "maskLuma": {"fullAtOrBelow": 35.0, "zeroAtOrAbove": 60.0},
}
CONDENSER_CLEANUP = {
    "method": "ffmpeg-removelogo-bitmap-mask",
    "baseState": "extract-end",
    "referenceBounds": (376, 259, 966, 825),
    "statePlateBounds": {
        "focused-settled": (0, 70, 650, 692),
        "extract-mid": (206, 174, 812, 752),
        "extract-end": (376, 259, 966, 825),
    },
    "polygon": ((900, 548), (936, 540), (960, 790), (928, 810)),
    "protectedCircles": ((891, 330, 52), (891, 540, 52), (891, 750, 52)),
}
HUMAN_APPROVAL = {
    "approved": True,
    "approvedAt": "2026-08-25",
    "sourceThreadId": "01a0386f-a914-7960-a3c7-f49ab62c9063",
    "scope": "stage1-formal-asset-replacement-and-closeout-only",
    "stage2Authorized": False,
    "deploymentAuthorized": False,
    "publicationAuthorized": False,
}
RENDER_PROFILE = {
    "engine": "BLENDER_EEVEE",
    "resolution": (1280, 900, 100),
    "taaRenderSamples": 512,
    "viewTransform": "AgX",
    "look": "AgX - Medium High Contrast",
    "exposure": -1.6,
    "gamma": 1.0,
    "filmTransparent": False,
    "existingLights": (
        "WS_Key_Softbox",
        "WS_Fill_Softbox",
        "WS_Rim_Light",
        "WS_Front_Bounce",
    ),
    "sharedTechnicalLights": {
        "key": {"energy": 10.0, "size": 0.10, "location": (0.34, 0.48, 0.48)},
        "fill": {"energy": 3.5, "size": 0.14, "location": (0.24, 0.66, 0.52)},
    },
    "sharedHiddenObjects": ("WS_Studio_Floor",),
    "panelCopy": "紧固件解除后，底盖/侧板沿法线移开。",
}
LEGACY_CONDENSER_HASHES = {
    "focused-settled": "F60DE02B9A9612036FBDAB7E4EF35792CD2F20F59D47565CAE72D6D444BF837D",
    "extract-mid": "2B886A06E115F410582A7E1CA45F751CEB5D6D4A44E00A758754D5470DA20C34",
    "extract-end": "BD605CD7018B9505B0394623D1858428926CE5580E0F4A3764A28342240D1FBC",
}
STAGE1_DELETED_DIRECTORIES = (
    ".twinkle-route1-camera-board-r1-1-pre-connection-oblique-20260823",
    ".twinkle-route1-settled-preview-visible-20260823",
    ".twinkle-route1-settled-preview-f-shifty-neg008-20260823",
    ".twinkle-route1-settled-preview-f-flat-top-20260823",
    ".twinkle-route1-settled-preview-f-topcap-flat-20260823",
    ".twinkle-route1-settled-preview-f-no-weighted-topcap-20260823",
    ".twinkle-route1-settled-preview-f-no-normal-map-20260823",
    ".twinkle-route1-settled-preview-j-soft-layout-20260823",
    ".twinkle-route1-settled-preview-f-soft-layout-20260823",
    ".twinkle-route1-triptych-preview-j-fast-reveal-20260823",
    ".twinkle-route1-triptych-preview-f-fast-reveal-20260823",
    ".twinkle-route1-triptych-preview-j-front-hero-20260824",
    ".twinkle-route1-triptych-preview-f-front-hero-20260824",
    ".twinkle-route1-triptych-preview-j-green-contrast-20260824",
    ".twinkle-route1-triptych-preview-j-pmt-connection-hero-20260824",
    ".twinkle-hotspot-candidate-comparison-20260824",
    ".twinkle-digger-local-window-triptych-20260824",
    ".twinkle-endoscope-camera-probe-20260824",
    ".twinkle-internal-visibility-survey-20260824",
    ".twinkle-collection-box-bottom-tour-20260824",
    ".twinkle-collection-box-bottom-tour-floor-hidden-20260824",
    ".twinkle-collection-box-official-open-tour-20260824",
    ".twinkle-ir-separation-side-context-20260824",
    ".twinkle-bottom-side-sequential-tour-20260824",
    ".twinkle-bottom-side-simultaneous-stable-light-20260824",
)
FROZEN_SENTINELS = (
    "web-blender-page-coordinated-experiment-v7",
    "twinkle-route1-motion-sample-r1-sync",
    ".twinkle-route1-j-optic-detail-sample-r1-1a-failed-contract-rounding-first",
)
STAGE1_CLEANUP_SUMMARY = {
    "directories": 29,
    "files": 244,
    "bytes": 118412245,
    "dedicatedCodeAndTestFiles": 4,
    "cacheFiles": 5,
}
VISUAL_REPAIR_CLEANUP_EVIDENCE = {
    "directories": 3,
    "files": 42,
    "bytes": 24950197,
    "paths": [
        ".twinkle-shared-light-bracket-20260824",
        ".twinkle-route1-camera-board-light-fix-staging-20260824",
        ".twinkle-route1-camera-board-pre-exposure-fix-20260824",
    ],
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_hash(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def should_apply_shared_top_plate_material_copy(unit_id):
    if unit_id not in UNITS:
        raise ValueError(f"unknown unit: {unit_id}")
    return True


def cleanup_geometry_for_plate_bounds(bounds):
    left, top, right, bottom = [int(value) for value in bounds]
    reference_left, reference_top, reference_right, reference_bottom = CONDENSER_CLEANUP[
        "referenceBounds"
    ]
    scale_x = (right - left) / (reference_right - reference_left)
    scale_y = (bottom - top) / (reference_bottom - reference_top)

    def point(x, y):
        return [
            int(round(left + (x - reference_left) * scale_x)),
            int(round(top + (y - reference_top) * scale_y)),
        ]

    return {
        "plateBoundsPx": [left, top, right, bottom],
        "polygon": [point(x, y) for x, y in CONDENSER_CLEANUP["polygon"]],
        "protectedCircles": [
            [
                *point(x, y),
                int(round(radius * (scale_x + scale_y) / 2.0)),
            ]
            for x, y, radius in CONDENSER_CLEANUP["protectedCircles"]
        ],
    }


def authored_camera_spec(unit_id):
    preset = AUTHORED_PRESETS[unit_id]
    return CameraSpec(
        location=preset["location"],
        target=preset["target"],
        lens_mm=preset["lensMm"],
        sensor_width_mm=preset["sensorWidthMm"],
        shift_x=preset["shiftX"],
        shift_y=preset["shiftY"],
        resolution_x=RENDER_PROFILE["resolution"][0],
        resolution_y=RENDER_PROFILE["resolution"][1],
    )


def parse_outer_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--refresh-review-metadata-only", action="store_true")
    return parser.parse_args()


def worker_args():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--probe-only", action="store_true")
    return parser.parse_args(args)


def run_blender(output_root, probe_only=False):
    if BLENDER is None or not BLENDER.is_file():
        raise RuntimeError("TWINKLE_BLENDER must point to a Blender executable")
    if SOURCE_BLEND is None or CANDIDATE_BLEND is None:
        raise RuntimeError(
            "TWINKLE_SOURCE_BLEND and TWINKLE_CANDIDATE_BLEND are required"
        )
    command = [
        str(BLENDER),
        "--background",
        str(CANDIDATE_BLEND),
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--worker",
        "--output-root",
        str(output_root),
    ]
    if probe_only:
        command.append("--probe-only")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        raise RuntimeError(
            f"Blender worker failed with {result.returncode}:\n{result.stderr}"
        )
    if probe_only:
        if "CAMERA_BOARD_PROBE=" not in result.stdout:
            raise RuntimeError(f"Blender probe completion marker missing:\n{result.stderr}")
    if not probe_only:
        if "CAMERA_BOARD_WORKER=" not in result.stdout:
            raise RuntimeError(f"Blender worker completion marker missing:\n{result.stderr}")


def finalize_approved_stage1_assets(output_root):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    manifest_path = output_root / "camera-board-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    chamber = manifest["units"][CHAMBER]
    base_path = output_root / chamber["frames"][CHAMBER_INSPECTION["state"]]["asset"]
    raw_path = output_root / CHAMBER_INSPECTION["rawAsset"]
    if not raw_path.is_file():
        raise RuntimeError("chamber inspection raw pass missing")
    base = Image.open(base_path).convert("RGB")
    lit = Image.open(raw_path).convert("RGB")
    if base.size != (1280, 900) or lit.size != base.size:
        raise RuntimeError("chamber inspection pass dimensions invalid")
    spatial = Image.new("L", base.size, 0)
    spatial_draw = ImageDraw.Draw(spatial)
    spatial_draw.polygon(
        ((340, 210), (680, 170), (770, 300), (700, 490), (570, 590), (330, 540), (270, 350)),
        fill=255,
    )
    spatial_draw.polygon(
        ((780, 170), (1090, 40), (1220, 140), (1180, 500), (950, 530), (810, 420)),
        fill=255,
    )
    spatial = spatial.filter(ImageFilter.GaussianBlur(18.0))
    base_array = np.asarray(base, dtype=np.float32)
    lit_array = np.asarray(lit, dtype=np.float32)
    luma = base_array[..., 0] * 0.2126 + base_array[..., 1] * 0.7152 + base_array[..., 2] * 0.0722
    luma_rule = CHAMBER_INSPECTION["maskLuma"]
    dark_weight = np.clip(
        (luma_rule["zeroAtOrAbove"] - luma)
        / (luma_rule["zeroAtOrAbove"] - luma_rule["fullAtOrBelow"]),
        0.0,
        1.0,
    )
    mask = np.asarray(spatial, dtype=np.float32) / 255.0 * dark_weight
    inspection_array = np.clip(
        base_array * (1.0 - mask[..., None]) + lit_array * mask[..., None], 0, 255
    ).astype(np.uint8)
    inspection_path = output_root / CHAMBER_INSPECTION["asset"]
    Image.fromarray(inspection_array, "RGB").save(inspection_path)
    changed = np.any(inspection_array != base_array.astype(np.uint8), axis=2)
    outside = mask <= 0.0
    chamber["inspectionLight"] = {
        "baseState": CHAMBER_INSPECTION["state"],
        "asset": CHAMBER_INSPECTION["asset"],
        "sha256": sha256(inspection_path),
        "transitionMs": {
            "enter": CHAMBER_INSPECTION["enterMs"],
            "hold": CHAMBER_INSPECTION["holdMs"],
            "exit": CHAMBER_INSPECTION["exitMs"],
        },
        "light": CHAMBER_INSPECTION["light"],
        "maskLuma": CHAMBER_INSPECTION["maskLuma"],
        "maskAudit": {
            "changedPixels": int(changed.sum()),
            "outsideMaskChangedPixels": int(np.logical_and(changed, outside).sum()),
            "totalPixels": int(changed.size),
        },
    }
    if chamber["inspectionLight"]["maskAudit"]["outsideMaskChangedPixels"] != 0:
        raise RuntimeError("chamber inspection changed pixels outside mask")
    raw_path.unlink()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg with removelogo filter is required for approved condenser cleanup")
    condenser = manifest["units"][CONDENSER]
    condenser["inspectionLight"] = None
    cleanup_records = {}
    for state, frame in condenser["frames"].items():
        frame_path = output_root / frame["asset"]
        original = Image.open(frame_path).convert("RGB")
        original_array = np.asarray(original, dtype=np.uint8)
        plate_bounds = CONDENSER_CLEANUP["statePlateBounds"][state]
        geometry = cleanup_geometry_for_plate_bounds(plate_bounds)
        mask_image = Image.new("L", original.size, 0)
        mask_draw = ImageDraw.Draw(mask_image)
        mask_draw.polygon(tuple(tuple(point) for point in geometry["polygon"]), fill=255)
        for x, y, radius in geometry["protectedCircles"]:
            mask_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=0)
        mask_name = f".condenser-cleanup-{state}-mask.png"
        filtered_name = f".condenser-cleanup-{state}-filtered.png"
        mask_path = frame_path.parent / mask_name
        filtered_path = frame_path.parent / filtered_name
        mask_image.save(mask_path)
        filter_value = f"removelogo=filename={mask_name}"
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-i",
                frame_path.name,
                "-vf",
                filter_value,
                "-frames:v",
                "1",
                "-update",
                "1",
                filtered_name,
            ],
            cwd=frame_path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not filtered_path.is_file():
            raise RuntimeError(f"ffmpeg condenser cleanup failed for {state}: {result.stderr}")
        filtered_array = np.asarray(Image.open(filtered_path).convert("RGB"), dtype=np.uint8)
        hard_mask = np.asarray(mask_image, dtype=np.uint8) > 0
        cleaned_array = np.where(hard_mask[..., None], filtered_array, original_array)
        Image.fromarray(cleaned_array, "RGB").save(frame_path)
        changed = np.any(cleaned_array != original_array, axis=2)
        outside_changed = int(np.logical_and(changed, ~hard_mask).sum())
        if outside_changed != 0:
            raise RuntimeError(f"condenser cleanup changed pixels outside mask: {state}")
        frame["sha256"] = sha256(frame_path)
        frame["cleanupAudit"] = {
            "method": CONDENSER_CLEANUP["method"],
            "plateBoundsPx": geometry["plateBoundsPx"],
            "changedPixels": int(changed.sum()),
            "outsideMaskChangedPixels": outside_changed,
        }
        cleanup_records[state] = frame["cleanupAudit"]
        mask_path.unlink()
        filtered_path.unlink()
    condenser["cleanup"] = {
        "method": CONDENSER_CLEANUP["method"],
        "baseState": CONDENSER_CLEANUP["baseState"],
        "ffmpeg": str(Path(ffmpeg).resolve()),
        "frames": cleanup_records,
    }
    manifest["humanReviewApproved"] = HUMAN_APPROVAL["approved"]
    manifest["humanApproval"] = HUMAN_APPROVAL
    manifest["postprocessAudit"] = {
        "temporaryFilesRemaining": [],
        "chamberOutsideMaskChangedPixels": chamber["inspectionLight"]["maskAudit"][
            "outsideMaskChangedPixels"
        ],
        "condenserOutsideMaskChangedPixels": sum(
            record["outsideMaskChangedPixels"] for record in cleanup_records.values()
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_review_sheets(output_root):
    from PIL import Image, ImageDraw, ImageFont

    manifest_path = output_root / "camera-board-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not CJK_REVIEW_FONT:
        raise RuntimeError("TWINKLE_CJK_REVIEW_FONT is required")
    try:
        cjk_heading_font = ImageFont.truetype(str(CJK_REVIEW_FONT), size=20)
    except OSError as error:
        raise RuntimeError("configured CJK review font is unavailable") from error
    condenser_display_name = manifest["units"][CONDENSER]["displayNameZh"]

    sheet = Image.new("RGB", (960, 592), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), "STAGE 1 | SHARED MODEL + SHARED LIGHT + SHARED RENDER PROFILE", fill=(20, 32, 38))
    chamber_frames = manifest["units"][CHAMBER]["frames"]
    for index, (state, record) in enumerate(chamber_frames.items()):
        image = Image.open(output_root / record["asset"]).convert("RGB")
        image = image.resize((240, 169))
        x = index * 240
        sheet.paste(image, (x, 34))
        draw.text((x + 6, 38), state, fill=(20, 32, 38))
    draw.text(
        (8, 229),
        condenser_display_name,
        fill=(20, 32, 38),
        font=cjk_heading_font,
    )
    condenser_frames = manifest["units"][CONDENSER]["frames"]
    for index, (state, record) in enumerate(condenser_frames.items()):
        image = Image.open(output_root / record["asset"]).convert("RGB")
        image = image.resize((320, 225))
        x = index * 320
        sheet.paste(image, (x, 254))
        draw.text((x + 6, 258), state, fill=(20, 32, 38))
    draw.text((8, 562), "HUMAN REVIEW REQUIRED | no production integration", fill=(75, 92, 98))
    sheet.save(output_root / manifest["reviewSheet"])

    comparison = Image.new("RGB", (960, 518), "white")
    comparison_draw = ImageDraw.Draw(comparison)
    comparison_draw.text(
        (8, 8),
        f"{condenser_display_name} | LEGACY ACCEPTED (TOP) vs SHARED PROFILE (BOTTOM)",
        fill=(20, 32, 38),
        font=cjk_heading_font,
    )
    if not LEGACY_CONDENSER_REFERENCE.is_file():
        raise RuntimeError("stable legacy condenser reference is unavailable")
    if sha256(LEGACY_CONDENSER_REFERENCE) != LEGACY_CONDENSER_REFERENCE_SHA256:
        raise RuntimeError("stable legacy condenser reference drift")
    legacy_reference = Image.open(LEGACY_CONDENSER_REFERENCE).convert("RGB")
    for index, state in enumerate(STATE_PROGRESS[CONDENSER]):
        new_path = output_root / condenser_frames[state]["asset"]
        old_image = legacy_reference.crop((index * 320, 0, (index + 1) * 320, 225))
        new_image = Image.open(new_path).convert("RGB").resize((320, 225))
        comparison.paste(old_image, (index * 320, 34))
        comparison.paste(new_image, (index * 320, 293))
        comparison_draw.text((index * 320 + 6, 38), state, fill=(20, 32, 38))
        comparison_draw.text((index * 320 + 6, 297), state, fill=(20, 32, 38))
    comparison.save(output_root / manifest["condenserComparisonSheet"])
    inspection = Image.new("RGB", (960, 372), "white")
    inspection_draw = ImageDraw.Draw(inspection)
    inspection_draw.text(
        (8, 8),
        "COLLECTION CHAMBER | GLOBAL BASE (LEFT) vs INTERNAL INSPECTION (RIGHT)",
        fill=(20, 32, 38),
    )
    base_record = chamber_frames[manifest["units"][CHAMBER]["inspectionLight"]["baseState"]]
    base_image = Image.open(output_root / base_record["asset"]).convert("RGB").resize((480, 338))
    lit_image = Image.open(
        output_root / manifest["units"][CHAMBER]["inspectionLight"]["asset"]
    ).convert("RGB").resize((480, 338))
    inspection.paste(base_image, (0, 34))
    inspection.paste(lit_image, (480, 34))
    inspection_draw.text((8, 38), "global rotation light", fill=(20, 32, 38))
    inspection_draw.text((488, 38), "narration internal light", fill=(20, 32, 38))
    inspection.save(output_root / manifest["inspectionReviewSheet"])
    manifest["reviewEvidence"] = {
        "sevenFrameContactSheet": {
            "asset": manifest["reviewSheet"],
            "sha256": sha256(output_root / manifest["reviewSheet"]),
        },
        "condenserComparisonSheet": {
            "asset": manifest["condenserComparisonSheet"],
            "sha256": sha256(output_root / manifest["condenserComparisonSheet"]),
        },
        "inspectionLightComparisonSheet": {
            "asset": manifest["inspectionReviewSheet"],
            "sha256": sha256(output_root / manifest["inspectionReviewSheet"]),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def validate_output(output_root):
    from PIL import Image

    manifest_path = output_root / "camera-board-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["schema"] != "twinkle-route1-camera-board-v4":
        raise RuntimeError("unexpected manifest schema")
    assets = []
    for unit in manifest["units"].values():
        for frame in unit["frames"].values():
            path = output_root / frame["asset"]
            if sha256(path) != frame["sha256"]:
                raise RuntimeError(f"frame hash mismatch: {path}")
            with Image.open(path) as image:
                if image.size != (1280, 900):
                    raise RuntimeError(f"frame dimensions invalid: {path}")
            assets.append(frame["asset"])
    inspection_record = manifest["units"][CHAMBER]["inspectionLight"]
    inspection_path = output_root / inspection_record["asset"]
    if sha256(inspection_path) != inspection_record["sha256"]:
        raise RuntimeError("inspection asset hash mismatch")
    with Image.open(inspection_path) as image:
        if image.size != (1280, 900):
            raise RuntimeError("inspection asset dimensions invalid")
    expected = {
        *assets,
        inspection_record["asset"],
        "camera-board-manifest.json",
        manifest["reviewSheet"],
        manifest["condenserComparisonSheet"],
        manifest["inspectionReviewSheet"],
    }
    actual = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise RuntimeError(
            f"formal inventory mismatch: missing={sorted(expected-actual)} unknown={sorted(actual-expected)}"
        )
    for record in manifest["reviewEvidence"].values():
        if sha256(output_root / record["asset"]) != record["sha256"]:
            raise RuntimeError(f"review evidence hash mismatch: {record['asset']}")


def frame_hashes(manifest, output_root):
    return {
        frame["asset"]: sha256(output_root / frame["asset"])
        for unit in manifest["units"].values()
        for frame in unit["frames"].values()
    }


def refresh_review_metadata_only(output_root):
    output_root = Path(output_root).resolve()
    validate_output(output_root)
    original_manifest = json.loads(
        (output_root / "camera-board-manifest.json").read_text(encoding="utf-8")
    )
    original_frames = frame_hashes(original_manifest, output_root)
    parent = output_root.parent
    backup_root = parent / f".{output_root.name}-metadata-refresh-backup"
    if backup_root.exists():
        raise RuntimeError(f"metadata refresh backup already exists: {backup_root}")
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}-metadata-refresh-", dir=parent)
    )
    published = False
    try:
        shutil.copytree(output_root, staging_root, dirs_exist_ok=True)
        staging_manifest_path = staging_root / "camera-board-manifest.json"
        staging_manifest = json.loads(staging_manifest_path.read_text(encoding="utf-8"))
        for unit_id, display_name in DISPLAY_NAMES_ZH.items():
            staging_manifest["units"][unit_id]["semanticId"] = unit_id
            staging_manifest["units"][unit_id]["displayNameZh"] = display_name
        staging_manifest["nameCompatibilityRefresh"] = {
            "mode": "review-metadata-only",
            "renderedFramesPreserved": True,
            "blenderInvoked": False,
        }
        staging_manifest_path.write_text(
            json.dumps(staging_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        create_review_sheets(staging_root)
        validate_output(staging_root)
        refreshed_manifest = json.loads(staging_manifest_path.read_text(encoding="utf-8"))
        if frame_hashes(refreshed_manifest, staging_root) != original_frames:
            raise RuntimeError("metadata refresh changed rendered frame hashes or names")

        os.replace(output_root, backup_root)
        try:
            os.replace(staging_root, output_root)
            validate_output(output_root)
            published = True
        except Exception:
            if output_root.exists():
                shutil.rmtree(output_root)
            os.replace(backup_root, output_root)
            raise
        shutil.rmtree(backup_root)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        if backup_root.exists() and published:
            shutil.rmtree(backup_root)
    return {
        "output": str(output_root),
        "displayNamesZh": DISPLAY_NAMES_ZH,
        "renderedFrameHashes": original_frames,
    }


def main():
    args = parse_outer_args()
    output_root = Path(args.output_root).resolve()
    if args.refresh_review_metadata_only:
        if args.probe_only:
            raise ValueError("--probe-only cannot be combined with --refresh-review-metadata-only")
        result = refresh_review_metadata_only(output_root)
        print(
            "CAMERA_BOARD_METADATA_REFRESH="
            + json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        )
        return
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")
    run_blender(output_root, probe_only=args.probe_only)
    if args.probe_only:
        return
    finalize_approved_stage1_assets(output_root)
    create_review_sheets(output_root)
    validate_output(output_root)
    print(f"CAMERA_BOARD={output_root}")


def blender_worker(output_root, probe_only=False):
    import bpy
    from mathutils import Matrix, Vector

    output_root = Path(output_root)

    def require(condition, message):
        if not condition:
            raise RuntimeError(message)

    def rounded(values):
        return [round(float(value), 8) for value in values]

    def matrix_record(matrix):
        return [[round(float(value), 8) for value in row] for row in matrix]

    def camera_snapshot(camera):
        return {
            "matrix": camera.matrix_world.copy(),
            "lens": float(camera.data.lens),
            "sensor": float(camera.data.sensor_width),
            "shiftX": float(camera.data.shift_x),
            "shiftY": float(camera.data.shift_y),
            "clipStart": float(camera.data.clip_start),
            "clipEnd": float(camera.data.clip_end),
        }

    def restore_camera(camera, snapshot):
        camera.matrix_world = snapshot["matrix"]
        camera.data.lens = snapshot["lens"]
        camera.data.sensor_width = snapshot["sensor"]
        camera.data.shift_x = snapshot["shiftX"]
        camera.data.shift_y = snapshot["shiftY"]
        camera.data.clip_start = snapshot["clipStart"]
        camera.data.clip_end = snapshot["clipEnd"]

    def set_camera(camera, preset):
        camera.location = Vector(preset["location"])
        camera.rotation_euler = (
            Vector(preset["target"]) - camera.location
        ).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = preset["lensMm"]
        camera.data.sensor_width = preset["sensorWidthMm"]
        camera.data.shift_x = preset["shiftX"]
        camera.data.shift_y = preset["shiftY"]

    def camera_record(camera, preset):
        return {
            "location": rounded(camera.location),
            "rotation": rounded(camera.rotation_euler),
            "target": rounded(preset["target"]),
            "lensMm": float(camera.data.lens),
            "sensorWidthMm": float(camera.data.sensor_width),
            "shiftX": float(camera.data.shift_x),
            "shiftY": float(camera.data.shift_y),
        }

    require(SOURCE_BLEND is not None, "TWINKLE_SOURCE_BLEND is required")
    require(CANDIDATE_BLEND is not None, "TWINKLE_CANDIDATE_BLEND is required")
    require(Path(bpy.data.filepath).resolve() == CANDIDATE_BLEND.resolve(), "wrong blend")
    require(sha256(SOURCE_BLEND) == EXPECTED_SOURCE_SHA256, "source blend drift")
    require(sha256(CANDIDATE_BLEND) == EXPECTED_CANDIDATE_SHA256, "candidate blend drift")
    require(AUTHORITY_MANIFEST.is_file(), "authority manifest missing")

    scene = bpy.context.scene
    camera = scene.camera
    require(camera is not None, "scene camera missing")
    all_roots = {
        name: bpy.data.objects.get(name)
        for config in UNITS.values()
        for name in config["rootObjects"]
    }
    require(all(all_roots.values()), "required mechanical root missing")
    for name in RENDER_PROFILE["existingLights"]:
        light = bpy.data.objects.get(name)
        require(light is not None and light.type == "LIGHT", f"required light missing: {name}")

    if probe_only:
        print(
            "CAMERA_BOARD_PROBE="
            + json.dumps(
                {
                    "schema": "twinkle-route1-authored-camera-presets-v3",
                    "rendersWritten": 0,
                    "candidateBlendSaved": False,
                    "modelSha256": EXPECTED_CANDIDATE_SHA256,
                    "units": {
                        unit_id: {
                            "preset": AUTHORED_PRESETS[unit_id],
                            "projectionCamera": authored_camera_spec(unit_id).as_dict(),
                            "rootObjects": list(config["rootObjects"]),
                            "states": STATE_PROGRESS[unit_id],
                        }
                        for unit_id, config in UNITS.items()
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return

    require(not output_root.exists(), "output root already exists")
    output_root.mkdir(parents=True)
    assets_root = output_root / "assets"
    assets_root.mkdir()

    original_scene_camera = scene.camera
    original_camera = camera_snapshot(camera)
    original_render = {
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "format": scene.render.image_settings.file_format,
        "mode": scene.render.image_settings.color_mode,
        "transparent": scene.render.film_transparent,
        "filepath": scene.render.filepath,
        "taaRenderSamples": scene.eevee.taa_render_samples,
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": scene.view_settings.exposure,
        "gamma": scene.view_settings.gamma,
    }
    original_objects = set(bpy.data.objects.keys())
    original_lights = set(bpy.data.lights.keys())
    original_matrices = {
        name: obj.matrix_world.copy() for name, obj in bpy.data.objects.items()
    }
    original_visibility = {
        name: bool(obj.hide_render) for name, obj in bpy.data.objects.items()
    }
    original_material_slots = {
        obj.name: tuple(slot.material.name if slot.material else None for slot in obj.material_slots)
        for obj in bpy.data.objects
        if obj.type == "MESH"
    }

    for name in RENDER_PROFILE["sharedHiddenObjects"]:
        require(name in bpy.data.objects, f"shared hidden object missing: {name}")
        bpy.data.objects[name].hide_render = True

    scene.render.engine = RENDER_PROFILE["engine"]
    scene.render.resolution_x = RENDER_PROFILE["resolution"][0]
    scene.render.resolution_y = RENDER_PROFILE["resolution"][1]
    scene.render.resolution_percentage = RENDER_PROFILE["resolution"][2]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = RENDER_PROFILE["filmTransparent"]
    scene.eevee.taa_render_samples = RENDER_PROFILE["taaRenderSamples"]
    scene.view_settings.view_transform = RENDER_PROFILE["viewTransform"]
    scene.view_settings.look = RENDER_PROFILE["look"]
    scene.view_settings.exposure = RENDER_PROFILE["exposure"]
    scene.view_settings.gamma = RENDER_PROFILE["gamma"]

    technical_lights = []
    for key, config in RENDER_PROFILE["sharedTechnicalLights"].items():
        data = bpy.data.lights.new(f"TEMP__SHARED_{key.upper()}_DATA", "AREA")
        data.energy = config["energy"]
        data.shape = "DISK"
        data.size = config["size"]
        obj = bpy.data.objects.new(f"TEMP__SHARED_{key.upper()}", data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = Vector(config["location"])
        obj.rotation_euler = (
            Vector(AUTHORED_PRESETS[CHAMBER]["target"]) - obj.location
        ).to_track_quat("-Z", "Y").to_euler()
        technical_lights.append((obj, data))

    top_plate = bpy.data.objects.get("DetectBoxTopPlate :: 实体1")
    require(top_plate is not None and len(top_plate.material_slots) == 1, "top plate material missing")
    material_slot = top_plate.material_slots[0]
    original_material = material_slot.material
    original_link = material_slot.link
    require(original_material is not None, "top plate material empty")
    temporary_material = original_material.copy()
    temporary_material.name = "TEMP__SHARED_TOP_PLATE_NO_NORMAL"
    temporary_material_name = temporary_material.name
    normal_nodes = [
        node
        for node in temporary_material.node_tree.nodes
        if node.bl_idname == "ShaderNodeNormalMap"
    ]
    require(len(normal_nodes) == 1, "top plate normal map rule changed")
    normal_before = float(normal_nodes[0].inputs["Strength"].default_value)
    normal_nodes[0].inputs["Strength"].default_value = 0.0
    material_slot.link = "OBJECT"
    material_slot.material = temporary_material

    light_record = []
    for name in RENDER_PROFILE["existingLights"]:
        obj = bpy.data.objects[name]
        light_record.append(
            {
                "name": name,
                "type": obj.data.type,
                "energy": float(obj.data.energy),
                "color": rounded(obj.data.color),
                "location": rounded(obj.location),
                "rotation": rounded(obj.rotation_euler),
            }
        )
    for obj, data in technical_lights:
        light_record.append(
            {
                "name": obj.name,
                "type": data.type,
                "energy": float(data.energy),
                "color": rounded(data.color),
                "location": rounded(obj.location),
                "rotation": rounded(obj.rotation_euler),
                "size": float(data.size),
            }
        )
    material_rule = {
        "object": top_plate.name,
        "originalMaterial": original_material.name,
        "temporaryMaterial": temporary_material.name,
        "normalMapStrengthBefore": normal_before,
        "normalMapStrengthDuringRender": 0.0,
        "scope": "all-seven-frames",
    }
    color_management = {
        "viewTransform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": float(scene.view_settings.exposure),
        "gamma": float(scene.view_settings.gamma),
    }
    light_hash = canonical_hash(light_record)
    material_hash = canonical_hash(material_rule)
    color_hash = canonical_hash(color_management)
    profile_for_hash = {
        **RENDER_PROFILE,
        "lightRigHash": light_hash,
        "materialRuleHash": material_hash,
        "colorManagementHash": color_hash,
    }
    profile_id = "shared-render-" + canonical_hash(profile_for_hash)[:16].lower()
    batch_id = "stage1-" + canonical_hash(
        {"model": EXPECTED_CANDIDATE_SHA256, "profile": profile_id, "states": STATE_PROGRESS}
    )[:16].lower()

    units_manifest = {}
    try:
        for unit_id, config in UNITS.items():
            preset = AUTHORED_PRESETS[unit_id]
            set_camera(camera, preset)
            camera_data = camera_record(camera, preset)
            roots = [all_roots[name] for name in config["rootObjects"]]
            root_originals = {root.name: original_matrices[root.name] for root in roots}
            frames = {}
            for state, progress in STATE_PROGRESS[unit_id].items():
                component_offsets = {}
                for root, component, full_offset in zip(
                    roots, config["componentNames"], config["fullOffsets"]
                ):
                    offset = Vector(full_offset) * progress
                    root.matrix_world = Matrix.Translation(offset) @ root_originals[root.name]
                    component_offsets[component] = rounded(offset)
                filename = f"{unit_id.replace('_', '-')}--{state}.png"
                relative_asset = f"assets/{filename}"
                path = output_root / relative_asset
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                frame_record = {
                    "progress": progress,
                    "asset": relative_asset,
                    "componentOffsetsM": component_offsets,
                    "rootWorldMatrices": {
                        root.name: matrix_record(root.matrix_world) for root in roots
                    },
                    "camera": camera_data,
                    "modelSha256": EXPECTED_CANDIDATE_SHA256,
                    "renderBatchId": batch_id,
                    "renderProfileId": profile_id,
                    "lightRigHash": light_hash,
                    "materialRuleHash": material_hash,
                    "colorManagementHash": color_hash,
                    "sha256": sha256(path),
                }
                frames[state] = frame_record
            if unit_id == CHAMBER:
                inspection_config = CHAMBER_INSPECTION["light"]
                inspection_data = bpy.data.lights.new(
                    "TEMP__CHAMBER_INSPECTION_DATA", inspection_config["type"]
                )
                inspection_data.energy = inspection_config["energy"]
                inspection_data.shape = "DISK"
                inspection_data.size = inspection_config["size"]
                inspection_object = bpy.data.objects.new(
                    "TEMP__CHAMBER_INSPECTION", inspection_data
                )
                bpy.context.scene.collection.objects.link(inspection_object)
                camera_location = Vector(preset["location"])
                target = Vector(preset["target"])
                view = (target - camera_location).normalized()
                right = view.cross(Vector((0.0, 0.0, 1.0))).normalized()
                up = right.cross(view).normalized()
                right_offset, up_offset, forward_offset = inspection_config[
                    "cameraRelativeOffset"
                ]
                inspection_object.location = (
                    camera_location
                    + right * right_offset
                    + up * up_offset
                    + view * forward_offset
                )
                inspection_target = target + view * inspection_config["aimDepth"]
                inspection_object.rotation_euler = (
                    inspection_target - inspection_object.location
                ).to_track_quat("-Z", "Y").to_euler()
                raw_path = output_root / CHAMBER_INSPECTION["rawAsset"]
                scene.render.filepath = str(raw_path)
                bpy.ops.render.render(write_still=True)
                bpy.data.objects.remove(inspection_object, do_unlink=True)
                bpy.data.lights.remove(inspection_data)
            for root in roots:
                root.matrix_world = root_originals[root.name]
            record = {
                "rootObjects": list(config["rootObjects"]),
                "fullOffsetsM": {
                    component: rounded(offset)
                    for component, offset in zip(config["componentNames"], config["fullOffsets"])
                },
                "cameraPresetId": preset["id"],
                "camera": camera_data,
                "projectionCamera": authored_camera_spec(unit_id).as_dict(),
                "frames": frames,
                "semanticId": unit_id,
                "displayNameZh": DISPLAY_NAMES_ZH[unit_id],
            }
            if unit_id == CHAMBER:
                record.update(
                    {
                        "timingMs": {"settledHold": 200, "seam": 240, "acceleratedTravel": 760},
                        "panelCopy": RENDER_PROFILE["panelCopy"],
                        "hideRenderUsed": False,
                        "mirror3IdentityStatus": "reference-only",
                    }
                )
            else:
                record.update(
                    {
                        "legacySourceObjectId": config["legacySourceObjectId"],
                        "legacyAcceptedHashes": LEGACY_CONDENSER_HASHES,
                    }
                )
            units_manifest[unit_id] = record

    finally:
        for name, matrix in original_matrices.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].matrix_world = matrix
        for name, hidden in original_visibility.items():
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = hidden
        restore_camera(camera, original_camera)
        scene.camera = original_scene_camera
        material_slot.material = original_material
        material_slot.link = original_link
        if temporary_material_name in bpy.data.materials:
            bpy.data.materials.remove(temporary_material)
        for obj, data in technical_lights:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            if data.name in bpy.data.lights:
                bpy.data.lights.remove(data)
        scene.render.engine = original_render["engine"]
        scene.render.resolution_x = original_render["x"]
        scene.render.resolution_y = original_render["y"]
        scene.render.resolution_percentage = original_render["pct"]
        scene.render.image_settings.file_format = original_render["format"]
        scene.render.image_settings.color_mode = original_render["mode"]
        scene.render.film_transparent = original_render["transparent"]
        scene.render.filepath = original_render["filepath"]
        scene.eevee.taa_render_samples = original_render["taaRenderSamples"]
        scene.view_settings.view_transform = original_render["viewTransform"]
        scene.view_settings.look = original_render["look"]
        scene.view_settings.exposure = original_render["exposure"]
        scene.view_settings.gamma = original_render["gamma"]

    current_material_slots = {
        obj.name: tuple(slot.material.name if slot.material else None for slot in obj.material_slots)
        for obj in bpy.data.objects
        if obj.type == "MESH"
    }
    audit = {
        "cameraChanged": camera.matrix_world != original_camera["matrix"] or scene.camera != original_scene_camera,
        "renderSettingsChanged": (
            scene.render.engine != original_render["engine"]
            or scene.render.resolution_x != original_render["x"]
            or scene.render.resolution_y != original_render["y"]
            or scene.render.resolution_percentage != original_render["pct"]
            or scene.render.image_settings.file_format != original_render["format"]
            or scene.render.image_settings.color_mode != original_render["mode"]
            or scene.render.film_transparent != original_render["transparent"]
            or scene.eevee.taa_render_samples != original_render["taaRenderSamples"]
            or scene.view_settings.view_transform != original_render["viewTransform"]
            or scene.view_settings.look != original_render["look"]
            or float(scene.view_settings.exposure) != original_render["exposure"]
            or float(scene.view_settings.gamma) != original_render["gamma"]
        ),
        "renderVisibilityChanged": sorted(
            name for name, hidden in original_visibility.items()
            if name in bpy.data.objects and bool(bpy.data.objects[name].hide_render) != hidden
        ),
        "objectTransformsChanged": sorted(
            name for name, matrix in original_matrices.items()
            if name in bpy.data.objects and bpy.data.objects[name].matrix_world != matrix
        ),
        "materialSlotsChanged": sorted(
            name for name, slots in original_material_slots.items()
            if current_material_slots.get(name) != slots
        ),
        "newObjectsRemaining": sorted(set(bpy.data.objects.keys()) - original_objects),
        "objectsMissing": sorted(original_objects - set(bpy.data.objects.keys())),
        "temporaryDataBlocksRemaining": sorted(set(bpy.data.lights.keys()) - original_lights),
        "temporaryLightsRemoved": set(bpy.data.lights.keys()) == original_lights,
        "sharedMaterialRestored": (
            material_slot.material == original_material
            and material_slot.link == original_link
            and temporary_material_name not in bpy.data.materials
        ),
    }
    require(
        audit == {
            "cameraChanged": False,
            "renderSettingsChanged": False,
            "renderVisibilityChanged": [],
            "objectTransformsChanged": [],
            "materialSlotsChanged": [],
            "newObjectsRemaining": [],
            "objectsMissing": [],
            "temporaryDataBlocksRemaining": [],
            "temporaryLightsRemoved": True,
            "sharedMaterialRestored": True,
        },
        f"scene restoration failed: {audit}",
    )
    require(sha256(SOURCE_BLEND) == EXPECTED_SOURCE_SHA256, "source changed")
    require(sha256(CANDIDATE_BLEND) == EXPECTED_CANDIDATE_SHA256, "candidate changed")

    manifest = {
        "schema": "twinkle-route1-camera-board-v4",
        "canvas": {"width": 1280, "height": 900},
        "source": {"path": str(SOURCE_BLEND), "sha256": EXPECTED_SOURCE_SHA256},
        "candidateBlend": {"path": str(CANDIDATE_BLEND), "sha256": EXPECTED_CANDIDATE_SHA256},
        "designAuthority": {
            CHAMBER: {
                "kind": "codex-thread",
                "threadId": "01a02ff9-18a2-7da3-a250-12dc45e86ff9",
                "migratedToSpecification": True,
                "sourceEvidence": {
                    "irSideContextSha256": "CC7CB230CFD2065A7D312E56D213AD57DB835D677877D39D55F8108ED32E65AF",
                    "simultaneousTerminalSha256": "A681491EEA32638261583E9CEE6102A530EA14D4066F9F905885C548A2B529EB",
                },
            },
            CONDENSER: {
                "kind": "repository-record",
                "specification": "docs/superpowers/specs/2026-08-20-twinkle-page-coordinated-render-design.md",
                "legacyAcceptedReference": {
                    "path": str(LEGACY_CONDENSER_REFERENCE),
                    "sha256": LEGACY_CONDENSER_REFERENCE_SHA256,
                },
            },
        },
        "renderBatchId": batch_id,
        "renderProfileId": profile_id,
        "renderProfile": {
            "id": profile_id,
            "frameCount": 7,
            "engine": RENDER_PROFILE["engine"],
            "resolution": list(RENDER_PROFILE["resolution"]),
            "taaRenderSamples": RENDER_PROFILE["taaRenderSamples"],
            "filmTransparent": RENDER_PROFILE["filmTransparent"],
            "colorManagement": color_management,
            "existingLights": list(RENDER_PROFILE["existingLights"]),
            "sharedTechnicalLights": RENDER_PROFILE["sharedTechnicalLights"],
            "sharedHiddenObjects": list(RENDER_PROFILE["sharedHiddenObjects"]),
            "lightRig": light_record,
            "lightRigHash": light_hash,
            "materialRule": material_rule,
            "materialRuleHash": material_hash,
            "colorManagementHash": color_hash,
        },
        "units": units_manifest,
        "sceneMutationAudit": audit,
        "stage1CleanupEvidence": {
            "deletedDirectories": list(STAGE1_DELETED_DIRECTORIES),
            "frozenSentinels": list(FROZEN_SENTINELS),
            "deletedSummary": STAGE1_CLEANUP_SUMMARY,
        },
        "visualRepairCleanupEvidence": VISUAL_REPAIR_CLEANUP_EVIDENCE,
        "reviewSheet": "stage1-seven-frame-contact-sheet.png",
        "condenserComparisonSheet": "condenser-old-new-comparison.png",
        "inspectionReviewSheet": "collection-chamber-inspection-comparison.png",
        "humanReviewRequired": True,
        "humanReviewApproved": False,
        "candidateBlendSaved": False,
        "productionPageChanged": False,
    }
    (output_root / "camera-board-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        "CAMERA_BOARD_WORKER="
        + json.dumps(
            {
                "output": str(output_root),
                "renderBatchId": batch_id,
                "renderProfileId": profile_id,
                "frames": 7,
                "sceneMutationAudit": audit,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    if "--" in sys.argv and "--worker" in sys.argv:
        args = worker_args()
        blender_worker(args.output_root, probe_only=args.probe_only)
    else:
        main()
