from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import uuid
from pathlib import Path

from scripts.package_twinkle_stage5 import PackagingError, _is_reparse, _sha256


AUTHORITY_HASHES = {
    "index.html": "AD8F309FF130AC94F3DA4F16CB85D37238367AE669A3E712BEA085DEA5982A4E",
    "hero-flowmap.js": "BFF222DEED6510B9E0B928927EA583E153A76C6BB67D23E8BDF4AA1408021EBA",
    "preview-runtime.mjs": "C5DA34FD3088F6018E83AE00EF6A9DE3B487EE1300EE8F10FBF0F253C47E485B",
    "assets/rd-manufacturing-cgi.webp": "1178096608271F81513B7EF49F7B3F1A89BB07715D3AE3701E93AAB9D6F2FB8B",
}
BASELINE_HASHES = {
    "assets/vendor/ogl.mjs": "675E001DD80D91511ECD7AAC57D6E8D15D93FEBE2E31304A3ABA7E2FC58413F1",
    "assets/official-logo.png": "68BD2C6276D6F3A4287F651D5552F343A43923484799997595AE2045CEC89729",
    "assets/official-cvd-znse.png": "7002BCD28CEAB55323B772653E93CB36B13345453A02E1C941E9AEA0EA620328",
    "assets/official-high-tech-certificate.jpeg": "44B6F077B65B9D2489E8720DD172598DA39F1E6DF5D9A5DCE59C1A5569F68416",
    "assets/official-category-2020258820.jpg": "6F558D35471DF8EB554D8F387DD71313DB59BF90B1A6D618DFC8093812853BBB",
    "assets/official-dyf3.png": "D111E10D08E5EC055EC825DF5E9FDB1EE92B4F42CB21CBE692D5FDC14D855864",
    "assets/official-germanium.png": "EDD287018055B688C89A19C7B194764B7FBEAD8338CF36B351224C379B8DE06B",
    "product-items.mjs": "39B26CF6EABC7853C06390859EA3E47F475C5DC0B58A90CC683B0A8CD1CA32DE",
}
OGL_TREE_SHA256 = "18C3AF28539ED1B95D24C709C25F7A145D69B4303700CFCFA3BB91D42F5608B3"
CATALOG_AUTHORITY_NAME = "2026-08-08-paper-dithering-catalog"
CATALOG_TARGET_RELATIVE = Path("catalog")
CATALOG_TREE_SHA256 = "FD814AAFC78FFE24451C922B01B70202AA135577C1195E5B3E6AFD9E676F368A"
AUTHORITY_CATALOG_HREF = "../2026-08-08-paper-dithering-catalog/circular-gallery-preview.html"
CONTROLLED_CATALOG_HREF = "./catalog/circular-gallery-preview.html"
NAVIGATION_CSS = '.topbar{position:fixed;z-index:50;left:26px;right:26px;top:18px;height:62px;display:flex;align-items:center;padding:0 22px;border:1px solid rgba(255,255,255,.85);border-radius:22px;background:rgba(251,252,249,.76);backdrop-filter:blur(18px);box-shadow:0 12px 42px rgba(41,61,63,.07)}.brand{display:flex;align-items:center;gap:12px;min-height:44px;font-size:14px;font-weight:700;letter-spacing:.11em;color:var(--ink);text-decoration:none;transition:transform 110ms ease}.brand img{width:31px;height:31px;object-fit:contain}.topnav{margin-left:auto;display:flex;gap:6px;font-size:13px;color:#405158}.topnav a{display:flex;align-items:center;min-height:44px;padding:0 10px;border-radius:999px;color:inherit;text-decoration:none;transition:background 110ms ease,color 110ms ease,transform 110ms ease}.topnav a:hover{background:rgba(79,199,210,.12)}.topnav a[aria-current]{background:#173e44;color:#fff}.topnav a:focus-visible,.brand:focus-visible,.cta:focus-visible{outline:2px solid rgba(36,142,153,.58);outline-offset:2px}.topnav a:active{background:#173e44;color:#fff;transform:translateY(1px) scale(.96)}.brand:active{transform:scale(.98)}.cta{margin-left:20px;min-height:44px;padding:11px 17px;border:1px solid rgba(35,83,89,.15);border-radius:999px;display:flex;align-items:center;background:transparent;color:#405158;font:inherit;font-size:12px;cursor:pointer;transition:background 110ms ease,color 110ms ease,transform 110ms ease}.cta:hover{background:rgba(79,199,210,.12);color:#173e44}.cta:active{background:#173e44;color:#fff;transform:translateY(1px) scale(.96)}'
NAVIGATION_REDUCED_MOTION_CSS = '.brand,.topnav a,.cta{transition:none}.brand:active,.topnav a:active,.cta:active{transform:none}'
CATALOG_RETURN_CSS = '.catalog-return{position:fixed;z-index:49;left:24px;top:98px;display:grid;width:44px;height:44px;padding:0;place-items:center;border:1px solid rgba(220,245,250,.18);border-radius:50%;color:rgba(238,250,252,.82);background:rgba(4,18,25,.34);backdrop-filter:blur(8px);cursor:pointer;transform:translateY(0) scale(1);transition:transform 140ms ease,background-color 140ms ease,color 140ms ease,border-color 140ms ease}.catalog-return svg{display:block;width:18px;height:18px}.catalog-return:hover{color:rgba(238,250,252,.96);background:rgba(4,18,25,.52);transform:translateY(1px) scale(.985)}.catalog-return:active{transform:translateY(1px) scale(.96);transition-duration:90ms}.catalog-return:focus-visible{outline:2px solid rgba(220,245,250,.92);outline-offset:3px}@media(max-width:900px){.catalog-return{top:90px}}'
CATALOG_RETURN_REDUCED_MOTION_CSS = '.catalog-return,.catalog-return:hover,.catalog-return:active{transform:none;transition:background-color 140ms ease,color 140ms ease,border-color 140ms ease}'
HOMEPAGE_INQUIRY_CSS = '.inquiry-dialog{position:fixed;inset:auto;left:50%;top:50%;margin:0;transform:translate(-50%,-50%);width:min(390px,calc(100vw - 32px));height:auto;max-height:calc(100vh - 32px);border:1px solid rgba(35,83,89,.15);border-radius:22px;padding:0;overflow:hidden;background:#f9fbf9;color:var(--ink);box-shadow:0 24px 55px rgba(30,57,63,.16)}.inquiry-dialog::backdrop{background:rgba(16,35,40,.22);backdrop-filter:blur(3px)}.inquiry-dialog .dialog-close{position:absolute;right:16px;top:16px;width:40px;height:40px;border:1px solid rgba(35,83,89,.15);border-radius:50%;background:#fff;color:#44636a;font-size:20px;cursor:pointer}.inquiry-body{padding:54px 28px 28px}.inquiry-body .dialog-kicker{font-size:11px;letter-spacing:.15em;color:#2c8992}.inquiry-body h2{margin:10px 0 0;font-size:28px;letter-spacing:-.035em}.inquiry-body p{margin:18px 0 24px;color:#536d73;font-size:14px;line-height:1.7}.inquiry-dismiss{width:100%;min-height:44px;padding:12px 16px;border:1px solid rgba(35,83,89,.15);border-radius:999px;background:#fff;color:#295b63;font:inherit;font-size:13px;cursor:pointer}'
PRODUCT_IDS = ("cvd-znse", "germanium", "dyf3")
HOVER_PILOT_RELATIVE = Path("output/twinkle-stage5-rgba-hover-pilot")
HOVER_PREVIEW_RELATIVE = Path("assets/twinkle-entry/c360-hover")
HOVER_FRAME_HASHES = (
    "E2C15CEE3E30BE84D79BCA375653118B6DF159C9DBF1C4855F9AFBC62853FAAC",
    "BB356F37AEE265FF342A58AC24CCD2B1C4B7D429C9CAE8C302C3E13622CB8AF5",
    "86D8102A4BADEB3032BAD6DC7C1F929D501C30C090E4662F86EF20A57212D0AD",
    "67B2B83D2BCEDDF36344A788257516A79F81C7DC850F808ABFEE33B82D83FE07",
    "964DD67878D534D09E8A9017C7F96EA2C60D87E493E4D85DCFFBF6339A82C78D",
)
HOVER_FRAME_BYTES = (135716, 133429, 131755, 129640, 128445)
HOVER_SEQUENCE = (0, 1, 2, 3, 4, 3, 2, 1, 0)
HOVER_FRAME_INTERVAL_MS = 80
HERO_ORBIT_DOT_CSS = '.lens-orbit:after{content:"";position:absolute;width:13px;height:13px;border-radius:50%;right:13%;top:15%;background:#6d65db;box-shadow:0 0 0 9px rgba(109,101,219,.1)}'
APPROVED_REGISTRY_SHA256 = (
    "8D32267C20218FA575E34E78415D69EEFA58F76C4CF71CBB7903952E7EFB03C4"
)


TWINKLE_SECTION = """    <section class="twinkle-stage5-entry scene" data-layout="dossier" id="quality" data-twinkle-stage5-entry>
      <div class="twinkle-stage5-entry-copy">
        <p class="twinkle-stage5-entry-eyebrow">技术能力展示样机</p>
        <h2>TWINKLE 开放光学系统</h2>
        <p class="twinkle-stage5-entry-value">从整体设计到细节呈现，近距离了解 TWINKLE 对品质与体验的坚持。</p>
      </div>
      <a class="twinkle-stage5-entry-card" href="#quality" aria-label="打开 TWINKLE 结构视窗">
        <span class="twinkle-stage5-entry-visual"><img src="./assets/twinkle-entry/c360-hover/frame-000.png" alt="TWINKLE 开放光学系统 360°结构探索入口"></span>
        <span class="twinkle-stage5-entry-meta"><span><small>360° 结构探索</small><b>匠心设计 · 品质呈现</b></span><em>点击打开视窗 →</em></span>
      </a>
    </section>"""


TWINKLE_VIEWPORT_HOST = """  <div class="twinkle-stage5-viewport-backdrop" data-open="false" aria-hidden="true"></div>
  <div class="twinkle-stage5-viewport" data-open="false" role="dialog" aria-modal="true" aria-hidden="true" aria-label="TWINKLE 结构视窗"><iframe class="twinkle-stage5-viewport-frame" title="TWINKLE 结构视窗" data-src="../../output/twinkle-stage5-h2-full-flow-review/index.html"></iframe></div>
  <div class="twinkle-stage5-viewport-blackout" aria-hidden="true" hidden></div>"""


HOMEPAGE_INQUIRY_HOST = """  <dialog class="inquiry-dialog" data-inquiry-dialog aria-labelledby="inquiry-title">
    <button class="dialog-close" type="button" data-close-inquiry aria-label="关闭技术询盘提示">×</button>
    <div class="inquiry-body"><div class="dialog-kicker">TECHNICAL INQUIRY</div><h2 id="inquiry-title">技术询盘</h2><p>该功能开发中，敬请期待</p><button class="inquiry-dismiss" type="button" data-close-inquiry>关闭</button></div>
  </dialog>
  <script>
    (() => {
      const inquiryDialog = document.querySelector('[data-inquiry-dialog]');
      const inquiryButton = document.querySelector('[data-open-inquiry]');
      let inquiryTrigger = null;
      const closeInquiry = () => {
        inquiryDialog.close?.();
        inquiryDialog.removeAttribute('open');
        inquiryTrigger?.focus();
        inquiryTrigger = null;
      };
      inquiryButton.addEventListener('click', event => {
        inquiryTrigger = event.currentTarget;
        inquiryDialog.showModal?.();
        if (!inquiryDialog.open) inquiryDialog.setAttribute('open', '');
      });
      inquiryDialog.querySelectorAll('[data-close-inquiry]').forEach(button => button.addEventListener('click', closeInquiry));
      inquiryDialog.addEventListener('click', event => { if (event.target === inquiryDialog) closeInquiry(); });
      inquiryDialog.addEventListener('cancel', event => { event.preventDefault(); closeInquiry(); });
    })();
  </script>"""


HOMEPAGE_NAVIGATION_SCRIPT = """  <script>
    (() => {
      const navigation = document.querySelector('.topnav');
      const sectionIds = ['home', 'materials', 'applications', 'quality', 'products', 'company'];
      const targets = sectionIds.map(id => ({
        id,
        link: navigation?.querySelector(`a[href="#${id}"]`),
        section: document.getElementById(id),
      })).filter(({ link, section }) => link && section);
      if (!navigation || targets.length !== sectionIds.length) return;

      const visible = new Set();
      const setCurrent = id => targets.forEach(({ id: targetId, link }) => {
        if (targetId === id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
      const updateCurrent = () => {
        const active = [...targets].reverse().find(({ id }) => visible.has(id));
        if (active) setCurrent(active.id);
      };
      const syncHash = () => {
        const id = decodeURIComponent(location.hash.slice(1));
        if (sectionIds.includes(id)) setCurrent(id);
      };

      navigation.addEventListener('click', event => {
        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        const id = link.getAttribute('href').slice(1);
        if (sectionIds.includes(id)) setCurrent(id);
      });
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        });
        updateCurrent();
      }, { rootMargin: '-92px 0px -85% 0px', threshold: 0 });
      targets.forEach(({ section }) => observer.observe(section));
      addEventListener('hashchange', syncHash);
      addEventListener('pageshow', () => {
        if (location.hash) syncHash();
        else updateCurrent();
      });
      syncHash();
    })();
  </script>"""


CATALOG_RETURN_HOST = """  <!-- Lucide ArrowLeft, https://github.com/lucide-icons/lucide/blob/main/icons/arrow-left.svg
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
  <a class="catalog-return" href="../index.html#products" aria-label="返回产品中心"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-arrow-left" aria-hidden="true"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg></a>"""


ENTRY_CSS = """#quality[data-twinkle-stage5-entry]{position:relative;display:grid;min-height:100vh;padding:clamp(118px,14vh,160px) 7vw clamp(80px,10vh,120px);grid-template-areas:none;grid-template-columns:minmax(300px,.76fr) minmax(520px,1.24fr);grid-template-rows:auto;align-items:center;gap:clamp(40px,6vw,84px);background:#f6f8f5}
.twinkle-stage5-entry-copy{max-width:500px}.twinkle-stage5-entry-eyebrow{margin:0 0 18px;font-size:12px;font-weight:700;letter-spacing:.16em;color:#2d7880}.twinkle-stage5-entry h2{margin:0;font-size:clamp(46px,4.8vw,68px);font-weight:500;line-height:1.02;letter-spacing:-.05em}.twinkle-stage5-entry-value{margin:24px 0 0;max-width:480px;color:#52686e;font-size:16px;line-height:1.8}
.twinkle-stage5-entry-card{display:grid;width:100%;min-width:44px;min-height:44px;aspect-ratio:1280/900;grid-template-rows:minmax(0,1fr) auto;border:1px solid rgba(54,93,99,.18);border-radius:28px;background:rgba(255,255,255,.72);overflow:hidden;box-shadow:0 28px 64px rgba(29,74,81,.12);opacity:0;transform:translateY(28px);transition:opacity 700ms ease,transform 700ms ease,box-shadow 220ms ease}.twinkle-stage5-entry-card.is-visible{opacity:1;transform:translateY(0)}.twinkle-stage5-entry-card:hover,.twinkle-stage5-entry-card:focus-visible{transform:translateY(0) scale(1.01);box-shadow:0 36px 78px rgba(29,74,81,.2)}
.twinkle-stage5-entry-visual{min-height:0;padding:22px 28px 0;display:grid;place-items:center;background:radial-gradient(circle at 50% 45%,rgba(84,187,196,.13),transparent 62%)}.twinkle-stage5-entry-visual img{display:block;width:100%;height:100%;min-height:0;max-height:430px;object-fit:contain;transform:translateY(11.2%);filter:drop-shadow(0 26px 34px rgba(20,48,53,.16))}.twinkle-stage5-entry-meta{min-height:92px;padding:18px 22px;display:flex;align-items:center;justify-content:space-between;gap:22px;border-top:1px solid rgba(54,93,99,.16)}.twinkle-stage5-entry-meta span{display:grid;gap:6px}.twinkle-stage5-entry-meta small{font-size:10px;letter-spacing:.16em;color:#347881}.twinkle-stage5-entry-meta b{font-size:17px;letter-spacing:-.02em}.twinkle-stage5-entry-meta em{font-style:normal;font-size:13px;color:#2d7880;white-space:nowrap;transition:transform 220ms ease}.twinkle-stage5-entry-card:hover .twinkle-stage5-entry-meta em,.twinkle-stage5-entry-card:focus-visible .twinkle-stage5-entry-meta em{transform:translateX(4px)}
.twinkle-stage5-viewport-backdrop{position:fixed;z-index:80;inset:0;visibility:hidden;background:rgba(18,49,55,.42);opacity:0;pointer-events:none;transition:opacity 180ms ease,visibility 0s linear 180ms}.twinkle-stage5-viewport{position:fixed;inset:0;z-index:81;visibility:hidden;overflow:hidden;background:#000;opacity:0;pointer-events:none;transition:opacity 180ms ease,visibility 0s linear 180ms}.twinkle-stage5-viewport-backdrop[data-open="true"],.twinkle-stage5-viewport[data-open="true"]{visibility:visible;opacity:1;pointer-events:auto;transition-delay:0s}.twinkle-stage5-viewport-frame{display:block;width:100%;height:100%;border:0;background:#000}.twinkle-stage5-viewport-blackout{position:fixed;inset:0;z-index:82;background:#000;opacity:0;pointer-events:none}.twinkle-stage5-viewport-blackout[hidden]{display:none}
@media(max-width:900px){.twinkle-stage5-entry h2{font-size:clamp(42px,12vw,58px)}.twinkle-stage5-entry-meta{align-items:flex-start;flex-direction:column;gap:12px}.twinkle-stage5-entry-visual{padding:16px 12px 0}}
@media(max-width:860px){#quality[data-twinkle-stage5-entry]{min-height:auto;padding:110px 6vw 72px;grid-template-areas:none;grid-template-columns:1fr;grid-template-rows:auto auto;gap:36px}}
@media(prefers-reduced-motion: reduce){.twinkle-stage5-entry-card,.twinkle-stage5-entry-card.is-visible,.twinkle-stage5-entry-card:hover,.twinkle-stage5-entry-card:focus-visible{opacity:1;transform:none;transition: none;box-shadow:0 28px 64px rgba(29,74,81,.12)}.twinkle-stage5-entry-meta em,.twinkle-stage5-entry-card:hover .twinkle-stage5-entry-meta em,.twinkle-stage5-entry-card:focus-visible .twinkle-stage5-entry-meta em{transform:none;transition: none}}
"""


ENTRY_JS = """const entry = document.querySelector('[data-twinkle-stage5-entry] .twinkle-stage5-entry-card');
const model = entry?.querySelector('.twinkle-stage5-entry-visual img');
const backdrop = document.querySelector('.twinkle-stage5-viewport-backdrop');
const viewport = document.querySelector('.twinkle-stage5-viewport');
const viewer = viewport?.querySelector('.twinkle-stage5-viewport-frame');
const blackout = document.querySelector('.twinkle-stage5-viewport-blackout');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const fineHover = window.matchMedia('(hover: hover) and (pointer: fine)');
const sequence = [0, 1, 2, 3, 4, 3, 2, 1, 0];
const frameIntervalMs = 80;
const frameUrl = (index) => {
  const label = String(index).padStart(3, '0');
  return `./assets/twinkle-entry/c360-hover/frame-${label}.png`;
};

if (entry && model) {
  let enteredViewport = false;
  let preloadStarted = false;
  let ready = false;
  let failed = false;
  let activationPending = false;
  let playedThisActivation = false;
  let playing = false;
  let timer = 0;
  let previousFocus = null;
  let savedScrollY = 0;
  let previousOverflow = '';
  let closing = false;
  let inertRecords = [];
  const preloadedFrames = new Map();

  const nextPaint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

  function setBackgroundInert() {
    const bodyTargets = [...document.body.children].filter(element => (
      element.tagName !== 'SCRIPT' && ![backdrop, viewport, blackout].includes(element)
    ));
    inertRecords = bodyTargets.map(target => ({
      target,
      inert: target.inert,
      ariaHidden: target.getAttribute('aria-hidden'),
    }));
    inertRecords.forEach(({ target }) => {
      target.inert = true;
      target.setAttribute('aria-hidden', 'true');
    });
  }

  function restoreBackgroundInert() {
    inertRecords.forEach(({ target, inert, ariaHidden }) => {
      target.inert = inert;
      if (ariaHidden === null) target.removeAttribute('aria-hidden');
      else target.setAttribute('aria-hidden', ariaHidden);
    });
    inertRecords = [];
  }

  async function setHomepageBlackCover(covered) {
    blackout.hidden = false;
    const from = Number(getComputedStyle(blackout).opacity);
    const to = covered ? 1 : 0;
    if (Math.abs(from - to) > .001) {
      const animation = blackout.animate([{ opacity: from }, { opacity: to }], {
        duration: reducedMotion.matches ? 0 : 320,
        easing: 'ease',
        fill: 'forwards',
      });
      await animation.finished;
    }
    blackout.style.opacity = String(to);
    if (!covered) blackout.hidden = true;
  }

  async function openViewport(event) {
    event.preventDefault();
    if (!viewport || closing || viewport.dataset.open === 'true') return;
    previousFocus = document.activeElement;
    savedScrollY = window.scrollY;
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    setBackgroundInert();
    if (!viewer.src) viewer.src = viewer.dataset.src;
    backdrop.hidden = false;
    viewport.hidden = false;
    backdrop.dataset.open = 'true';
    viewport.dataset.open = 'true';
    viewport.setAttribute('aria-hidden', 'false');
    await nextPaint();
    viewer.focus();
  }

  async function closeViewport() {
    if (!viewport || closing || viewport.dataset.open !== 'true') return false;
    closing = true;
    await setHomepageBlackCover(true);
    viewport.hidden = true;
    backdrop.hidden = true;
    viewport.dataset.open = 'false';
    backdrop.dataset.open = 'false';
    viewport.setAttribute('aria-hidden', 'true');
    restoreBackgroundInert();
    document.body.style.overflow = previousOverflow;
    window.scrollTo(0, savedScrollY);
    previousFocus?.focus();
    await nextPaint();
    await setHomepageBlackCover(false);
    closing = false;
    return true;
  }

  const observer = new IntersectionObserver((entries) => {
    if (!entries.some(item => item.isIntersecting)) return;
    enteredViewport = true;
    entry.classList.add('is-visible');
    observer.unobserve(entry);
    beginPreload();
  }, { threshold: 0.2 });

  function eligible() {
    return fineHover.matches && !reducedMotion.matches;
  }

  function decodeImage(image) {
    if (typeof image.decode !== 'function') return Promise.resolve(image);
    return image.decode().then(() => image);
  }

  function waitForInitialFrame() {
    if (model.complete && model.naturalWidth > 0) return decodeImage(model);
    if (model.complete) return Promise.reject(new Error('initial hover preview failed'));
    return new Promise((resolve, reject) => {
      model.addEventListener('load', () => decodeImage(model).then(resolve, reject), { once: true });
      model.addEventListener('error', reject, { once: true });
    });
  }

  function loadFrame(index) {
    const image = new Image();
    image.decoding = 'async';
    return new Promise((resolve, reject) => {
      image.addEventListener('load', () => decodeImage(image).then((decoded) => resolve([index, decoded]), reject), { once: true });
      image.addEventListener('error', reject, { once: true });
      image.src = frameUrl(index);
    });
  }

  function beginPreload() {
    if (preloadStarted || !enteredViewport || !eligible()) return;
    preloadStarted = true;
    Promise.all([waitForInitialFrame().then((image) => [0, image]), ...[1, 2, 3, 4].map(loadFrame)])
      .then((frames) => {
        frames.forEach(([index, image]) => {
          if (index > 0) preloadedFrames.set(index, image);
        });
        ready = true;
        playOnce();
      })
      .catch(failStatic);
  }

  function show(index) {
    model.src = index === 0 ? frameUrl(0) : (preloadedFrames.get(index)?.src || frameUrl(index));
  }

  function failStatic() {
    clearTimeout(timer);
    timer = 0;
    playing = false;
    ready = false;
    failed = true;
    activationPending = false;
    playedThisActivation = true;
    if (!model.currentSrc.endsWith('/frame-000.png')) show(0);
  }

  function reset() {
    clearTimeout(timer);
    timer = 0;
    playing = false;
    show(0);
  }

  function playOnce() {
    if (!ready || failed || !activationPending || !eligible() || playing || playedThisActivation) return;
    playing = true;
    playedThisActivation = true;
    let position = 0;
    const tick = () => {
      if (!playing) return;
      if (position >= sequence.length) {
        reset();
        return;
      }
      show(sequence[position]);
      position += 1;
      timer = setTimeout(tick, frameIntervalMs);
    };
    tick();
  }

  function requestPlayback() {
    activationPending = true;
    beginPreload();
    playOnce();
  }

  function deactivate() {
    activationPending = false;
    playedThisActivation = false;
    reset();
  }

  function handleMotionPolicyChange() {
    if (!eligible()) {
      activationPending = false;
      reset();
      return;
    }
    beginPreload();
    playOnce();
  }

  entry.addEventListener('mouseenter', requestPlayback);
  entry.addEventListener('mouseleave', deactivate);
  entry.addEventListener('focusin', requestPlayback);
  entry.addEventListener('focusout', deactivate);
  entry.addEventListener('click', (event) => {
    activationPending = false;
    playedThisActivation = true;
    reset();
    void openViewport(event);
  });
  viewer.addEventListener('twinkle-model-viewport-close-request', () => void closeViewport());
  backdrop.addEventListener('click', () => void closeViewport());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && viewport?.dataset.open === 'true' && document.activeElement !== viewer) void closeViewport();
  });
  model.addEventListener('error', failStatic);
  reducedMotion.addEventListener('change', handleMotionPolicyChange);
  fineHover.addEventListener('change', handleMotionPolicyChange);
  if (reducedMotion.matches) entry.classList.add('is-visible');
  observer.observe(entry);
}
"""


def _read_hover_json(path: Path, schema: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackagingError(f"hover preview report drift: {path.name}") from error
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise PackagingError(f"hover preview report drift: {path.name}")
    return value


def _validate_rgba_png(path: Path) -> None:
    try:
        header = path.read_bytes()[:33]
    except OSError as error:
        raise PackagingError(f"hover preview frame drift: {path.name}") from error
    if (
        len(header) != 33
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise PackagingError(f"hover preview frame drift: {path.name}")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
    if (width, height, bit_depth, color_type) != (640, 450, 8, 6):
        raise PackagingError(f"hover preview frame drift: {path.name}")


def validate_hover_preview_source(pilot_root: Path) -> tuple[Path, ...]:
    pilot = Path(pilot_root).resolve(strict=True)
    report = _read_hover_json(pilot / "pilot-report.json", "twinkle-stage5-rgba-hover-pilot-v1")
    worker = _read_hover_json(pilot / "worker-audit.json", "twinkle-stage5-rgba-hover-worker-v1")
    browser = _read_hover_json(
        pilot / "browser-results.json", "twinkle-stage5-rgba-hover-browser-results-v1"
    )
    continuity = report.get("continuity")
    worker_records = worker.get("frames")
    browser_sections = [
        browser.get(section)
        for section in (
            "desktop",
            "delayedReadiness",
            "reducedMotion",
            "noFineHoverMobile",
            "visualReview",
        )
    ]
    if (
        not isinstance(continuity, dict)
        or not isinstance(worker_records, list)
        or not all(isinstance(item, dict) for item in worker_records)
        or not all(isinstance(section, dict) for section in browser_sections)
    ):
        raise PackagingError("hover preview report drift")
    report_ok = (
        report.get("frameCount") == 5
        and report.get("frameIndices") == [0, 1, 2, 3, 4]
        and report.get("playbackSequence") == list(HOVER_SEQUENCE)
        and report.get("frameIntervalMs") == HOVER_FRAME_INTERVAL_MS
        and report.get("workerAuditValidated") is True
        and report.get("formalAssetsUnchanged") is True
        and report.get("formalRegistrySha256") == APPROVED_REGISTRY_SHA256
        and continuity.get("machinePassed") is True
    )
    worker_ok = (
        worker.get("frameIndices") == [0, 1, 2, 3, 4]
        and worker.get("renderedFrameCount") == 5
        and worker.get("oneBlenderInvocation") is True
        and worker.get("filmTransparent") is True
        and worker.get("studioFloorHidden") is True
        and worker.get("contactShadowIncluded") is False
        and worker.get("candidateBlendSaved") is False
    )
    browser_ok = all(section.get("machinePassed") is True for section in browser_sections)
    if not report_ok or not worker_ok or not browser_ok:
        raise PackagingError("hover preview report drift")

    frames_root = pilot / "frames"
    expected_names = {f"frame-{index:03d}.png" for index in range(5)}
    actual_names = {path.name for path in frames_root.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise PackagingError("hover preview frame inventory drift")
    frames = []
    worker_frames = {item.get("frameIndex"): item for item in worker_records}
    for index, (expected_hash, expected_bytes) in enumerate(
        zip(HOVER_FRAME_HASHES, HOVER_FRAME_BYTES, strict=True)
    ):
        path = frames_root / f"frame-{index:03d}.png"
        report_frame = report.get("frames", {}).get(f"frame-{index:03d}", {})
        worker_frame = worker_frames.get(index, {})
        if (
            path.stat().st_size != expected_bytes
            or _sha256(path) != expected_hash
            or report_frame.get("sha256") != expected_hash
            or report_frame.get("bytes") != expected_bytes
            or worker_frame.get("sha256") != expected_hash
        ):
            raise PackagingError(f"hover preview frame drift: {path.name}")
        _validate_rgba_png(path)
        frames.append(path)
    return tuple(frames)


def _validate_file(root: Path, relative: str, expected_hash: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            raise PackagingError(f"homepage dependency is missing: {relative}")
        if _is_reparse(current):
            raise PackagingError(f"homepage dependency is a reparse point: {relative}")
    if not current.is_file() or _sha256(current) != expected_hash:
        raise PackagingError(f"homepage dependency drift: {relative}")
    return current


def _tree_digest(root: Path) -> str:
    lines = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if _is_reparse(path):
            raise PackagingError(f"OGL dependency is a reparse point: {path}")
        if path.is_file():
            lines.append(f"{path.relative_to(root).as_posix()}:{_sha256(path)}")
        elif not path.is_dir():
            raise PackagingError(f"OGL dependency is not a regular file: {path}")
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest().upper()


def _extract_product_objects(source: str) -> str:
    marker = "export const PRODUCT_ITEMS = ["
    start = source.find(marker)
    if start < 0:
        raise PackagingError("product data module marker is missing")
    index = start + len(marker)
    objects = []
    depth = 0
    object_start = None
    quote = None
    escaped = False
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            if depth == 0:
                object_start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise PackagingError("product data braces are unbalanced")
            if depth == 0 and object_start is not None:
                objects.append(source[object_start : index + 1])
                object_start = None
        elif char == "]" and depth == 0:
            break
        index += 1
    by_id = {}
    for value in objects:
        match = re.search(r"\bid:\s*'([^']+)'", value)
        if match:
            by_id[match.group(1)] = value
    if any(product_id not in by_id for product_id in PRODUCT_IDS):
        raise PackagingError("required homepage product data is missing")
    return "export const PRODUCT_ITEMS = [\n" + ",\n".join(
        by_id[product_id] for product_id in PRODUCT_IDS
    ) + ",\n];\n"


def _render_html(source: str) -> str:
    if source.count(HERO_ORBIT_DOT_CSS) != 1:
        raise PackagingError("hero orbit dot marker drift")
    source = source.replace(HERO_ORBIT_DOT_CSS, "")
    stylesheet = '<link rel="stylesheet" href="./twinkle-m4.css">'
    if source.count(stylesheet) != 1:
        raise PackagingError("old TWINKLE stylesheet marker drift")
    source = source.replace(
        stylesheet, '<link rel="stylesheet" href="./twinkle-entry.css">'
    )
    start = source.find('    <section class="twinkle-m4-overview scene"')
    end = source.find("</section>", start)
    if start < 0 or end < 0:
        raise PackagingError("old TWINKLE section marker drift")
    source = source[:start] + TWINKLE_SECTION + source[end + len("</section>") :]
    old_dialog = '<dialog class="twinkle-development-dialog"'
    dialog_start = source.find(old_dialog)
    if dialog_start < 0:
        raise PackagingError("old TWINKLE dialog marker drift")
    dialog_end = source.find("</dialog>", dialog_start)
    old_script = '<script type="module" src="./twinkle-m4.js"></script>'
    script_start = source.find(old_script, dialog_end)
    if dialog_end < 0 or script_start < 0:
        raise PackagingError("old TWINKLE runtime marker drift")
    source = source[:dialog_start] + source[script_start + len(old_script) :]
    source = source.replace(
        "../../showcase-baselines/2026-08-05-before-authority-redesign/assets/",
        "./assets/",
    )
    source = source.replace(
        "../../showcase-baselines/2026-08-05-before-authority-redesign/product-items.mjs",
        "./product-items.mjs",
    )
    if source.count(AUTHORITY_CATALOG_HREF) != 4:
        raise PackagingError("product catalog route markers drift")
    source = source.replace(AUTHORITY_CATALOG_HREF, CONTROLLED_CATALOG_HREF)
    homepage_replacements = {
        '.topbar{position:fixed;z-index:50;left:26px;right:26px;top:18px;height:62px;display:flex;align-items:center;padding:0 22px;border:1px solid rgba(255,255,255,.85);border-radius:22px;background:rgba(251,252,249,.76);backdrop-filter:blur(18px);box-shadow:0 12px 42px rgba(41,61,63,.07)}.brand{display:flex;align-items:center;gap:12px;font-size:14px;font-weight:700;letter-spacing:.11em}.brand img{width:31px;height:31px;object-fit:contain}.topnav{margin-left:auto;display:flex;gap:26px;font-size:13px;color:#405158}.topnav a{padding:8px 0}.cta{margin-left:26px;padding:11px 17px;border-radius:999px;background:#173e44;color:#fff;font-size:12px}': (
            NAVIGATION_CSS,
            1,
        ),
        '<nav class="topnav"><a href="#materials">材料光路</a><a href="./catalog/circular-gallery-preview.html">产品中心</a><a href="#applications">应用</a><a href="#quality">参数</a><a href="#company">公司</a></nav>': (
            '<nav class="topnav"><a href="#home" aria-current="location">首页</a><a href="#materials">能力概览</a><a href="#applications">应用方向</a><a href="#quality">TWINKLE</a><a href="#products">产品中心</a><a href="#company">业务范围</a></nav>',
            1,
        ),
        '<a class="cta" href="#contact" data-inquiry-notice>技术询盘</a>': (
            '<button class="cta" type="button" data-open-inquiry>技术询盘</button>',
            1,
        ),
        '@media(prefers-reduced-motion:reduce){html{': (
            f'@media(prefers-reduced-motion:reduce){{{NAVIGATION_REDUCED_MOTION_CSS}html{{',
            1,
        ),
        '  </style>': (
            f'    {HOMEPAGE_INQUIRY_CSS}\n    @media(max-width:620px){{.brand span{{display:none}}}}\n  </style>',
            1,
        ),
    }
    for old, (new, expected_count) in homepage_replacements.items():
        if source.count(old) != expected_count:
            raise PackagingError(f"homepage navigation marker drift: {old}")
        source = source.replace(old, new)
    if source.count("</body>") != 1:
        raise PackagingError("homepage body marker drift")
    return source.replace(
        "</body>",
        HOMEPAGE_NAVIGATION_SCRIPT
        + "\n"
        + HOMEPAGE_INQUIRY_HOST
        + "\n"
        + TWINKLE_VIEWPORT_HOST
        + '\n<script type="module" src="./twinkle-entry.js"></script></body>',
    )


def _render_catalog_html(source: str) -> str:
    replacements = {
        "../2026-08-06-homepage-authority/index.html#home": ("../index.html#home", 2),
        "../2026-08-06-homepage-authority/index.html#quality": ("../index.html#quality", 1),
        '.topbar{height:76px;padding:0 5vw;display:flex;align-items:center;justify-content:space-between;position:relative;z-index:10;border-bottom:1px solid rgba(44,92,98,.08);background:rgba(249,252,250,.72);backdrop-filter:blur(14px)}.brand{display:flex;align-items:center;gap:14px;text-decoration:none;color:var(--ink);font-size:11px;letter-spacing:.16em;font-weight:700}.brand img{width:112px;height:auto}.topbar nav{display:flex;gap:26px;font-size:13px;color:#42646b}.topbar nav a{color:inherit;text-decoration:none}.header-contact{padding:10px 15px;border-radius:999px;background:#173f46;color:#fff;text-decoration:none;font-size:12px}': (
            NAVIGATION_CSS + CATALOG_RETURN_CSS,
            1,
        ),
        'main{position:relative;z-index:1;min-height:calc(100vh - 76px);display:grid;grid-template-columns:minmax(310px,34vw) 1fr;align-items:stretch}': (
            'main{position:relative;z-index:1;min-height:100vh;padding-top:98px;display:grid;grid-template-columns:minmax(310px,34vw) 1fr;align-items:stretch}',
            1,
        ),
        '.detail-sources,.dialog-sources{display:flex;flex-wrap:wrap;gap:5px 9px;margin-top:14px;font-size:10px;line-height:1.5;color:#6a8186}.detail-sources:before,.dialog-sources:before{content:"数据依据";font-weight:700;color:#42666d}.detail-sources a,.dialog-sources a{color:#2b727b;text-decoration:none;border-bottom:1px solid rgba(43,114,123,.28)}': (
            '.detail-sources,.dialog-sources{margin-top:14px;font-size:10px;line-height:1.5;color:#6a8186}.source-heading{font-weight:700;color:#42666d}.source-links{display:flex;flex-wrap:wrap;gap:5px 9px;margin-top:6px}.source-links a{color:#2b727b;text-decoration:none;border-bottom:1px solid rgba(43,114,123,.28)}',
            1,
        ),
        '.dialog-actions{display:flex;gap:10px}.dialog-actions a{padding:13px 16px;border-radius:999px;text-decoration:none;font-size:13px}.dialog-actions .official{background:#173f46;color:#fff}.dialog-actions .contact{border:1px solid var(--line);color:#295b63;background:#fff}': (
            '.dialog-sources{padding-bottom:20px;border-bottom:1px solid rgba(35,103,111,.16)}.dialog-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.dialog-actions a,.dialog-actions button{padding:13px 16px;border-radius:999px;text-decoration:none;font:inherit;font-size:13px;cursor:pointer}.dialog-actions .official{background:#173f46;color:#fff}.dialog-actions .contact{border:1px solid var(--line);color:#295b63;background:#fff}',
            1,
        ),
        '<nav><a href="../index.html#home">首页</a><a href="./circular-gallery-preview.html" aria-current="page">产品</a><a href="../index.html#quality">品质</a></nav>': (
            '<nav class="topnav"><a href="../index.html#home">首页</a><a href="../index.html#materials">能力概览</a><a href="../index.html#applications">应用方向</a><a href="../index.html#quality">TWINKLE</a><a href="./circular-gallery-preview.html" aria-current="page">产品中心</a><a href="../index.html#company">业务范围</a></nav>',
            1,
        ),
        '</header>\n  <main>': (
            '</header>\n' + CATALOG_RETURN_HOST + '\n  <main>',
            1,
        ),
        '<a class="header-contact" href="mailto:sales@supreme-oe.com">技术询盘</a>': (
            '<button class="cta" type="button" data-open-inquiry>技术询盘</button>',
            1,
        ),
        '<div class="detail-sources" data-detail-sources>': (
            '<div class="detail-sources"><div class="source-heading">参考资料</div><div class="source-links" data-detail-sources>',
            1,
        ),
        '</a></div>\n    </section>\n    <section class="gallery-shell"': (
            '</a></div></div>\n    </section>\n    <section class="gallery-shell"',
            1,
        ),
        '<div class="dialog-sources" data-dialog-sources></div>': (
            '<div class="dialog-sources"><div class="source-heading">参考资料</div><div class="source-links" data-dialog-sources></div></div>',
            1,
        ),
        '<a class="official" data-dialog-official target="_blank" rel="noopener">完整产品页 ↗</a><a class="contact" href="mailto:sales@supreme-oe.com">技术询盘</a>': (
            '<a class="official" data-dialog-official target="_blank" rel="noopener">查看企业产品页 ↗</a><button class="contact" type="button" data-open-inquiry>技术询盘</button>',
            1,
        ),
        '  <script type="module" src="./paper-dithering-background.js"></script>': (
            '  <dialog class="inquiry-dialog" data-inquiry-dialog aria-labelledby="inquiry-title">\n'
            '    <button class="dialog-close" type="button" data-close-inquiry aria-label="关闭技术询盘提示">×</button>\n'
            '    <div class="inquiry-body"><div class="dialog-kicker">TECHNICAL INQUIRY</div><h2 id="inquiry-title">技术询盘</h2><p>该功能开发中，敬请期待</p><button class="inquiry-dismiss" type="button" data-close-inquiry>关闭</button></div>\n'
            '  </dialog>\n'
            '  <script type="module" src="./paper-dithering-background.js"></script>',
            1,
        ),
        '@media(max-width:980px){.topbar nav{display:none}main{grid-template-columns:1fr;min-height:auto}.product-detail{padding:8vh 7vw 2vh}.detail-summary{margin-top:24px}.detail-facts{margin-top:30px}.gallery-shell{min-height:680px}.gallery-shell:before{width:120vw;height:85vw}.active-product{left:7vw;right:7vw;width:auto;transform:none;bottom:5vh}.fallback-list{inset:7vh 5vw 15vh}}': (
            '@media(max-width:980px){main{grid-template-columns:1fr;min-height:auto}.product-detail{padding:8vh 7vw 2vh}.detail-summary{margin-top:24px}.detail-facts{margin-top:30px}.gallery-shell{min-height:680px}.gallery-shell:before{width:120vw;height:85vw}.active-product{left:7vw;right:7vw;width:auto;transform:none;bottom:5vh}.fallback-list{inset:7vh 5vw 15vh}}',
            1,
        ),
        '@media(max-width:620px){[data-spectral-flow]{inset:66px 0 0}[data-spectral-flow] canvas{opacity:.34}.topbar{height:66px;padding:0 5vw}.brand span,.header-contact{display:none}.product-detail{padding-top:7vh}.product-detail h1{font-size:44px}.detail-formula{font-size:28px}.detail-summary{font-size:13px}.detail-facts{grid-template-columns:repeat(2,minmax(0,1fr));gap:0 14px}.detail-fact{display:block}.detail-fact b{display:block;margin-top:5px;text-align:left;font-size:12px}.gallery-shell{min-height:610px}.active-product{grid-template-columns:1fr}.active-product button{width:100%}.fallback-list{grid-template-columns:1fr}.dialog-body{padding:24px}.dialog-media{padding-left:24px;padding-right:24px}}': (
            '@media(max-width:620px){[data-spectral-flow]{inset:66px 0 0}[data-spectral-flow] canvas{opacity:.34}.brand span{display:none}.product-detail{padding-top:7vh}.product-detail h1{font-size:44px}.detail-formula{font-size:28px}.detail-summary{font-size:13px}.detail-facts{grid-template-columns:repeat(2,minmax(0,1fr));gap:0 14px}.detail-fact{display:block}.detail-fact b{display:block;margin-top:5px;text-align:left;font-size:12px}.gallery-shell{min-height:610px}.active-product{grid-template-columns:1fr}.active-product button{width:100%}.fallback-list{grid-template-columns:1fr}.dialog-body{padding:24px}.dialog-media{padding-left:24px;padding-right:24px}.dialog-actions{display:grid}.dialog-actions a,.dialog-actions button{text-align:center}}',
            1,
        ),
        '  </style>': (
            f'    @media(prefers-reduced-motion:reduce){{{NAVIGATION_REDUCED_MOTION_CSS}{CATALOG_RETURN_REDUCED_MOTION_CSS}}}\n  </style>',
            1,
        ),
    }
    for old, (new, expected_count) in replacements.items():
        if source.count(old) != expected_count:
            raise PackagingError(f"catalog HTML marker drift: {old}")
        source = source.replace(old, new)
    inquiry_css_anchor = "    @media(max-width:980px)"
    if source.count(inquiry_css_anchor) != 1:
        raise PackagingError("catalog inquiry CSS marker drift")
    inquiry_css = (
        '    .inquiry-dialog{inset:auto;left:50%;top:50%;margin:0;transform:translate(-50%,-50%);width:min(390px,calc(100vw - 32px));height:auto;max-height:calc(100vh - 32px);border:1px solid var(--line);border-radius:22px;padding:0;overflow:hidden;background:#f9fbf9;box-shadow:0 24px 55px rgba(30,57,63,.16)}.inquiry-dialog .dialog-close{right:16px;top:16px}.inquiry-body{padding:54px 28px 28px}.inquiry-body h2{margin:10px 0 0;font-size:28px;letter-spacing:-.035em}.inquiry-body p{margin:18px 0 24px;color:#536d73;font-size:14px;line-height:1.7}.inquiry-dismiss{width:100%;padding:12px 16px;border:1px solid var(--line);border-radius:999px;background:#fff;color:#295b63;font:inherit;font-size:13px;cursor:pointer}\n'
    )
    navigation_narrow_css = (
        '    @media(max-width:900px){.topnav{display:none}.topbar{left:12px;right:12px;top:10px;padding:0 14px}.cta{margin-left:auto}main{padding-top:84px}}\n'
    )
    source = source.replace(
        inquiry_css_anchor, inquiry_css + navigation_narrow_css + inquiry_css_anchor
    )
    return source


def _render_catalog_script(source: str) -> str:
    replacements = {
        "let selectedItem = PRODUCT_ITEMS[0];": (
            "let selectedItem = PRODUCT_ITEMS[0];\n"
            "const inquiryDialog = document.querySelector('[data-inquiry-dialog]');\n"
            "let inquiryTrigger = null;",
            1,
        ),
        "dialogSources.innerHTML = selectedItem.sources.map(source => `<a href=\"${source.url}\" target=\"_blank\" rel=\"noopener\">${source.label}</a>`).join('<span>·</span>');": (
            "dialogSources.innerHTML = selectedItem.sources.filter(source => source.url !== selectedItem.officialUrl).map(source => `<a href=\"${source.url}\" target=\"_blank\" rel=\"noopener\">${source.label}</a>`).join('<span>·</span>');",
            1,
        ),
        "function closeProduct() { dialog.close?.(); dialog.removeAttribute('open'); }": (
            "function closeProduct() { dialog.close?.(); dialog.removeAttribute('open'); }\n\n"
            "function openInquiry(event) {\n"
            "  inquiryTrigger = event.currentTarget;\n"
            "  inquiryDialog.showModal?.();\n"
            "  if (!inquiryDialog.open) inquiryDialog.setAttribute('open', '');\n"
            "}\n\n"
            "function closeInquiry() {\n"
            "  inquiryDialog.close?.();\n"
            "  inquiryDialog.removeAttribute('open');\n"
            "  inquiryTrigger?.focus();\n"
            "  inquiryTrigger = null;\n"
            "}",
            1,
        ),
        "dialog.addEventListener('click', event => { if (event.target === dialog) closeProduct(); });": (
            "dialog.addEventListener('click', event => { if (event.target === dialog) closeProduct(); });\n"
            "document.querySelectorAll('[data-open-inquiry]').forEach(button => button.addEventListener('click', openInquiry));\n"
            "document.querySelectorAll('[data-close-inquiry]').forEach(button => button.addEventListener('click', closeInquiry));\n"
            "inquiryDialog.addEventListener('click', event => { if (event.target === inquiryDialog) closeInquiry(); });\n"
            "inquiryDialog.addEventListener('cancel', event => { event.preventDefault(); closeInquiry(); });",
            1,
        ),
    }
    for old, (new, expected_count) in replacements.items():
        if source.count(old) != expected_count:
            raise PackagingError(f"catalog script marker drift: {old}")
        source = source.replace(old, new)
    return source


def build_controlled_homepage(
    authority_root: Path, baseline_root: Path, target_repo: Path
) -> Path:
    authority = Path(authority_root).resolve(strict=True)
    baseline = Path(baseline_root).resolve(strict=True)
    target = Path(target_repo).resolve(strict=True)
    hover_frames = validate_hover_preview_source(target / HOVER_PILOT_RELATIVE)
    inputs = {
        relative: _validate_file(authority, relative, expected)
        for relative, expected in AUTHORITY_HASHES.items()
    }
    dependencies = {
        relative: _validate_file(baseline, relative, expected)
        for relative, expected in BASELINE_HASHES.items()
    }
    ogl_root = baseline / "assets/vendor/ogl"
    if not ogl_root.is_dir() or _tree_digest(ogl_root) != OGL_TREE_SHA256:
        raise PackagingError("OGL dependency closure drift")
    catalog_source = authority.parent / CATALOG_AUTHORITY_NAME
    if (
        not catalog_source.is_dir()
        or _is_reparse(catalog_source)
        or _tree_digest(catalog_source) != CATALOG_TREE_SHA256
    ):
        raise PackagingError("product catalog authority closure drift")

    showcase = target / "showcase"
    created_showcase = False
    if not showcase.exists():
        showcase.mkdir()
        created_showcase = True
    if _is_reparse(showcase) or not showcase.is_dir():
        raise PackagingError("showcase parent must be a regular directory")
    destination = showcase / "homepage"
    if destination.exists() or destination.is_symlink():
        raise PackagingError("controlled homepage destination already exists")
    stage = showcase / f".homepage-stage5-{uuid.uuid4().hex}.staging"
    stage.mkdir()
    try:
        (stage / "assets/vendor").mkdir(parents=True)
        shutil.copyfile(inputs["preview-runtime.mjs"], stage / "preview-runtime.mjs")
        flowmap = inputs["hero-flowmap.js"].read_text(encoding="utf-8").replace(
            "../../showcase-baselines/2026-08-05-before-authority-redesign/assets/vendor/ogl.mjs",
            "./assets/vendor/ogl.mjs",
        ).replace(
            "../../showcase-baselines/2026-08-05-before-authority-redesign/assets/official-cvd-znse.png",
            "./assets/official-cvd-znse.png",
        )
        (stage / "hero-flowmap.js").write_text(flowmap, encoding="utf-8", newline="\n")
        html = _render_html(inputs["index.html"].read_text(encoding="utf-8"))
        (stage / "index.html").write_text(html, encoding="utf-8", newline="\n")
        (stage / "twinkle-entry.css").write_text(ENTRY_CSS, encoding="utf-8", newline="\n")
        (stage / "twinkle-entry.js").write_text(ENTRY_JS, encoding="utf-8", newline="\n")
        products = _extract_product_objects(
            dependencies["product-items.mjs"].read_text(encoding="utf-8")
        )
        (stage / "product-items.mjs").write_text(products, encoding="utf-8", newline="\n")
        catalog_target = stage / CATALOG_TARGET_RELATIVE
        shutil.copytree(catalog_source, catalog_target)
        catalog_html = catalog_target / "circular-gallery-preview.html"
        catalog_html.write_text(
            _render_catalog_html(catalog_html.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        catalog_script = catalog_target / "product-ring-gallery.js"
        catalog_script.write_text(
            _render_catalog_script(catalog_script.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        for relative in (
            "assets/official-logo.png",
            "assets/official-cvd-znse.png",
            "assets/official-high-tech-certificate.jpeg",
            "assets/official-category-2020258820.jpg",
            "assets/official-dyf3.png",
            "assets/official-germanium.png",
        ):
            target_path = stage / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dependencies[relative], target_path)
        rd_target = stage / "assets/rd-manufacturing-cgi.webp"
        rd_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inputs["assets/rd-manufacturing-cgi.webp"], rd_target)
        hover_target = stage / HOVER_PREVIEW_RELATIVE
        hover_target.mkdir(parents=True)
        for source in hover_frames:
            destination_frame = hover_target / source.name
            shutil.copyfile(source, destination_frame)
            if (
                destination_frame.stat().st_size != source.stat().st_size
                or _sha256(destination_frame) != _sha256(source)
            ):
                raise PackagingError(f"hover preview copy drift: {source.name}")
        shutil.copyfile(dependencies["assets/vendor/ogl.mjs"], stage / "assets/vendor/ogl.mjs")
        shutil.copytree(ogl_root, stage / "assets/vendor/ogl")
        os.replace(stage, destination)
    except (OSError, PackagingError) as error:
        if stage.exists() or stage.is_symlink():
            shutil.rmtree(stage)
        if created_showcase and showcase.exists() and not any(showcase.iterdir()):
            showcase.rmdir()
        raise PackagingError(f"controlled homepage build failed: {error}") from error
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the controlled TWINKLE stage-five homepage")
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--target-repo", type=Path, required=True)
    args = parser.parse_args()
    try:
        destination = build_controlled_homepage(
            args.authority, args.baseline, args.target_repo
        )
    except PackagingError as error:
        print(f"TWINKLE stage-five homepage: FAIL - {error}")
        return 1
    print(f"TWINKLE stage-five homepage: PASS - {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
