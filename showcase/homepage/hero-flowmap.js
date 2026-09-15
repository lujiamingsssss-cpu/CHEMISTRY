import { Flowmap, Mesh, Program, Renderer, Texture, Triangle, Vec2 } from './assets/vendor/ogl.mjs';
import { createFrameScheduler } from './preview-runtime.mjs';

const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
const narrowScreenQuery = window.matchMedia('(max-width: 900px)');
const instances = new Set();
const instancesByElement = new Map();
const scheduler = createFrameScheduler({
  requestFrame: (callback) => requestAnimationFrame(callback),
  cancelFrame: (frame) => cancelAnimationFrame(frame),
});

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    const instance = instancesByElement.get(entry.target);
    if (instance) scheduler.setVisible(instance.job, entry.isIntersecting);
  });
}, { threshold: 0.05 });

const vertex = `
  attribute vec2 uv;
  attribute vec2 position;
  varying vec2 vUv;
  void main(){ vUv=uv; gl_Position=vec4(position,0.0,1.0); }
`;

function releaseRenderer(renderer, contextLost) {
  if (!renderer || contextLost) return;
  const extension = renderer.gl.getExtension('WEBGL_lose_context');
  if (extension) extension.loseContext();
}

function registerInstance(element, instance) {
  instances.add(instance);
  instancesByElement.set(element, instance);
  scheduler.add(instance.job);
  observer.observe(element);
}

function unregisterInstance(element, instance) {
  observer.unobserve(element);
  instancesByElement.delete(element);
  instances.delete(instance);
  scheduler.remove(instance.job);
}

function createHero() {
  const lens = document.querySelector('[data-material-lens]');
  const canvas = lens?.querySelector('[data-webgl-layer]');
  if (!lens || !canvas || reducedMotionQuery.matches || narrowScreenQuery.matches) return;

  let renderer;
  let image;
  let instance;
  let job;
  let disposed = false;
  let contextLost = false;
  let ready = false;
  const removers = [];
  const listen = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    removers.push(() => target.removeEventListener(type, handler, options));
  };
  const dispose = ({ releaseContext = true } = {}) => {
    if (disposed) return;
    disposed = true;
    ready = false;
    lens.classList.remove('lens-ready');
    if (job) scheduler.setReady(job, false);
    if (instance) unregisterInstance(lens, instance);
    removers.splice(0).forEach((remove) => remove());
    if (image) {
      image.onload = null;
      image.onerror = null;
    }
    releaseRenderer(renderer, contextLost || !releaseContext);
    canvas.remove();
  };

  try {
    renderer = new Renderer({
      canvas,
      dpr: Math.min(window.devicePixelRatio || 1, 2),
      alpha: true,
      antialias: true,
    });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);
    const flowmap = new Flowmap(gl, {
      size: 256,
      falloff: 0.26,
      alpha: 0.72,
      dissipation: 0.965,
    });
    const texture = new Texture(gl, { minFilter: gl.LINEAR, magFilter: gl.LINEAR });
    const pointer = new Vec2(-1, -1);
    const last = new Vec2();
    const velocity = new Vec2();
    let lastTime = performance.now();
    let moving = false;
    const program = new Program(gl, {
      vertex,
      fragment: `
        precision highp float;
        uniform sampler2D tImage; uniform sampler2D tFlow;
        uniform float uTime; uniform float uAspect; uniform float uImageAspect; uniform float uAccent;
        varying vec2 vUv;
        void main(){
          vec2 flow=texture2D(tFlow,vUv).rg*2.0-1.0; vec2 uv=vUv-0.5;
          if(uAspect>uImageAspect) uv.y*=uImageAspect/uAspect; else uv.x*=uAspect/uImageAspect;
          uv+=0.5+flow*0.055; vec4 photo=texture2D(tImage,uv); vec2 p=vUv-0.5;
          p.x*=uAspect>1.0?uAspect:1.0; float angle=atan(p.y,p.x);
          float radius=.43+.026*sin(angle*3.0+uTime*.32)+.018*sin(angle*5.0-uTime*.21);
          float distanceToCenter=length(p); float alpha=1.0-smoothstep(radius-.045,radius,distanceToCenter);
          float rim=smoothstep(radius-.045,radius-.018,distanceToCenter)*(1.0-smoothstep(radius-.018,radius+.002,distanceToCenter));
          vec3 accent=mix(vec3(.22,.72,.76),vec3(.48,.40,.91),uAccent);
          gl_FragColor=vec4(photo.rgb+accent*(length(flow)*.2+rim*.65),alpha*photo.a);
        }
      `,
      uniforms: {
        tImage: { value: texture },
        tFlow: flowmap.uniform,
        uTime: { value: 0 },
        uAspect: { value: 1 },
        uImageAspect: { value: 800 / 650 },
        uAccent: { value: .2 },
      },
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    const resize = () => {
      const rect = lens.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width));
      const height = Math.max(1, Math.round(rect.height));
      renderer.setSize(width, height);
      flowmap.aspect = width / height;
      program.uniforms.uAspect.value = width / height;
    };
    const move = (event) => {
      const rect = lens.getBoundingClientRect();
      pointer.set(
        (event.clientX - rect.left) / rect.width,
        1 - (event.clientY - rect.top) / rect.height,
      );
      moving = true;
    };
    const leave = () => {
      moving = false;
      pointer.set(-1, -1);
    };
    const contextLostHandler = (event) => {
      event.preventDefault();
      contextLost = true;
      dispose({ releaseContext: false });
    };

    job = {
      render(time) {
        if (!ready || disposed) return;
        const delta = Math.max(16, time - lastTime);
        lastTime = time;
        if (moving) {
          velocity.set(
            (pointer.x - last.x) / delta * 16,
            (pointer.y - last.y) / delta * 16,
          );
          last.copy(pointer);
        } else {
          velocity.lerp(new Vec2(), .12);
        }
        flowmap.mouse.copy(pointer);
        flowmap.velocity.lerp(velocity, .18);
        flowmap.update();
        program.uniforms.uTime.value = time * .001;
        renderer.render({ scene: mesh });
        lens.classList.add('lens-ready');
      },
    };
    instance = {
      job,
      dispose,
      revealFallback: () => lens.classList.remove('lens-ready'),
      restoreReady: () => { if (ready && !disposed) lens.classList.add('lens-ready'); },
    };
    registerInstance(lens, instance);
    listen(lens, 'pointermove', move, { passive: true });
    listen(lens, 'pointerleave', leave, { passive: true });
    listen(window, 'resize', resize, { passive: true });
    listen(canvas, 'webglcontextlost', contextLostHandler, false);
    lens.querySelectorAll('[data-lens-accent]').forEach((item) => {
      const setAccent = () => {
        program.uniforms.uAccent.value = Number(item.dataset.lensAccent || .2);
      };
      listen(item, 'pointerenter', setAccent);
      listen(item, 'focus', setAccent);
    });

    image = new Image();
    image.onload = () => {
      if (disposed) return;
      texture.image = image;
      program.uniforms.uImageAspect.value = image.naturalWidth / image.naturalHeight;
      ready = true;
      scheduler.setReady(job, true);
    };
    image.onerror = () => dispose();
    resize();
    image.src = './assets/official-cvd-znse.png';
  } catch (error) {
    dispose();
    document.documentElement.classList.add('no-webgl');
    console.warn('Material lens fallback enabled:', error);
  }
}

function createOrganicBlob(container, index) {
  const fallback = container.querySelector('[data-static-fallback]');
  if (!fallback) return;

  let canvas;
  let renderer;
  let image;
  let instance;
  let job;
  let disposed = false;
  let contextLost = false;
  let ready = false;
  const removers = [];
  const listen = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    removers.push(() => target.removeEventListener(type, handler, options));
  };
  const dispose = ({ releaseContext = true } = {}) => {
    if (disposed) return;
    disposed = true;
    ready = false;
    container.classList.remove('blob-ready');
    if (job) scheduler.setReady(job, false);
    if (instance) unregisterInstance(container, instance);
    removers.splice(0).forEach((remove) => remove());
    if (image) {
      image.onload = null;
      image.onerror = null;
    }
    if (canvas) canvas.remove();
    releaseRenderer(renderer, contextLost || !releaseContext);
  };

  try {
    canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    container.append(canvas);
    renderer = new Renderer({
      canvas,
      dpr: Math.min(window.devicePixelRatio || 1, 1.5),
      alpha: true,
      antialias: true,
    });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);
    const texture = new Texture(gl, { minFilter: gl.LINEAR, magFilter: gl.LINEAR });
    const program = new Program(gl, {
      vertex,
      fragment: `
        precision highp float; uniform sampler2D tImage; uniform float uTime; uniform float uAspect; uniform float uImageAspect; uniform float uPhase; varying vec2 vUv;
        void main(){
          vec2 p=vUv-.5; p.x*=uAspect>1.0?uAspect:1.0; float a=atan(p.y,p.x);
          float r=.42+.032*sin(a*3.0+uTime*.31+uPhase)+.018*sin(a*5.0-uTime*.19);
          float alpha=1.0-smoothstep(r-.055,r,length(p)); vec2 uv=vUv-.5;
          if(uAspect>uImageAspect) uv.y*=uImageAspect/uAspect; else uv.x*=uAspect/uImageAspect;
          uv+=.5; vec4 photo=texture2D(tImage,uv);
          gl_FragColor=vec4(photo.rgb,photo.a*alpha);
        }
      `,
      uniforms: {
        tImage: { value: texture },
        uTime: { value: 0 },
        uAspect: { value: 1 },
        uImageAspect: { value: 1 },
        uPhase: { value: index * 2.1 },
      },
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    const resize = () => {
      const rect = container.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width));
      const height = Math.max(1, Math.round(rect.height));
      renderer.setSize(width, height);
      program.uniforms.uAspect.value = width / height;
    };
    const contextLostHandler = (event) => {
      event.preventDefault();
      contextLost = true;
      dispose({ releaseContext: false });
    };

    job = {
      render(time) {
        if (!ready || disposed) return;
        program.uniforms.uTime.value = time * .001;
        renderer.render({ scene: mesh });
        container.classList.add('blob-ready');
      },
    };
    instance = {
      job,
      dispose,
      revealFallback: () => container.classList.remove('blob-ready'),
      restoreReady: () => { if (ready && !disposed) container.classList.add('blob-ready'); },
    };
    registerInstance(container, instance);
    listen(window, 'resize', resize, { passive: true });
    listen(canvas, 'webglcontextlost', contextLostHandler, false);

    image = new Image();
    image.onload = () => {
      if (disposed) return;
      texture.image = image;
      program.uniforms.uImageAspect.value = image.naturalWidth / image.naturalHeight;
      ready = true;
      scheduler.setReady(job, true);
    };
    image.onerror = () => dispose();
    resize();
    image.src = fallback.currentSrc || fallback.src;
  } catch (error) {
    dispose();
    console.warn('Organic image fallback enabled:', error);
  }
}

function createOrganicBlobs() {
  if (reducedMotionQuery.matches || narrowScreenQuery.matches) return;
  document.querySelectorAll('[data-organic-blob]').forEach(createOrganicBlob);
}

function revealFallbacks() {
  instances.forEach((instance) => instance.revealFallback());
}

function restoreReadyCanvases() {
  instances.forEach((instance) => instance.restoreReady());
}

function disposeAll() {
  [...instances].forEach((instance) => instance.dispose());
  observer.disconnect();
  scheduler.pause();
}

const visibilityHandler = () => {
  if (document.hidden) scheduler.pause();
  else scheduler.resume();
};
const pagehideHandler = (event) => {
  scheduler.pause();
  revealFallbacks();
  if (!event.persisted) disposeAll();
};
const pageshowHandler = (event) => {
  if (!event.persisted) return;
  restoreReadyCanvases();
  scheduler.resume();
};
const reloadForMotionPolicy = () => window.location.reload();

document.addEventListener('visibilitychange', visibilityHandler);
window.addEventListener('pagehide', pagehideHandler);
window.addEventListener('pageshow', pageshowHandler);
reducedMotionQuery.addEventListener('change', reloadForMotionPolicy);
narrowScreenQuery.addEventListener('change', reloadForMotionPolicy);

createHero();
createOrganicBlobs();
