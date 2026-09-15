import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts/build_twinkle_stage5_h2_full_flow_review.py"
OUTPUT = REPO / "output/twinkle-stage5-h2-full-flow-review"
PLAYWRIGHT = REPO / "output/playwright/twinkle-stage5-h2-full-flow-review"
ROUTE_DURATIONS = {
    "dual_channel_collection_optics_chamber--entry-006--A": (1000, 650, 25),
    "dual_channel_collection_optics_chamber--entry-065--B": (1000, 650, 25),
    "dual_channel_condenser_lens_assembly--entry-087--A": (1000, 650, 25),
    "dual_channel_condenser_lens_assembly--entry-008--A": (1000, 650, 25),
    "dual_channel_collection_optics_chamber--entry-074--full-quality-candidate": (3058, 1400, 49),
    "dual_channel_collection_optics_chamber--entry-081--full-quality-candidate": (2457, 1400, 49),
    "dual_channel_collection_optics_chamber--entry-091--full-quality-candidate": (2100, 1260, 49),
    "dual_channel_condenser_lens_assembly--entry-005--full-quality-candidate": (2100, 1260, 49),
    "dual_channel_condenser_lens_assembly--entry-000--full-quality-candidate": (2100, 1260, 49),
    "dual_channel_condenser_lens_assembly--entry-092--full-quality-candidate": (687, 650, 25),
}


def _builder():
    spec = importlib.util.spec_from_file_location("twinkle_h2_full_flow", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build() -> tuple[object, dict, str]:
    module = _builder()
    manifest = module.build_review(REPO, OUTPUT)
    html = (OUTPUT / "index.html").read_text(encoding="utf-8")
    return module, manifest, html


def test_plan_preserves_all_ten_approved_routes_and_exact_speed_mapping():
    module = _builder()
    plan = module.plan_review(REPO)
    routes = {route["routeId"]: route for route in plan["routes"]}

    assert set(routes) == set(ROUTE_DURATIONS)
    for route_id, (old_ms, new_ms, frame_count) in ROUTE_DURATIONS.items():
        assert routes[route_id]["oldFocusDurationMs"] == old_ms
        assert routes[route_id]["newFocusDurationMs"] == new_ms
        assert routes[route_id]["sampleCount"] == frame_count
        assert len(routes[route_id]["sampleAssets"]) == frame_count
        assert all((REPO / asset).is_file() for asset in routes[route_id]["sampleAssets"])
    for route_id in module.EARLY_ROUTE_IDS:
        assert routes[route_id]["sourceManifest"] == (
            "registry/twinkle/stage5-source-manifests/stage4-c2.json"
        )
        assert all(
            asset.startswith(f"showcase/homepage/assets/twinkle/focus/{route_id}/")
            for asset in routes[route_id]["sampleAssets"]
        )
    assert plan["executionOrder"] == [
        "a192-overview", "f96-hotspot-entry", "approved-turn", "approved-focus",
        "mechanical", "chamber-inspection-if-applicable", "v18-explanation",
        "strict-reverse-via-matched-a192-boundary",
        "overview-close-request-owned-by-homepage",
    ]
    assert plan["formalIntegrationAuthorized"] is False


def test_plan_binds_a192_f96_hotspot_turn_reference_mechanical_and_v18_authorities():
    plan = _builder().plan_review(REPO)
    authorities = plan["authorities"]

    assert authorities["output/twinkle-stage5-a192-full-sequence/a192-manifest.json"] == (
        "0AD45675F90BA19CE9F7D60AF6C1ECF6E5437BC559BF6BD4C34412AA8FFB53E4"
    )
    assert authorities["registry/twinkle/stage5-source-manifests/stage4-c360.json"] == (
        "8D774A5821AF2D66AFF6480465C2F69007A556B0FAAA9B831FD9E3ADF51E3623"
    )
    assert authorities["scripts/build_twinkle_stage5_fixed_orbit_drag_pilot.py"] == (
        "2CD5A92F69D63BE573F7385555CB6473126481C13173B91E5329D866BE3BBF27"
    )
    assert authorities["scripts/build_twinkle_stage5_entry_count_pilot.py"] == (
        "FE4FAF7F00235F9D1CFBEDF490971277F457B86962DEF10B4AE7243005537E2A"
    )
    assert authorities["output/playwright/twinkle-stage5-lowres-mapping-review.html"] == (
        "ED720B8A776CFC29582A11D913E703A237A68D204B49E88957A01AD5BD41281C"
    )
    assert plan["display"] == {
        "manifest": "output/twinkle-stage5-a192-full-sequence/a192-manifest.json",
        "assetRoot": "output/twinkle-stage5-a192-full-sequence",
        "frameCount": 192,
        "fps": 24,
        "durationMs": 8000,
    }
    assert plan["mechanical"] == {
        "durationMs": 1000,
        "frameCount": 25,
        "roots": {
            "chamber": "showcase/homepage/assets/twinkle/mechanical/chamber",
            "condenser": "showcase/homepage/assets/twinkle-condenser-unified-v1/mechanical",
        },
    }
    assert plan["inspection"]["enterMs"] == 900
    assert plan["inspection"]["exitMs"] == 700
    assert plan["inspection"]["geometrySha256"] == (
        "25029A30042CEE2B12EFFA20B8BB8C7E8A46E35220F799AF8117CCB1BCD50E74"
    )
    assert authorities[
        "output/twinkle-stage5-blender-product-film/preview-v2/dip-to-black-loop-v2/dip-to-black-loop-review.mp4"
    ] == "2FD7A7CE89ECA556A896F1DE9AE5BCC9E0B5BC5A34BE091D590EF1F6391822FA"


def test_current_condenser_routes_use_an_isolated_v1_authority_without_changing_frozen_assets():
    frozen_registry = REPO / "registry/twinkle/stage5-runtime-assets.json"
    condenser_authority = REPO / "registry/twinkle/stage5-condenser-homepage-v1.json"
    version_root = "showcase/homepage/assets/twinkle-condenser-unified-v1"

    assert hashlib.sha256(frozen_registry.read_bytes()).hexdigest().upper() == (
        "8D32267C20218FA575E34E78415D69EEFA58F76C4CF71CBB7903952E7EFB03C4"
    )
    assert condenser_authority.is_file()

    authority = json.loads(condenser_authority.read_text(encoding="utf-8"))
    plan = _builder().plan_review(REPO)
    routes = {route["routeId"]: route for route in plan["routes"]}
    condenser_routes = {
        route_id: route
        for route_id, route in routes.items()
        if route["unit"] == "dual_channel_condenser_lens_assembly"
    }
    chamber_routes = {
        route_id: route
        for route_id, route in routes.items()
        if route["unit"] == "dual_channel_collection_optics_chamber"
    }

    assert authority["schema"] == "twinkle-stage5-condenser-homepage-assets-v1"
    assert authority["assetRoot"] == version_root
    assert authority["sourceCandidateManifestSha256"] == (
        "1C5E00B3D5DF490E72AA4D88BBBCABE0AA1D2D438467A45EF387CB09A3932EF7"
    )
    assert len(authority["routes"]) == 3
    assert sum(route["frameCount"] for route in authority["routes"]) == 123
    assert authority["mechanical"]["frameCount"] == 25
    assert plan["condenserAuthority"]["manifest"] == (
        "registry/twinkle/stage5-condenser-homepage-v1.json"
    )
    authority_route_ids = {route["routeId"] for route in authority["routes"]}
    assert all(
        all(asset.startswith(version_root + "/focus/") for asset in route["sampleAssets"])
        for route_id, route in condenser_routes.items()
        if route_id in authority_route_ids
    )
    assert all(
        all(asset.startswith("showcase/homepage/assets/twinkle/focus/") for asset in route["sampleAssets"])
        for route_id, route in condenser_routes.items()
        if route_id not in authority_route_ids
    )
    early_chamber = {
        route_id: route for route_id, route in chamber_routes.items()
        if route_id.endswith(("entry-006--A", "entry-065--B"))
    }
    later_chamber = {
        route_id: route for route_id, route in chamber_routes.items()
        if route_id not in early_chamber
    }
    assert len(early_chamber) == 2
    assert all(
        all(asset.startswith("showcase/homepage/assets/twinkle/focus/") for asset in route["sampleAssets"])
        for route in early_chamber.values()
    )
    assert len(later_chamber) == 3
    assert all(
        all(asset.startswith("output/twinkle-stage5-full-quality-focus-candidates/") for asset in route["sampleAssets"])
        for route in later_chamber.values()
    )
    assert plan["mechanical"]["roots"] == {
        "chamber": "showcase/homepage/assets/twinkle/mechanical/chamber",
        "condenser": version_root + "/mechanical",
    }
    assert plan["detail"]["condenser"] == {
        "background": version_root + "/detail/condenser-fixed.png",
        "foreground": version_root + "/detail/mechanical-expanded.png",
    }

    _, _, html = _build()
    compact = html.replace(" ", "")
    assert "stage5-condenser-homepage-v1.json" in compact
    assert version_root in compact
    assert "backgroundSource:'../twinkle-stage5-formal-model-motion-candidates/backgrounds/chamber-fixed.png'" in compact


def test_generated_page_embeds_the_unmodified_approved_a192_hotspot_player():
    _, _, html = _build()
    compact = html.replace(" ", "")

    for token in (
        '<iframeid="overviewPlayer"',
        'src="../twinkle-stage5-a192-full-sequence/index.html?embedded=1"',
        "approvedHotspotBuilderSha256:'2CD5A92F69D63BE573F7385555CB6473126481C13173B91E5329D866BE3BBF27'",
        "approvedA192BuilderSha256:'BFF0A962E8902571B30574DC22DAAADB44B47AD82964E5223177B59FF9C6288C'",
        "qualificationByUnit",
        "sourceAuthorityIndex",
    ):
        assert token in compact
    assert 'data-flow-unit=' not in html
    assert "border:2px solid #20a1ac" not in html


def test_overview_host_uses_the_same_approved_edge_gray_behind_the_a192_iframe():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "#flowOverlay{position:fixed;z-index:20;inset:0;background:rgb(233234233)" in compact
    assert "#overviewPlayer{position:absolute;inset:0;width:100%;height:100%;border:0;background:rgb(233234233)" in compact
    blackout = compact[
        compact.index("#initializationSequence{") :
        compact.index("}", compact.index("#initializationSequence{"))
    ]
    assert "background:#000" in blackout


def test_generated_page_uses_a192_display_f96_authority_and_approved_turn_profile():
    _, _, html = _build()
    compact = html.replace(" ", "")

    for token in (
        "twinkle-stage5-a192-full-sequence/a192-manifest.json",
        "stage5-source-manifests/stage4-c360.json",
        "qualificationByUnit",
        "functioncyclicShortestTurn(",
        "functionmotionProfile(",
        "functionmotionProgress(",
        "maximumAngularSpeedDegreesPerSecond:90",
        "accelerationRampMs:250",
        "decelerationRampMs:250",
        "settledHoldMs:100",
    ):
        assert token in compact
    assert "orbitFrameMs" not in html
    assert "#flowHud" not in html
    assert "flow-controls" not in html
    approved_player_css = (
        REPO / "output/twinkle-stage5-a192-full-sequence/player.css"
    ).read_text(encoding="utf-8").replace(" ", "")
    assert ".orbit-frame{display:block;width:100%;height:100%;object-fit:contain" in approved_player_css
    assert 'id="flowFrame"class="flow-canvas"' in compact
    assert 'id="flowFrameBack"class="flow-canvas"' in compact
    assert ".flow-canvas{position:absolute;inset:0;display:block;width:100%;height:100%" in compact


def test_turn_loop_terminates_by_elapsed_time_instead_of_float_progress():
    _, _, html = _build()
    compact = html.replace(" ", "")
    start = compact.index("asyncfunctionapprovedTurn(")
    end = compact.index("asyncfunctionwaitForOverview(", start)
    turn = compact[start:end]

    assert "constelapsed=now-startTime" in turn
    assert "if(elapsed<profile.movementMs&&!reduced.matches)requestAnimationFrame(step)" in turn
    assert "if(sample.progress<1&&!reduced.matches)" not in turn


def test_public_runtime_prepares_a_bounded_worker_bitmap_cache_before_ready():
    _, _, html = _build()
    compact = html.replace(" ", "")

    for token in (
        "constMAX_DECODE_CONCURRENCY=2",
        "createImageBitmap(blob",
        "caches.open(CACHE_NAME)",
        "bitmap.close()",
        "routeReadiness:newMap()",
        "awaitprepareRuntimeAssets(assets)",
        "state.initialization.ready=true",
    ):
        assert token in compact
    assert "state.ready=true;updateInitialization('模型视窗已就绪')" in compact


def test_nearest_ready_selection_is_deterministic_and_pins_the_route():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "functionnearestReadyRoute(" in compact
    assert "mathematicallyNearestEntry" in compact
    assert "chosenEntryFrame" in compact
    assert "fallbackUsed" in compact
    assert "readinessGeneration" in compact
    assert "state.pinnedRouteId=selected.route.routeId" in compact
    assert "if(!selected)returnfalse" in compact


def test_click_to_first_turn_paint_has_no_resource_preparation_in_its_critical_path():
    _, _, html = _build()
    compact = html.replace(" ", "")
    start = compact.index("asyncfunctionenter(unit)")
    end = compact.index("asyncfunctionreverse", start)
    enter = compact[start:end]

    assert "awaitapprovedTurn(selected.turn,token" in enter
    assert "preload(" not in enter
    assert "decodeImage(" not in enter
    assert "awaitPromise.all([...selected.route.sampleAssets" not in enter
    assert "clickToFirstTurnPaintMs" in compact


def test_reverse_uses_pinned_bitmaps_normalized_durations_and_presented_overview_handoff():
    _, _, html = _build()
    compact = html.replace(" ", "")
    start = compact.index("asyncfunctionreverseFromStable(")
    end = compact.index("asyncfunctionstrictReverse(", start)
    reverse = compact[start:end]

    assert "sequenceReverse(" in reverse
    assert "presentOverviewFrame(" in reverse
    assert "state.pinnedRouteId" in reverse
    assert "decode(" not in reverse
    assert "fetch(" not in reverse
    assert "state.history" not in reverse
    assert "item.interval" not in reverse


def test_approved_product_film_reports_real_progress_while_looping_until_ready_then_enters_at_black():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert 'id="initializationSequence"' in compact
    assert 'id="productFilm"' in compact
    assert '../twinkle-stage5-blender-product-film/preview-v2/dip-to-black-loop-v2/dip-to-black-loop-review.mp4' in html
    assert 'mutedplaysinlinepreload="auto"' in compact
    assert 'id="initializationStatus"role="status"aria-live="polite"' in compact
    assert 'id="initializationPercent"' in compact
    assert 'id="initializationProgress"aria-label="模型资源准备进度"' in compact
    assert 'id="initializationRetry"' in compact
    assert 'initialization-optics' not in html
    initialization_style = html[html.index('#initializationSequence'):html.index('#flowOverlay')]
    assert 'radial-gradient' not in initialization_style
    assert '#initializationFeedback' in html and 'width:260px' in html
    assert '#initializationProgress' in html and 'height:2px' in html
    assert 'font-size:clamp(12px,0.8vw,14px)' in html
    assert 'line-height:1.45' in html
    assert 'font-weight:500' in html
    assert 'letter-spacing:.06em' in html
    assert 'font-variant-numeric:tabular-nums' in html
    assert '@media(max-width:600px){#initializationFeedback{width:min(260px,calc(100vw - 48px));font-size:13px}}' in html
    for label in ("正在读取产品结构", "正在拼装模型", "正在校准光学细节", "正在准备交互视窗", "模型视窗已就绪"):
        assert label in html
    assert "initialization.completedAssets" in compact
    assert "initialization.totalAssets" in compact
    assert "functioncollectRuntimeAssets()" in compact
    assert "newSet(state.a192.frames.map(frame=>frame.src))" in compact
    assert "overviewSources.size+bitmapSources.size+detailSources.size" in compact
    assert "awaitwaitForOverview(overviewSources.size)" in compact
    assert "snap.decodedFrameCount" in compact
    assert "Math.max(state.initialization.completedAssets" in compact
    assert "Math.min(state.ready?100:99" in compact
    update = compact[compact.index("functionupdateInitialization("):compact.index("functioncreateBitmapWorker(")]
    assert "completedAssets/totalAssets" in update
    assert "if(totalAssets>0)" in update
    assert "initializationStatus.textContent!==label" in update
    assert "if(!state.ready||state.busy||state.phase!=='overview')returnfalse" in compact
    initialize = compact[compact.index("asyncfunctioninitialize("):compact.index("returnButton.onclick", compact.index("asyncfunctioninitialize("))]
    assert initialize.index("productFilm.loop=true") < initialize.index("awaitproductFilm.play()")
    assert initialize.index("awaitproductFilm.play()") < initialize.index("awaitprepareRuntimeAssets(assets)")
    assert initialize.index("awaitprepareRuntimeAssets(assets)") < initialize.index("productFilm.loop=false")
    assert initialize.index("productFilm.loop=false") < initialize.index("awaitplayProductFilmIntoOverview()")
    enter = compact[compact.index("asyncfunctionplayProductFilmIntoOverview("):compact.index("asyncfunctionenter(unit)")]
    assert "productFilm.play(" not in enter
    assert enter.index("awaitwaitForFilmEnd()") < enter.index("productFilm.hidden=true")
    assert enter.index("productFilm.hidden=true") < enter.index("awaitsetBlackCover(false)")
    assert "模型准备未完成" in html
    assert "initializationRetry.onclick=()=>location.reload()" in compact


def test_one_left_return_control_dispatches_by_phase_without_black_detail_exit():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert html.count('id="flowReturn"') == 1
    assert 'class="lucide lucide-arrow-left"' in html
    assert '<path d="m12 19-7-7 7-7"' in html
    assert '<path d="M19 12H5"' in html
    assert "Copyright (c) 2026 Lucide Icons and Contributors" in html
    assert "Copyright (c) 2013-present Cole Bemis" in html
    assert "Permission to use, copy, modify, and/or distribute this software for any" in html
    assert "Permission is hereby granted, free of charge, to any person obtaining a copy" in html
    assert 'width:44px' in html and 'height:44px' in html
    assert '#flowReturn:hover' in html and 'translateY(1px) scale(.985)' in html
    assert '#flowReturn:active' in html and 'scale(.96)' in html
    assert '#flowReturn:focus-visible' in html
    assert '@media(prefers-reduced-motion:reduce)' in compact
    assert "functionhandleReturnIntent()" in compact
    handler = compact[
        compact.index("functionhandleReturnIntent()"):
        compact.index("functionsnapshot(", compact.index("functionhandleReturnIntent()"))
    ]
    assert "state.phase==='overview'" in handler
    assert "requestModelViewportClose()" in handler
    assert "state.phase==='explanation-stable'" in handler
    assert "strictReverse()" in handler
    assert "setBlackCover(" not in handler
    assert "exitModelViewport" not in html
    assert "returnButton.onclick=handleReturnIntent" in compact
    assert "returnToOverview:strictReverse" in compact


def test_generated_page_uses_reference_carrier_mapping_instead_of_covering_full_carrier():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert 'class="reference-layer"' in html
    assert ".reference-layer{position:absolute;left:50%;top:50%;width:" in compact
    assert ".scene-image{position:absolute;left:-120%;top:-120%;width:340%;height:340%;" in compact
    assert ".scene-image{object-fit:cover" not in compact
    assert "transparentCanvas:[4352,3060]" in compact
    assert "referenceWindow:{x:1536,y:1080,width:1280,height:900}" in compact


def test_review_manifest_is_reference_only_and_records_ten_routes_without_sample_copy():
    _, manifest, _ = _build()
    files = sorted(path.relative_to(OUTPUT).as_posix() for path in OUTPUT.rglob("*") if path.is_file())

    assert files == ["index.html", "machine-results.json", "review-manifest.json"]
    assert not list(OUTPUT.rglob("*.png"))
    assert len(manifest["routes"]) == 10
    assert all("samples" not in route and "sampleAssets" not in route for route in manifest["routes"])
    assert all(route["sampleCount"] in {25, 49} for route in manifest["routes"])
    assert manifest["formalIntegrationAuthorized"] is False


def test_return_control_is_visible_only_at_stable_navigation_phases_and_escape_uses_same_dispatch():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "runToken" in html
    assert "handleReturnIntent" in html
    assert "reverseDetailEntry" not in html
    set_phase = compact[compact.index("functionsetPhase("):compact.index("functionoverviewApi(")]
    assert "phase==='overview'||phase==='explanation-stable'" in set_phase
    assert "returnButton.disabled" in set_phase
    assert "event.key==='Escape'" in compact
    assert "handleReturnIntent()" in compact[compact.index("document.addEventListener('keydown'"):]
    for phase in (
        "turn", "focus", "focus-settled", "mechanical-expand", "inspection-enter",
        "explanation-enter", "explanation-return", "inspection-exit",
        "mechanical-close", "focus-return", "turn-return",
    ):
        assert phase in html


def test_focus_return_matches_a192_content_rect_and_real_paint_before_atomic_swap():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert 'src="../twinkle-stage5-a192-full-sequence/index.html?embedded=1"' in html
    assert "functionoverviewContentRect()" in compact
    assert "setPositionAndWait" in compact
    assert "functionprepareOverviewBoundary(" in compact
    assert "functionmatchOverviewBoundary(" in compact
    reverse = compact[
        compact.index("asyncfunctionreverseFromStable("):
        compact.index("asyncfunctionstrictReverse(")
    ]
    assert reverse.index("prepareOverviewBoundary(") < reverse.index("sequenceReverse(focus")
    assert reverse.index("sequenceReverse(focus") < reverse.index("presentOverviewFrame(")
    assert reverse.index("presentOverviewFrame(") < reverse.index("approvedTurn(reverseTurn")
    assert "setBlackCover(" not in reverse
    assert "crossfade" not in reverse.lower()
    assert "fetch(" not in reverse
    assert "decode(" not in reverse
    assert reverse.index("approvedTurn(reverseTurn") < reverse.index("state.route=null")
    present = compact[
        compact.index("asyncfunctionpresentOverviewFrame("):
        compact.index("asyncfunctionreverseFromStable(")
    ]
    assert "awaitboundary.confirmPaint()" in present
    assert "rectDelta(" in present
    assert "value>.5" in present
    assert "overviewTargetPaintToSwapMs" in present
    assert present.index("awaitboundary.confirmPaint()") < present.index("sequenceReference.hidden=true")


def test_focus_entry_prepaints_at_the_a192_boundary_then_shares_one_animation_start():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "asyncfunctionprepareFocusBoundary(" in compact
    assert "functionmatchFocusBoundary(" in compact
    assert "asyncfunctionpresentFocusSequence(" in compact
    prepare = compact[
        compact.index("asyncfunctionprepareFocusBoundary(") :
        compact.index("functionmatchFocusBoundary(")
    ]
    match = compact[
        compact.index("functionmatchFocusBoundary(") :
        compact.index("asyncfunctionpresentFocusSequence(")
    ]
    present = compact[
        compact.index("asyncfunctionpresentFocusSequence(") :
        compact.index("asyncfunctionenter(unit)")
    ]
    enter = compact[
        compact.index("asyncfunctionenter(unit)") :
        compact.index("functionmatchOverviewBoundary(")
    ]

    assert "state.chosenEntryFrame*2" in prepare
    assert "awaitoverviewApi().setPositionAndWait(target)" in prepare
    assert "drawBitmap(items[0].source)" in prepare
    assert "awaitnextPaint()" in prepare
    assert "rectDelta(" in prepare and "value>.5" in prepare
    assert prepare.index("awaitoverviewApi().setPositionAndWait(target)") < prepare.index("drawBitmap(items[0].source)")
    assert prepare.index("drawBitmap(items[0].source)") < prepare.index("awaitnextPaint()")
    assert "duration:config.accelerationRampMs" in match
    assert "animation.startTime=startTime" in match
    assert "requestAnimationFrame(asyncstartTime=>" in present
    assert "sequenceReference.style.visibility='visible'" in present
    assert "matchFocusBoundary(boundary.focusRect,startTime)" in present
    assert "startedAt:startTime,skipFirst:true" in present
    assert "focusSequenceStartTime:startTime" in present
    assert enter.index("awaitapprovedTurn(selected.turn,token") < enter.index("awaitprepareFocusBoundary(focus,token)")
    assert enter.index("awaitprepareFocusBoundary(focus,token)") < enter.index("awaitpresentFocusSequence(")
    assert "fetch(" not in prepare + match + present + enter
    assert "decode(" not in prepare + match + present + enter


def test_detail_dom_images_geometry_and_diagnostics_are_ready_before_mechanical_starts():
    _, _, html = _build()
    compact = html.replace(" ", "")
    enter_start = compact.index("asyncfunctionenter(unit)")
    enter_end = compact.index("asyncfunctionpresentOverviewFrame(", enter_start)
    enter = compact[enter_start:enter_end]

    turn_call = enter.index("awaitapprovedTurn(selected.turn,token")
    prepare_call = enter.index("constdetailReady=prepareDetail(unit,token)")
    await_ready = enter.index("constdetail=awaitdetailReady")
    mechanical = enter.index("sequence(mechanical,config.mechanicalDurationMs")
    assert turn_call < prepare_call < await_ready < mechanical
    assert "functionprepareDetail(unit,token)" in compact
    assert "window.__V18__.select({component:key,size,preset:'B',duration:820})" in compact
    assert "state.detailImages.has(bitmapUrl(source))" in compact
    assert "awaitwarmDetailImage(source)" in compact
    assert "awaitwindow.__V18__.updateMetrics()" in compact
    assert "detailReady:true" in compact
    prepare_start = compact.index("asyncfunctionprepareDetail(unit,token)")
    prepare_end = compact.index("functionrectDelta(", prepare_start)
    prepare = compact[prepare_start:prepare_end]
    assert "approvedExplanation=entry.explanationSource" in prepare
    assert "if(key==='chamber')entry.explanationSource=entry.reviewSource" in prepare
    assert "entry.explanationSource=approvedExplanation" in prepare


def test_handoff_uses_matching_persistent_reference_layers_and_one_frame_atomic_swap():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert '<divid="sequenceReference"class="reference-layer"' in compact
    assert ".reference-layer{position:absolute;left:50%;top:50%;width:max(100vw,calc(100vh*64/45));height:max(100vh,calc(100vw*45/64));" in compact
    start = compact.index("asyncfunctionatomicVisualHandoff(")
    end = compact.index("asyncfunctioninspectionTransition(", start)
    handoff = compact[start:end]
    assert "requestAnimationFrame" in handoff
    assert "dispatchEvent(newCustomEvent('twinkle-handoff-before'" in handoff
    assert "dispatchEvent(newCustomEvent('twinkle-handoff-after'" in handoff
    assert "referenceDelta" in handoff
    assert "frameGapMs" in handoff
    assert "sleep(" not in handoff
    assert "sourceBbox(" not in handoff
    assert "getImageData(" not in handoff
    assert "overlay.hidden=true" not in compact


def test_v18_direction_controller_reuses_animation_objects_and_current_computed_state():
    _, _, html = _build()
    compact = html.replace(" ", "")

    start = compact.index("functionv18MasterTime(")
    end = compact.index("asyncfunctionenter(", start)
    shared = compact[start:end]
    assert "functionsetV18Direction(direction" in shared
    assert "document.timeline.currentTime" in shared
    assert "captureV18Styles()" in shared
    assert "animation.effect.setKeyframes(" in shared
    assert "animation.effect.updateTiming({duration})" in shared
    assert "animation.currentTime=0" in shared
    assert "animation.playbackRate=1" in shared
    assert "animation.startTime=sharedStart" in shared
    assert "v18AnimationStartTimes" in shared
    assert ".forEach(animation=>animation.reverse())" not in compact
    assert compact.count("setV18Direction('return')") == 1
    assert "setV18Direction('enter',{initialTime:0})" in compact


def test_v18_semantic_return_profile_has_the_approved_overlapping_windows():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "semanticReturnProfile={textStart:0,textEnd:.50,modelStart:.50,modelEnd:1,washStart:.50,washEnd:1,railStart:.50,railEnd:.65,durationMs:820}" in compact
    assert "semanticReturnProfile.modelStart,semanticReturnProfile.modelEnd" in compact
    assert "semanticReturnProfile.washStart,semanticReturnProfile.washEnd" in compact
    assert "functionsemanticReturnKeyframes(" in compact
    assert "reverseIndex=bodies.length-1-index" in compact
    assert "semanticReturnProfile.textEnd" in compact
    assert "semanticReturnProfile.modelStart" in compact
    assert "semanticReturnProfile.washStart" in compact
    assert "semanticReturnProfile.railStart" in compact
    assert "railFrom='scaleY('+railScale+')'" in compact
    assert "propertyFrames('transform',railFrom,'scaleY(0)'" in compact
    assert "matrix(1,0,0,0,0,0)" not in compact[compact.index("functionsemanticReturnKeyframes("):compact.index("functionsetV18Direction(")]
    assert "opacity" not in compact[compact.index("functionsemanticReturnKeyframes("):compact.index("functionsetV18Direction(")]


def test_v18_semantic_audit_reads_every_element_without_opacity_fades_or_duplicate_animations():
    _, _, html = _build()
    compact = html.replace(" ", "")
    start = compact.index("functionreadV18VisualState(")
    end = compact.index("asyncfunctionenter(", start)
    audit = compact[start:end]

    assert "railTransform" in audit
    assert "bodyTransforms" in audit
    assert "washClipPath" in audit
    assert "modelTransform" in audit
    assert "copyOpacity" in audit
    assert "functionseekV18Master(timeMs)" in audit
    assert "animation.currentTime=timeMs" in audit
    assert "setExplanationDirection:setV18Direction" in compact
    assert "readV18VisualState,seekV18Master" in compact
    assert html.count("function keyframes(") == 1
    assert "view.querySelectorAll('.reveal-body').forEach" in html
    assert "new Animation(" not in compact


def test_original_wash_and_model_window_is_preserved_for_mathematical_reverse():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "animations.push(view.querySelector('.content-wash').animate(washKeyframes(modelStart,modelEnd)" in compact
    assert "constview=singleShell.querySelector('.viewport'),total=selectedDuration,modelStart=.29,modelEnd=1" in compact
    assert "conststart=Math.min(.25+(index*rhythm.fieldInterval/total),.66)" in compact
    assert "rhythm={fieldInterval:52,groupGap:44}" in compact
    assert compact.count("functionwashKeyframes(") == 1
    assert "washKeyframes(.10,.24)" not in compact


def test_reverse_handoff_keeps_detail_visible_until_one_frame_atomic_mechanical_swap():
    _, _, html = _build()
    compact = html.replace(" ", "")
    start = compact.index("asyncfunctionreverseHandoff(")
    end = compact.index("asyncfunctioninspectionTransition(", start)
    reverse = compact[start:end]

    assert "detailLastPaintAt" in reverse
    assert "reverseReferenceDelta" in reverse
    assert "requestAnimationFrame" in reverse
    assert "reverseFrameGapMs" in reverse
    assert "dispatchEvent(newCustomEvent('twinkle-reverse-handoff-before'" in reverse
    assert "dispatchEvent(newCustomEvent('twinkle-reverse-handoff-after'" in reverse
    assert "sequenceReference.style.visibility='hidden';sequenceReference.hidden=false" in reverse
    assert reverse.index("returnnewPromise(resolve=>requestAnimationFrame") < reverse.index("sequenceReference.style.visibility='visible'")
    assert "sourceBbox(" not in reverse
    assert "getImageData(" not in reverse
    assert "sleep(" not in reverse


def test_continuity_fix_preserves_settled_mechanical_inspection_and_v18_timings():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "settledHoldMs:100" in compact
    assert "awaitsleep(selected.route.settledHoldMs)" in compact
    assert "mechanicalDurationMs:1000" in compact
    assert "inspectionEnterMs:900" in compact
    assert "inspectionExitMs:700" in compact
    assert "explanationDurationMs:820" in compact
    assert "preset:'B',duration:820" in compact


def test_handoff_is_atomic_while_user_operations_remain_locked():
    _, _, html = _build()
    compact = html.replace(" ", "")

    assert "setPhase('handoff'" in compact
    assert "state.phase==='handoff'" not in compact
    assert "reverseHandoff" in compact
    assert "sequenceReference.hidden=true" in compact
    assert "sequenceReference.hidden=false" in compact
    assert "cleanupHandoffLayers" in compact


def test_browser_evidence_validator_requires_all_ten_routes_and_approved_visual_sha():
    module = _builder()
    result = json.loads((PLAYWRIGHT / "browser-results.json").read_text(encoding="utf-8"))

    assert module.validate_browser_results(REPO, result) is True
    assert set(result["routeSelectionCoverage"]) == set(ROUTE_DURATIONS)
    assert len(result["routeSelectionRuns"]) == 10
    assert result["approvedVisualBaselines"] == {
        "condenser": "B5403CE933B707389A9CF7FD68880777390CA559A662A88BABA17B236EF31273",
        "chamber": "24294DE86CB68A4BFA415D0EF8F9D97A9ED14D3BA27191BAB9C88E3F3DDFB4A3",
    }
    assert result["approvedSemanticReturnSha256"] == (
        "963848401080C1735987DD82375DB4B212C08C1410FF208752F7C62D346984C5"
    )
    assert result["interactionSafety"]["entryMethods"]["realPointer"] is True
    assert result["negativeControls"] == {
        "condenser": "B99103B923D5B0BB12C342B28CB0B6F79B698321C41710B5303FEDAF984DC1D8",
        "chamber": "D798199140EFD12668662519C4FB3C310C94C17C0226C7C818C786201B984832",
    }

    drifted = copy.deepcopy(result)
    drifted["routeSelectionRuns"].pop()
    with pytest.raises(module.ReviewValidationError, match="browser evidence"):
        module.validate_browser_results(REPO, drifted)


def test_machine_results_bind_complete_browser_acceptance_closure():
    module = _builder()
    browser_path = PLAYWRIGHT / "browser-results.json"
    browser = json.loads(browser_path.read_text(encoding="utf-8"))
    module.build_review(REPO, OUTPUT)
    machine = module.record_browser_results(REPO, browser_path)

    assert machine["machinePassed"] is True
    assert machine["routeSelectionRuns"] == browser["routeSelectionRuns"]
    assert machine["approvedSemanticReturnSha256"] == browser["approvedSemanticReturnSha256"]
    assert machine["approvedVisualBaselines"] == browser["approvedVisualBaselines"]
    assert machine["hotspotSpeed"] == browser["hotspotSpeed"]
    assert machine["errorClosure"] == browser["errors"]


def test_browser_validator_accepts_only_positive_integer_resource_recovery_abort_counts():
    module = _builder()
    result = json.loads((PLAYWRIGHT / "browser-results.json").read_text(encoding="utf-8"))
    result["closure"] = {
        "reviewManifestSha256": module._sha256(OUTPUT / "review-manifest.json"),
        "reviewPageSha256": module._sha256(OUTPUT / "index.html"),
    }
    result["resourceRecovery"] = {
        "abortCount": 4,
        "failureObserved": True,
        "recovered": True,
        "machinePassed": True,
    }

    assert module.validate_browser_results(REPO, result) is True
    for invalid_abort_count in (0, -1, True, 1.0, "1", None):
        drifted = copy.deepcopy(result)
        drifted["resourceRecovery"]["abortCount"] = invalid_abort_count
        with pytest.raises(module.ReviewValidationError, match="browser evidence"):
            module.validate_browser_results(REPO, drifted)


def test_candidate_browser_payload_uses_the_same_strict_validator_without_formal_writes(tmp_path):
    module = _builder()
    result = json.loads((PLAYWRIGHT / "browser-results.json").read_text(encoding="utf-8"))
    result["closure"] = {
        "reviewManifestSha256": module._sha256(OUTPUT / "review-manifest.json"),
        "reviewPageSha256": module._sha256(OUTPUT / "index.html"),
    }
    result["resourceRecovery"] = {
        "abortCount": 4,
        "failureObserved": True,
        "recovered": True,
        "machinePassed": True,
    }
    for screenshot in result["screenshots"].values():
        source = PLAYWRIGHT / screenshot["name"]
        (tmp_path / screenshot["name"]).write_bytes(source.read_bytes())

    assert module._validate_browser_results(REPO, result, tmp_path) is True
    (tmp_path / next(iter(result["screenshots"].values()))["name"]).write_bytes(b"drift")
    with pytest.raises(module.ReviewValidationError, match="browser evidence"):
        module._validate_browser_results(REPO, result, tmp_path)


def test_final_closure_runner_opens_blank_page_so_collector_owns_the_only_formal_navigation():
    root = REPO / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
    runner = (root / "run-final-closure-v3.ps1").read_text(encoding="utf-8")
    collector = (root / "collect-formal-closure-v3.js").read_text(encoding="utf-8")

    assert "playwright-cli --session $sessionName open about:blank" in runner
    assert "playwright-cli --session $sessionName open $formalUrl" not in runner
    assert collector.count("await page.goto(formalUrl, {waitUntil: 'load'});") == 1


def test_final_closure_runner_always_persists_an_isolated_run_record_and_normal_raw_result():
    root = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
    )
    runner = (root / "run-final-closure-v3.ps1").read_text(encoding="utf-8")
    collector = (root / "collect-formal-closure-v3.js").read_text(encoding="utf-8")
    candidate_id = "twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2"

    assert "diagnostic-first-closure-v3-20260914" in runner
    assert candidate_id in runner
    assert candidate_id in collector
    assert "runId = 'diagnostic-first-closure-v3-20260914-v2'" in runner
    assert "run-record.json" in runner
    assert "raw-browser-result.json" in runner
    assert "twinkle-stage5-h2-closure-run-record-v3" in runner
    assert "playwright-cli-output.txt" in runner
    assert "### Result" in runner
    assert "ConvertFrom-Json" in runner
    assert "finally" in runner
    assert "Copy-Item" not in runner
    assert "--record-browser" not in runner


def test_closure_v3_collector_maps_f96_once_and_labels_phase_failures():
    collector = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "collect-formal-closure-v3.js"
    ).read_text(encoding="utf-8")

    assert "api.setOverviewFrame(target.entryFrame);" in collector
    assert "api.setOverviewFrame(target.entryFrame * 2);" not in collector
    assert "const waitPhase = async (phase, label, timeout = 45000)" in collector
    assert "const waitReady = (timeout = 120000)" in collector
    assert "expected=${phase}" in collector
    assert "actual=${state?.phase || 'unavailable'}" in collector
    assert "route=${state?.routeId || 'none'}" in collector
    assert "await waitPhase('explanation-stable', `route=${route.routeId} forward`);" in collector
    assert "await waitPhase('overview', `route=${route.routeId} reverse`);" in collector
    assert "await waitPhase('error', 'resource-recovery expected failure', 120000);" in collector
    assert "const expectedErrors = {console: [], request: []};" in collector
    assert "const expectedAbortConsole = recoveryActive" in collector
    assert "expectedErrors.console.push" in collector
    assert "expectedErrors.request.push" in collector
    assert "await page.route(recoveryPattern, abortTarget);" in collector
    assert "await page.unroute(recoveryPattern, abortTarget);" in collector
    assert "{times: 1}" not in collector
    assert "expectedAbortCount >= 1" in collector
    assert "expectedAbortCount === 1" not in collector
    assert "abortCount: expectedAbortCount" in collector


def test_closure_v3_collector_records_structured_outcomes_and_bounded_recovery():
    collector = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "collect-formal-closure-v3.js"
    ).read_text(encoding="utf-8")

    assert "const OUTCOME_STATUSES = new Set(['pass', 'fail', 'blocked', 'error']);" in collector
    assert "const recordOutcome = (id, status, detail = {})" in collector
    assert "const boundedRecoverOverview = async label" in collector
    assert "await boundedRecoverOverview" in collector
    assert "status: 'blocked'" in collector
    assert "status: machinePassed ? 'pass' : 'fail'" in collector
    assert "outcomes," in collector
    assert "outcomeSummary" in collector
    assert "outcomeSummary.fail === 0" in collector
    assert "outcomeSummary.blocked === 0" in collector
    assert "outcomeSummary.error === 0" in collector


def test_closure_v3_waits_for_product_owned_media_reload_without_starting_a_second_navigation():
    collector = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "collect-formal-closure-v3.js"
    ).read_text(encoding="utf-8")

    assert "const emulateMediaAndWaitForAutomaticReload = async (reducedMotion, label)" in collector
    assert "page.waitForEvent('framenavigated'" in collector
    assert "frame => frame === page.mainFrame()" in collector
    assert "await Promise.all([mainFrameNavigation, page.emulateMedia({reducedMotion})]);" in collector
    assert "await page.waitForLoadState('load');" in collector
    assert "await emulateMediaAndWaitForAutomaticReload('reduce', 'reduced-motion');" in collector
    assert "await emulateMediaAndWaitForAutomaticReload('no-preference', 'normal-motion');" in collector
    assert collector.count("page.reload({waitUntil: 'load'})") == 3
    assert "request.url() === formalUrl" not in collector
    assert "request.url().includes(formalUrl)" not in collector


def test_closure_v3_collector_samples_grace90_on_the_browser_timeline():
    collector = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "collect-formal-closure-v3.js"
    ).read_text(encoding="utf-8")
    speed = collector[
        collector.index("const speedRoute =") : collector.index("const routeSelectionRuns =")
    ]

    assert "__TWINKLE_H2_GRACE90_SAMPLE__" in speed
    assert speed.count("await speedButton.focus();") == 2
    assert "await page.mouse.move(1270, 10);\n  await speedButton.evaluate(element => element.blur());" in speed
    assert "element.addEventListener('pointerleave'" in speed
    assert "performance.now() - started" in speed
    assert "machinePassed: state.targetSpeedFactor === .67" in speed
    assert "grace90Sample.machinePassed" in speed
    assert "}, 90);" in speed
    assert "await page.waitForTimeout(90);" not in speed
    assert "grace90ElapsedMs" in speed


def test_closure_v3_layout_uses_the_approved_solid_orbit_viewport_background():
    collector = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "collect-formal-closure-v3.js"
    ).read_text(encoding="utf-8")
    layout = collector[
        collector.index("const layoutCheck =") : collector.index("await page.goto(formalUrl")
    ]

    assert "getComputedStyle(frame.parentElement)" in layout
    assert "letterboxBackgroundImage: viewportStyle.backgroundImage" in layout
    assert "letterboxBackgroundColor: viewportStyle.backgroundColor" in layout
    assert "record.letterboxBackgroundImage === 'none'" in layout
    assert "record.letterboxBackgroundColor === 'rgb(233, 234, 233)'" in layout
    assert "radial-gradient" not in layout


def test_focused_closure_contract_probe_is_independent_and_never_writes_formal_evidence():
    probe_path = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "probe-final-closure-contracts.js"
    )
    assert probe_path.is_file(), "focused closure contract probe is missing"
    probe = probe_path.read_text(encoding="utf-8")

    assert "page.url() !== 'about:blank'" in probe
    assert probe.count("await page.goto(formalUrl, {waitUntil: 'load'});") == 1
    assert "__TWINKLE_H2_GRACE90_SAMPLE__" in probe
    assert "await button.focus();" in probe
    assert "await page.mouse.move(1270, 10);\n  await button.evaluate(element => element.blur());" in probe
    assert "rgb(233, 234, 233)" in probe
    assert "unexpectedRequests" in probe
    assert "const checks = {" in probe
    assert "machinePassed: state.targetSpeedFactor === .67" in probe
    assert "machinePassed: state.targetSpeedFactor === 1" in probe
    assert "current: recovered.current," in probe
    assert "result.machinePassed = Object.values(checks).every(Boolean);" in probe
    assert "routeSelectionRuns" not in probe
    assert "browser-results.json" not in probe
    assert "machine-results.json" not in probe


def test_navigation_lifecycle_probe_correlates_exactly_one_reload_without_wide_url_ignores():
    probe_path = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "probe-navigation-lifecycle.js"
    )
    assert probe_path.is_file(), "navigation lifecycle probe is missing"
    probe = probe_path.read_text(encoding="utf-8")

    assert "let navigationSequence = 0;" in probe
    assert "let stage = 'bootstrap';" in probe
    assert "const requestContexts = new WeakMap();" in probe
    assert "startedNavigationSequence" in probe
    assert "startedStage" in probe
    assert "eventNavigationSequence: navigationSequence" in probe
    assert "eventStage: stage" in probe
    assert "resourceType: request.resourceType()" in probe
    assert "frame: request.frame() === page.mainFrame() ? 'main' : 'child'" in probe
    assert "frameUrl: request.frame().url()" in probe
    assert "failureReason: request.failure()?.errorText || null" in probe
    assert "page.on('request'" in probe
    assert "page.on('requestfinished'" in probe
    assert "page.on('requestfailed'" in probe
    assert "page.on('framenavigated'" in probe
    assert probe.count("await controlledNavigation(") == 3
    assert probe.count("page.goto(formalUrl") == 1
    assert probe.count("page.reload({waitUntil: 'load'})") == 2
    assert "emulateMediaAndWaitForAutomaticReload" in probe
    assert "await emulateMediaAndWaitForAutomaticReload('reduce', 'reduced-motion-change');" in probe
    assert "await emulateMediaAndWaitForAutomaticReload('no-preference', 'normal-motion-change');" in probe
    assert "explicit-reload-after-media-change" not in probe
    assert "explicit-reload-after-normal-motion-change" not in probe
    assert "await page.route(recoveryPattern, abortTarget);" in probe
    assert "await page.unroute(recoveryPattern, abortTarget);" in probe
    assert "fault-reload" in probe
    assert "recovery-reload" in probe
    assert "mediaDocumentCounts" in probe
    assert "includes(formalUrl)" not in probe
    assert "browser-results.json" not in probe
    assert "machine-results.json" not in probe


def test_resource_recovery_probe_is_layered_persistent_and_never_writes_formal_evidence():
    probe_path = (
        REPO
        / "output/playwright/twinkle-stage5-h2-full-flow-review-candidate-20260912"
        / "probe-resource-recovery.js"
    )
    assert probe_path.is_file(), "independent resource-recovery probe is missing"
    probe = probe_path.read_text(encoding="utf-8")

    assert "dual_channel_collection_optics_chamber--entry-006--A/focus-000.png" in probe
    assert "await page.route(recoveryPattern, abortTarget);" in probe
    assert "await page.unroute(recoveryPattern, abortTarget);" in probe
    assert "{times:" not in probe
    assert "abortCount += 1;" in probe
    assert "abortCount >= 1" in probe
    assert "const waitReady = (timeout = 120000)" in probe
    assert "const waitPhase = async (phase, label, timeout = 45000)" in probe
    assert "await waitPhase('error', 'fault-injection', 120000);" in probe
    assert "await waitInteractiveOverview('recovery-reload');" in probe
    assert "transition: ['error', 'overview']" in probe
    assert "expected=${expected}" in probe
    assert "actual=${actual}" in probe
    assert "abortCount=${abortCount}" in probe
    assert "const expectedErrors = {console: [], request: []};" in probe
    assert "const expectedAbortConsole = faultInjectionActive" in probe
    assert "message.text() === 'Failed to load resource: net::ERR_FAILED'" in probe
    assert "expectedErrors.console.push" in probe
    assert "expectedErrors.request.push" in probe
    assert "routeSelectionRuns" not in probe
    assert "browser-results.json" not in probe
    assert "machine-results.json" not in probe


_CORE_ONLY_TESTS = {
    "test_final_closure_runner_opens_blank_page_so_collector_owns_the_only_formal_navigation",
    "test_final_closure_runner_always_persists_an_isolated_run_record_and_normal_raw_result",
    "test_closure_v3_collector_maps_f96_once_and_labels_phase_failures",
    "test_closure_v3_collector_records_structured_outcomes_and_bounded_recovery",
    "test_closure_v3_waits_for_product_owned_media_reload_without_starting_a_second_navigation",
    "test_closure_v3_collector_samples_grace90_on_the_browser_timeline",
    "test_closure_v3_layout_uses_the_approved_solid_orbit_viewport_background",
    "test_focused_closure_contract_probe_is_independent_and_never_writes_formal_evidence",
    "test_navigation_lifecycle_probe_correlates_exactly_one_reload_without_wide_url_ignores",
    "test_resource_recovery_probe_is_layered_persistent_and_never_writes_formal_evidence",
}
if not os.environ.get("TWINKLE_STAGE5_H2_EVIDENCE_ROOT"):
    for _name, _test in tuple(globals().items()):
        if _name.startswith("test_") and _name not in _CORE_ONLY_TESTS:
            globals()[_name] = pytest.mark.skip(
                reason=(
                    "external H2 evidence not configured; set "
                    "TWINKLE_STAGE5_H2_EVIDENCE_ROOT to run the strict real-evidence contract"
                )
            )(_test)
