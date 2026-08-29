import hashlib
import json
import os
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
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
EXPECTED_SOURCE_SHA256 = (
    "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81"
)
EXPECTED_CANDIDATE_SHA256 = (
    "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
)
UNITS = {
    "dual_channel_collection_optics_chamber": {
        "unit": "dual_channel_collection_optics_chamber",
        "rootObjects": (
            "DetectBox_Bottom_Mala2020:1",
            "Side2_optics:1",
        ),
        "meshObjects": None,
        "authorityStateOffsets": (
            (0.0, 0.0, -0.14),
            (0.0, -0.10, 0.0),
        ),
        "mechanicalAuthorityUnit": "bottom-and-side-panels-synchronized",
    },
    "dual_channel_condenser_lens_assembly": {
        "unit": "dual_channel_condenser_lens_assembly",
        "rootObjects": ("SHOWCASE_GROUP__f_dual_acl_housing",),
        "meshObjects": None,
        "authorityStateOffsets": ((0.034, 0.012, -0.016),),
        "mechanicalAuthorityUnit": "f_dual_acl_housing",
        "legacySourceObjectId": "SHOWCASE_GROUP__f_dual_acl_housing",
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rounded(values):
    return tuple(round(float(value), 8) for value in values)


def descendants(root):
    pending = [root]
    result = []
    while pending:
        current = pending.pop()
        pending.extend(current.children)
        if current.type == "MESH":
            result.append(current)
    return sorted(result, key=lambda item: item.name)


def evaluated_world_vertices(meshes):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for mesh in meshes:
        evaluated = mesh.evaluated_get(depsgraph)
        points.extend(
            evaluated.matrix_world @ vertex.co
            for vertex in evaluated.data.vertices
        )
    return points


def convex_hull_points(points):
    mesh = bmesh.new()
    try:
        for point in points:
            mesh.verts.new(point)
        mesh.verts.ensure_lookup_table()
        result = bmesh.ops.convex_hull(
            mesh,
            input=list(mesh.verts),
            use_existing_faces=False,
        )
        hull = {
            rounded(item.co)
            for item in result["geom"]
            if isinstance(item, bmesh.types.BMVert)
        }
        if not hull:
            raise RuntimeError("convex hull contains no vertices")
        return sorted(hull)
    finally:
        mesh.free()


def main():
    if SOURCE_BLEND is None or CANDIDATE_BLEND is None:
        raise RuntimeError(
            "TWINKLE_SOURCE_BLEND and TWINKLE_CANDIDATE_BLEND are required"
        )
    if Path(bpy.data.filepath).resolve() != CANDIDATE_BLEND.resolve():
        raise RuntimeError("wrong candidate blend")
    candidate_before = sha256(CANDIDATE_BLEND)
    source_before = sha256(SOURCE_BLEND)
    if candidate_before != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("candidate blend drift")
    if source_before != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("source blend drift")

    authority = json.loads(AUTHORITY_MANIFEST.read_text(encoding="utf-8"))
    units = {}
    for code, config in UNITS.items():
        roots = [bpy.data.objects[name] for name in config["rootObjects"]]
        meshes = (
            [bpy.data.objects[name] for name in config["meshObjects"]]
            if config["meshObjects"] is not None
            else sorted(
                [mesh for root in roots for mesh in descendants(root)],
                key=lambda item: item.name,
            )
        )
        points = evaluated_world_vertices(meshes)
        hull = convex_hull_points(points)
        unit_record = {
            "unit": config["unit"],
            "rootObjects": [root.name for root in roots],
            "meshObjects": [mesh.name for mesh in meshes],
            "mechanicalAuthorityUnit": config["mechanicalAuthorityUnit"],
            "evaluatedVertexCount": len(points),
            "hullPointCount": len(hull),
            "hullPoints": hull,
            "authorityOriginalPositions": [
                [0.0, 0.0, 0.0] for _root in roots
            ],
            "authorityStateOffsets": [
                [round(float(value), 8) for value in offset]
                for offset in config["authorityStateOffsets"]
            ],
        }
        if "legacySourceObjectId" in config:
            unit_record["legacySourceObjectId"] = config["legacySourceObjectId"]
        units[code] = unit_record

    candidate_after = sha256(CANDIDATE_BLEND)
    source_after = sha256(SOURCE_BLEND)
    if candidate_after != candidate_before or source_after != source_before:
        raise RuntimeError("protected blend changed during extraction")
    print(
        "GEOMETRY_SNAPSHOT="
        + json.dumps(
            {
                "schema": "twinkle-route1-geometry-snapshot-v2",
                "method": "evaluated-world-vertices-3d-convex-hull",
                "sourceSha256": source_before,
                "candidateSha256": candidate_before,
                "source": {
                    "path": str(SOURCE_BLEND),
                    "sha256Before": source_before,
                    "sha256After": source_after,
                },
                "candidate": {
                    "path": str(CANDIDATE_BLEND),
                    "sha256Before": candidate_before,
                    "sha256After": candidate_after,
                },
                "units": units,
                "sceneSaved": False,
                "renderInvoked": False,
                "visualAssetsWritten": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
