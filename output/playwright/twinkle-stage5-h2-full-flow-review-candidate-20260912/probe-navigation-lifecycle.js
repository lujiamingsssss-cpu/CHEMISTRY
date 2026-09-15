async (page) => {
  const formalUrl = 'http://127.0.0.1:8765/output/twinkle-stage5-h2-full-flow-review/index.html';
  if (page.url() !== 'about:blank') throw new Error(`navigation probe must start blank, got ${page.url()}`);

  let navigationSequence = 0;
  let stage = 'bootstrap';
  let nextRequestId = 0;
  const requestContexts = new WeakMap();
  const lifecycle = [];
  const recordRequest = (event, request) => {
    if (!requestContexts.has(request)) {
      requestContexts.set(request, {
        requestId: ++nextRequestId,
        startedNavigationSequence: navigationSequence,
        startedStage: stage,
      });
    }
    if (request.resourceType() !== 'document' && event !== 'requestfailed') return;
    const context = requestContexts.get(request);
    lifecycle.push({
      event,
      startedNavigationSequence: context.startedNavigationSequence,
      startedStage: context.startedStage,
      eventNavigationSequence: navigationSequence,
      eventStage: stage,
      requestId: context.requestId,
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType(),
      frame: request.frame() === page.mainFrame() ? 'main' : 'child',
      frameUrl: request.frame().url(),
      failureReason: request.failure()?.errorText || null,
    });
  };
  page.on('request', request => recordRequest('request', request));
  page.on('requestfinished', request => recordRequest('requestfinished', request));
  page.on('requestfailed', request => recordRequest('requestfailed', request));
  page.on('framenavigated', frame => lifecycle.push({
    event: 'framenavigated',
    navigationSequence,
    stage,
    requestId: null,
    url: frame.url(),
    method: null,
    resourceType: 'document',
    frame: frame === page.mainFrame() ? 'main' : 'child',
    frameUrl: frame.url(),
    failureReason: null,
  }));

  const snapshot = () => page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__.snapshot());
  const waitInteractiveOverview = async label => {
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
    lifecycle.push({event: 'interactive', navigationSequence, stage: label, state: await snapshot()});
  };
  const controlledNavigation = async (label, action) => {
    navigationSequence += 1;
    stage = `${label}:start`;
    lifecycle.push({event: 'navigation-start', navigationSequence, stage});
    try {
      await action();
      stage = `${label}:load`;
      lifecycle.push({event: 'navigation-load', navigationSequence, stage, url: page.url()});
    } catch (error) {
      stage = `${label}:error`;
      lifecycle.push({event: 'navigation-error', navigationSequence, stage, failureReason: String(error)});
      throw error;
    }
  };
  const emulateMediaAndWaitForAutomaticReload = async (reducedMotion, label) => {
    navigationSequence += 1;
    stage = `${label}:dispatch`;
    lifecycle.push({event: 'media-change', navigationSequence, stage, reducedMotion});
    const mainFrameNavigation = page.waitForEvent('framenavigated', frame => frame === page.mainFrame());
    await Promise.all([mainFrameNavigation, page.emulateMedia({reducedMotion})]);
    await page.waitForLoadState('load');
    stage = `${label}:load`;
    lifecycle.push({event: 'navigation-load', navigationSequence, stage, url: page.url()});
    await waitInteractiveOverview(`${label}:ready`);
  };

  await controlledNavigation('initial-goto', () => page.goto(formalUrl, {waitUntil: 'load'}));
  await waitInteractiveOverview('initial-ready');
  await emulateMediaAndWaitForAutomaticReload('reduce', 'reduced-motion-change');
  await emulateMediaAndWaitForAutomaticReload('no-preference', 'normal-motion-change');

  await page.evaluate(async () => { for (const key of await caches.keys()) await caches.delete(key); });
  let injectedAbortCount = 0;
  const recoveryNeedle = 'dual_channel_collection_optics_chamber--entry-006--A/focus-000.png';
  const recoveryPattern = `**/${recoveryNeedle}`;
  const abortTarget = async route => {
    injectedAbortCount += 1;
    await route.abort('failed');
  };
  await page.route(recoveryPattern, abortTarget);
  await controlledNavigation('fault-reload', () => page.reload({waitUntil: 'load'}));
  await page.waitForFunction(
    () => window.__TWINKLE_H2_FULL_FLOW__?.snapshot().phase === 'error',
    undefined,
    {timeout: 120000},
  );
  await page.unroute(recoveryPattern, abortTarget);
  await page.evaluate(async () => { for (const key of await caches.keys()) await caches.delete(key); });
  await controlledNavigation('recovery-reload', () => page.reload({waitUntil: 'load'}));
  await waitInteractiveOverview('recovery-ready');

  const failures = lifecycle.filter(record => record.event === 'requestfailed');
  const documentFailures = failures.filter(record => record.resourceType === 'document');
  const injectedFailures = failures.filter(record => record.url.includes(recoveryNeedle));
  const mediaDocumentCounts = Object.fromEntries(
    ['reduced-motion-change', 'normal-motion-change'].map(label => [
      label,
      lifecycle.filter(record => record.event === 'request'
        && record.resourceType === 'document' && record.frame === 'main'
        && record.startedStage === `${label}:dispatch`).length,
    ]),
  );
  return {
    schema: 'twinkle-stage5-h2-navigation-lifecycle-probe-v1',
    machinePassed: documentFailures.length === 0 && injectedAbortCount >= 1
      && injectedFailures.length === injectedAbortCount
      && Object.values(mediaDocumentCounts).every(count => count === 1),
    navigationSequence,
    injectedAbortCount,
    finalState: await snapshot(),
    failures,
    documentFailures,
    injectedFailures,
    mediaDocumentCounts,
    lifecycle,
  };
}
