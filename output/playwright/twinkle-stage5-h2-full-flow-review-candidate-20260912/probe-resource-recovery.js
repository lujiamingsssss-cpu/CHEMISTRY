async (page) => {
  const formalUrl = 'http://127.0.0.1:8765/output/twinkle-stage5-h2-full-flow-review/index.html';
  const targetRouteId = 'dual_channel_collection_optics_chamber--entry-006--A';
  const recoveryNeedle = 'dual_channel_collection_optics_chamber--entry-006--A/focus-000.png';
  const recoveryPattern = `**/${recoveryNeedle}`;
  const errors = {console: [], page: [], request: [], response: []};
  const expectedErrors = {console: [], request: []};
  const trace = [];
  let faultInjectionActive = false;
  let abortCount = 0;

  const expectedRecoveryError = value => faultInjectionActive && String(value).includes(recoveryNeedle);
  page.on('console', message => {
    const expectedAbortConsole = faultInjectionActive
      && message.text() === 'Failed to load resource: net::ERR_FAILED';
    if (message.type() === 'error' && expectedAbortConsole) {
      expectedErrors.console.push({message: message.text(), abortCount});
    } else if (message.type() === 'error' && !expectedRecoveryError(message.text())) {
      errors.console.push(message.text());
    }
  });
  page.on('pageerror', error => {
    if (!expectedRecoveryError(error)) errors.page.push(String(error));
  });
  page.on('requestfailed', request => {
    if (expectedRecoveryError(request.url())) {
      expectedErrors.request.push({url: request.url(), error: request.failure()?.errorText || 'failed'});
    } else {
      errors.request.push(`${request.failure()?.errorText || 'failed'} ${request.url()}`);
    }
  });
  page.on('response', response => {
    if (response.status() >= 400 && !expectedRecoveryError(response.url())) {
      errors.response.push(`${response.status()} ${response.url()}`);
    }
  });

  const snapshot = () => page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__?.snapshot?.() || null);
  const recordPhase = (label, expected, state) => {
    trace.push({
      kind: 'phase', label, route: state?.routeId || targetRouteId,
      expected, actual: state?.phase || 'unavailable', ready: state?.ready,
      busy: state?.busy, abortCount,
    });
  };
  const fail = (label, expected, actual) => {
    throw new Error(
      `resource-recovery probe failed route=${targetRouteId} phase=${label} `
        + `expected=${expected} actual=${actual} abortCount=${abortCount} trace=${JSON.stringify(trace)}`,
    );
  };
  const waitReady = (timeout = 120000) => page.waitForFunction(
    () => window.__TWINKLE_H2_FULL_FLOW__?.snapshot().ready === true,
    undefined,
    {timeout},
  );
  const waitPhase = async (phase, label, timeout = 45000) => {
    try {
      await page.waitForFunction(
        value => window.__TWINKLE_H2_FULL_FLOW__?.snapshot().phase === value,
        phase,
        {timeout},
      );
    } catch (error) {
      const state = await snapshot().catch(() => null);
      recordPhase(label, phase, state);
      fail(label, phase, state?.phase || 'unavailable');
    }
  };
  const waitInteractiveOverview = async label => {
    await waitReady();
    await waitPhase('overview', `${label} overview`);
  };
  const clearRuntimeCaches = () => page.evaluate(async () => {
    for (const key of await caches.keys()) await caches.delete(key);
  });
  const abortTarget = async route => {
    abortCount += 1;
    trace.push({
      kind: 'abort', route: targetRouteId, phase: 'fault-injection',
      expected: 'request-aborted', actual: route.request().url(), abortCount,
    });
    await route.abort('failed');
  };

  await page.goto(formalUrl, {waitUntil: 'load'});
  await waitInteractiveOverview('initial-load');
  recordPhase('initial-load', 'overview', await snapshot());

  await clearRuntimeCaches();
  await page.route(recoveryPattern, abortTarget);
  faultInjectionActive = true;
  await page.reload({waitUntil: 'load'});
  await waitPhase('error', 'fault-injection', 120000);
  const failedState = await snapshot();
  recordPhase('fault-injection', 'error', failedState);
  if (!(abortCount >= 1 && failedState?.phase === 'error' && failedState?.ready === false)) {
    fail('fault-injection', 'error with ready=false and abortCount>=1', failedState?.phase || 'unavailable');
  }

  await page.unroute(recoveryPattern, abortTarget);
  await clearRuntimeCaches();
  await page.reload({waitUntil: 'load'});
  await waitInteractiveOverview('recovery-reload');
  const recoveredState = await snapshot();
  recordPhase('recovery-reload', 'overview', recoveredState);
  faultInjectionActive = false;

  const errorClosure = Object.values(errors).every(values => values.length === 0)
    && Array.isArray(recoveredState?.errors) && recoveredState.errors.length === 0;
  const result = {
    schema: 'twinkle-stage5-h2-resource-recovery-probe-v1',
    routeId: targetRouteId,
    resource: recoveryNeedle,
    abortCount,
    transition: ['error', 'overview'],
    failedState: {
      phase: failedState.phase, ready: failedState.ready,
      errors: failedState.errors, cacheAvailable: failedState.initialization?.cacheAvailable,
      workerAvailable: failedState.initialization?.workerAvailable,
    },
    recoveredState: {
      phase: recoveredState.phase, ready: recoveredState.ready,
      errors: recoveredState.errors, readyRouteCount: recoveredState.readyRouteIds?.length,
      cacheAvailable: recoveredState.initialization?.cacheAvailable,
      workerAvailable: recoveredState.initialization?.workerAvailable,
    },
    errors,
    expectedErrors,
    trace,
    timeouts: {readyMs: 120000, phaseMs: 45000, errorMs: 120000},
    machinePassed: abortCount >= 1
      && failedState.phase === 'error' && failedState.ready === false
      && recoveredState.phase === 'overview' && recoveredState.ready === true
      && errorClosure,
  };
  if (!result.machinePassed) {
    fail('result', 'error→overview, ready=true, errors closed', JSON.stringify(result));
  }
  return result;
}
