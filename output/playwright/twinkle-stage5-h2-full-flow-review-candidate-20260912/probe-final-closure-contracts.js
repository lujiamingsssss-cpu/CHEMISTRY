async (page) => {
  const formalUrl = 'http://127.0.0.1:8765/output/twinkle-stage5-h2-full-flow-review/index.html';
  if (page.url() !== 'about:blank') throw new Error(`probe must start blank, got ${page.url()}`);

  const unexpectedRequests = [];
  page.on('requestfailed', request => {
    unexpectedRequests.push({
      url: request.url(),
      error: request.failure()?.errorText || 'failed',
    });
  });
  await page.goto(formalUrl, {waitUntil: 'load'});
  await page.waitForFunction(
    () => window.__TWINKLE_H2_FULL_FLOW__?.snapshot().ready === true,
    undefined,
    {timeout: 120000},
  );
  await page.waitForFunction(
    () => window.__TWINKLE_H2_FULL_FLOW__?.snapshot().phase === 'overview',
    undefined,
    {timeout: 45000},
  );

  const layouts = [];
  for (const viewport of [[1280, 800], [900, 700]]) {
    await page.setViewportSize({width: viewport[0], height: viewport[1]});
    layouts.push(await page.evaluate(size => {
      const iframe = document.querySelector('#overviewPlayer');
      const frame = iframe.contentDocument.querySelector('#orbit-frame');
      const viewportStyle = iframe.contentWindow.getComputedStyle(frame.parentElement);
      const result = {
        viewport: size,
        backgroundImage: viewportStyle.backgroundImage,
        backgroundColor: viewportStyle.backgroundColor,
      };
      result.machinePassed = result.backgroundImage === 'none'
        && result.backgroundColor === 'rgb(233, 234, 233)';
      return result;
    }, viewport));
  }

  await page.setViewportSize({width: 1280, height: 800});
  const route = await page.evaluate(() => {
    const api = window.__TWINKLE_H2_FULL_FLOW__;
    const target = api.runtimeRoutes().find(record => record.routeId.endsWith('entry-006--A'));
    for (const record of api.runtimeRoutes()) {
      if (record.unit === target.unit) api.setRouteReadiness(record.routeId, record.routeId === target.routeId);
    }
    api.setOverviewFrame(target.entryFrame);
    return target;
  });
  const button = page.frameLocator('#overviewPlayer').locator(
    `[data-unit="${route.unit}"]:not([disabled])`,
  );
  await button.waitFor({state: 'visible', timeout: 10000});
  await button.focus();
  await button.hover();
  await page.waitForTimeout(130);
  await button.hover();
  await button.evaluate(element => {
    const playerWindow = element.ownerDocument.defaultView;
    playerWindow.__TWINKLE_H2_GRACE90_SAMPLE__ = new Promise(resolve => {
      element.addEventListener('pointerleave', () => {
        const started = performance.now();
        setTimeout(() => {
          const state = playerWindow.__twinkleA192.snapshot();
          resolve({
            current: state.currentSpeedFactor,
            target: state.targetSpeedFactor,
            elapsedMs: performance.now() - started,
            machinePassed: state.targetSpeedFactor === .67
              && Math.abs(state.currentSpeedFactor - .67) < .03,
          });
        }, 90);
      }, {once: true});
    });
  });
  await page.mouse.move(1270, 10);
  await button.evaluate(element => element.blur());
  const grace90 = await button.evaluate(
    element => element.ownerDocument.defaultView.__TWINKLE_H2_GRACE90_SAMPLE__,
  );
  await page.waitForTimeout(220);
  const recovered = await page.evaluate(() => {
    const state = document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot();
    return {
      current: state.currentSpeedFactor,
      target: state.targetSpeedFactor,
      machinePassed: state.targetSpeedFactor === 1
        && Math.abs(state.currentSpeedFactor - 1) < .03,
    };
  });

  const checks = {
    noUnexpectedRequests: unexpectedRequests.length === 0,
    graceHeld: grace90.machinePassed,
    recoveryRestored: recovered.machinePassed,
    approvedSolidLayouts: layouts.every(record => record.machinePassed),
  };
  const result = {
    unexpectedRequests,
    grace90,
    recovered: {
      current: recovered.current,
      target: recovered.target,
      machinePassed: recovered.machinePassed,
    },
    layouts,
    checks,
  };
  result.machinePassed = Object.values(checks).every(Boolean);
  return result;
}
