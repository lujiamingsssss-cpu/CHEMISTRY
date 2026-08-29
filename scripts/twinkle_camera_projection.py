"""Pure-Python perspective projection for the TWINKLE camera-board gate.

The implementation follows Blender 5.2 world_to_camera_view: transform a
world point into camera-local coordinates, scale the perspective frame to its
positive view depth, then map the point into normalized device coordinates.
This module intentionally supports only the camera mode exercised by frozen
project evidence: perspective projection, landscape output, square pixels,
and AUTO/HORIZONTAL sensor fit.
"""

from __future__ import annotations

import math
from typing import NamedTuple


SUPPORTED_SENSOR_FITS = {"AUTO", "HORIZONTAL"}


class CameraSpec:
    __slots__ = (
        "location",
        "target",
        "lens_mm",
        "sensor_width_mm",
        "shift_x",
        "shift_y",
        "resolution_x",
        "resolution_y",
        "sensor_fit",
    )

    def __init__(
        self,
        *,
        location,
        target,
        lens_mm,
        sensor_width_mm,
        shift_x,
        shift_y,
        resolution_x,
        resolution_y,
        sensor_fit="AUTO",
    ):
        self.location = _vector3(location, "location")
        self.target = _vector3(target, "target")
        self.lens_mm = float(lens_mm)
        self.sensor_width_mm = float(sensor_width_mm)
        self.shift_x = float(shift_x)
        self.shift_y = float(shift_y)
        self.resolution_x = int(resolution_x)
        self.resolution_y = int(resolution_y)
        self.sensor_fit = str(sensor_fit).upper()
        if not math.isfinite(self.lens_mm) or self.lens_mm <= 0.0:
            raise ValueError("lens_mm must be positive")
        if not math.isfinite(self.sensor_width_mm) or self.sensor_width_mm <= 0.0:
            raise ValueError("sensor_width_mm must be positive")
        if not math.isfinite(self.shift_x) or not math.isfinite(self.shift_y):
            raise ValueError("camera shift must be finite")
        if self.resolution_x <= 0 or self.resolution_y <= 0:
            raise ValueError("resolution must be positive")
        if self.sensor_fit not in SUPPORTED_SENSOR_FITS:
            raise ValueError(f"unsupported sensor_fit: {self.sensor_fit}")
        if self.aspect < 1.0:
            raise ValueError("only landscape horizontal sensor fit is supported")
        if _length(_subtract(self.target, self.location)) <= 1e-12:
            raise ValueError("camera location and target must differ")

    @property
    def aspect(self):
        return self.resolution_x / self.resolution_y

    def as_dict(self):
        return {
            "location": self.location,
            "target": self.target,
            "lens_mm": self.lens_mm,
            "sensor_width_mm": self.sensor_width_mm,
            "shift_x": self.shift_x,
            "shift_y": self.shift_y,
            "resolution_x": self.resolution_x,
            "resolution_y": self.resolution_y,
            "sensor_fit": self.sensor_fit,
        }


class ProjectedPoint(NamedTuple):
    x: float
    y: float
    depth: float


class Bounds(NamedTuple):
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self):
        return self.max_x - self.min_x

    @property
    def height(self):
        return self.max_y - self.min_y

    def as_list(self):
        return [self.min_x, self.min_y, self.max_x, self.max_y]


class StateProjection(NamedTuple):
    bounds: Bounds
    width_of_left_stage: float
    depth_positive: bool
    target_clipped: bool
    panel_intrusion: bool


class CompositionResult(NamedTuple):
    left_stage_bounds: Bounds
    sweep_bounds: Bounds
    sweep_width_of_left_stage: float
    by_state: dict[str, StateProjection]
    diagnostics: tuple[str, ...]
    reject_reasons: tuple[str, ...]


def _vector3(values, label):
    result = tuple(float(value) for value in values)
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise ValueError(f"{label} must contain three finite values")
    return result


def _subtract(left, right):
    return tuple(a - b for a, b in zip(left, right))


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length(vector):
    return math.sqrt(_dot(vector, vector))


def _normalize(vector, label):
    length = _length(vector)
    if length <= 1e-12:
        raise ValueError(f"cannot normalize {label}")
    return tuple(value / length for value in vector)


def camera_basis(camera):
    """Return Blender-style camera right, up, and forward world axes."""

    forward = _normalize(_subtract(camera.target, camera.location), "view axis")
    world_up = (0.0, 0.0, 1.0)
    right = _normalize(_cross(forward, world_up), "camera right axis")
    up = _normalize(_cross(right, forward), "camera up axis")
    return right, up, forward


def project_world_point(point, camera):
    """Project one world point to top-left-origin NDC plus positive view depth."""

    point = _vector3(point, "point")
    delta = _subtract(point, camera.location)
    right, up, forward = camera_basis(camera)
    local_x = _dot(delta, right)
    local_y = _dot(delta, up)
    depth = _dot(delta, forward)
    if abs(depth) <= 1e-12:
        return ProjectedPoint(0.5, 0.5, 0.0)

    half_width = depth * camera.sensor_width_mm / (2.0 * camera.lens_mm)
    half_height = half_width / camera.aspect
    ndc_x = 0.5 - camera.shift_x + local_x / (2.0 * half_width)
    ndc_y_bottom = (
        0.5
        - camera.shift_y * camera.aspect
        + local_y / (2.0 * half_height)
    )
    return ProjectedPoint(ndc_x, 1.0 - ndc_y_bottom, depth)


def project_bounds(points, camera):
    projected = [project_world_point(point, camera) for point in points]
    if not projected:
        raise ValueError("at least one point is required")
    return Bounds(
        min(point.x for point in projected),
        min(point.y for point in projected),
        max(point.x for point in projected),
        max(point.y for point in projected),
    )


def evaluate_composition(
    points_by_state,
    camera,
    *,
    reserved_right,
    minimum_target_width,
    maximum_target_width,
    maximum_sweep_width,
):
    """Evaluate one fixed authored camera without selecting or changing it."""

    reserved_right = float(reserved_right)
    left_stage_right = 1.0 - reserved_right
    if not 0.0 < left_stage_right < 1.0:
        raise ValueError("reserved_right must leave a non-empty left stage")
    left_stage = Bounds(0.0, 0.0, left_stage_right, 1.0)
    by_state = {}
    all_projected = []
    diagnostics = []
    reject_reasons = []

    for state, points in points_by_state.items():
        projected = [project_world_point(point, camera) for point in points]
        if not projected:
            raise ValueError(f"state has no points: {state}")
        bounds = Bounds(
            min(point.x for point in projected),
            min(point.y for point in projected),
            max(point.x for point in projected),
            max(point.y for point in projected),
        )
        depth_positive = all(point.depth > 0.0 for point in projected)
        width = bounds.width / left_stage_right
        panel_intrusion = bounds.max_x > left_stage_right
        clipped = (
            bounds.min_x < 0.0
            or bounds.min_y < 0.0
            or bounds.max_x > 1.0
            or bounds.max_y > 1.0
        )
        by_state[state] = StateProjection(
            bounds,
            width,
            depth_positive,
            clipped,
            panel_intrusion,
        )
        all_projected.extend(projected)
        if not depth_positive:
            reject_reasons.append(f"{state}-target-behind-camera")
        if width < minimum_target_width:
            diagnostics.append(f"{state}-target-width-below-{minimum_target_width:.2f}")
        if width > maximum_target_width:
            diagnostics.append(f"{state}-target-width-above-{maximum_target_width:.2f}")
        if clipped:
            diagnostics.append(f"{state}-target-clipped")
        if panel_intrusion:
            diagnostics.append(f"{state}-panel-intrusion")

    sweep = Bounds(
        min(point.x for point in all_projected),
        min(point.y for point in all_projected),
        max(point.x for point in all_projected),
        max(point.y for point in all_projected),
    )
    sweep_width = sweep.width / left_stage_right
    if sweep_width > maximum_sweep_width:
        diagnostics.append(f"target-sweep-width-above-{maximum_sweep_width:.2f}")
    return CompositionResult(
        left_stage,
        sweep,
        sweep_width,
        by_state,
        tuple(diagnostics),
        tuple(reject_reasons),
    )
