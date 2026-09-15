import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import test from 'node:test';

const root = path.dirname(fileURLToPath(import.meta.url));
const read = relativePath => readFile(path.join(root, relativePath), 'utf8');
const readBuffer = relativePath => readFile(path.join(root, relativePath));

test('product catalog loads the isolated Paper Dithering background entrypoint', async () => {
  const html = await read('circular-gallery-preview.html');

  assert.match(html, /data-spectral-flow/);
  assert.match(html, /src="\.\/paper-dithering-background\.js"/);
  assert.doesNotMatch(html, /src="\.\/spectral-flow-background\.js"/);
  assert.match(html, /--dither-x:/);
  assert.match(html, /--dither-y:/);
  assert.match(html, /var\(--dither-x\)/);
  assert.match(html, /var\(--dither-y\)/);
});

test('Paper Shaders is pinned locally with its license and required runtime modules', async () => {
  const packageJson = JSON.parse(await read('assets/vendor/paper-shaders/package.json'));
  const license = await read('assets/vendor/paper-shaders/LICENSE');
  const notice = await read('assets/vendor/paper-shaders/NOTICE');
  const mount = await read('assets/vendor/paper-shaders/dist/shader-mount.js');
  const dithering = await read('assets/vendor/paper-shaders/dist/shaders/dithering.js');

  assert.equal(packageJson.name, '@paper-design/shaders');
  assert.equal(packageJson.version, '0.0.79');
  assert.equal(packageJson.license, 'Apache-2.0');
  assert.match(license, /Apache License/);
  assert.match(notice, /Paper Shaders/i);
  assert.match(mount, /class ShaderMount/);
  assert.match(dithering, /const ditheringFragmentShader/);
});

test('background wrapper uses the approved balanced motion and cleans up safely', async () => {
  const source = await read('paper-dithering-background.js');

  assert.match(source, /from '\.\/assets\/vendor\/paper-shaders\/dist\/shader-mount\.js'/);
  assert.match(source, /from '\.\/assets\/vendor\/paper-shaders\/dist\/shaders\/dithering\.js'/);
  assert.match(source, /new ShaderMount\(/);
  assert.match(source, /DitheringShapes\.warp/);
  assert.match(source, /DitheringTypes\['4x4'\]/);
  assert.match(source, /u_pxSize:\s*3/);
  assert.match(source, /speed:\s*0\.14/);
  assert.match(source, /prefers-reduced-motion/);
  assert.match(source, /mount\.dispose\(\)/);
  assert.doesNotMatch(source, /https?:\/\//);
});

test('catalog background does not react to pointer movement', async () => {
  const source = await read('paper-dithering-background.js');

  assert.doesNotMatch(source, /pointermove/);
  assert.doesNotMatch(source, /clientX|clientY/);
  assert.doesNotMatch(source, /style\.setProperty\(['"]--dither-[xy]/);
});

test('static gradient remains the fallback when Paper Dithering cannot initialize', async () => {
  const html = await read('circular-gallery-preview.html');
  const source = await read('paper-dithering-background.js');

  assert.match(html, /\[data-spectral-flow\]\{[^}]*background:/s);
  assert.match(source, /dataset\.ditherState = 'ready'/);
  assert.match(source, /dataset\.ditherState = 'fallback'/);
  assert.match(source, /catch \(error\)/);
});

test('balanced layering keeps the Paper back color transparent and the ink restrained', async () => {
  const html = await read('circular-gallery-preview.html');
  const source = await read('paper-dithering-background.js');

  assert.match(source, /u_colorBack: getShaderColorFromString\('#d7e7e800'\)/);
  assert.match(source, /u_colorFront: getShaderColorFromString\('#2aaab866'\)/);
  assert.match(html, /\[data-spectral-flow\] canvas\{[^}]*opacity:\.56/s);
});

test('mobile view reduces dither opacity so product facts remain dominant', async () => {
  const html = await read('circular-gallery-preview.html');

  assert.match(
    html,
    /@media\(max-width:620px\)\{.*?\[data-spectral-flow\] canvas\{opacity:\.34\}/s,
  );
});

test('homepage routes every product-catalog entry to the new Paper Dithering preview', async () => {
  const homepage = await read('../2026-08-06-homepage-authority/index.html');
  const catalog = await read('circular-gallery-preview.html');
  const newCatalog = '../2026-08-08-paper-dithering-catalog/circular-gallery-preview.html';

  assert.equal(homepage.split(newCatalog).length - 1, 4);
  assert.doesNotMatch(
    homepage,
    /showcase-baselines\/2026-08-05-before-authority-redesign\/circular-gallery-preview\.html/,
  );
  assert.match(catalog, /href="\.\.\/2026-08-06-homepage-authority\/index\.html#home"/);
  assert.match(catalog, /href="\.\.\/2026-08-06-homepage-authority\/index\.html#quality"/);
  assert.doesNotMatch(catalog, /href="\.\/curated-four-scene-v6\.html/);
});

test('frozen catalog baseline remains byte-for-byte unchanged', async () => {
  const baseline = await readBuffer(
    '../../showcase-baselines/2026-08-05-before-authority-redesign/circular-gallery-preview.html',
  );
  const sha256 = createHash('sha256').update(baseline).digest('hex').toUpperCase();

  assert.equal(
    sha256,
    'ABA1D031CAECF76F5B8C69B1647A2992EA028922B08511C22BAC7A75129DB01E',
  );
});
