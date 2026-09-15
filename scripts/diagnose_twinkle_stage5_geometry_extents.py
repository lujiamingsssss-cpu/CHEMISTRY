"""Read-only TWINKLE Stage 5 visibility and camera-projection extent diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


CONTRACT_SHA256 = "2A90B6FEDF7C58606EDF8E11702E79706C9F0D4726187CD356D5EE517256C758"
SOURCE_SHA256 = "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "HAIR", "CURVES"}


class DiagnosticError(ValueError):
    """Raised when the read-only diagnostic authority or geometry drifts."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def classify_object(
    object_type: str,
    hide_render: bool,
    shared_background_excluded: bool,
    collection_hidden: bool,
) -> str:
    if object_type in {"LIGHT", "CAMERA"}:
        return "lightingOrCamera"
    if hide_render or collection_hidden:
        return "hiddenGeometry" if object_type in RENDERABLE_TYPES else "hiddenAuxiliary"
    if shared_background_excluded:
        return "fixedBackgroundExcluded"
    if object_type in RENDERABLE_TYPES:
        return "modelForeground"
    return "auxiliaryNonRenderable"


def viewport_safety(
    multiplier: float,
    viewports: tuple[tuple[int, int], ...],
    translate_x: float,
    scale: float,
) -> list[dict[str, Any]]:
    reference_width, reference_height = 1280.0, 900.0
    canvas_width = reference_width * multiplier
    canvas_height = reference_height * multiplier
    margin_x = (canvas_width - reference_width) / 2.0
    margin_y = (canvas_height - reference_height) / 2.0
    results = []
    for viewport_width, viewport_height in viewports:
        fit = min(viewport_width / reference_width, viewport_height / reference_height)
        reference_left = (viewport_width - reference_width * fit) / 2.0
        reference_top = (viewport_height - reference_height * fit) / 2.0
        canvas_edges = {
            "left": reference_left - margin_x * fit,
            "right": reference_left + (reference_width + margin_x) * fit,
            "top": reference_top - margin_y * fit,
            "bottom": reference_top + (reference_height + margin_y) * fit,
        }
        center_x, center_y = viewport_width / 2.0, viewport_height / 2.0
        terminal = {
            "left": center_x + (canvas_edges["left"] - center_x) * scale + translate_x,
            "right": center_x + (canvas_edges["right"] - center_x) * scale + translate_x,
            "top": center_y + (canvas_edges["top"] - center_y) * scale,
            "bottom": center_y + (canvas_edges["bottom"] - center_y) * scale,
        }
        outside = {
            "left": -terminal["left"],
            "right": terminal["right"] - viewport_width,
            "top": -terminal["top"],
            "bottom": terminal["bottom"] - viewport_height,
        }
        results.append(
            {
                "viewport": [viewport_width, viewport_height],
                "edges": {
                    name: {"outsidePx": round(value, 6), "passed": value >= 64.0}
                    for name, value in outside.items()
                },
            }
        )
    return results


def minimum_centered_carrier(
    state_ranges: dict[str, dict[str, float]],
    *,
    reference: tuple[int, int],
    viewports: tuple[tuple[int, int], ...],
    translate_x: float,
    scale: float,
    transparent_guard: int,
) -> dict[str, Any]:
    reference_width, reference_height = reference
    union = {
        "minX": min(record["minX"] for record in state_ranges.values()),
        "minY": min(record["minY"] for record in state_ranges.values()),
        "maxX": max(record["maxX"] for record in state_ranges.values()),
        "maxY": max(record["maxY"] for record in state_ranges.values()),
    }
    chosen = None
    for k in range(10, 1002, 2):
        multiplier = k / 10.0
        width, height = 64 * k, 45 * k
        origin_x = (width - reference_width) // 2
        origin_y = (height - reference_height) // 2
        geometry_margins = {
            "left": origin_x + union["minX"],
            "top": origin_y + union["minY"],
            "right": width - (origin_x + union["maxX"]),
            "bottom": height - (origin_y + union["maxY"]),
        }
        safety = viewport_safety(multiplier, viewports, translate_x, scale)
        geometry_passed = min(geometry_margins.values()) >= transparent_guard
        viewport_passed = all(
            edge["passed"] for viewport in safety for edge in viewport["edges"].values()
        )
        if geometry_passed and viewport_passed:
            chosen = (k, multiplier, width, height, origin_x, origin_y, geometry_margins, safety)
            break
    if chosen is None:
        raise DiagnosticError("no bounded 64:45 centered carrier satisfies measured geometry")
    k, multiplier, width, height, origin_x, origin_y, margins, safety = chosen
    full_width, full_height = width * 2, height * 2
    return {
        "projectionUnionInReferencePixels": {key: round(value, 6) for key, value in union.items()},
        "transparentGuardBandPx": transparent_guard,
        "resolutionMultiplier": multiplier,
        "lensShiftCoefficient": round(1.0 / multiplier, 10),
        "lowResolutionCanvas": [width, height],
        "lowResolutionReferenceWindow": {
            "x": origin_x,
            "y": origin_y,
            "width": reference_width,
            "height": reference_height,
        },
        "lowResolutionOverscanMargins": {
            "left": origin_x,
            "top": origin_y,
            "right": origin_x,
            "bottom": origin_y,
        },
        "measuredAlphaGuardMargins": {key: round(value, 6) for key, value in margins.items()},
        "fullQualityCanvas": [full_width, full_height],
        "fullQualityReferenceWindow": {
            "x": origin_x * 2,
            "y": origin_y * 2,
            "width": reference_width * 2,
            "height": reference_height * 2,
        },
        "fullQualityOverscanMargins": {
            "left": origin_x * 2,
            "top": origin_y * 2,
            "right": origin_x * 2,
            "bottom": origin_y * 2,
        },
        "viewportSafety": safety,
        "runtimeVisualOffsetChangeRequired": False,
        "runtimeCarrierMappingScaleChangeRequired": True,
        "runtimeMappingNote": "centered reference window remains authoritative; update carrier-to-reference scale, but add no visual translation",
    }


def _collection_hidden_map(layer_collection, inherited: bool = False, result=None):
    if result is None:
        result = {}
    hidden = inherited or bool(layer_collection.exclude) or bool(layer_collection.collection.hide_render)
    result[layer_collection.collection.name] = hidden
    for child in layer_collection.children:
        _collection_hidden_map(child, hidden, result)
    return result


def _matrix_rows(matrix) -> list[list[float]]:
    return [[round(float(value), 10) for value in row] for row in matrix]


def _project_state(bpy, state_name: str, unit_id: str, stage1: dict[str, Any]) -> dict[str, Any]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Matrix, Vector

    scene = bpy.context.scene
    camera = scene.camera
    unit = stage1["units"][unit_id]
    camera_record = unit["camera"]
    camera.location = Vector(camera_record["location"])
    camera.rotation_mode = "XYZ"
    camera.rotation_euler = Vector(camera_record["rotation"])
    camera.data.lens = camera_record["lensMm"]
    camera.data.sensor_width = camera_record["sensorWidthMm"]
    camera.data.shift_x = camera_record["shiftX"]
    camera.data.shift_y = camera_record["shiftY"]
    component_names = tuple(unit["fullOffsetsM"])
    roots = [bpy.data.objects.get(name) for name in unit["rootObjects"]]
    if not all(roots):
        raise DiagnosticError(f"missing state roots: {state_name}")
    for root, component in zip(roots, component_names):
        root.matrix_world = Matrix.Translation(Vector(unit["fullOffsetsM"][component])) @ root.matrix_world

    scene.render.resolution_x = 640
    scene.render.resolution_y = 450
    scene.render.resolution_percentage = 100
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    hidden_collections = _collection_hidden_map(bpy.context.view_layer.layer_collection)
    shared_excluded = set(stage1["renderProfile"]["sharedHiddenObjects"])
    classifications: dict[str, list[str]] = {}
    projected = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        collection_hidden = bool(obj.users_collection) and all(
            hidden_collections.get(collection.name, False) for collection in obj.users_collection
        )
        category = classify_object(
            obj.type,
            bool(obj.hide_render),
            obj.name in shared_excluded,
            collection_hidden,
        )
        classifications.setdefault(category, []).append(obj.name)
        if category != "modelForeground":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        points = []
        for corner in evaluated.bound_box:
            coordinate = world_to_camera_view(scene, camera, evaluated.matrix_world @ Vector(corner))
            if coordinate.z <= 0:
                continue
            points.append((float(coordinate.x) * 640.0, (1.0 - float(coordinate.y)) * 450.0))
        if not points:
            continue
        projected.append(
            {
                "object": obj.name,
                "minX": min(point[0] for point in points),
                "minY": min(point[1] for point in points),
                "maxX": max(point[0] for point in points),
                "maxY": max(point[1] for point in points),
            }
        )
    if not projected:
        raise DiagnosticError(f"no projected foreground geometry: {state_name}")
    extremes = {
        "left": min(projected, key=lambda record: record["minX"]),
        "top": min(projected, key=lambda record: record["minY"]),
        "right": max(projected, key=lambda record: record["maxX"]),
        "bottom": max(projected, key=lambda record: record["maxY"]),
    }
    bounds = {
        "minX": extremes["left"]["minX"],
        "minY": extremes["top"]["minY"],
        "maxX": extremes["right"]["maxX"],
        "maxY": extremes["bottom"]["maxY"],
    }
    return {
        "state": state_name,
        "unit": unit_id,
        "camera": {
            "location": camera_record["location"],
            "rotation": camera_record["rotation"],
            "lensMm": camera_record["lensMm"],
            "sensorWidthMm": camera_record["sensorWidthMm"],
            "shiftX": camera_record["shiftX"],
            "shiftY": camera_record["shiftY"],
        },
        "projectionBoundsIn640x450Reference": {key: round(value, 6) for key, value in bounds.items()},
        "outsideReferencePx": {
            "left": round(max(0.0, -bounds["minX"]), 6),
            "top": round(max(0.0, -bounds["minY"]), 6),
            "right": round(max(0.0, bounds["maxX"] - 640.0), 6),
            "bottom": round(max(0.0, bounds["maxY"] - 450.0), 6),
        },
        "extremeObjects": {
            edge: {"object": record["object"], "value": round(record["minX" if edge == "left" else "minY" if edge == "top" else "maxX" if edge == "right" else "maxY"], 6)}
            for edge, record in extremes.items()
        },
        "foregroundObjectCount": len(projected),
        "projectedObjects": [
            {key: round(value, 6) if isinstance(value, float) else value for key, value in record.items()}
            for record in projected
        ],
        "classifications": classifications,
    }


def run_diagnostic(repo: Path) -> dict[str, Any]:
    import bpy

    repo = repo.resolve()
    contract_path = repo / "output/twinkle-stage5-formal-model-motion-candidates/work/two-component-asset-contract.json"
    if sha256(contract_path) != CONTRACT_SHA256:
        raise DiagnosticError("contract SHA drift")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source = Path(contract["authority"]["candidateBlend"]["path"])
    source_before = sha256(source)
    if source_before != SOURCE_SHA256 or Path(bpy.data.filepath).resolve() != source.resolve():
        raise DiagnosticError("source blend authority drift")
    stage1_path = repo / contract["authority"]["stage1CameraBoard"]["path"]
    stage1 = json.loads(stage1_path.read_text(encoding="utf-8"))
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise DiagnosticError("active camera missing")
    original = {
        "cameraMatrix": camera.matrix_world.copy(),
        "lens": camera.data.lens,
        "sensorWidth": camera.data.sensor_width,
        "shiftX": camera.data.shift_x,
        "shiftY": camera.data.shift_y,
        "resolutionX": scene.render.resolution_x,
        "resolutionY": scene.render.resolution_y,
        "resolutionPercentage": scene.render.resolution_percentage,
        "rootMatrices": {
            name: bpy.data.objects[name].matrix_world.copy()
            for unit in stage1["units"].values()
            for name in unit["rootObjects"]
            if name in bpy.data.objects
        },
    }
    states = (
        ("condenser.mechanicalExpanded", "dual_channel_condenser_lens_assembly"),
        ("chamber.mechanicalExpanded", "dual_channel_collection_optics_chamber"),
        ("chamber.inspectionStable", "dual_channel_collection_optics_chamber"),
    )
    results = []
    try:
        for state_name, unit_id in states:
            for name, matrix in original["rootMatrices"].items():
                bpy.data.objects[name].matrix_world = matrix
            results.append(_project_state(bpy, state_name, unit_id, stage1))
    finally:
        from mathutils import Matrix

        for name, matrix in original["rootMatrices"].items():
            bpy.data.objects[name].matrix_world = matrix
        camera.matrix_world = Matrix(original["cameraMatrix"])
        camera.data.lens = original["lens"]
        camera.data.sensor_width = original["sensorWidth"]
        camera.data.shift_x = original["shiftX"]
        camera.data.shift_y = original["shiftY"]
        scene.render.resolution_x = original["resolutionX"]
        scene.render.resolution_y = original["resolutionY"]
        scene.render.resolution_percentage = original["resolutionPercentage"]
        bpy.context.view_layer.update()
    source_after = sha256(source)
    if source_after != source_before:
        raise DiagnosticError("source blend changed during read-only diagnostic")
    state_ranges = {record["state"]: record["projectionBoundsIn640x450Reference"] for record in results}
    recommendation = minimum_centered_carrier(
        state_ranges,
        reference=(640, 450),
        viewports=((1280, 800), (900, 700)),
        translate_x=240,
        scale=0.97,
        transparent_guard=1,
    )
    chamber_bounds_equal = results[1]["projectionBoundsIn640x450Reference"] == results[2]["projectionBoundsIn640x450Reference"]
    return {
        "schema": "twinkle-stage5-read-only-geometry-extent-diagnostic-v1",
        "contractSha256": CONTRACT_SHA256,
        "sourceBlendSha256Before": source_before,
        "sourceBlendSha256After": source_after,
        "renderInvoked": False,
        "sourceBlendSaved": False,
        "referenceWindow": {"x": 0, "y": 0, "width": 640, "height": 450},
        "states": results,
        "chamberMechanicalAndInspectionProjectionEqual": chamber_bounds_equal,
        "minimumCentered64x45Recommendation": recommendation,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    values = list(sys.argv if argv is None else argv)
    if "--" in values:
        values = values[values.index("--") + 1 :]
    elif argv is None:
        values = values[1:]
    return parser.parse_args(values)


def main() -> int:
    report = run_diagnostic(parse_args().repo)
    print("TWINKLE_GEOMETRY_EXTENTS_JSON=" + json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
