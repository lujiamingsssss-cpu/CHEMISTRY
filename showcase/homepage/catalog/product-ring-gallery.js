import { Camera, Mesh, Plane, Program, Raycast, Renderer, Texture, Transform } from './assets/vendor/ogl.mjs';
import { PRODUCT_ITEMS } from './product-items.mjs';
import { arcPosition, rotationForDrag, softenVelocity, stepInertia, targetRotationForItem, targetRotationForRelease, wrapPosition } from './ring-gallery-core.mjs';

const stage = document.querySelector('[data-ring-stage]');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

const vertex = `
  precision highp float;
  attribute vec3 position;
  attribute vec2 uv;
  uniform mat4 modelViewMatrix;
  uniform mat4 projectionMatrix;
  uniform float uBend;
  uniform float uVelocity;
  varying vec2 vUv;
  void main(){
    vUv=uv;
    vec3 p=position;
    float centered=uv.x-.5;
    p.z+=cos(centered*3.14159265)*uBend*.09-uBend*.09;
    p.y+=sin(uv.x*3.14159265)*abs(uVelocity)*.055;
    gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.0);
  }
`;

const fragment = `
  precision highp float;
  uniform sampler2D tMap;
  uniform vec2 uImageSize;
  uniform vec2 uPlaneSize;
  uniform float uRadius;
  uniform float uFocus;
  varying vec2 vUv;
  vec2 coverUv(vec2 uv,vec2 plane,vec2 image){
    float rs=plane.x/plane.y,ri=image.x/image.y;
    vec2 ratio=rs<ri?vec2(plane.y*ri/plane.x,1.0):vec2(1.0,plane.x/(ri*plane.y));
    return (uv-.5)/ratio+.5;
  }
  float roundedBox(vec2 p,vec2 b,float r){
    vec2 q=abs(p)-b+r;
    return length(max(q,0.0))+min(max(q.x,q.y),0.0)-r;
  }
  void main(){
    vec2 uv=coverUv(vUv,uPlaneSize,uImageSize);
    vec4 tex=texture2D(tMap,uv);
    float mask=1.0-smoothstep(-.012,.012,roundedBox(vUv-.5,vec2(.5),uRadius));
    vec3 tint=mix(vec3(.92,.97,.96),vec3(1.0),uFocus);
    gl_FragColor=vec4(tex.rgb*tint,tex.a*mask*(.55+.45*uFocus));
  }
`;

function loadTexture(gl, item, uniform) {
  const texture = new Texture(gl, { minFilter: gl.LINEAR, magFilter: gl.LINEAR, generateMipmaps: false });
  const image = new Image();
  image.onload = () => {
    texture.image = image;
    uniform.value = [image.naturalWidth || 1, image.naturalHeight || 1];
  };
  image.src = item.image;
  return texture;
}

class ProductRingGallery {
  constructor(container, items, { bend = 3.4, scrollSpeed = 1.8, scrollEase = 0.14, borderRadius = 0.075, clickThreshold = 6 } = {}) {
    this.container = container;
    this.items = items;
    this.bend = bend;
    this.scrollSpeed = scrollSpeed;
    this.scrollEase = scrollEase;
    this.borderRadius = borderRadius;
    this.clickThreshold = clickThreshold;
    this.rotation = { current: 0, target: 0, last: 0 };
    this.activeIndex = 0;
    this.dragging = false;
    this.dragDistance = 0;
    this.startX = 0;
    this.startTarget = 0;
    this.dragVelocity = 0;
    this.lastPointerX = 0;
    this.lastPointerTime = 0;
    this.snapTimer = 0;
    this.frame = 0;
    this.visible = true;
    this.createScene();
    this.raycast = new Raycast();
    this.bindEvents();
    this.resize();
    this.updateActive(true);
    this.frame = requestAnimationFrame(() => this.render());
  }

  createScene() {
    this.renderer = new Renderer({ dpr: Math.min(devicePixelRatio || 1, 1.75), alpha: true, antialias: true });
    this.gl = this.renderer.gl;
    this.gl.clearColor(0, 0, 0, 0);
    this.gl.canvas.setAttribute('aria-hidden', 'true');
    this.container.prepend(this.gl.canvas);
    this.camera = new Camera(this.gl, { fov: 45 });
    this.camera.position.set(0, 0, 20);
    this.camera.lookAt([0, 0, 0]);
    this.scene = new Transform();
    this.geometry = new Plane(this.gl, { widthSegments: 28, heightSegments: 6 });
    this.medias = this.items.map((item, index) => {
      const imageSize = { value: [800, 650] };
      const texture = loadTexture(this.gl, item, imageSize);
      const program = new Program(this.gl, {
        vertex,
        fragment,
        transparent: true,
        depthTest: true,
        depthWrite: true,
        uniforms: {
          tMap: { value: texture },
          uImageSize: imageSize,
          uPlaneSize: { value: [2.65, 3.45] },
          uRadius: { value: this.borderRadius },
          uBend: { value: this.bend },
          uVelocity: { value: 0 },
          uFocus: { value: index === 0 ? 1 : 0 },
        },
      });
      const mesh = new Mesh(this.gl, { geometry: this.geometry, program });
      mesh.scale.set(2.2, 2.85, 1);
      mesh.setParent(this.scene);
      return { item, mesh, program };
    });
  }

  bindEvents() {
    this.onWheel = event => {
      event.preventDefault();
      const delta = Math.max(-90, Math.min(90, event.deltaY || event.deltaX));
      this.rotation.target += delta * 0.0032 * this.scrollSpeed;
      clearTimeout(this.snapTimer);
      this.snapTimer = setTimeout(() => this.snap(), 110);
    };
    this.onPointerDown = event => {
      if (event.target.closest?.('button, a')) return;
      this.dragging = true;
      this.dragDistance = 0;
      this.startX = event.clientX;
      this.startTarget = this.rotation.current;
      this.rotation.target = this.rotation.current;
      this.dragVelocity = 0;
      this.lastPointerX = event.clientX;
      this.lastPointerTime = event.timeStamp;
      this.container.setPointerCapture?.(event.pointerId);
    };
    this.onPointerMove = event => {
      if (!this.dragging) return;
      this.dragDistance = event.clientX - this.startX;
      const elapsed = Math.max(1, event.timeStamp - this.lastPointerTime);
      const pointerVelocity = (event.clientX - this.lastPointerX) / elapsed;
      this.dragVelocity = this.dragVelocity * 0.35 + pointerVelocity * 0.65;
      this.lastPointerX = event.clientX;
      this.lastPointerTime = event.timeStamp;
      this.rotation.target = rotationForDrag(
        this.startTarget,
        this.dragDistance,
        this.itemWidth,
        this.itemPixelWidth,
      );
      this.rotation.current = this.rotation.target;
    };
    this.onPointerUp = event => {
      if (!this.dragging) return;
      const wasClick = Math.abs(this.dragDistance) <= this.clickThreshold;
      const releaseVelocity = event.timeStamp - this.lastPointerTime <= 80 ? this.dragVelocity : 0;
      this.dragging = false;
      this.container.releasePointerCapture?.(event.pointerId);
      if (wasClick) this.selectClickedCard(event);
      else {
        this.rotation.target = targetRotationForRelease(
          this.startTarget,
          this.dragDistance,
          releaseVelocity,
          this.itemWidth,
          this.itemPixelWidth,
          { clickThreshold: this.clickThreshold },
        );
        this.snap();
      }
    };
    this.onKeyDown = event => {
      if (!['ArrowLeft', 'ArrowRight', 'Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Enter' || event.key === ' ') return openProduct();
      this.rotation.target += event.key === 'ArrowLeft' ? -this.itemWidth : this.itemWidth;
      this.snap();
    };
    this.container.addEventListener('wheel', this.onWheel, { passive: false });
    this.container.addEventListener('pointerdown', this.onPointerDown);
    this.container.addEventListener('pointermove', this.onPointerMove);
    this.container.addEventListener('pointerup', this.onPointerUp);
    this.container.addEventListener('pointercancel', this.onPointerUp);
    this.container.addEventListener('keydown', this.onKeyDown);
    addEventListener('resize', () => this.resize(), { passive: true });
    new IntersectionObserver(entries => { this.visible = entries[0]?.isIntersecting ?? true; }).observe(this.container);
  }

  snap() {
    this.rotation.target = Math.round(this.rotation.target / this.itemWidth) * this.itemWidth;
  }

  selectClickedCard(event) {
    const rect = this.container.getBoundingClientRect();
    const mouse = [
      ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
      (1 - (event.clientY - rect.top) / Math.max(1, rect.height)) * 2 - 1,
    ];
    this.raycast.castMouse(this.camera, mouse);
    const hits = this.raycast.intersectBounds(this.medias.map(({ mesh }) => mesh));
    const selectedIndex = hits.length
      ? this.medias.findIndex(({ mesh }) => mesh === hits[0])
      : -1;
    if (selectedIndex < 0) return this.snap();
    this.rotation.target = targetRotationForItem(
      this.rotation.current,
      selectedIndex,
      this.itemWidth,
      this.cycleWidth,
    );
    this.snap();
  }

  resize() {
    const rect = this.container.getBoundingClientRect();
    this.renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height));
    this.camera.perspective({ aspect: rect.width / Math.max(1, rect.height) });
    const fov = this.camera.fov * Math.PI / 180;
    this.viewport = {
      height: 2 * Math.tan(fov / 2) * this.camera.position.z,
      width: 2 * Math.tan(fov / 2) * this.camera.position.z * (rect.width / Math.max(1, rect.height)),
    };
    this.screen = { width: rect.width, height: rect.height };
    this.planeWidth = this.viewport.width * (rect.width < 620 ? 0.34 : 0.185);
    this.planeHeight = this.planeWidth * 1.28;
    this.itemWidth = this.planeWidth + this.viewport.width * 0.028;
    this.itemPixelWidth = this.itemWidth / (this.viewport.width / Math.max(1, this.screen.width));
    this.cycleWidth = this.itemWidth * this.items.length;
    this.arcDepth = rect.width < 620 ? 1.2 : 2.25;
    this.medias.forEach(({ mesh, program }) => {
      mesh.scale.set(this.planeWidth, this.planeHeight, 1);
      program.uniforms.uPlaneSize.value = [this.planeWidth, this.planeHeight];
    });
  }

  updateActive(force = false) {
    const next = ((Math.round(this.rotation.current / this.itemWidth) % this.items.length) + this.items.length) % this.items.length;
    if (!force && next === this.activeIndex) return;
    this.activeIndex = next;
    renderActive(this.items[next], next);
  }

  render() {
    this.frame = requestAnimationFrame(() => this.render());
    if (!this.visible) return;
    this.rotation.current = stepInertia(this.rotation.current, this.rotation.target, this.scrollEase);
    const velocity = this.rotation.current - this.rotation.last;
    this.rotation.last = this.rotation.current;
    this.medias.forEach(({ mesh, program }, index) => {
      const x = wrapPosition(index * this.itemWidth - this.rotation.current, this.cycleWidth);
      const arc = arcPosition(x, this.viewport.width / 2, this.arcDepth);
      mesh.position.set(x, arc.y + 0.65, -Math.abs(x) * 0.025);
      mesh.rotation.z = arc.rotation;
      const focus = Math.max(0, 1 - Math.abs(x) / (this.viewport.width * 0.5));
      program.uniforms.uVelocity.value = softenVelocity(velocity);
      program.uniforms.uFocus.value += (focus - program.uniforms.uFocus.value) * 0.09;
    });
    this.updateActive();
    this.renderer.render({ scene: this.scene, camera: this.camera });
  }
}

const activeCategory = document.querySelector('[data-active-category]');
const activeName = document.querySelector('[data-active-name]');
const detailCategory = document.querySelector('[data-detail-category]');
const detailName = document.querySelector('[data-detail-name]');
const detailFormula = document.querySelector('[data-detail-formula]');
const detailSummary = document.querySelector('[data-detail-summary]');
const detailFacts = document.querySelector('[data-detail-facts]');
const detailSources = document.querySelector('[data-detail-sources]');
const dialog = document.querySelector('[data-product-dialog]');
const dialogSummary = dialog.querySelector('[data-dialog-summary]');
const dialogFacts = dialog.querySelector('[data-dialog-facts]');
const dialogSources = dialog.querySelector('[data-dialog-sources]');
let selectedItem = PRODUCT_ITEMS[0];
const inquiryDialog = document.querySelector('[data-inquiry-dialog]');
let inquiryTrigger = null;

function renderActive(item, index) {
  selectedItem = item;
  activeCategory.textContent = item.category;
  activeName.textContent = `${item.name} · ${item.formula}`;
  detailCategory.textContent = item.category;
  detailName.textContent = item.name;
  detailFormula.textContent = item.formula;
  detailSummary.textContent = item.summary;
  detailFacts.innerHTML = item.facts.map(fact => `<div class="detail-fact"><span>${fact.label}</span><b>${fact.value}</b></div>`).join('');
  detailSources.innerHTML = item.sources.map(source => `<a href="${source.url}" target="_blank" rel="noopener">${source.label}</a>`).join('<span>·</span>');
}

function openProduct() {
  if (!selectedItem) return;
  dialog.querySelector('[data-dialog-image]').src = selectedItem.image;
  dialog.querySelector('[data-dialog-image]').alt = selectedItem.name;
  dialog.querySelector('[data-dialog-category]').textContent = selectedItem.category;
  dialog.querySelector('[data-dialog-name]').textContent = selectedItem.name;
  dialog.querySelector('[data-dialog-formula]').textContent = selectedItem.formula;
  dialogSummary.textContent = selectedItem.summary;
  dialogFacts.innerHTML = selectedItem.facts.map(fact => `<div class="dialog-fact"><span>${fact.label}</span><b>${fact.value}</b></div>`).join('');
  dialogSources.innerHTML = selectedItem.sources.filter(source => source.url !== selectedItem.officialUrl).map(source => `<a href="${source.url}" target="_blank" rel="noopener">${source.label}</a>`).join('<span>·</span>');
  dialog.querySelector('[data-dialog-official]').href = selectedItem.officialUrl;
  dialog.showModal?.();
  if (!dialog.open) dialog.setAttribute('open', '');
}

function closeProduct() { dialog.close?.(); dialog.removeAttribute('open'); }

function openInquiry(event) {
  inquiryTrigger = event.currentTarget;
  inquiryDialog.showModal?.();
  if (!inquiryDialog.open) inquiryDialog.setAttribute('open', '');
}

function closeInquiry() {
  inquiryDialog.close?.();
  inquiryDialog.removeAttribute('open');
  inquiryTrigger?.focus();
  inquiryTrigger = null;
}

function buildFallback() {
  const list = document.querySelector('[data-fallback-list]');
  PRODUCT_ITEMS.forEach((item, index) => {
    const button = document.createElement('button');
    button.className = 'fallback-card';
    button.type = 'button';
    button.innerHTML = `<img src="${item.image}" alt=""><span><b>${item.name} · ${item.formula}</b><span>${item.category}</span></span>`;
    button.addEventListener('click', () => { renderActive(item, index); openProduct(); });
    list.append(button);
  });
}

buildFallback();
document.querySelector('[data-open-product]').addEventListener('click', event => {
  if ((window.productRing?.dragDistance || 0) > 7) return;
  event.stopPropagation();
  openProduct();
});
document.querySelector('[data-close-product]').addEventListener('click', closeProduct);
dialog.addEventListener('click', event => { if (event.target === dialog) closeProduct(); });
document.querySelectorAll('[data-open-inquiry]').forEach(button => button.addEventListener('click', openInquiry));
document.querySelectorAll('[data-close-inquiry]').forEach(button => button.addEventListener('click', closeInquiry));
inquiryDialog.addEventListener('click', event => { if (event.target === inquiryDialog) closeInquiry(); });
inquiryDialog.addEventListener('cancel', event => { event.preventDefault(); closeInquiry(); });

if (!stage || reducedMotion.matches) {
  stage?.classList.add('is-static');
} else {
  try {
    window.productRing = new ProductRingGallery(stage, PRODUCT_ITEMS);
  } catch (error) {
    console.error('OGL product gallery fallback', error);
    stage.classList.add('is-static');
  }
}
