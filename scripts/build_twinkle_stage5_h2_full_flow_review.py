"""Build and validate the reconciled isolated TWINKLE H2 full-flow review."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

try:
    from scripts.twinkle_stage5_h2_evidence import (
        EvidenceBundle,
        EvidenceBundleError,
        validate_evidence_bundle,
    )
except ModuleNotFoundError:
    from twinkle_stage5_h2_evidence import (
        EvidenceBundle,
        EvidenceBundleError,
        validate_evidence_bundle,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_RECEIPT_RELATIVE = Path("registry/twinkle/stage5-h2-evidence-receipt.json")
OUTPUT_RELATIVE = Path("output/twinkle-stage5-h2-full-flow-review")
PLAYWRIGHT_RELATIVE = Path("output/playwright/twinkle-stage5-h2-full-flow-review")
C2_RELATIVE = Path("registry/twinkle/stage5-source-manifests/stage4-c2.json")
C360_RELATIVE = Path("registry/twinkle/stage5-source-manifests/stage4-c360.json")
STAGE3_RELATIVE = Path("registry/twinkle/stage5-source-manifests/stage3-r2.json")
A192_RELATIVE = Path("output/twinkle-stage5-a192-full-sequence/a192-manifest.json")
FULL_FOCUS_RELATIVE = Path("output/twinkle-stage5-full-quality-focus-candidates/full-quality-focus-manifest.json")
FULL_FOCUS_ROOT = FULL_FOCUS_RELATIVE.parent
CONDENSER_AUTHORITY_RELATIVE = Path("registry/twinkle/stage5-condenser-homepage-v1.json")
RUNTIME_ASSETS_RELATIVE = Path("registry/twinkle/stage5-runtime-assets.json")
FIXED_BUILDER_RELATIVE = Path("scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py")
A192_BUILDER_RELATIVE = Path("scripts/build_twinkle_stage5_a192_full_sequence.py")
ENTRY_BUILDER_RELATIVE = Path("scripts/build_twinkle_stage5_entry_count_pilot.py")
ASSET_ROOT_RELATIVE = Path("output/twinkle-stage5-formal-model-motion-candidates")
ASSET_CONTRACT_RELATIVE = ASSET_ROOT_RELATIVE / "work/two-component-asset-contract.json"
ASSET_MANIFEST_RELATIVE = ASSET_ROOT_RELATIVE / "model-motion-manifest.json"
MAPPING_REVIEW_RELATIVE = Path("output/playwright/twinkle-stage5-lowres-mapping-review.html")
V18_RELATIVE = Path(".superpowers/brainstorm/936-1788488553/content/generated-rail-push-motion-v18.html")
PRODUCT_FILM_RELATIVE = Path("output/twinkle-stage5-blender-product-film/preview-v2/dip-to-black-loop-v2/dip-to-black-loop-review.mp4")
EXPECTED_FORMAL_EVIDENCE = {
    "browserResultsSha256": "FD8000AB655F88B743C2CBB80F926C1FD747E7BECFF7B899D5D4DD5E2CC4E026",
    "machineResultsSha256": "2E95D6A241373F8CFEBB24734FB3FAB92EAFF4A9710F0EB0EF0258D1879823B6",
    "reviewPageSha256": "B5E693D91312AB1D1B153418D53F08E9FBBEE07B1E1E897E06CC007B4AA6F9D7",
    "reviewManifestSha256": "F6965D48C261FD4608177D380D75270D18F3D9DA6CF439F3057FB518CC2DCD4D",
    "condenserScreenshotSha256": "79DFF7411B33C0A338CB63EB42EFB433972AD77F81298EF343ED3F5CED443F63",
    "chamberScreenshotSha256": "7394FFDC7267605F8DF4CBCB22ECB71BA0FE3F6B2BA792036B23DE5BC64039F3",
}
EXPECTED_HASHES = {
    C2_RELATIVE.as_posix(): "93A6453E451407913BCD6DE716BEB25ABB89FA14C0B2257F88D673DA90518D88",
    C360_RELATIVE.as_posix(): "8D774A5821AF2D66AFF6480465C2F69007A556B0FAAA9B831FD9E3ADF51E3623",
    STAGE3_RELATIVE.as_posix(): "67674A09A7E4C4C26DA57824AFB30DEC1F77C562C954A963CA266FAF8C776332",
    A192_RELATIVE.as_posix(): "0AD45675F90BA19CE9F7D60AF6C1ECF6E5437BC559BF6BD4C34412AA8FFB53E4",
    FULL_FOCUS_RELATIVE.as_posix(): "A915F285DCD45DCF086CAE4EBCA8B085C7BC27D500F2A3CEB6BC788099D3AB3D",
    CONDENSER_AUTHORITY_RELATIVE.as_posix(): "6B6DE037CAD6BF5F4902F0EAA78662C6713C76FC7C134563A62E7AF8991D7B10",
    RUNTIME_ASSETS_RELATIVE.as_posix(): "8D32267C20218FA575E34E78415D69EEFA58F76C4CF71CBB7903952E7EFB03C4",
    FIXED_BUILDER_RELATIVE.as_posix(): "2CD5A92F69D63BE573F7385555CB6473126481C13173B91E5329D866BE3BBF27",
    A192_BUILDER_RELATIVE.as_posix(): "BFF0A962E8902571B30574DC22DAAADB44B47AD82964E5223177B59FF9C6288C",
    ENTRY_BUILDER_RELATIVE.as_posix(): "FE4FAF7F00235F9D1CFBEDF490971277F457B86962DEF10B4AE7243005537E2A",
    ASSET_CONTRACT_RELATIVE.as_posix(): "0B4D02D379BD013A2A95C93EFCBB72B17CED2F5DFC7546E6F4D4206FF16EAF57",
    ASSET_MANIFEST_RELATIVE.as_posix(): "502AF3878B7BE37FE1721EC79DEE4340053B5205D355E6A23974F1A875BAB97D",
    MAPPING_REVIEW_RELATIVE.as_posix(): "ED720B8A776CFC29582A11D913E703A237A68D204B49E88957A01AD5BD41281C",
    V18_RELATIVE.as_posix(): "5B8332F02749307222F27674BAC61BCCB4091FF39574547CD1A30876FFDC5296",
    PRODUCT_FILM_RELATIVE.as_posix(): "2FD7A7CE89ECA556A896F1DE9AE5BCC9E0B5BC5A34BE091D590EF1F6391822FA",
}
APPROVED_SCREENSHOTS = {
    "condenser": (Path("output/playwright/twinkle-full-quality-1280-condenser-b.png"), "B5403CE933B707389A9CF7FD68880777390CA559A662A88BABA17B236EF31273"),
    "chamber": (Path("output/playwright/twinkle-full-quality-900-chamber-b.png"), "24294DE86CB68A4BFA415D0EF8F9D97A9ED14D3BA27191BAB9C88E3F3DDFB4A3"),
}
APPROVED_SEMANTIC_RETURN = (
    Path("output/playwright/twinkle-stage5-h2-full-flow-review/twinkle-v18-semantic-return-review.gif"),
    "963848401080C1735987DD82375DB4B212C08C1410FF208752F7C62D346984C5",
)
NEGATIVE_SCREENSHOTS = {
    "condenser": (PLAYWRIGHT_RELATIVE / "condenser-1280x800-stable.png", "B99103B923D5B0BB12C342B28CB0B6F79B698321C41710B5303FEDAF984DC1D8"),
    "chamber": (PLAYWRIGHT_RELATIVE / "chamber-900x700-stable.png", "D798199140EFD12668662519C4FB3C310C94C17C0226C7C818C786201B984832"),
}
EARLY_ROUTE_IDS = {
    "dual_channel_collection_optics_chamber--entry-006--A",
    "dual_channel_collection_optics_chamber--entry-065--B",
    "dual_channel_condenser_lens_assembly--entry-087--A",
    "dual_channel_condenser_lens_assembly--entry-008--A",
}
LATER_ROUTE_IDS = {
    "dual_channel_collection_optics_chamber--entry-074--full-quality-candidate",
    "dual_channel_collection_optics_chamber--entry-081--full-quality-candidate",
    "dual_channel_collection_optics_chamber--entry-091--full-quality-candidate",
    "dual_channel_condenser_lens_assembly--entry-005--full-quality-candidate",
    "dual_channel_condenser_lens_assembly--entry-000--full-quality-candidate",
    "dual_channel_condenser_lens_assembly--entry-092--full-quality-candidate",
}
EXPECTED_ROUTE_IDS = EARLY_ROUTE_IDS | LATER_ROUTE_IDS
MECHANICAL_DURATION_MS = 1000
SETTLED_HOLD_MS = 100
EXPLANATION_DURATION_MS = 820


class ReviewValidationError(ValueError):
    """Raised when an approved authority or isolated output boundary drifts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree_sha256(root: Path) -> tuple[int, str]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return len(files), digest.hexdigest().upper()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mapped_duration(old_duration: int) -> int:
    return min(old_duration, max(650, min(1400, round(old_duration * 0.60))))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewValidationError(f"cannot load approved source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_js_function(source: str, name: str) -> str:
    start = source.find(f"function {name}(")
    if start < 0:
        raise ReviewValidationError(f"approved JS function missing: {name}")
    brace = source.find("{", start)
    depth = 0
    quote = None
    escaped = False
    for index in range(brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', chr(96)}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ReviewValidationError(f"approved JS function is not closed: {name}")


def _validate_file(path: Path, expected_sha: str | None = None) -> None:
    if not path.is_file():
        raise ReviewValidationError(f"approved asset missing: {path}")
    if expected_sha and _sha256(path) != expected_sha:
        raise ReviewValidationError(f"approved asset drift: {path}")


def _load_evidence_bundle(repo: Path, evidence_root: Path | None) -> EvidenceBundle:
    if evidence_root is None:
        configured = os.environ.get("TWINKLE_STAGE5_H2_EVIDENCE_ROOT")
        evidence_root = Path(configured) if configured else None
    if evidence_root is None:
        raise ReviewValidationError("an explicit evidence root is required")
    try:
        return validate_evidence_bundle(
            repo / EVIDENCE_RECEIPT_RELATIVE,
            Path(evidence_root),
        )
    except (EvidenceBundleError, OSError, ValueError) as error:
        raise ReviewValidationError(f"H2 evidence bundle invalid: {error}") from error


def _resolve(repo: Path, bundle: EvidenceBundle, relative: Path | str) -> Path:
    key = Path(relative).as_posix()
    if key in bundle.inventory_paths:
        return bundle.resolve(key)
    if (
        key.startswith("output/")
        or key.startswith(".superpowers/")
        or key.startswith("showcase/homepage/assets/twinkle-condenser-unified-v1/")
    ):
        return bundle.resolve(key)
    return repo / relative


def _validate_authorities(repo: Path, bundle: EvidenceBundle) -> None:
    for relative, expected in EXPECTED_HASHES.items():
        _validate_file(_resolve(repo, bundle, relative), expected)
    for path, expected in [*APPROVED_SCREENSHOTS.values(), *NEGATIVE_SCREENSHOTS.values()]:
        _validate_file(_resolve(repo, bundle, path), expected)


def plan_review(repo: Path, evidence_root: Path | None = None) -> dict:
    repo = Path(repo).resolve(strict=True)
    bundle = _load_evidence_bundle(repo, evidence_root)
    _validate_authorities(repo, bundle)
    c2 = _read_json(repo / C2_RELATIVE)
    c360 = _read_json(repo / C360_RELATIVE)
    stage3 = _read_json(repo / STAGE3_RELATIVE)
    a192 = _read_json(_resolve(repo, bundle, A192_RELATIVE))
    full_focus = _read_json(_resolve(repo, bundle, FULL_FOCUS_RELATIVE))
    condenser_authority = _read_json(repo / CONDENSER_AUTHORITY_RELATIVE)
    runtime_assets = _read_json(repo / RUNTIME_ASSETS_RELATIVE)
    contract = _read_json(_resolve(repo, bundle, ASSET_CONTRACT_RELATIVE))
    model_manifest = _read_json(_resolve(repo, bundle, ASSET_MANIFEST_RELATIVE))
    if c360.get("physicalFrameCount") != 96 or len(c360.get("frames", [])) != 96:
        raise ReviewValidationError("F96 authority drift")
    if (a192.get("frameCount"), a192.get("fps"), a192.get("durationMs"), len(a192.get("frames", []))) != (192, 24, 8000, 192):
        raise ReviewValidationError("A/192 display drift")
    for frame in a192["frames"]:
        _validate_file(
            _resolve(repo, bundle, A192_RELATIVE.parent / frame["src"]),
            frame["sha256"],
        )

    selected = [choice for choices in c2["routeByUnit"].values() for choice in choices]
    if {choice["routeId"] for choice in selected} != EARLY_ROUTE_IDS:
        raise ReviewValidationError("early approved route choice drift")
    routes = []
    runtime_root = runtime_assets.get("runtimeInventory", {})
    if (
        runtime_root.get("root") != "showcase/homepage/assets/twinkle"
        or set(runtime_root.get("selectedRoutes", [])) != EARLY_ROUTE_IDS
    ):
        raise ReviewValidationError("early runtime route set drift")
    runtime_focus = {
        (record.get("routeId"), record.get("targetPath")): record
        for record in runtime_root.get("files", [])
        if record.get("role") == "focus"
    }
    c2_routes = {route["routeId"]: route for route in c2["routes"]}
    for choice in selected:
        route = c2_routes[choice["routeId"]]
        assets = []
        for frame in route["focusFrames"]:
            asset = Path("showcase/homepage/assets/twinkle/focus") / route["routeId"] / f"focus-{frame['sampleIndex']:03d}.png"
            record = runtime_focus.get((route["routeId"], asset.as_posix()))
            if record is None or record.get("sha256") != frame["sha256"]:
                raise ReviewValidationError(f"early runtime focus record drift: {asset}")
            _validate_file(repo / asset, frame["sha256"])
            assets.append(asset.as_posix())
        duration = route["commonFields"]["durationMs"]
        routes.append({
            "routeId": route["routeId"], "unit": route["unit"], "entryFrame": route["entryFrame"],
            "oldFocusDurationMs": duration, "newFocusDurationMs": _mapped_duration(duration),
            "settledHoldMs": route["commonFields"]["settledHoldMs"], "sampleCount": len(assets),
            "sampleAssets": assets, "sourceManifest": C2_RELATIVE.as_posix(),
            "assetRoot": "showcase/homepage/assets/twinkle/focus",
        })
    if {route["routeId"] for route in full_focus["routes"]} != LATER_ROUTE_IDS:
        raise ReviewValidationError("later approved route set drift")
    for route in full_focus["routes"]:
        if route["unit"] == "dual_channel_condenser_lens_assembly":
            continue
        assets = [(FULL_FOCUS_ROOT / sample["asset"]).as_posix() for sample in route["samples"]]
        for sample, asset in zip(route["samples"], assets):
            _validate_file(_resolve(repo, bundle, asset), sample["sha256"])
        routes.append({
            "routeId": route["routeId"], "unit": route["unit"], "entryFrame": route["entryFrame"],
            "oldFocusDurationMs": route["durationMs"], "newFocusDurationMs": _mapped_duration(route["durationMs"]),
            "settledHoldMs": route["settledHoldMs"], "sampleCount": len(assets),
            "sampleAssets": assets, "sourceManifest": FULL_FOCUS_RELATIVE.as_posix(),
            "assetRoot": FULL_FOCUS_ROOT.as_posix(),
        })
    if condenser_authority.get("schema") != "twinkle-stage5-condenser-homepage-assets-v1":
        raise ReviewValidationError("condenser authority schema drift")
    condenser_root = Path(condenser_authority["assetRoot"])
    expected_condenser_routes = {
        route_id for route_id in LATER_ROUTE_IDS
        if route_id.startswith("dual_channel_condenser_lens_assembly--")
    }
    if {route["routeId"] for route in condenser_authority.get("routes", [])} != expected_condenser_routes:
        raise ReviewValidationError("condenser authority route set drift")
    for route in condenser_authority["routes"]:
        route_root = _resolve(
            repo, bundle, condenser_root / Path(route["framePattern"]).parent
        )
        if _tree_sha256(route_root) != (route["frameCount"], route["treeSha256"]):
            raise ReviewValidationError(f"condenser focus asset closure drift: {route['routeId']}")
        assets = [
            (condenser_root / route["framePattern"].format(index=index)).as_posix()
            for index in range(route["frameCount"])
        ]
        routes.append({
            "routeId": route["routeId"], "unit": route["unit"], "entryFrame": route["entryFrame"],
            "oldFocusDurationMs": route["durationMs"], "newFocusDurationMs": _mapped_duration(route["durationMs"]),
            "settledHoldMs": route["settledHoldMs"], "sampleCount": len(assets),
            "sampleAssets": assets, "sourceManifest": CONDENSER_AUTHORITY_RELATIVE.as_posix(),
            "assetRoot": condenser_root.as_posix(),
        })
    if {route["routeId"] for route in routes} != EXPECTED_ROUTE_IDS:
        raise ReviewValidationError("reconciled route set drift")

    mechanical_roots = {
        "chamber": "showcase/homepage/assets/twinkle/mechanical/chamber",
        "condenser": (condenser_root / Path(condenser_authority["mechanical"]["framePattern"]).parent).as_posix(),
    }
    if len(list((repo / mechanical_roots["chamber"]).glob("frame-*.png"))) != 25:
        raise ReviewValidationError(f"mechanical frame closure drift: {mechanical_roots['chamber']}")
    mechanical = condenser_authority["mechanical"]
    if _tree_sha256(_resolve(repo, bundle, mechanical_roots["condenser"])) != (mechanical["frameCount"], mechanical["treeSha256"]):
        raise ReviewValidationError("condenser mechanical asset closure drift")
    assets = model_manifest.get("assets", {})
    required = [
        "backgrounds/chamber-fixed.png", "backgrounds/condenser-fixed.png",
        "models/chamber/mechanical-expanded.png", "models/chamber/inspection-stable.png",
        "models/condenser/mechanical-expanded.png",
    ]
    for relative in required:
        record = assets.get(relative)
        if not record:
            raise ReviewValidationError(f"full-quality asset record missing: {relative}")
        _validate_file(
            _resolve(repo, bundle, ASSET_ROOT_RELATIVE / relative),
            record["sha256"],
        )
    condenser_detail = {
        name: (condenser_root / record["asset"]).as_posix()
        for name, record in condenser_authority["detail"].items()
    }
    for name, record in condenser_authority["detail"].items():
        _validate_file(
            _resolve(repo, bundle, condenser_root / record["asset"]),
            record["sha256"],
        )
    geometry_sha = "25029A30042CEE2B12EFFA20B8BB8C7E8A46E35220F799AF8117CCB1BCD50E74"
    if any(assets[name]["alphaSha256"] != geometry_sha for name in ("models/chamber/mechanical-expanded.png", "models/chamber/inspection-stable.png")):
        raise ReviewValidationError("inspection geometry drift")
    inspection = stage3["inspectionLight"]
    if (inspection["fadeInMs"], inspection["fadeOutMs"], inspection["hold"]) != (900, 700, "stable-until-close"):
        raise ReviewValidationError("inspection timing drift")
    profile = contract["samplePlan"][1]
    if profile["backgroundCanvas"] != [1280, 900] or profile["transparentCanvas"] != [4352, 3060] or profile["referenceWindow"] != {"x": 1536, "y": 1080, "width": 1280, "height": 900} or profile["projectionScale"]["resolution"] != 3.4:
        raise ReviewValidationError("reference mapping drift")
    return {
        "schema": "twinkle-stage5-h2-isolated-full-flow-review-v2",
        "scope": "reconciled-isolated-two-component-full-flow-review-only",
        "authorities": dict(EXPECTED_HASHES),
        "executionOrder": ["a192-overview", "f96-hotspot-entry", "approved-turn", "approved-focus", "mechanical", "chamber-inspection-if-applicable", "v18-explanation", "strict-reverse-via-matched-a192-boundary", "overview-close-request-owned-by-homepage"],
        "routes": routes,
        "display": {"manifest": A192_RELATIVE.as_posix(), "assetRoot": A192_RELATIVE.parent.as_posix(), "frameCount": 192, "fps": 24, "durationMs": 8000},
        "mechanical": {"durationMs": 1000, "frameCount": 25, "roots": mechanical_roots},
        "detail": {
            "condenser": condenser_detail,
            "chamber": {
                "background": (ASSET_ROOT_RELATIVE / "backgrounds/chamber-fixed.png").as_posix(),
                "foreground": (ASSET_ROOT_RELATIVE / "models/chamber/mechanical-expanded.png").as_posix(),
            },
        },
        "condenserAuthority": {
            "manifest": CONDENSER_AUTHORITY_RELATIVE.as_posix(),
            "assetRoot": condenser_root.as_posix(),
            "sourceCandidateManifestSha256": condenser_authority["sourceCandidateManifestSha256"],
        },
        "inspection": {
            "unlitAsset": (ASSET_ROOT_RELATIVE / "models/chamber/mechanical-expanded.png").as_posix(),
            "litAsset": (ASSET_ROOT_RELATIVE / "models/chamber/inspection-stable.png").as_posix(),
            "enterMs": 900, "exitMs": 700, "geometrySha256": geometry_sha,
        },
        "referenceMapping": {"backgroundCanvas": [1280, 900], "transparentCanvas": [4352, 3060], "referenceWindow": profile["referenceWindow"], "scale": 3.4},
        "motion": {"preset": "B", "durationMs": 820, "reverseUsesSameTimeline": True},
        "formalIntegrationAuthorized": False,
    }


FLOW_STYLE = r"""
    html,body{width:100%;height:100%;overflow:hidden;background:#eef1f3}
    .audit-bar,.intro,.proxy-warning,.status-line,.stage-head,.diagnostics{display:none!important}
    .page{position:fixed;inset:0;width:100%;min-width:0;padding:0}
    .stage-shell{position:fixed;inset:0;width:100%;height:100%;margin:0}
    .stage-shell>div{width:100%;height:100%}.pane-title{display:none}
    .viewport{width:100%!important;height:100%!important;box-shadow:none;overflow:hidden}
    .reference-layer{position:absolute;left:50%;top:50%;width:max(100vw,calc(100vh * 64 / 45));height:max(100vh,calc(100vw * 45 / 64));transform:translate(-50%,-50%);overflow:visible}
    .fixed-background{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 50%}
    .scene-image{position:absolute;left:-120%;top:-120%;width:340%;height:340%;object-fit:fill;transform-origin:50% 50%;will-change:transform}
    #initializationSequence{position:fixed;z-index:60;inset:0;display:block;opacity:1;background:#000;overflow:hidden;pointer-events:none}
    #initializationSequence[hidden]{display:none}#productFilm{display:block;width:100%;height:100%;object-fit:cover;background:#000}
    #initializationFeedback{position:absolute;z-index:1;left:50%;bottom:34px;width:260px;transform:translateX(-50%);color:rgba(238,244,246,.88);font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:clamp(12px,0.8vw,14px);line-height:1.45;font-weight:500;letter-spacing:.06em;font-variant-numeric:tabular-nums}
    .initialization-feedback-row{display:flex;align-items:center;justify-content:space-between;gap:14px}.initialization-feedback-row span{min-width:0;white-space:nowrap}.initialization-feedback-row output{color:rgba(238,244,246,.94);font:inherit;font-variant-numeric:tabular-nums}
    #initializationProgress{display:block;width:100%;height:2px;margin-top:8px;border:0;border-radius:0;overflow:hidden;appearance:none;background:rgba(207,216,220,.18)}#initializationProgress[hidden]{display:none}
    #initializationProgress::-webkit-progress-bar{background:rgba(207,216,220,.18)}#initializationProgress::-webkit-progress-value{background:rgba(238,244,246,.70);transition:width .14s ease}#initializationProgress::-moz-progress-bar{background:rgba(238,244,246,.70);transition:width .14s ease}
    #initializationRetry{padding:0;border:0;color:rgba(238,244,246,.82);background:transparent;font:inherit;letter-spacing:inherit;text-decoration:underline;text-underline-offset:3px;pointer-events:auto;cursor:pointer}
    @media(max-width:600px){#initializationFeedback{width:min(260px,calc(100vw - 48px));font-size:13px}}
    #flowOverlay{position:fixed;z-index:20;inset:0;background:rgb(233 234 233);overflow:hidden}
    #overviewPlayer{position:absolute;inset:0;width:100%;height:100%;border:0;background:rgb(233 234 233)}
    #sequenceReference{position:fixed;z-index:30}
    #sequenceReference[hidden]{display:none}
    .flow-canvas{position:absolute;inset:0;display:block;width:100%;height:100%;background:#eef1f3}
    .flow-canvas[hidden]{display:none}
    #flowReturn{position:fixed;z-index:55;left:24px;top:20px;display:grid;width:44px;height:44px;padding:0;place-items:center;border:1px solid rgba(220,245,250,.18);border-radius:50%;color:rgba(238,250,252,.82);background:rgba(4,18,25,.34);backdrop-filter:blur(8px);cursor:pointer;transform:translateY(0) scale(1);transition:transform 140ms ease,background-color 140ms ease,color 140ms ease,border-color 140ms ease}
    #flowReturn svg{display:block;width:18px;height:18px}#flowReturn:hover{color:rgba(238,250,252,.96);background:rgba(4,18,25,.52);transform:translateY(1px) scale(.985)}#flowReturn:active{transform:translateY(1px) scale(.96);transition-duration:90ms}#flowReturn:focus-visible{outline:2px solid rgba(220,245,250,.92);outline-offset:3px}
    #flowReturn[hidden]{display:none}
    @media(prefers-reduced-motion:reduce){#flowReturn,#flowReturn:hover,#flowReturn:active{transform:none;transition:background-color 140ms ease,color 140ms ease,border-color 140ms ease}}
    .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
    .inspection-overlay{position:absolute;left:-120%;top:-120%;width:340%;height:340%;object-fit:fill;pointer-events:none}
"""


FLOW_MARKUP = r"""
  <section id="initializationSequence" aria-label="TWINKLE 产品特摄转场">
    <video id="productFilm" src="../twinkle-stage5-blender-product-film/preview-v2/dip-to-black-loop-v2/dip-to-black-loop-review.mp4" muted playsinline preload="auto"></video>
    <div id="initializationFeedback">
      <div class="initialization-feedback-row"><span id="initializationStatus" role="status" aria-live="polite">正在读取产品结构</span><output id="initializationPercent" hidden></output><button id="initializationRetry" type="button" hidden>重试</button></div>
      <progress id="initializationProgress" aria-label="模型资源准备进度" max="100" value="0" hidden></progress>
    </div>
  </section>
  <section id="flowOverlay" aria-label="TWINKLE A/192 总览与聚焦流程">
    <iframe id="overviewPlayer" title="TWINKLE A/192 已批准总览" src="../twinkle-stage5-a192-full-sequence/index.html?embedded=1"></iframe>
  </section>
  <div id="sequenceReference" class="reference-layer" hidden><canvas id="flowFrame" class="flow-canvas" aria-label="TWINKLE 聚焦与机械序列"></canvas><canvas id="flowFrameBack" class="flow-canvas" hidden></canvas></div>
  <!-- Lucide ArrowLeft, https://github.com/lucide-icons/lucide/blob/main/icons/arrow-left.svg
       ISC License
       Copyright (c) 2026 Lucide Icons and Contributors
       Permission to use, copy, modify, and/or distribute this software for any
       purpose with or without fee is hereby granted, provided that the above
       copyright notice and this permission notice appear in all copies.
       THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
       WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
       MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
       ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
       WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
       ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
       OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
       The MIT License (MIT) for the Feather-derived arrow-left icon
       Copyright (c) 2013-present Cole Bemis
       Permission is hereby granted, free of charge, to any person obtaining a copy
       of this software and associated documentation files (the "Software"), to deal
       in the Software without restriction, including without limitation the rights
       to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
       copies of the Software, and to permit persons to whom the Software is
       furnished to do so, subject to the following conditions:
       The above copyright notice and this permission notice shall be included in all
       copies or substantial portions of the Software.
       THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
       IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
       FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
       AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
       LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
       OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
       SOFTWARE. -->
  <button id="flowReturn" type="button" aria-label="返回360°视窗" hidden><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-left" aria-hidden="true"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg></button>
  <p id="flowStatus" class="sr-only" role="status" aria-live="polite">正在加载隔离审核流程</p>
"""


FLOW_SCRIPT = r"""
  <script>
  (()=>{'use strict';
    const ROOT='../../';
    const config={blackTransitionMs:320,mechanicalDurationMs:1000,inspectionEnterMs:900,inspectionExitMs:700,explanationDurationMs:820,maximumAngularSpeedDegreesPerSecond:90,accelerationRampMs:250,decelerationRampMs:250,settledHoldMs:100,transparentCanvas:[4352,3060],referenceWindow:{x:1536,y:1080,width:1280,height:900},approvedHotspotBuilderSha256:'2CD5A92F69D63BE573F7385555CB6473126481C13173B91E5329D866BE3BBF27',approvedA192BuilderSha256:'BFF0A962E8902571B30574DC22DAAADB44B47AD82964E5223177B59FF9C6288C'};
    const units={dual_channel_collection_optics_chamber:{key:'chamber',name:'双通道采集光学舱'},dual_channel_condenser_lens_assembly:{key:'condenser',name:'聚光镜组件'}};
    const MAX_DECODE_CONCURRENCY=2,CACHE_NAME='twinkle-h2-runtime-v3';
    const state={ready:false,busy:false,reversing:false,phase:'loading',runToken:0,c2:null,c360:null,a192:null,fullFocus:null,condenserAuthority:null,route:null,unit:null,baseOverviewFrame:0,currentOverviewFrame:0,chosenEntryFrame:null,entryTurn:null,pinnedRouteId:null,readinessGeneration:0,routeReadiness:new Map(),frameBitmaps:new Map(),bitmapPromises:new Map(),detailImages:new Map(),detailTransition:null,handoff:{},errors:[],events:[],metrics:{},activeCanvas:0,worker:null,workerRequests:new Map(),workerSequence:0,initialization:{ready:false,completedAssets:0,totalAssets:0,cacheAvailable:true,workerAvailable:true,decodedBytes:0,quality:null}};
    const overlay=document.querySelector('#flowOverlay'),overview=document.querySelector('#overviewPlayer'),sequenceReference=document.querySelector('#sequenceReference'),frame=document.querySelector('#flowFrame'),frameBack=document.querySelector('#flowFrameBack'),flowCanvases=[frame,frameBack],status=document.querySelector('#flowStatus'),returnButton=document.querySelector('#flowReturn'),reduced=matchMedia('(prefers-reduced-motion: reduce)'),initializationSequence=document.querySelector('#initializationSequence'),productFilm=document.querySelector('#productFilm'),initializationFeedback=document.querySelector('#initializationFeedback'),initializationStatus=document.querySelector('#initializationStatus'),initializationPercent=document.querySelector('#initializationPercent'),initializationProgress=document.querySelector('#initializationProgress'),initializationRetry=document.querySelector('#initializationRetry');
    const pad=value=>String(value).padStart(3,'0'),wrap=(value,size)=>((value%size)+size)%size,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    __APPROVED_TURN_FUNCTIONS__
    function setPhase(phase,label){state.phase=phase;status.textContent=label;state.events.push({type:'phase',phase,at:performance.now()});const enabled=phase==='overview'||phase==='explanation-stable';returnButton.hidden=!enabled;returnButton.disabled=!enabled;returnButton.setAttribute('aria-label',phase==='overview'?'返回首页':'返回360°视窗')}
    function overviewApi(){return overview.contentWindow&&overview.contentWindow.__twinkleA192}
    function overviewSnapshot(){const api=overviewApi();return api&&api.snapshot()}
    function setOverviewPosition(position){overviewApi().setPosition(wrap(position*2,192));state.currentOverviewFrame=wrap(Math.round(position),96)}
    function overviewContentRect(){const frameRect=overview.getBoundingClientRect(),content=overviewApi().contentRect();return{left:frameRect.left+content.offsetX,top:frameRect.top+content.offsetY,width:content.width,height:content.height}}
    function authorityAtDisplay(){const snap=overviewSnapshot(),display=state.a192.frames[snap.displayedFrame],index=display.sourceAuthorityIndex;return{display,index,record:state.c360.frames[index]}}
    function focusSource(route,index){return ROOT+route.sampleAssets[index]}
    function authorityFrame(root,pattern,index){return root+'/'+pattern.replace('{index:03d}',pad(index))}
    function mechanicalSource(unit,index){if(units[unit].key==='condenser')return ROOT+authorityFrame(state.condenserAuthority.assetRoot,state.condenserAuthority.mechanical.framePattern,index);return ROOT+'showcase/homepage/assets/twinkle/mechanical/chamber/frame-'+pad(index)+'.png'}
    function runtimeRoutes(){const early=Object.values(state.c2.routeByUnit).flat().map(choice=>{const route=state.c2.routes.find(record=>record.routeId===choice.routeId),duration=route.commonFields.durationMs;return{routeId:route.routeId,unit:route.unit,entryFrame:route.entryFrame,oldFocusDurationMs:duration,newFocusDurationMs:Math.min(duration,Math.max(650,Math.min(1400,Math.round(duration*.6)))),settledHoldMs:route.commonFields.settledHoldMs,sampleAssets:route.focusFrames.map(frame=>'showcase/homepage/assets/twinkle/focus/'+route.routeId+'/focus-'+pad(frame.sampleIndex)+'.png')}}),chamber=state.fullFocus.routes.filter(route=>route.unit==='dual_channel_collection_optics_chamber').map(route=>({routeId:route.routeId,unit:route.unit,entryFrame:route.entryFrame,oldFocusDurationMs:route.durationMs,newFocusDurationMs:Math.min(route.durationMs,Math.max(650,Math.min(1400,Math.round(route.durationMs*.6)))),settledHoldMs:route.settledHoldMs,sampleAssets:route.samples.map(sample=>'output/twinkle-stage5-full-quality-focus-candidates/'+sample.asset)})),condenser=state.condenserAuthority.routes.map(route=>({routeId:route.routeId,unit:route.unit,entryFrame:route.entryFrame,oldFocusDurationMs:route.durationMs,newFocusDurationMs:Math.min(route.durationMs,Math.max(650,Math.min(1400,Math.round(route.durationMs*.6)))),settledHoldMs:route.settledHoldMs,sampleAssets:Array.from({length:route.frameCount},(_,index)=>authorityFrame(state.condenserAuthority.assetRoot,route.framePattern,index))}));return[...early,...chamber,...condenser]}
    const BITMAP_WORKER_SOURCE=`
      const CACHE_NAME='twinkle-h2-runtime-v3',MAX_DECODE_CONCURRENCY=2,queue=[];let active=0;
      self.onmessage=event=>{if(event.data.type==='decode'){queue.push(event.data);pump()}};
      function pump(){while(active<MAX_DECODE_CONCURRENCY&&queue.length){active+=1;decode(queue.shift()).finally(()=>{active-=1;pump()})}}
      async function cachedResponse(url){let response=null,cacheAvailable=true;try{const cache=await caches.open(CACHE_NAME);response=await cache.match(url);if(!response){response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error(url+' '+response.status);await cache.put(url,response.clone())}}catch(error){cacheAvailable=false;response=await fetch(url);if(!response.ok)throw Error(url+' '+response.status)}return{response,cacheAvailable}}
      async function decode(task){try{const loaded=await cachedResponse(task.url),blob=await loaded.response.blob(),bitmap=await createImageBitmap(blob,{resizeWidth:task.width,resizeHeight:task.height,resizeQuality:'high'});self.postMessage({type:'decoded',id:task.id,url:task.url,bitmap,cacheAvailable:loaded.cacheAvailable},[bitmap])}catch(error){self.postMessage({type:'failed',id:task.id,url:task.url,error:String(error)})}}
    `;
    function bitmapUrl(source){return new URL(source,location.href).href}
    function decodeDimensions(){const scale=Math.min(1,Math.max(innerWidth/1280,innerHeight/900)),memory=Number(navigator.deviceMemory||8),quality=memory<4?.67:memory<8?.82:1;return{width:Math.max(2,Math.round(1280*scale*quality)),height:Math.max(2,Math.round(900*scale*quality)),tier:quality===1?'full':quality>.7?'balanced':'constrained'}}
    function updateInitialization(label){const{completedAssets,totalAssets}=state.initialization;if(label&&initializationStatus.textContent!==label)initializationStatus.textContent=label;if(totalAssets>0){const percentage=Math.min(state.ready?100:99,Math.round(completedAssets/totalAssets*100));initializationPercent.hidden=false;initializationProgress.hidden=false;initializationPercent.textContent=percentage+'%';initializationProgress.value=percentage}else{initializationPercent.hidden=true;initializationProgress.hidden=true}}
    function createBitmapWorker(){if(!('Worker'in window)||!('createImageBitmap'in window))return null;const url=URL.createObjectURL(new Blob([BITMAP_WORKER_SOURCE],{type:'text/javascript'})),worker=new Worker(url);URL.revokeObjectURL(url);worker.onmessage=event=>{const task=state.workerRequests.get(event.data.id);if(!task)return;state.workerRequests.delete(event.data.id);if(event.data.type==='failed'){task.reject(Error(event.data.error));return}if(event.data.cacheAvailable===false)state.initialization.cacheAvailable=false;task.resolve(event.data.bitmap)};worker.onerror=()=>{state.initialization.workerAvailable=false;for(const task of state.workerRequests.values())task.reject(Error('bitmap worker failed'));state.workerRequests.clear();worker.terminate();if(state.worker===worker)state.worker=null};return worker}
    async function mainThreadBitmap(url,width,height){let response=null;try{const cache=await caches.open(CACHE_NAME);response=await cache.match(url);if(!response){response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error(url+' '+response.status);await cache.put(url,response.clone())}}catch(error){state.initialization.cacheAvailable=false;response=await fetch(url);if(!response.ok)throw Error(url+' '+response.status)}const blob=await response.blob();return createImageBitmap(blob,{resizeWidth:width,resizeHeight:height,resizeQuality:'high'})}
    async function requestBitmap(url){const dimensions=state.initialization.quality;if(!state.worker)return mainThreadBitmap(url,dimensions.width,dimensions.height);const id=++state.workerSequence;try{return await new Promise((resolve,reject)=>{state.workerRequests.set(id,{resolve,reject});state.worker.postMessage({type:'decode',id,url,width:dimensions.width,height:dimensions.height})})}catch(error){state.worker=null;state.initialization.workerAvailable=false;return mainThreadBitmap(url,dimensions.width,dimensions.height)}}
    function prepareBitmap(source){const url=bitmapUrl(source);if(state.frameBitmaps.has(url))return Promise.resolve(state.frameBitmaps.get(url));if(state.bitmapPromises.has(url))return state.bitmapPromises.get(url);const promise=requestBitmap(url).then(bitmap=>{state.bitmapPromises.delete(url);state.frameBitmaps.set(url,bitmap);state.initialization.completedAssets+=1;state.initialization.decodedBytes+=bitmap.width*bitmap.height*4;updateInitialization();return bitmap},error=>{state.bitmapPromises.delete(url);throw error});state.bitmapPromises.set(url,promise);return promise}
    function drawBitmap(source){const bitmap=state.frameBitmaps.get(bitmapUrl(source));if(!bitmap)throw Error('bitmap not READY: '+source);const next=1-state.activeCanvas,canvas=flowCanvases[next],context=canvas.getContext('2d',{alpha:false});if(canvas.width!==bitmap.width||canvas.height!==bitmap.height){canvas.width=bitmap.width;canvas.height=bitmap.height}context.drawImage(bitmap,0,0,canvas.width,canvas.height);canvas.dataset.source=source;sequenceReference.hidden=false;flowCanvases[state.activeCanvas].hidden=true;canvas.hidden=false;state.activeCanvas=next;return performance.now()}
    function presentSource(source,targetAt=performance.now(),token=state.runToken){return new Promise(resolve=>{function present(now){if(token!==state.runToken){resolve(false);return}if(now+.5<targetAt){requestAnimationFrame(present);return}drawBitmap(source);resolve(true)}requestAnimationFrame(present)})}
    async function sequence(items,durationMs,phase,label,token,{startedAt=performance.now(),skipFirst=false}={}){if(!items.length)return true;setPhase(phase,label);if(reduced.matches)return presentSource(items.at(-1).source,startedAt,token);const interval=items.length>1?durationMs/(items.length-1):0;for(let index=skipFirst?1:0;index<items.length;index++){if(!(await presentSource(items[index].source,startedAt+index*interval,token)))return false}return token===state.runToken}
    async function sequenceReverse(items,durationMs,phase,label,token){return sequence([...items].reverse(),durationMs,phase,label,token)}
    function nearestReadyRoute(unit,current){const routes=runtimeRoutes().filter(route=>route.unit===unit),mathematicalTurn=cyclicShortestTurn(current,routes.map(route=>route.entryFrame),state.orbitDirection),ready=routes.filter(route=>state.routeReadiness.get(route.routeId)?.ready===true);if(!ready.length)return null;const turn=cyclicShortestTurn(current,ready.map(route=>route.entryFrame),state.orbitDirection),route=ready.find(value=>value.entryFrame===turn.entry);return{route,turn,mathematicallyNearestEntry:mathematicalTurn.entry,chosenEntryFrame:turn.entry,fallbackUsed:mathematicalTurn.entry!==turn.entry,readinessGeneration:state.readinessGeneration}}
    async function approvedTurn(turn,token,{phase='turn',measurePaint=false}={}){const profile=motionProfile(turn.distance),start=state.currentOverviewFrame,direction=turn.direction==='forward'?1:-1,startTime=performance.now();state.orbitDirection=turn.direction;setPhase(phase,phase==='turn'?'转向 '+pad(turn.entry)+' 入口':'返回客户角度');return new Promise(resolve=>{let controlTaken=false;function step(now){if(token!==state.runToken){resolve(false);return}if(!controlTaken){overview.contentWindow.dispatchEvent(new Event('blur'));controlTaken=true;if(measurePaint){state.metrics.firstTurnPaintAt=now;state.metrics.clickToFirstTurnPaintMs=now-state.metrics.clickedAt}}const elapsed=now-startTime,sample=motionProgress(profile,elapsed),position=wrap(start+direction*sample.distanceDegrees/3.75,96);setOverviewPosition(position);if(elapsed<profile.movementMs&&!reduced.matches)requestAnimationFrame(step);else{setOverviewPosition(turn.entry);sleep(reduced.matches?0:config.settledHoldMs).then(()=>resolve(token===state.runToken))}}requestAnimationFrame(step)})}
    async function waitForOverview(overviewAssetCount){if(!overview.contentDocument||overview.contentDocument.readyState!=='complete')await new Promise(resolve=>overview.addEventListener('load',resolve,{once:true}));for(let count=0;count<300;count++){const snap=overviewSnapshot();if(snap){const decoded=Math.min(overviewAssetCount,Math.max(0,Number(snap.decodedFrameCount)||0));state.initialization.completedAssets=Math.max(state.initialization.completedAssets,decoded);updateInitialization();if(snap.ready)return}await sleep(50)}throw Error('A/192 overview did not become ready')}
    function bindHotspots(){for(const button of overview.contentDocument.querySelectorAll('[data-unit]'))button.addEventListener('click',event=>{event.preventDefault();enter(button.dataset.unit)})}
    function decodeImage(source){return new Promise((resolve,reject)=>{const image=new Image();image.onload=async()=>{try{if(image.decode)await image.decode()}catch{}resolve(image)};image.onerror=()=>reject(new Error('detail asset failed: '+source));image.src=source})}
    async function prepareDetail(unit,token){const key=units[unit].key,size=innerWidth<=900?900:1280,entry=window.__V18__.units[key],approvedExplanation=entry.explanationSource,detailSources=[entry.backgroundSource,entry.explanationSource,entry.reviewSource];if(detailSources.some(source=>!state.detailImages.has(bitmapUrl(source))))throw Error('detail not READY');if(key==='chamber')entry.explanationSource=entry.reviewSource;await window.__V18__.select({component:key,size,preset:'B',duration:820});entry.explanationSource=approvedExplanation;captureForwardProfile();const metrics=await window.__V18__.updateMetrics();if(token!==state.runToken)return null;const view=document.querySelector('#singleShell .viewport'),reference=view.querySelector('.reference-layer');return{view,reference,metrics,detailReady:true}}
    function rectDelta(left,right){return{left:Math.abs(left.left-right.left),top:Math.abs(left.top-right.top),width:Math.abs(left.width-right.width),height:Math.abs(left.height-right.height),centerX:Math.abs((left.left+left.width/2)-(right.left+right.width/2)),centerY:Math.abs((left.top+left.height/2)-(right.top+right.height/2))}}
    function nextPaint(){return new Promise(resolve=>requestAnimationFrame(time=>resolve(time)))}
    function waitForFilmEnd(){if(productFilm.ended)return Promise.resolve();return new Promise((resolve,reject)=>{productFilm.addEventListener('ended',resolve,{once:true});productFilm.addEventListener('error',()=>reject(Error('approved product film failed')),{once:true})})}
    async function setBlackCover(covered,token=state.runToken){initializationSequence.hidden=false;const from=Number(getComputedStyle(initializationSequence).opacity),to=covered?1:0;if(Math.abs(from-to)>.001){const animation=initializationSequence.animate([{opacity:from},{opacity:to}],{duration:config.blackTransitionMs,easing:'ease',fill:'forwards'});await animation.finished}if(token!==state.runToken)return false;initializationSequence.style.opacity=String(to);if(!covered)initializationSequence.hidden=true;return true}
    async function playProductFilmIntoOverview(){await waitForFilmEnd();productFilm.hidden=true;initializationFeedback.hidden=true;overlay.style.visibility='visible';sequenceReference.hidden=true;await nextPaint();return await setBlackCover(false)}
    function cleanupHandoffLayers(){document.querySelectorAll('.inspection-overlay').forEach(node=>node.remove())}
    async function atomicVisualHandoff(detail,token){setPhase('handoff','机械终态接棒');await nextPaint();if(token!==state.runToken)return false;const sequenceRect=sequenceReference.getBoundingClientRect(),detailRect=detail.reference.getBoundingClientRect(),referenceDelta=rectDelta(sequenceRect,detailRect),mechanicalLastPaintAt=performance.now();if(Object.values(referenceDelta).some(value=>value>.5))throw Error('handoff reference geometry drift');dispatchEvent(new CustomEvent('twinkle-handoff-before',{detail:{mechanicalLastPaintAt,referenceDelta}}));return new Promise(resolve=>requestAnimationFrame(detailFirstPaintAt=>{if(token!==state.runToken){resolve(false);return}sequenceReference.hidden=true;overlay.style.visibility='hidden';state.handoff={detailReady:true,mechanicalLastPaintAt,detailFirstPaintAt,frameGapMs:detailFirstPaintAt-mechanicalLastPaintAt,referenceDelta,backgroundBefore:flowCanvases[state.activeCanvas].dataset.source,backgroundAfter:detail.view.querySelector('.fixed-background').getAttribute('src')};dispatchEvent(new CustomEvent('twinkle-handoff-after',{detail:{...state.handoff}}));resolve(true)}))}
    const semanticReturnProfile={textStart:0,textEnd:.50,modelStart:.50,modelEnd:1,washStart:.50,washEnd:1,railStart:.50,railEnd:.65,durationMs:820};
    let forwardKeyframes=[],activeV18Direction='idle',activeV18Duration=820;
    function cleanKeyframe(frame){const clean={offset:frame.offset,easing:frame.easing};for(const property of['transform','clipPath'])if(frame[property]!==undefined)clean[property]=frame[property];return clean}
    function captureForwardProfile(){forwardKeyframes=window.__V18__.animations.map(animation=>animation.effect.getKeyframes().map(cleanKeyframe));activeV18Direction='idle';activeV18Duration=820}
    function v18MasterTime(){const times=window.__V18__.animations.map(animation=>Number(animation.currentTime));if(!times.length)return 0;const first=times[0];if(times.some(time=>Math.abs(time-first)>.5))throw Error('v18 master time drift');return Math.max(0,Math.min(activeV18Duration,first))}
    function captureV18Styles(){const view=document.querySelector('#singleShell .viewport'),rail=view.querySelector('.rail'),bodies=[...view.querySelectorAll('.reveal-body')],wash=view.querySelector('.content-wash'),model=view.querySelector('.scene-image');return{rail:getComputedStyle(rail).transform,bodies:bodies.map(node=>getComputedStyle(node).transform),wash:getComputedStyle(wash).clipPath,model:getComputedStyle(model).transform,opacity:bodies.map(node=>getComputedStyle(node).opacity)}}
    function propertyFrames(property,from,to,start,end){return[{[property]:from,offset:0},{[property]:from,offset:start,easing:'cubic-bezier(0.22,1,0.36,1)'},{[property]:to,offset:end},{[property]:to,offset:1}]}
    function semanticReturnKeyframes(styles){const view=document.querySelector('#singleShell .viewport'),bodies=[...view.querySelectorAll('.reveal-body')],textDuration=.18,textStride=(semanticReturnProfile.textEnd-textDuration)/(bodies.length-1),railScale=new DOMMatrixReadOnly(styles.rail).d,railFrom='scaleY('+railScale+')',frames=[];frames.push(propertyFrames('transform',railFrom,'scaleY(0)',semanticReturnProfile.railStart,semanticReturnProfile.railEnd));frames.push(propertyFrames('clipPath',styles.wash,'inset(0 100% 0 0)',semanticReturnProfile.washStart,semanticReturnProfile.washEnd));bodies.forEach((_,index)=>{const reverseIndex=bodies.length-1-index,start=semanticReturnProfile.textStart+reverseIndex*textStride,end=Math.min(semanticReturnProfile.textEnd,start+textDuration);frames.push(propertyFrames('transform',styles.bodies[index],'translate3d(-104%,0,0)',start,end))});frames.push(propertyFrames('transform',styles.model,'translate3d(0,0,0) scale(1)',semanticReturnProfile.modelStart,semanticReturnProfile.modelEnd));return frames}
    function semanticEnterResumeKeyframes(styles){const preset=window.__V18__.presets.B,targetModel='translate3d('+preset.shift+'px,0,0) scale('+preset.scale+')',frames=[];frames.push(propertyFrames('transform',styles.rail,'scaleY(1)',0,1));frames.push(propertyFrames('clipPath',styles.wash,'inset(0 0% 0 0)',0,1));styles.bodies.forEach(value=>frames.push(propertyFrames('transform',value,'translate3d(0,0,0)',0,1)));frames.push(propertyFrames('transform',styles.model,targetModel,0,1));return frames}
    function setV18Direction(direction,{initialTime}={}){const animations=window.__V18__.animations,styles=captureV18Styles(),previousTime=v18MasterTime(),previousProgress=activeV18Duration?previousTime/activeV18Duration:0;let keyframes,duration;if(direction==='return'){keyframes=semanticReturnKeyframes(styles);duration=Math.max(1,activeV18Direction==='enter'?820*Math.min(1,previousTime/820):820*(1-previousProgress))}else if(initialTime===0||activeV18Direction==='idle'){keyframes=forwardKeyframes;duration=820}else{keyframes=semanticEnterResumeKeyframes(styles);duration=Math.max(1,820*previousProgress)}const timelineTime=document.timeline.currentTime,sharedStart=timelineTime;animations.forEach((animation,index)=>{animation.pause();animation.effect.setKeyframes(keyframes[index]);animation.effect.updateTiming({duration});animation.currentTime=0;animation.playbackRate=1;animation.play();animation.startTime=sharedStart});activeV18Direction=direction;activeV18Duration=duration;state.handoff.v18AnimationStartTimes=animations.map(animation=>animation.startTime);state.handoff.v18DirectionControl='single-semantic-master-time';state.handoff.v18Profile=direction;return animations}
    function readV18VisualState(){const styles=captureV18Styles();return{masterTime:v18MasterTime(),duration:activeV18Duration,direction:activeV18Direction,railTransform:styles.rail,bodyTransforms:styles.bodies,washClipPath:styles.wash,modelTransform:styles.model,copyOpacity:styles.opacity}}
    function seekV18Master(timeMs){for(const animation of window.__V18__.animations){animation.pause();animation.currentTime=timeMs}return readV18VisualState()}
    async function reverseHandoff(token){setPhase('handoff-return','讲解初态接回机械终态');cleanupHandoffLayers();sequenceReference.style.visibility='hidden';sequenceReference.hidden=false;const detailLastPaintAt=await new Promise(resolve=>requestAnimationFrame(resolve));if(token!==state.runToken)return false;const detailReference=document.querySelector('#singleShell .reference-layer'),reverseReferenceDelta=rectDelta(detailReference.getBoundingClientRect(),sequenceReference.getBoundingClientRect());if(Object.values(reverseReferenceDelta).some(value=>value>.5))throw Error('reverse handoff reference geometry drift');dispatchEvent(new CustomEvent('twinkle-reverse-handoff-before',{detail:{detailLastPaintAt,reverseReferenceDelta}}));return new Promise(resolve=>requestAnimationFrame(mechanicalFirstPaintAt=>{if(token!==state.runToken){resolve(false);return}overlay.style.visibility='visible';sequenceReference.style.visibility='visible';state.handoff.reverseDetailLastPaintAt=detailLastPaintAt;state.handoff.reverseMechanicalFirstPaintAt=mechanicalFirstPaintAt;state.handoff.reverseFrameGapMs=mechanicalFirstPaintAt-detailLastPaintAt;state.handoff.reverseReferenceDelta=reverseReferenceDelta;dispatchEvent(new CustomEvent('twinkle-reverse-handoff-after',{detail:{...state.handoff}}));resolve(true)}))}
    async function inspectionTransition(direction,token){const view=document.querySelector('#singleShell .viewport'),layer=view.querySelector('.reference-layer'),base=view.querySelector('.scene-image'),unit=window.__V18__.units.chamber,incoming=document.createElement('img');incoming.className='inspection-overlay';incoming.alt='';incoming.src=direction==='enter'?unit.explanationSource:unit.reviewSource;incoming.style.opacity='0';layer.append(incoming);const duration=direction==='enter'?config.inspectionEnterMs:config.inspectionExitMs,animation=incoming.animate([{opacity:0},{opacity:1}],{duration,fill:'forwards'});state.detailTransition={animation,incoming,base};setPhase(direction==='enter'?'inspection-enter':'inspection-exit',direction==='enter'?'检查灯进入':'检查灯退出');await animation.finished;if(token!==state.runToken)return false;base.src=incoming.src;incoming.remove();state.detailTransition=null;return true}
    async function warmDetailImage(source){const url=bitmapUrl(source);if(state.detailImages.has(url))return state.detailImages.get(url);const image=new Image();image.src=source;await image.decode();state.detailImages.set(url,image);state.initialization.completedAssets+=1;updateInitialization();return image}
    async function prepareBounded(sources){let cursor=0;async function worker(){while(cursor<sources.length){const index=cursor++;await prepareBitmap(sources[index])}}await Promise.all(Array.from({length:MAX_DECODE_CONCURRENCY},worker))}
    function collectRuntimeAssets(){const routes=runtimeRoutes(),overviewSources=new Set(state.a192.frames.map(frame=>frame.src)),bitmapSources=new Set(),detailSources=new Set();for(const route of routes){route.sampleAssets.forEach((_,index)=>bitmapSources.add(focusSource(route,index)));for(let index=0;index<25;index++)bitmapSources.add(mechanicalSource(route.unit,index))}for(const unit of Object.keys(units)){const entry=window.__V18__.units[units[unit].key];[entry.backgroundSource,entry.explanationSource,entry.reviewSource].forEach(source=>detailSources.add(source))}return{routes,overviewSources,bitmapSources,detailSources}}
    async function prepareRuntimeAssets({routes,bitmapSources,detailSources}){state.initialization.quality=decodeDimensions();state.worker=createBitmapWorker();if(!state.worker)state.initialization.workerAvailable=false;updateInitialization('正在校准光学细节');await prepareBounded([...bitmapSources]);updateInitialization('正在准备交互视窗');for(const source of detailSources)await warmDetailImage(source);for(const route of routes)state.routeReadiness.set(route.routeId,{ready:route.sampleAssets.every((_,index)=>state.frameBitmaps.has(bitmapUrl(focusSource(route,index))))&&Array.from({length:25},(_,index)=>mechanicalSource(route.unit,index)).every(source=>state.frameBitmaps.has(bitmapUrl(source))),generation:state.readinessGeneration+1});state.readinessGeneration+=1;if([...state.routeReadiness.values()].some(record=>record.ready!==true))throw Error('route READY closure failed');state.initialization.ready=true}
    function setSequenceRect(rect){sequenceReference.style.left=rect.left+'px';sequenceReference.style.top=rect.top+'px';sequenceReference.style.width=rect.width+'px';sequenceReference.style.height=rect.height+'px';sequenceReference.style.transform='none'}
    function resetSequenceRect(){for(const property of['left','top','width','height','transform'])sequenceReference.style.removeProperty(property)}
    async function prepareFocusBoundary(items,token){const target=wrap(state.chosenEntryFrame*2,192),painted=await overviewApi().setPositionAndWait(target);if(token!==state.runToken||painted.displayedFrame!==target)return null;state.currentOverviewFrame=state.chosenEntryFrame;sequenceReference.style.visibility='hidden';sequenceReference.hidden=false;resetSequenceRect();const focusRect=sequenceReference.getBoundingClientRect(),overviewRect=overviewContentRect(),focusPreparedAt=drawBitmap(items[0].source);setSequenceRect(overviewRect);await nextPaint();if(token!==state.runToken)return null;const geometry=rectDelta(sequenceReference.getBoundingClientRect(),overviewRect);if(Object.values(geometry).some(value=>value>.5))throw Error('focus entry boundary geometry drift');return{target,painted,focusRect,overviewRect,geometry,focusPreparedAt}}
    function matchFocusBoundary(targetRect,startTime){const current=sequenceReference.getBoundingClientRect(),animation=sequenceReference.animate([{left:current.left+'px',top:current.top+'px',width:current.width+'px',height:current.height+'px',transform:'none'},{left:targetRect.left+'px',top:targetRect.top+'px',width:targetRect.width+'px',height:targetRect.height+'px',transform:'none'}],{duration:config.accelerationRampMs,easing:'ease',fill:'forwards'});animation.startTime=startTime;if(reduced.matches)animation.finish();return animation}
    async function presentFocusSequence(boundary,items,durationMs,token){return new Promise(resolve=>requestAnimationFrame(async startTime=>{if(token!==state.runToken){resolve(false);return}sequenceReference.style.visibility='visible';const animation=matchFocusBoundary(boundary.focusRect,startTime),geometryFinished=animation.finished.then(()=>{if(token===state.runToken)setSequenceRect(boundary.focusRect);animation.cancel()});state.handoff={...state.handoff,focusOverviewGeometry:boundary.geometry,overviewPaintedFrame:boundary.painted.displayedFrame,overviewTargetPaintedAt:boundary.painted.paintedAt,focusPreparedAt:boundary.focusPreparedAt,focusFirstVisibleAt:startTime,focusSequenceStartTime:startTime,focusGeometryAnimationStartTime:animation.startTime};const played=await sequence(items,durationMs,'focus','聚焦进入',token,{startedAt:startTime,skipFirst:true});await geometryFinished;resolve(played&&token===state.runToken)}))}
    async function enter(unit){
      if(!state.ready||state.busy||state.phase!=='overview')return false;
      const authority=authorityAtDisplay(),qualification=authority.record.qualificationByUnit[unit];
      if(qualification.status!=='visible'||qualification.machineQualified!==true)return false;
      const selected=nearestReadyRoute(unit,authority.index);if(!selected)return false;
      state.busy=true;state.unit=unit;state.baseOverviewFrame=authority.index;state.currentOverviewFrame=authority.index;state.chosenEntryFrame=selected.chosenEntryFrame;state.entryTurn=selected.turn;state.route=selected.route;state.pinnedRouteId=selected.route.routeId;state.handoff={};state.metrics={clickedAt:performance.now(),startFrame:authority.index,clickedFrame:authority.index,mathematicallyNearestEntry:selected.mathematicallyNearestEntry,chosenEntryFrame:selected.chosenEntryFrame,fallbackUsed:selected.fallbackUsed,readinessGeneration:selected.readinessGeneration,routeId:selected.route.routeId,turnDistance:selected.turn.distance};
      const token=++state.runToken;
      try{
        if(!(await approvedTurn(selected.turn,token,{measurePaint:true})))return false;
        const focus=selected.route.sampleAssets.map((_,index)=>({source:focusSource(selected.route,index)})),boundary=await prepareFocusBoundary(focus,token);if(!boundary)return false;
        const detailReady=prepareDetail(unit,token);
        if(!(await presentFocusSequence(boundary,focus,selected.route.newFocusDurationMs,token)))return false;
        state.metrics.focusCompletedAt=performance.now();
        if(!reduced.matches){setPhase('focus-settled','聚焦终点稳定');await sleep(selected.route.settledHoldMs);if(token!==state.runToken)return false}
        const detail=await detailReady;if(!detail||token!==state.runToken)return false;
        const mechanical=Array.from({length:25},(_,index)=>({source:mechanicalSource(unit,index)}));
        if(!(await sequence(mechanical,config.mechanicalDurationMs,'mechanical-expand','机械展开',token)))return false;
        if(!(await atomicVisualHandoff(detail,token)))return false;
        if(units[unit].key==='chamber'&&!reduced.matches&&!(await inspectionTransition('enter',token)))return false;
        const animations=reduced.matches?(window.__V18__.play('enter'),window.__V18__.animations):setV18Direction('enter',{initialTime:0});
        if(!reduced.matches){setPhase('explanation-enter','v18 B/820 讲解进入');await Promise.all(animations.map(animation=>animation.finished));if(token!==state.runToken)return false}
        setPhase('explanation-stable',units[unit].name+' 讲解稳定');state.metrics.enteredAt=performance.now();state.busy=false;return true
      }catch(error){if(token===state.runToken){state.errors.push(String(error));setPhase('error',String(error));state.busy=false}return false}
    }
    function matchOverviewBoundary(targetRect,durationMs){const current=sequenceReference.getBoundingClientRect(),tailMs=Math.min(config.accelerationRampMs,durationMs),animation=sequenceReference.animate([{left:current.left+'px',top:current.top+'px',width:current.width+'px',height:current.height+'px',transform:'none'},{left:targetRect.left+'px',top:targetRect.top+'px',width:targetRect.width+'px',height:targetRect.height+'px',transform:'none'}],{delay:Math.max(0,durationMs-tailMs),duration:tailMs,easing:'ease',fill:'forwards'});if(reduced.matches)animation.finish();return animation}
    function prepareOverviewBoundary(durationMs,token){const target=wrap(state.chosenEntryFrame*2,192),targetRect=overviewContentRect();overviewApi().setPosition(target);state.currentOverviewFrame=state.chosenEntryFrame;state.metrics.overviewPreparedAt=performance.now();return{target,targetRect,confirmPaint:()=>overviewApi().setPositionAndWait(target),animation:matchOverviewBoundary(targetRect,durationMs),token}}
    async function presentOverviewFrame(boundary,token){await boundary.animation.finished;const painted=await boundary.confirmPaint();if(token!==state.runToken||painted.displayedFrame!==boundary.target)return false;const geometry=rectDelta(sequenceReference.getBoundingClientRect(),boundary.targetRect);if(Object.values(geometry).some(value=>value>.5))throw Error('focus overview boundary geometry drift');return new Promise(resolve=>requestAnimationFrame(firstVisibleAt=>{if(token!==state.runToken){resolve(false);return}sequenceReference.hidden=true;boundary.animation.cancel();state.handoff.focusLastPaintAt=state.metrics.focusLastPaintAt;state.handoff.overviewFirstVisibleAt=firstVisibleAt;state.handoff.focusOverviewFrameGapMs=firstVisibleAt-state.metrics.focusLastPaintAt;state.handoff.focusOverviewGeometry=geometry;state.handoff.overviewPaintedFrame=painted.displayedFrame;state.handoff.overviewTargetPaintedAt=painted.paintedAt;state.handoff.overviewTargetPaintToSwapMs=firstVisibleAt-painted.paintedAt;requestAnimationFrame(presentedAt=>{state.handoff.overviewPresentedAt=presentedAt;resolve(token===state.runToken)})}))}
    async function reverseFromStable(token){
      if(!reduced.matches){setPhase('explanation-return','v18 B/820 严格反向');const animations=setV18Direction('return');await Promise.all(animations.map(animation=>animation.finished));if(token!==state.runToken)return false;if(units[state.unit].key==='chamber'&&!(await inspectionTransition('exit',token)))return false}
      if(!(await reverseHandoff(token)))return false;
      const mechanical=Array.from({length:25},(_,index)=>({source:mechanicalSource(state.unit,index)})),focus=state.route.sampleAssets.map((_,index)=>({source:focusSource(state.route,index)}));
      if(!(await sequenceReverse(mechanical,config.mechanicalDurationMs,'mechanical-close','机械闭合',token)))return false;
      const boundary=prepareOverviewBoundary(state.route.newFocusDurationMs,token);
      if(!(await sequenceReverse(focus,state.route.newFocusDurationMs,'focus-return','聚焦返回',token)))return false;
      state.metrics.focusLastPaintAt=performance.now();if(!(await presentOverviewFrame(boundary,token)))return false;
      const reverseTurn={entry:state.baseOverviewFrame,distance:state.entryTurn.distance,direction:state.entryTurn.direction==='forward'?'backward':'forward'};
      if(!(await approvedTurn(reverseTurn,token,{phase:'turn-return'})))return false;
      cleanupHandoffLayers();setOverviewPosition(state.baseOverviewFrame);overview.contentWindow.dispatchEvent(new Event('focus'));state.metrics.returnedAt=performance.now();state.metrics.baseOverviewFrame=state.baseOverviewFrame;state.route=null;state.unit=null;state.chosenEntryFrame=null;state.entryTurn=null;state.pinnedRouteId=null;state.busy=false;state.reversing=false;setPhase('overview','A/192 总览');return true
    }
    async function strictReverse(){if(!state.ready||state.phase!=='explanation-stable'||state.busy||state.reversing)return false;const token=++state.runToken;state.busy=true;state.reversing=true;try{return await reverseFromStable(token)}catch(error){if(token===state.runToken){state.errors.push(String(error));state.busy=false;state.reversing=false;setPhase('error',String(error))}return false}}
    function requestModelViewportClose(){if(!state.ready||state.phase!=='overview'||state.busy||state.reversing)return false;const target=frameElement||window;target.dispatchEvent(new Event('twinkle-model-viewport-close-request',{bubbles:true}));return true}
    function handleReturnIntent(){if(state.phase==='overview')return requestModelViewportClose();if(state.phase==='explanation-stable')return strictReverse();return false}
    function snapshot(){const metrics={...state.metrics};if(metrics.clickedAt&&metrics.focusCompletedAt)metrics.clickToFocusCompleteMs=metrics.focusCompletedAt-metrics.clickedAt;if(metrics.clickedAt&&metrics.enteredAt)metrics.completeEnterMs=metrics.enteredAt-metrics.clickedAt;return{ready:state.ready,busy:state.busy,reversing:state.reversing,phase:state.phase,routeId:state.route&&state.route.routeId,unit:state.unit,currentOverviewFrame:state.currentOverviewFrame,baseOverviewFrame:state.baseOverviewFrame,chosenEntryFrame:state.chosenEntryFrame,pinnedRouteId:state.pinnedRouteId,readinessGeneration:state.readinessGeneration,readyRouteIds:[...state.routeReadiness].filter(([,record])=>record.ready).map(([routeId])=>routeId),bitmapCount:state.frameBitmaps.size,initialization:{...state.initialization},handoff:{...state.handoff},errors:[...state.errors],metrics,config}}
    async function initialize(){try{initializationFeedback.hidden=false;initializationRetry.hidden=true;updateInitialization('正在读取产品结构');productFilm.loop=true;await productFilm.play();const paths=['registry/twinkle/stage5-source-manifests/stage4-c2.json','registry/twinkle/stage5-source-manifests/stage4-c360.json','output/twinkle-stage5-a192-full-sequence/a192-manifest.json','output/twinkle-stage5-full-quality-focus-candidates/full-quality-focus-manifest.json','output/twinkle-stage5-formal-model-motion-candidates/model-motion-manifest.json','registry/twinkle/stage5-condenser-homepage-v1.json'],responses=await Promise.all(paths.map(path=>fetch(ROOT+path).then(response=>{if(!response.ok)throw Error(path+' '+response.status);return response.json()})));[state.c2,state.c360,state.a192,state.fullFocus]=responses;state.condenserAuthority=responses[5];const assets=collectRuntimeAssets(),{overviewSources,bitmapSources,detailSources}=assets;state.initialization.totalAssets=overviewSources.size+bitmapSources.size+detailSources.size;updateInitialization('正在拼装模型');await waitForOverview(overviewSources.size);for(const display of state.a192.frames){const authority=state.c360.frames[display.sourceAuthorityIndex];if(!authority)throw Error('F96 sourceAuthorityIndex missing');for(const [unit,hotspot] of Object.entries(display.hotspots)){const approved=authority.qualificationByUnit[unit];if(hotspot.status!==approved.status||hotspot.eligible!==approved.machineQualified)throw Error('F96 hotspot qualification drift')}}bindHotspots();await prepareRuntimeAssets(assets);const current=authorityAtDisplay();state.currentOverviewFrame=current.index;state.ready=true;updateInitialization('模型视窗已就绪');productFilm.loop=false;if(!(await playProductFilmIntoOverview()))return;setPhase('overview','A/192 总览')}catch(error){state.errors.push(String(error));state.ready=false;state.initialization.ready=false;initializationFeedback.hidden=false;initializationPercent.hidden=true;initializationProgress.hidden=true;initializationStatus.textContent='模型准备未完成';initializationRetry.hidden=false;setPhase('error','模型准备未完成')}}
    returnButton.onclick=handleReturnIntent;
    initializationRetry.onclick=()=>location.reload();
    document.querySelector('#singleShell').addEventListener('click',event=>{if(state.phase==='explanation-stable'&&!event.target.closest('.copy-panel'))strictReverse()});
    document.addEventListener('keydown',event=>{if(event.key==='Escape')handleReturnIntent()});
    reduced.addEventListener('change',()=>location.reload());
    addEventListener('pagehide',()=>{for(const bitmap of state.frameBitmaps.values())bitmap.close();state.frameBitmaps.clear();if(state.worker)state.worker.terminate()},{once:true});
    function setRouteReadiness(routeId,ready){if(state.phase!=='overview'||!state.routeReadiness.has(routeId))return false;state.readinessGeneration+=1;state.routeReadiness.set(routeId,{ready:Boolean(ready),generation:state.readinessGeneration});return true}
    window.__TWINKLE_H2_FULL_FLOW__={snapshot,enter,strictReverse,requestModelViewportClose,returnToOverview:strictReverse,setOverviewFrame:index=>{if(state.phase==='overview'){setOverviewPosition(index);state.baseOverviewFrame=index}},setRouteReadiness,runtimeRoutes,v18MasterTime,setExplanationDirection:setV18Direction,readV18VisualState,seekV18Master,config};
    initialize();
  })();
  </script>
"""


def _render_html(repo: Path, bundle: EvidenceBundle) -> str:
    html = _resolve(repo, bundle, V18_RELATIVE).read_text(encoding="utf-8")
    replacements = {
        "<title>TWINKLE 竖线推出动效审核 v18</title>": "<title>TWINKLE H2 统一后隔离全流程审核</title>",
        "shortName:'聚光镜',explanationSource:'/files/condenser-mechanical-expanded.png',reviewSource:'/files/condenser-mechanical-expanded.png',": "shortName:'聚光镜',backgroundSource:'../../showcase/homepage/assets/twinkle-condenser-unified-v1/detail/condenser-fixed.png',explanationSource:'../../showcase/homepage/assets/twinkle-condenser-unified-v1/detail/mechanical-expanded.png',reviewSource:'../../showcase/homepage/assets/twinkle-condenser-unified-v1/detail/mechanical-expanded.png',",
        "shortName:'光学舱',explanationSource:'/files/chamber-inspection-stable.png',reviewSource:'/files/chamber-mechanical-expanded.png',": "shortName:'光学舱',backgroundSource:'../twinkle-stage5-formal-model-motion-candidates/backgrounds/chamber-fixed.png',explanationSource:'../twinkle-stage5-formal-model-motion-candidates/models/chamber/inspection-stable.png',reviewSource:'../twinkle-stage5-formal-model-motion-candidates/models/chamber/mechanical-expanded.png',",
        '<div class="fixed-background"></div><img class="scene-image" src="${imageSource}" alt="${imageLabel}">': '<div class="reference-layer"><img class="fixed-background" src="${currentUnit.backgroundSource}" alt=""><img class="scene-image" src="${imageSource}" alt="${imageLabel}"></div>',
    }
    for source, target in replacements.items():
        if html.count(source) != 1:
            raise ReviewValidationError(f"v18 transform anchor drift: {source[:70]}")
        html = html.replace(source, target)
    entry = _load_module(repo / ENTRY_BUILDER_RELATIVE, "twinkle_entry_count_authority")
    functions = "\n".join(_extract_js_function(entry.PILOT_JS, name) for name in ("cyclicShortestTurn", "motionProfile", "motionProgress"))
    flow_script = FLOW_SCRIPT.replace("__APPROVED_TURN_FUNCTIONS__", functions)
    html = html.replace("  </style>", FLOW_STYLE + "  </style>", 1)
    html = html.replace("<body>", "<body>\n" + FLOW_MARKUP, 1)
    html = html.replace("</body>", flow_script + "</body>", 1)
    return html


def build_review(
    repo: Path,
    output: Path | None = None,
    evidence_root: Path | None = None,
) -> dict:
    repo = Path(repo).resolve(strict=True)
    bundle = _load_evidence_bundle(repo, evidence_root)
    expected = (repo / OUTPUT_RELATIVE).resolve()
    output = expected if output is None else Path(output).resolve()
    if output != expected:
        raise ReviewValidationError(f"review output must be exactly {expected}")
    output.mkdir(parents=True, exist_ok=True)
    allowed = {"index.html", "review-manifest.json", "machine-results.json"}
    unexpected = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file() and path.relative_to(output).as_posix() not in allowed}
    if unexpected:
        raise ReviewValidationError(f"refusing mixed review output: {sorted(unexpected)}")
    plan = plan_review(repo, evidence_root)
    manifest = {
        **plan,
        "routes": [{key: route[key] for key in ("routeId", "unit", "entryFrame", "oldFocusDurationMs", "newFocusDurationMs", "settledHoldMs", "sampleCount", "sourceManifest", "assetRoot")} for route in plan["routes"]],
    }
    (output / "index.html").write_text(_render_html(repo, bundle), encoding="utf-8")
    _write_json(output / "review-manifest.json", manifest)
    machine = {
        "schema": "twinkle-stage5-h2-isolated-full-flow-machine-results-v2",
        "reviewManifestSha256": _sha256(output / "review-manifest.json"),
        "reviewPageSha256": _sha256(output / "index.html"),
        "browserPassed": False, "browserEvidence": None, "machinePassed": False,
        "formalIntegrationAuthorized": False,
    }
    _write_json(output / "machine-results.json", machine)
    return manifest


def _validate_browser_results(
    repo: Path,
    result: dict,
    screenshot_root: Path,
    closure_root: Path | None = None,
    bundle: EvidenceBundle | None = None,
) -> bool:
    repo = Path(repo).resolve(strict=True)
    output = repo / OUTPUT_RELATIVE if closure_root is None else Path(closure_root)
    screenshot_root = Path(screenshot_root).resolve(strict=True)
    try:
        runs, errors, closure = result["routeSelectionRuns"], result["errors"], result["closure"]
        speed = result["hotspotSpeed"]
        recovery = result["resourceRecovery"]
        valid = (
            result["schema"] == "twinkle-stage5-h2-full-flow-browser-results-v2"
            and result["machinePassed"] is True and result["failures"] == []
            and result["viewports"] == [[1280, 800], [900, 700]]
            and set(result["routeSelectionCoverage"]) == EXPECTED_ROUTE_IDS
            and len(result["routeSelectionCoverage"]) == 10 and len(runs) == 10
            and {record["routeId"] for record in runs} == EXPECTED_ROUTE_IDS
            and all(record["machinePassed"] is True and record["startFrame"] == record["returnedFrame"] for record in runs)
            and set(errors) == {"console", "page", "request", "response"}
            and all(isinstance(values, list) and not values for values in errors.values())
            and result["approvedVisualBaselines"] == {key: sha for key, (_, sha) in APPROVED_SCREENSHOTS.items()}
            and result["approvedSemanticReturnSha256"] == APPROVED_SEMANTIC_RETURN[1]
            and _sha256(
                _resolve(repo, bundle, APPROVED_SEMANTIC_RETURN[0])
                if bundle is not None
                else repo / APPROVED_SEMANTIC_RETURN[0]
            ) == APPROVED_SEMANTIC_RETURN[1]
            and result["negativeControls"] == {key: sha for key, (_, sha) in NEGATIVE_SCREENSHOTS.items()}
            and closure["reviewManifestSha256"] == _sha256(output / "review-manifest.json")
            and closure["reviewPageSha256"] == _sha256(output / "index.html")
            and result["interactionSafety"]["strictReversePassed"] is True
            and result["interactionSafety"]["repeatedTriggerPassed"] is True
            and result["interactionSafety"]["entryMethods"] == {"hotspot": True, "fixedName": True, "realPointer": True}
            and all(result["interactionSafety"]["phaseInterruptions"].get(phase) is True for phase in (
                "turn", "focus", "mechanical", "handoff", "inspection", "explanation", "return"
            ))
            and result["reducedMotion"]["machinePassed"] is True
            and set(recovery) == {"abortCount", "failureObserved", "recovered", "machinePassed"}
            and type(recovery["abortCount"]) is int and recovery["abortCount"] >= 1
            and recovery["failureObserved"] is True
            and recovery["recovered"] is True
            and recovery["machinePassed"] is True
            and speed["machinePassed"] is True
            and speed["beforeTarget"] == 1 and speed["steadyTarget"] == 0.67
            and speed["enterDurationMs"] == 120 and speed["leaveGraceMs"] == 100
            and speed["recoveryDurationMs"] == 180
            and max(speed["rapidTransitionJumps"]) < 0.03
            and all(record["machinePassed"] is True for record in result["layoutChecks"])
            and {tuple(record["viewport"]) for record in result["layoutChecks"]} == {(1280, 800), (900, 700)}
            and len(result["screenshots"]) == 2
        )
        for record in result["screenshots"].values():
            path = screenshot_root / record["name"]
            valid = valid and path.is_file() and record["sha256"] == _sha256(path)
    except (KeyError, TypeError, OSError, ValueError):
        valid = False
    if not valid:
        raise ReviewValidationError("browser evidence drift")
    return True


def validate_browser_results(
    repo: Path, result: dict, evidence_root: Path | None = None
) -> bool:
    repo = Path(repo).resolve(strict=True)
    bundle = _load_evidence_bundle(repo, evidence_root)
    files_root = bundle.root / "files"
    return _validate_browser_results(
        repo,
        result,
        files_root / PLAYWRIGHT_RELATIVE,
        files_root / OUTPUT_RELATIVE,
        bundle,
    )


def record_browser_results(
    repo: Path,
    browser_results: Path,
    evidence_root: Path | None = None,
) -> dict:
    repo = Path(repo).resolve(strict=True)
    bundle = _load_evidence_bundle(repo, evidence_root)
    browser_results = Path(browser_results).resolve(strict=True)
    if browser_results.parent != (repo / PLAYWRIGHT_RELATIVE).resolve():
        raise ReviewValidationError("browser evidence must remain in the isolated Playwright root")
    result = _read_json(browser_results)
    passed = _validate_browser_results(
        repo,
        result,
        browser_results.parent,
        repo / OUTPUT_RELATIVE,
        bundle,
    )
    output = repo / OUTPUT_RELATIVE
    machine = _read_json(output / "machine-results.json")
    machine.update(
        browserPassed=passed,
        browserEvidence=browser_results.relative_to(repo).as_posix(),
        browserEvidenceSha256=_sha256(browser_results),
        routeSelectionRuns=result["routeSelectionRuns"],
        approvedSemanticReturnSha256=result["approvedSemanticReturnSha256"],
        approvedVisualBaselines=result["approvedVisualBaselines"],
        hotspotSpeed=result["hotspotSpeed"],
        errorClosure=result["errors"],
        machinePassed=passed,
    )
    _write_json(output / "machine-results.json", machine)
    return machine


def validate_milestone_evidence(
    repo: Path, evidence_root: Path | None
) -> dict:
    repo = Path(repo).resolve(strict=True)
    bundle = _load_evidence_bundle(repo, evidence_root)
    files_root = bundle.root / "files"
    receipt = _read_json(repo / EVIDENCE_RECEIPT_RELATIVE)
    formal = receipt["formalEvidence"]
    if formal != EXPECTED_FORMAL_EVIDENCE:
        raise ReviewValidationError("formal evidence definition drift")
    paths = {
        "browserResultsSha256": files_root / PLAYWRIGHT_RELATIVE / "browser-results.json",
        "machineResultsSha256": files_root / OUTPUT_RELATIVE / "machine-results.json",
        "reviewPageSha256": files_root / OUTPUT_RELATIVE / "index.html",
        "reviewManifestSha256": files_root / OUTPUT_RELATIVE / "review-manifest.json",
        "condenserScreenshotSha256": files_root / PLAYWRIGHT_RELATIVE / "condenser-1280x800-closure-v3.png",
        "chamberScreenshotSha256": files_root / PLAYWRIGHT_RELATIVE / "chamber-900x700-closure-v3.png",
    }
    if any(_sha256(path) != formal[name] for name, path in paths.items()):
        raise ReviewValidationError("formal evidence receipt drift")
    plan_review(repo, evidence_root)
    browser = _read_json(paths["browserResultsSha256"])
    _validate_browser_results(
        repo,
        browser,
        files_root / PLAYWRIGHT_RELATIVE,
        files_root / OUTPUT_RELATIVE,
        bundle,
    )
    machine = _read_json(paths["machineResultsSha256"])
    if not (
        machine.get("browserPassed") is True
        and machine.get("machinePassed") is True
        and machine.get("browserEvidenceSha256") == formal["browserResultsSha256"]
        and machine.get("reviewPageSha256") == formal["reviewPageSha256"]
        and machine.get("reviewManifestSha256") == formal["reviewManifestSha256"]
    ):
        raise ReviewValidationError("formal machine evidence drift")
    run_record_path = bundle.resolve(
        "output/playwright/twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2/run-record.json"
    )
    run_record = _read_json(run_record_path)
    if not (
        run_record.get("lifecycleStatus") == "completed"
        and run_record.get("summary") == receipt["outcomeSummary"]
        and run_record.get("pureValidation", {}).get("passed") is True
        and run_record.get("pureValidation", {}).get("strictValidatorPassed") is True
        and run_record.get("promotion", {}).get("performed") is True
        and run_record.get("promotion", {}).get("formalBrowserResultsSha256")
        == formal["browserResultsSha256"]
        and run_record.get("promotion", {}).get("formalMachineResultsSha256")
        == formal["machineResultsSha256"]
        and run_record.get("verification")
        == {
            "originalClosureTests": {"passed": 3, "exitCode": 0},
            "completeH2Tests": {"passed": 41, "exitCode": 0},
            "formalBrowserMachineContract": {"passed": True, "exitCode": 0},
            "fullPytest": {"progress": "100%", "exitCode": 0, "runs": 1},
        }
        and run_record.get("errors") == []
    ):
        raise ReviewValidationError("formal run record drift")
    return {
        "schema": "twinkle-stage5-h2-evidence-validation-v1",
        "bundleSha256": bundle.bundle_sha256,
        "bundleFileCount": receipt["bundleFileCount"],
        "bundleBytes": receipt["bundleBytes"],
        "outcomeSummary": receipt["outcomeSummary"],
        "browserPassed": True,
        "machinePassed": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--record-browser", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--validate-evidence", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_evidence:
        result = validate_milestone_evidence(args.repo, args.evidence_root)
    elif args.record_browser:
        result = record_browser_results(
            args.repo, args.record_browser, args.evidence_root
        )
    else:
        result = build_review(args.repo, args.output, args.evidence_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
