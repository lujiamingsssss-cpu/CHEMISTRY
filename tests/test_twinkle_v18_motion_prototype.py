from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PROTOTYPE = (
    REPO
    / ".superpowers"
    / "brainstorm"
    / "936-1788488553"
    / "content"
    / "generated-rail-push-motion-v18.html"
)


def _html() -> str:
    assert PROTOTYPE.is_file(), "v18 isolated motion prototype is missing"
    return PROTOTYPE.read_text(encoding="utf-8")


def test_v18_is_an_isolated_condenser_motion_proxy_with_explicit_limit():
    html = _html()

    assert "TWINKLE 竖线推出动效审核 v18" in html
    assert "/files/condenser-mechanical-expanded.png" in html
    assert "当前模型与背景已经烘焙在同一不透明PNG中；整图平移仅用于确定动效、位移和构图，不代表最终正式资产实现，也不能证明背景连续性。" in html
    for forbidden in ("mask-image", "runtime manifest", "viewportLocked=true"):
        assert forbidden not in html


def test_v18_exposes_only_the_primary_visual_review_controls():
    html = _html()

    assert html.count("data-size=") == 2
    assert html.count("data-preset=") == 3
    assert html.count("data-duration=") == 2
    for action in ("enter", "return", "replay", "compare"):
        assert f'data-action="{action}"' in html
    assert "<details" in html and "运行时诊断" in html
    for obsolete_label in ("cover · 待批准候选", "无雾幕文字", "context-softening", "光学舱·检查灯稳定"):
        assert obsolete_label not in html


def test_v18_declares_exact_viewports_presets_and_monotonic_waapi_contract():
    html = _html()

    for token in (
        "1280: { width: 1280, height: 800 }",
        "900: { width: 900, height: 700 }",
        "A: { shift: 150, scale: 1 }",
        "B: { shift: 240, scale: 0.97 }",
        "C: { shift: 300, scale: 0.95 }",
        "const durations = [720, 820]",
        "cubic-bezier(0.22, 1, 0.36, 1)",
        "translate3d(",
        ".animate(",
        "prefers-reduced-motion: reduce",
        "function settleReducedMotion()",
        "animation.currentTime = selectedDuration",
        "window.__V18__",
    ):
        assert token in html
    assert "scaleX(" not in html
    assert "skew(" not in html and "perspective(" not in html


def test_v18_keeps_copy_opaque_and_uses_a_clipped_push_reveal():
    html = _html()

    assert "overflow:clip" in html.replace(" ", "")
    assert 'class="content-wash"' in html
    assert "independent fixed readability layer" in html
    assert "computed opacity must remain 1" in html
    assert "fieldInterval: 52" in html
    assert "groupGap: 44" in html
    assert "opacity:0" not in html.replace(" ", "")


def test_v18_wash_is_clipped_into_the_same_reversible_waapi_timeline():
    html = _html()

    for token in (
        "washVisibleWidth",
        "washClipPath",
        "washStart",
        "washEnd",
        "clipPath: 'inset(0 100% 0 0)'",
        "clipPath: 'inset(0 0% 0 0)'",
        "view.querySelector('.content-wash').animate(",
        'class="boundary-clip reveal-clip" data-reveal="6"',
    ):
        assert token in html
    assert "opacity" not in html[html.index("function washKeyframes"):html.index("function setupAnimations")]


def test_v18_reports_required_geometry_and_motion_metrics():
    html = _html()

    for metric in (
        "viewportRect",
        "imageElementRect",
        "naturalWidth",
        "naturalHeight",
        "scaleX",
        "scaleY",
        "imageLeft",
        "imageTop",
        "transformMatrix",
        "actualCrop",
        "subjectBbox",
        "railRect",
        "copyRect",
        "reducedMotion",
        "monotonic",
        "jumpFree",
    ):
        assert metric in html


def test_v18_has_exactly_two_compact_primary_component_controls():
    html = _html()

    assert html.count("data-component=") == 2
    assert '<small>组件</small>' in html
    assert '<button data-component="condenser"' in html
    assert '<button data-component="chamber"' in html
    assert ">聚光镜</button>" in html
    assert ">光学舱</button>" in html


def test_v18_chamber_uses_inspection_for_explanation_and_mechanical_only_for_review():
    html = _html()

    assert "explanationSource:'/files/chamber-inspection-stable.png'" in html
    assert "reviewSource:'/files/chamber-mechanical-expanded.png'" in html
    assert "explanationLabel:'光学舱检查灯稳定亮态（完整讲解承载画面）'" in html
    assert "reviewLabel:'光学舱机械完全展开终态（检查灯进入前，仅构图核对）'" in html
    assert "currentUnit.reviewSource" in html
    assert "currentUnit.explanationSource" in html


def test_v18_chamber_copy_and_field_order_match_the_approved_contract():
    html = _html()

    ordered = (
        "FLUORESCENCE COLLECTION",
        "双通道采集光学舱",
        "采集光学舱承接从物镜后孔径出射的荧光，并将其引导至两条独立探测支路。",
        "底盖与侧板沿各自表面法向分离后，画面显示采集镜组安装结构、分光与滤光元件安装界面，以及双路探测连接区域。",
        "公开设计中的长通二向色元件先分离激发光与荧光；后级分光、滤光元件再将荧光分配至两条探测支路。",
        "每条探测支路末端各连接一片非球面聚光镜与对应的光电倍增管接口。",
        "['探测支路','2 路']",
    )
    positions = [html.index(text) for text in ordered]
    assert positions == sorted(positions)
    for label in ("系统职责", "结构呈现", "工作原理", "系统关系", "关键数据"):
        assert label in html


def test_v18_component_switch_rebuilds_isolated_animation_and_measurement_state():
    html = _html()

    for token in (
        "let selectedComponent = 'condenser'",
        "function selectComponent(component)",
        "animations.forEach(animation=>animation.cancel())",
        "sourceBboxCache = undefined",
        "selectedComponent,selectedSize,selectedPreset,selectedDuration",
    ):
        assert token in html


def test_v18_uses_the_approved_field_and_data_typography_contract():
    html = _html().replace(" ", "")

    assert ".field-label{" in html
    assert ".field-label{display:block;margin-bottom:9px;color:#28727a;font-size:12px;line-height:1;font-weight:720;letter-spacing:.10em}" in html
    assert ".data-label{display:block;margin:24px08px;color:#28727a;font-size:12px;font-weight:720;letter-spacing:.10em}" in html
    assert ".data-itemsmall{color:#697e82;font-size:11px}" in html
    assert ".data-itemb{font-size:15px;font-weight:630;white-space:nowrap}" in html
    assert ".v900.field-label,.v900.data-label{font-size:11px}" in html
    assert ".field+.field{margin-top:44px}" in html
