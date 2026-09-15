import { ShaderMount } from './assets/vendor/paper-shaders/dist/shader-mount.js';
import {
  DitheringShapes,
  DitheringTypes,
  ditheringFragmentShader,
} from './assets/vendor/paper-shaders/dist/shaders/dithering.js';
import { getShaderColorFromString } from './assets/vendor/paper-shaders/dist/get-shader-color-from-string.js';
import { ShaderFitOptions } from './assets/vendor/paper-shaders/dist/shader-sizing.js';

const host = document.querySelector('[data-spectral-flow]');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const mobile = matchMedia('(max-width: 620px)');
const settings = {
  speed: 0.14,
  maxDesktopPixels: 2_400_000,
  maxMobilePixels: 1_200_000,
};

if (host) {
  try {
    const uniforms = {
      u_originX: 0.5,
      u_originY: 0.5,
      u_worldWidth: 0,
      u_worldHeight: 0,
      u_fit: ShaderFitOptions.none,
      u_scale: mobile.matches ? 0.68 : 0.82,
      u_rotation: 0,
      u_offsetX: 0.08,
      u_offsetY: -0.04,
      u_colorBack: getShaderColorFromString('#d7e7e800'),
      u_colorFront: getShaderColorFromString('#2aaab866'),
      u_shape: DitheringShapes.warp,
      u_type: DitheringTypes['4x4'],
      u_pxSize: 3,
    };
    const speed = reducedMotion.matches
      ? 0
      : settings.speed * (mobile.matches ? 0.68 : 1);
    const mount = new ShaderMount(
      host,
      ditheringFragmentShader,
      uniforms,
      { alpha: true, antialias: false, premultipliedAlpha: true },
      speed,
      1_500,
      1,
      mobile.matches ? settings.maxMobilePixels : settings.maxDesktopPixels,
    );
    host.dataset.ditherState = 'ready';

    const cleanup = () => {
      mount.dispose();
    };
    addEventListener('pagehide', cleanup, { once: true });
  } catch (error) {
    host.dataset.ditherState = 'fallback';
    console.error('Paper Dithering fallback', error);
  }
}
