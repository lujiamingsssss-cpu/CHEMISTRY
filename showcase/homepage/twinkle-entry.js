const entry = document.querySelector('[data-twinkle-stage5-entry] .twinkle-stage5-entry-card');
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
