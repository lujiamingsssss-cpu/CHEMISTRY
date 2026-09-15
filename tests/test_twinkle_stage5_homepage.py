import hashlib
import json
import os
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
from PIL import Image

from scripts import build_twinkle_stage5_homepage as homepage_builder
from scripts.package_twinkle_stage5 import PackagingError


REPO = Path(__file__).resolve().parents[1]
HOMEPAGE = REPO / "showcase" / "homepage"
CATALOG = HOMEPAGE / "catalog"
PREVIEW = HOMEPAGE / "assets" / "twinkle-entry" / "c360-hover"
PILOT = REPO / "output" / "twinkle-stage5-rgba-hover-pilot"
PREVIEW_HASHES = (
    "E2C15CEE3E30BE84D79BCA375653118B6DF159C9DBF1C4855F9AFBC62853FAAC",
    "BB356F37AEE265FF342A58AC24CCD2B1C4B7D429C9CAE8C302C3E13622CB8AF5",
    "86D8102A4BADEB3032BAD6DC7C1F929D501C30C090E4662F86EF20A57212D0AD",
    "67B2B83D2BCEDDF36344A788257516A79F81C7DC850F808ABFEE33B82D83FE07",
    "964DD67878D534D09E8A9017C7F96EA2C60D87E493E4D85DCFFBF6339A82C78D",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class _ResourceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"img", "script"} and values.get("src"):
            self.resources.append(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.resources.append(values["href"])


def _local_path(base: Path, value: str) -> Path | None:
    if value.startswith(("data:", "http://", "https://", "mailto:", "tel:", "#")):
        return None
    return (base / value.split("?", 1)[0].split("#", 1)[0]).resolve()


def test_controlled_homepage_has_exact_static_twinkle_entry_contract():
    html = (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    css = (HOMEPAGE / "twinkle-entry.css").read_text(encoding="utf-8")
    script = (HOMEPAGE / "twinkle-entry.js").read_text(encoding="utf-8")

    for text in (
        "技术能力展示样机",
        "TWINKLE 开放光学系统",
        "从整体设计到细节呈现，近距离了解 TWINKLE 对品质与体验的坚持。",
        "360° 结构探索",
        "匠心设计 · 品质呈现",
        "点击打开视窗 →",
    ):
        assert text in html
    assert homepage_builder.TWINKLE_SECTION in html
    for forbidden in ("路线", "聚焦", "结构单元", "受控视窗"):
        assert forbidden not in homepage_builder.TWINKLE_SECTION
    assert 'id="quality"' in html
    assert 'class="twinkle-stage5-entry-card"' in html
    assert 'src="./assets/twinkle-entry/c360-hover/frame-000.png"' in html
    assert "700ms" in css
    assert "scale(1.01)" in css
    assert "translateX(4px)" in css
    assert '#quality[data-twinkle-stage5-entry]' in css
    assert "grid-template-columns:minmax(300px,.76fr) minmax(520px,1.24fr)" in css
    assert "gap:clamp(40px,6vw,84px)" in css
    assert "aspect-ratio:1280/900" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "transition: none" in css
    assert "IntersectionObserver" in script
    assert ".unobserve(" in script
    assert "setInterval" not in script
    assert "const nextPaint" in script


def test_twinkle_entry_uses_only_natural_rows_instead_of_legacy_dossier_rows():
    css = homepage_builder.ENTRY_CSS.replace(" ", "")
    desktop_start = css.index("#quality[data-twinkle-stage5-entry]{")
    desktop = css[desktop_start : css.index("}", desktop_start) + 1]
    mobile_start = css.index("@media(max-width:860px)")
    mobile = css[mobile_start : css.index("}}", mobile_start) + 2]

    assert "grid-template-areas:none" in desktop
    assert "grid-template-rows:auto" in desktop
    assert "grid-template-rows:autoauto" in mobile
    assert "72px" not in desktop


def test_homepage_keeps_hero_lens_orbit_without_the_purple_decorative_dot():
    html = (HOMEPAGE / "index.html").read_text(encoding="utf-8")

    assert ".lens-orbit{" in html
    assert ".lens-orbit:after" not in html


def test_h1_preview_is_exactly_five_rgba_frames_isolated_from_runtime_c360():
    files = sorted(path for path in PREVIEW.glob("*.png") if path.is_file())

    assert [path.name for path in files] == [f"frame-{index:03d}.png" for index in range(5)]
    assert PREVIEW.resolve() != (HOMEPAGE / "assets" / "twinkle" / "c360").resolve()
    for index, path in enumerate(files):
        assert _sha256(path) == PREVIEW_HASHES[index]
        assert path.read_bytes() == (PILOT / "frames" / path.name).read_bytes()
        with Image.open(path) as image:
            assert image.size == (640, 450)
            assert image.mode == "RGBA"


def test_builder_binds_and_validates_authoritative_hover_pilot(tmp_path):
    validator = getattr(homepage_builder, "validate_hover_preview_source", None)
    if validator is None:
        pytest.fail("homepage builder has no H1 hover preview validator")

    validated = validator(PILOT)
    assert tuple(path.name for path in validated) == tuple(
        f"frame-{index:03d}.png" for index in range(5)
    )
    assert tuple(_sha256(path) for path in validated) == PREVIEW_HASHES

    drifted = tmp_path / PILOT.name
    shutil.copytree(PILOT, drifted)
    (drifted / "frames" / "frame-004.png").write_bytes(b"not the approved RGBA frame")
    with pytest.raises(Exception, match="hover preview.*drift"):
        validator(drifted)


def test_h1_script_has_exact_gated_single_round_static_fallback_contract():
    script = (HOMEPAGE / "twinkle-entry.js").read_text(encoding="utf-8")

    assert "const sequence = [0, 1, 2, 3, 4, 3, 2, 1, 0];" in script
    assert "const frameIntervalMs = 80;" in script
    assert "matchMedia('(prefers-reduced-motion: reduce)')" in script
    assert "matchMedia('(hover: hover) and (pointer: fine)')" in script
    assert "IntersectionObserver" in script
    assert script.index("item.isIntersecting") < script.index("new Image()")
    assert "mouseenter" in script and "mouseleave" in script
    assert "focusin" in script and "focusout" in script
    assert "click" in script
    assert script.count("preventDefault") == 1
    assert script.index("event.preventDefault()") > script.index("async function openViewport(")
    assert "Promise.all" in script and ".catch(" in script
    assert "playedThisActivation" in script
    assert "activationPending" in script
    assert "preloadedFrames" in script
    assert "model.addEventListener('error'" in script
    assert "frame-005" not in script and "frame-095" not in script
    assert script.count("setTimeout") == 1


def test_entry_visual_applies_one_uniform_vertical_correction_without_asset_drift():
    css = homepage_builder.ENTRY_CSS.replace(" ", "")

    image_rule = css[
        css.index(".twinkle-stage5-entry-visualimg{") :
        css.index("}.twinkle-stage5-entry-meta", css.index(".twinkle-stage5-entry-visualimg{"))
    ]
    assert "transform:translateY(11.2%)" in image_rule
    assert "min-height:0" in image_rule
    assert css.count("translateY(11.2%)") == 1
    assert tuple(_sha256(path) for path in sorted(PREVIEW.glob("*.png"))) == PREVIEW_HASHES


def test_twinkle_entry_restores_only_the_authoritative_outer_host_for_h2():
    section = homepage_builder.TWINKLE_SECTION
    css = homepage_builder.ENTRY_CSS.replace(" ", "")
    script = homepage_builder.ENTRY_JS.replace(" ", "")

    assert 'class="twinkle-stage5-entry-card"' in section
    assert 'class="twinkle-stage5-viewport-backdrop"' not in section
    assert 'class="twinkle-stage5-viewport"' not in section
    assert 'class="twinkle-stage5-viewport-blackout"' not in section
    assert "document.querySelector('.twinkle-stage5-viewport-backdrop')" in homepage_builder.ENTRY_JS
    assert "document.querySelector('.twinkle-stage5-viewport')" in homepage_builder.ENTRY_JS
    assert "document.querySelector('.twinkle-stage5-viewport-blackout')" in homepage_builder.ENTRY_JS
    assert "const bodyTargets = [...document.body.children]" in homepage_builder.ENTRY_JS
    assert ".twinkle-stage5-viewport{position:fixed;inset:0" in css
    assert ".twinkle-stage5-viewport-blackout{position:fixed;inset:0" in css
    assert "functionsetBackgroundInert()" in script
    assert "functionrestoreBackgroundInert()" in script
    assert "document.body.style.overflow='hidden'" in script
    assert "window.scrollTo(0,savedScrollY)" in script
    assert "previousFocus?.focus()" in script
    assert "twinkle-model-viewport-close-request" in script
    assert "viewer.addEventListener" in script
    assert "postMessage" not in script
    assert "__TWINKLE_H2_FULL_FLOW__" not in script
    assert "j-reveal" not in script and "f-reveal" not in script
    close = script[
        script.index("asyncfunctioncloseViewport("):
        script.index("entry.addEventListener('mouseenter'", script.index("asyncfunctioncloseViewport("))
    ]
    assert close.index("awaitsetHomepageBlackCover(true)") < close.index("viewport.dataset.open='false'")
    assert close.index("viewport.dataset.open='false'") < close.index("awaitnextPaint()")
    assert close.index("awaitnextPaint()") < close.index("awaitsetHomepageBlackCover(false)")


def test_overview_close_hides_old_viewport_while_black_before_homepage_reveal():
    script = homepage_builder.ENTRY_JS.replace(" ", "")
    open_viewport = script[
        script.index("asyncfunctionopenViewport(") :
        script.index("asyncfunctioncloseViewport(")
    ]
    close = script[
        script.index("asyncfunctioncloseViewport(") :
        script.index("constobserver=", script.index("asyncfunctioncloseViewport("))
    ]

    assert "viewport.hidden=false" in open_viewport
    assert "backdrop.hidden=false" in open_viewport
    assert "viewport.hidden=true" in close
    assert "backdrop.hidden=true" in close
    assert open_viewport.index("viewport.hidden=false") < open_viewport.index("viewport.dataset.open='true'")
    assert open_viewport.index("backdrop.hidden=false") < open_viewport.index("backdrop.dataset.open='true'")
    assert close.index("awaitsetHomepageBlackCover(true)") < close.index("viewport.hidden=true")
    assert close.index("viewport.hidden=true") < close.index("restoreBackgroundInert()")
    assert close.index("backdrop.hidden=true") < close.index("restoreBackgroundInert()")
    assert close.index("viewport.hidden=true") < close.index("awaitnextPaint()")
    assert close.index("awaitnextPaint()") < close.index("awaitsetHomepageBlackCover(false)")
    assert "setTimeout" not in close
    assert "viewer.src=''" not in close


def test_h1_dynamic_preview_assets_are_in_homepage_packaging_closure():
    script = (HOMEPAGE / "twinkle-entry.js").read_text(encoding="utf-8")
    report = json.loads((PILOT / "pilot-report.json").read_text(encoding="utf-8"))

    assert "./assets/twinkle-entry/c360-hover/frame-${label}.png" in script
    assert sum(path.stat().st_size for path in PREVIEW.glob("*.png")) == 658_985
    assert report["downloadBytes"] == {
        "fiveRgbaFrames": 658_985,
        "initialStaticFrame": 135_716,
        "fourAdditionalHoverFrames": 523_269,
        "preloadedFrameCount": 5,
    }


def _integration_roots() -> tuple[Path, Path]:
    authority_value = os.environ.get("TWINKLE_HOMEPAGE_AUTHORITY")
    baseline_value = os.environ.get("TWINKLE_HOMEPAGE_BASELINE")
    if not authority_value or not baseline_value:
        pytest.skip("set TWINKLE_HOMEPAGE_AUTHORITY and TWINKLE_HOMEPAGE_BASELINE")
    return Path(authority_value).resolve(strict=True), Path(baseline_value).resolve(strict=True)


def _copy_pilot_contract(target: Path) -> None:
    pilot_target = target / homepage_builder.HOVER_PILOT_RELATIVE
    (pilot_target / "frames").mkdir(parents=True)
    for name in ("pilot-report.json", "worker-audit.json", "browser-results.json"):
        shutil.copyfile(PILOT / name, pilot_target / name)
    for index in range(5):
        name = f"frame-{index:03d}.png"
        shutil.copyfile(PILOT / "frames" / name, pilot_target / "frames" / name)


def test_builder_fresh_target_packages_exact_h1_preview_and_leaves_no_staging(tmp_path):
    authority, baseline = _integration_roots()
    target = tmp_path / "target"
    target.mkdir()
    _copy_pilot_contract(target)

    homepage = homepage_builder.build_controlled_homepage(authority, baseline, target)

    preview = homepage / homepage_builder.HOVER_PREVIEW_RELATIVE
    assert [_sha256(path) for path in sorted(preview.glob("*.png"))] == list(PREVIEW_HASHES)
    assert (homepage / "twinkle-entry.js").read_text(encoding="utf-8") == homepage_builder.ENTRY_JS
    assert (homepage / "twinkle-entry.css").read_text(encoding="utf-8") == homepage_builder.ENTRY_CSS
    built_html = (homepage / "index.html").read_text(encoding="utf-8")
    assert homepage_builder.TWINKLE_SECTION in built_html
    assert homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT in built_html
    assert built_html == (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    assert ".lens-orbit{" in built_html
    assert ".lens-orbit:after" not in built_html
    assert built_html.count('href="./catalog/circular-gallery-preview.html"') == 3
    assert (homepage / "catalog/circular-gallery-preview.html").is_file()
    assert (homepage / "catalog/circular-gallery-preview.html").read_text(
        encoding="utf-8"
    ) == (CATALOG / "circular-gallery-preview.html").read_text(encoding="utf-8")
    assert (homepage / "catalog/product-ring-gallery.js").read_text(
        encoding="utf-8"
    ) == (CATALOG / "product-ring-gallery.js").read_text(encoding="utf-8")
    assert not (homepage / "assets" / "twinkle").exists()
    assert not list((target / "showcase").glob(".homepage-stage5-*.staging"))


@pytest.mark.parametrize(
    ("report_name", "field"),
    [
        ("pilot-report.json", "continuity"),
        ("worker-audit.json", "frames"),
        ("browser-results.json", "desktop"),
    ],
)
def test_builder_rejects_wrong_report_container_types_as_packaging_error(
    tmp_path, report_name, field
):
    drifted = tmp_path / PILOT.name
    shutil.copytree(PILOT, drifted)
    report_path = drifted / report_name
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report[field] = None
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(PackagingError, match="hover preview report drift"):
        homepage_builder.validate_hover_preview_source(drifted)


def test_controlled_homepage_excludes_old_m4_and_runtime_state_machine():
    files = [path.relative_to(HOMEPAGE).as_posix() for path in HOMEPAGE.rglob("*") if path.is_file()]
    combined_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in HOMEPAGE.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js", ".mjs", ".json"}
    )

    assert "twinkle-m4.js" not in files
    assert "twinkle-m4.css" not in files
    assert not any("assets/twinkle-m4/" in value for value in files)
    assert "data-twinkle-m4" not in combined_text
    assert "state-j_green_filter_subassembly" not in combined_text
    assert "state-f_dual_acl_housing" not in combined_text
    assert "twinkle-runtime-manifest.json" not in files
    assert "twinkle-runtime-manifest" not in combined_text


def test_controlled_homepage_keeps_three_catalog_entries_routed_to_local_gallery():
    html = (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<a class="product-preview-action"[^>]+>', html)
    assert match
    tag = match.group(0)
    local_gallery = "./catalog/circular-gallery-preview.html"
    assert html.count(f'href="{local_gallery}"') == 3
    assert f'href="{local_gallery}"' in tag
    assert 'target="_blank"' not in tag
    assert "supreme-oe.com/products.aspx" not in tag
    assert "浏览完整目录 →" in html


def test_homepage_and_catalog_share_navigation_content_links_and_feedback():
    homepage = (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    catalog = (CATALOG / "circular-gallery-preview.html").read_text(encoding="utf-8")

    expected = {
        "homepage": [
            ("#home", "首页"),
            ("#materials", "能力概览"),
            ("#applications", "应用方向"),
            ("#quality", "TWINKLE"),
            ("#products", "产品中心"),
            ("#company", "业务范围"),
        ],
        "catalog": [
            ("../index.html#home", "首页"),
            ("../index.html#materials", "能力概览"),
            ("../index.html#applications", "应用方向"),
            ("../index.html#quality", "TWINKLE"),
            ("./circular-gallery-preview.html", "产品中心"),
            ("../index.html#company", "业务范围"),
        ],
    }

    for name, html in (("homepage", homepage), ("catalog", catalog)):
        header = re.search(r'<header class="topbar">.*?</header>', html).group(0)
        nav = re.search(r'<nav class="topnav">(.*?)</nav>', header).group(1)
        links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', nav)
        assert links == expected[name]
        assert '<button class="cta" type="button" data-open-inquiry>技术询盘</button>' in header
        assert "mailto:" not in header
        assert "该功能开发中，敬请期待" in html
        assert "data-inquiry-dialog" in html

        assert ".topnav a:hover" in html
        assert ".topnav a:focus-visible" in html
        assert ".topnav a:active" in html
        assert ".topnav a[aria-current]" in html
        current_rule = re.search(
            r"\.topnav a\[aria-current\]\{([^}]*)\}", html
        ).group(1)
        assert "background:#173e44" in current_rule
        assert "color:#fff" in current_rule
        assert "box-shadow" not in current_rule
        assert "inset" not in current_rule
        assert ".brand:active" in html
        assert ".cta:active" in html
        cta_rule = re.search(r"\.cta\{([^}]*)\}", html).group(1)
        assert "background:transparent" in cta_rule
        assert "color:#405158" in cta_rule
        assert "background:#173e44" not in cta_rule
        assert ".cta:hover{background:rgba(79,199,210,.12);color:#173e44}" in html
        cta_active_rule = re.search(r"\.cta:active\{([^}]*)\}", html).group(1)
        assert "background:#173e44" in cta_active_rule
        assert "color:#fff" in cta_active_rule
        assert "min-height:44px" in html
        assert "transform:translateY(1px) scale(.96)" in html
        assert re.search(
            r"@media\(max-width:900px\)\{.*?\.topnav\{display:none\}", html
        )
        assert re.search(
            r"@media\(prefers-reduced-motion:reduce\).*?\.topnav a:active.*?transform:none",
            html,
        )

    homepage_nav = re.search(r'<nav class="topnav">(.*?)</nav>', homepage).group(1)
    catalog_nav = re.search(r'<nav class="topnav">(.*?)</nav>', catalog).group(1)
    assert homepage_nav.count('aria-current="location"') == 1
    assert re.search(r'<a href="#home" aria-current="location">首页</a>', homepage_nav)
    assert "aria-pressed" not in homepage_nav
    assert "aria-pressed" not in catalog_nav
    assert catalog_nav.count('aria-current="page"') == 1
    assert re.search(
        r'<a href="\./circular-gallery-preview\.html" aria-current="page">产品中心</a>',
        catalog_nav,
    )
    assert homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT in homepage
    assert "IntersectionObserver" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "rootMargin" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "['home', 'materials', 'applications', 'quality', 'products', 'company']" in (
        homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    )
    assert "aria-current" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "location" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "hashchange" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "pageshow" in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert "history." not in homepage_builder.HOMEPAGE_NAVIGATION_SCRIPT
    assert re.search(
        r'<a class="product-preview-action"[^>]+href="\./catalog/circular-gallery-preview\.html"',
        homepage,
    )
    assert homepage_builder.CATALOG_RETURN_CSS in catalog
    assert homepage_builder.CATALOG_RETURN_HOST in catalog
    assert catalog.count('class="catalog-return"') == 1
    assert re.search(
        r'<a class="catalog-return" href="\.\./index\.html#products" aria-label="返回产品中心">',
        catalog,
    )
    assert 'class="lucide lucide-arrow-left"' in catalog
    assert '<path d="m12 19-7-7 7-7"' in catalog
    assert '<path d="M19 12H5"' in catalog
    return_rule = re.search(r"\.catalog-return\{([^}]*)\}", catalog).group(1)
    assert "left:24px" in return_rule
    assert "top:98px" in return_rule
    assert "width:44px" in return_rule
    assert "height:44px" in return_rule
    assert ".catalog-return:hover" in catalog
    assert ".catalog-return:active" in catalog
    assert ".catalog-return:focus-visible" in catalog
    assert "@media(max-width:900px){.catalog-return{top:90px}" in catalog
    assert re.search(
        r"@media\(prefers-reduced-motion:reduce\).*?\.catalog-return:active.*?transform:none",
        catalog,
    )


def test_controlled_homepage_packages_the_frozen_rotating_catalog_closure():
    assert (CATALOG / "circular-gallery-preview.html").is_file()
    html = (CATALOG / "circular-gallery-preview.html").read_text(encoding="utf-8")
    products = (CATALOG / "product-items.mjs").read_text(encoding="utf-8")
    files = [path for path in CATALOG.rglob("*") if path.is_file()]

    assert len(files) == 228
    assert len(re.findall(r"\bid:\s*'", products)) == 10
    assert 'href="../index.html#home"' in html
    assert 'href="../index.html#quality"' in html
    assert "2026-08-06-homepage-authority" not in html
    assert (CATALOG / "product-ring-gallery.js").is_file()
    assert (CATALOG / "ring-gallery-core.mjs").is_file()
    assert (CATALOG / "paper-dithering-background.js").is_file()
    assert (CATALOG / "assets/vendor/ogl.mjs").is_file()
    assert (CATALOG / "assets/vendor/OGL-LICENSE.txt").is_file()
    assert (CATALOG / "assets/vendor/paper-shaders/LICENSE").is_file()
    assert (CATALOG / "assets/vendor/paper-shaders/NOTICE").is_file()
    assert homepage_builder.CATALOG_TREE_SHA256 == (
        "FD814AAFC78FFE24451C922B01B70202AA135577C1195E5B3E6AFD9E676F368A"
    )
    assert _sha256(CATALOG / "ring-gallery-core.mjs") == (
        "E0176BAE1C61AFEF9F10943BC8FF020D979E4A0A7A59301348EEBE92F7CD5294"
    )
    assert _sha256(CATALOG / "product-items.mjs") == (
        "39B26CF6EABC7853C06390859EA3E47F475C5DC0B58A90CC683B0A8CD1CA32DE"
    )


def test_controlled_catalog_separates_inquiry_and_reference_actions():
    html = (CATALOG / "circular-gallery-preview.html").read_text(encoding="utf-8")
    script = (CATALOG / "product-ring-gallery.js").read_text(encoding="utf-8")

    inquiry_buttons = re.findall(r"<button[^>]+data-open-inquiry[^>]*>技术询盘</button>", html)
    assert len(inquiry_buttons) == 2
    assert "mailto:sales@supreme-oe.com" not in html
    assert '<dialog class="inquiry-dialog" data-inquiry-dialog' in html
    assert "该功能开发中，敬请期待" in html
    assert "data-close-inquiry" in html
    assert "inquiryDialog.showModal" in script
    assert "event.target === inquiryDialog" in script
    assert "inquiryDialog.addEventListener('cancel'" in script
    assert "inquiryTrigger?.focus()" in script

    assert html.count('<div class="source-heading">参考资料</div>') == 2
    assert "数据依据" not in html
    assert "查看企业产品页 ↗" in html
    assert "完整产品页 ↗" not in html
    assert "source.url !== selectedItem.officialUrl" in script
    assert html.index('class="dialog-sources"') < html.index('class="dialog-actions"')


def test_controlled_homepage_has_exact_local_resource_closure_and_three_products():
    html = (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    parser = _ResourceParser()
    parser.feed(html)
    missing = []
    for value in parser.resources:
        path = _local_path(HOMEPAGE, value)
        if path is not None and not path.is_file():
            missing.append(value)
    assert missing == []

    module_files = [HOMEPAGE / "hero-flowmap.js", HOMEPAGE / "product-items.mjs"]
    seen = set()
    while module_files:
        module = module_files.pop()
        if module in seen:
            continue
        seen.add(module)
        source = module.read_text(encoding="utf-8")
        for relative in re.findall(r"(?:from\s+|import\s*)['\"](\.[^'\"]+)['\"]", source):
            dependency = (module.parent / relative).resolve()
            assert dependency.is_file(), f"missing ESM dependency: {relative} from {module}"
            if dependency.suffix in {".js", ".mjs"}:
                module_files.append(dependency)

    products = (HOMEPAGE / "product-items.mjs").read_text(encoding="utf-8")
    assert re.findall(r"\bid:\s*'([^']+)'", products) == [
        "cvd-znse",
        "germanium",
        "dyf3",
    ]
    expected_images = {
        "assets/official-logo.png",
        "assets/official-cvd-znse.png",
        "assets/official-high-tech-certificate.jpeg",
        "assets/official-category-2020258820.jpg",
        "assets/official-dyf3.png",
        "assets/official-germanium.png",
        "assets/rd-manufacturing-cgi.webp",
    }
    actual_images = {
        path.relative_to(HOMEPAGE).as_posix()
        for path in (HOMEPAGE / "assets").rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    }
    assert expected_images <= actual_images


def test_git_lfs_rule_is_exactly_scoped_to_twinkle_runtime_pngs():
    attributes = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    expected = "showcase/homepage/assets/twinkle/**/*.png filter=lfs diff=lfs merge=lfs -text"
    assert attributes.count(expected) == 1
    assert not any(line.startswith("*.png ") for line in attributes)


def test_design_spec_records_approved_stage_five_contract_and_stage_six_boundary():
    spec = (
        REPO
        / "docs/superpowers/specs/2026-08-20-twinkle-page-coordinated-render-design.md"
    ).read_text(encoding="utf-8")

    assert "### 8.7 阶段 5：首页受控基线、单状态机与 H0–H3 门禁" in spec
    assert "showcase/homepage/assets/twinkle/**/*.png" in spec
    assert "248 张 PNG" in spec
    assert "130,156,891 bytes" in spec
    assert "单一状态机" in spec
    for gate in ("H0", "H1", "H2", "H3"):
        assert f"**{gate}**" in spec
    assert "阶段四的 `authorizesStage5=false` 保持历史事实不变" in spec
    assert "阶段 6" in spec
    assert "不授权提交、push、PR、部署或线上覆盖" in spec


def _split_quality(html: str, marker: str) -> tuple[str, str]:
    start = html.index(marker)
    end = html.index("</section>", start) + len("</section>")
    return html[:start], html[end:]


def test_non_quality_dom_text_and_order_match_read_only_homepage_authority():
    authority_value = os.environ.get("TWINKLE_HOMEPAGE_AUTHORITY")
    if not authority_value:
        pytest.skip("set TWINKLE_HOMEPAGE_AUTHORITY for source-to-target integration")
    authority = Path(authority_value).resolve(strict=True)
    source = (authority / "index.html").read_text(encoding="utf-8")
    target = (HOMEPAGE / "index.html").read_text(encoding="utf-8")
    rendered = homepage_builder._render_html(source)
    rendered_before, rendered_after = _split_quality(
        rendered, '    <section class="twinkle-stage5-entry scene"'
    )
    target_before, target_after = _split_quality(
        target, '    <section class="twinkle-stage5-entry scene"'
    )
    assert target_before == rendered_before
    assert target_after == rendered_after
