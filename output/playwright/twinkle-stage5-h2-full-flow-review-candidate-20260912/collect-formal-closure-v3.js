async (page) => {
  const repo = 'F:/半导体材料产品展示/.worktrees/twinkle-stage5-integration';
  const evidenceRoot = `${repo}/output/playwright/twinkle-stage5-h2-full-flow-review`;
  const captureRoot = `${repo}/output/playwright/twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2`;
  const captureRelative = 'output/playwright/twinkle-stage5-h2-diagnostic-first-closure-v3-20260914-v2';
  const formalUrl = 'http://127.0.0.1:8765/output/twinkle-stage5-h2-full-flow-review/index.html';
  const screenshotNames = {
    condenser: 'condenser-1280x800-closure-v3.png',
    chamber: 'chamber-900x700-closure-v3.png',
  };
  const OUTCOME_STATUSES = new Set(['pass', 'fail', 'blocked', 'error']);
  const outcomes = [];
  const recordOutcome = (id, status, detail = {}) => {
    if (!OUTCOME_STATUSES.has(status)) throw new Error(`invalid outcome status ${status}`);
    const outcome = {id, status, detail};
    outcomes.push(outcome);
    return outcome;
  };
  const recordContract = (id, machinePassed, detail = {}, available = true) => {
    const outcome = available
      ? {id, status: machinePassed ? 'pass' : 'fail', detail}
      : {id, status: 'blocked', detail};
    return recordOutcome(outcome.id, outcome.status, outcome.detail);
  };
  const errors = {console: [], page: [], request: [], response: []};
  const expectedErrors = {console: [], request: []};
  let recoveryActive = false;
  const recoveryNeedle = 'dual_channel_collection_optics_chamber--entry-006--A/focus-000.png';
  const expectedRecoveryError = value => recoveryActive && String(value).includes(recoveryNeedle);
  page.on('console', message => {
    const expectedAbortConsole = recoveryActive
      && message.text() === 'Failed to load resource: net::ERR_FAILED';
    if (message.type() === 'error' && expectedAbortConsole) {
      expectedErrors.console.push({message: message.text(), abortCount: expectedAbortCount});
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
    if (response.status() >= 400 && !expectedRecoveryError(response.url())) errors.response.push(`${response.status()} ${response.url()}`);
  });

  const snapshot = () => page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__.snapshot());
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
      throw new Error(
        `waitPhase timeout label=${label} expected=${phase} actual=${state?.phase || 'unavailable'} `
          + `route=${state?.routeId || 'none'} ready=${state?.ready ?? 'unavailable'} busy=${state?.busy ?? 'unavailable'}`,
        {cause: error},
      );
    }
  };
  const waitInteractiveOverview = async label => {
    await waitReady();
    await waitPhase('overview', `${label} interactive-overview`);
  };
  const emulateMediaAndWaitForAutomaticReload = async (reducedMotion, label) => {
    const mainFrameNavigation = page.waitForEvent('framenavigated', frame => frame === page.mainFrame());
    await Promise.all([mainFrameNavigation, page.emulateMedia({reducedMotion})]);
    await page.waitForLoadState('load');
    await waitInteractiveOverview(`${label} automatic-reload`);
  };
  const boundedRecoverOverview = async label => {
    const attempts = [];
    try {
      const state = await snapshot();
      if (state.ready === true && state.phase === 'overview') {
        return {recovered: true, method: 'already-overview', attempts};
      }
      const reversed = await page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__?.strictReverse?.() || false);
      attempts.push({method: 'strict-reverse', accepted: reversed === true});
      if (reversed === true) {
        await waitPhase('overview', `${label} bounded-recovery-reverse`);
        return {recovered: true, method: 'strict-reverse', attempts};
      }
    } catch (error) {
      attempts.push({method: 'strict-reverse', error: String(error)});
    }
    try {
      await page.reload({waitUntil: 'load'});
      await waitInteractiveOverview(`${label} bounded-recovery-reload`);
      attempts.push({method: 'single-reload', accepted: true});
      return {recovered: true, method: 'single-reload', attempts};
    } catch (error) {
      attempts.push({method: 'single-reload', error: String(error)});
      return {recovered: false, method: null, attempts};
    }
  };
  const routes = () => page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__.runtimeRoutes());
  const prepareRoute = async route => {
    await page.evaluate(target => {
      const api = window.__TWINKLE_H2_FULL_FLOW__;
      for (const record of api.runtimeRoutes()) {
        if (record.unit === target.unit) api.setRouteReadiness(record.routeId, record.routeId === target.routeId);
      }
      api.setOverviewFrame(target.entryFrame);
    }, route);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  };
  const resetRouteReadiness = route => page.evaluate(target => {
    const api = window.__TWINKLE_H2_FULL_FLOW__;
    for (const record of api.runtimeRoutes()) {
      if (record.unit === target.unit) api.setRouteReadiness(record.routeId, true);
    }
  }, route);
  const setPhaseAudit = () => page.evaluate(() => {
    const audit = window.__H2_CLOSURE_PHASE_AUDIT__ = {
      turn: false, focus: false, mechanical: false, handoff: false,
      inspection: false, explanation: false, return: false,
    };
    const patterns = [
      ['turn', phase => phase === 'turn'],
      ['focus', phase => phase === 'focus'],
      ['mechanical', phase => phase === 'mechanical-expand'],
      ['handoff', phase => phase === 'handoff'],
      ['inspection', phase => phase === 'inspection-enter'],
      ['explanation', phase => phase === 'explanation-enter'],
      ['return', phase => phase === 'explanation-return'],
    ];
    const probe = () => {
      const before = window.__TWINKLE_H2_FULL_FLOW__.snapshot();
      for (const [key, matches] of patterns) {
        if (!audit[key] && matches(before.phase)) {
          document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
          const after = window.__TWINKLE_H2_FULL_FLOW__.snapshot();
          audit[key] = after.phase === before.phase && after.busy === before.busy && after.routeId === before.routeId;
        }
      }
    };
    const observer = new MutationObserver(probe);
    observer.observe(document.querySelector('#flowStatus'), {childList: true, subtree: true, characterData: true});
    window.__H2_CLOSURE_PHASE_AUDIT_STOP__ = () => observer.disconnect();
  });
  const readPhaseAudit = () => page.evaluate(() => {
    window.__H2_CLOSURE_PHASE_AUDIT_STOP__?.();
    return {...window.__H2_CLOSURE_PHASE_AUDIT__};
  });
  const layoutCheck = async viewport => page.evaluate(size => {
    const iframe = document.querySelector('#overviewPlayer');
    const overview = iframe.getBoundingClientRect();
    const reference = document.querySelector('#singleShell .reference-layer').getBoundingClientRect();
    const frame = iframe.contentDocument.querySelector('#orbit-frame');
    const frameStyle = iframe.contentWindow.getComputedStyle(frame);
    const viewportStyle = iframe.contentWindow.getComputedStyle(frame.parentElement);
    const covers = rect => rect.left <= .5 && rect.top <= .5 && rect.right >= innerWidth - .5 && rect.bottom >= innerHeight - .5;
    const record = {
      viewport: size,
      noHorizontalScroll: document.documentElement.scrollWidth <= innerWidth,
      noVerticalScroll: document.documentElement.scrollHeight <= innerHeight,
      overviewCovers: covers(overview),
      overviewObjectFit: frameStyle.objectFit,
      letterboxBackgroundImage: viewportStyle.backgroundImage,
      letterboxBackgroundColor: viewportStyle.backgroundColor,
      referenceCovers: covers(reference),
      referenceHasExpectedCrop: reference.width >= innerWidth && reference.height >= innerHeight,
      overflow: getComputedStyle(document.documentElement).overflow,
    };
    record.machinePassed = record.noHorizontalScroll && record.noVerticalScroll && record.overviewCovers
      && record.overviewObjectFit === 'contain' && record.letterboxBackgroundImage === 'none'
      && record.letterboxBackgroundColor === 'rgb(233, 234, 233)'
      && record.referenceCovers && record.referenceHasExpectedCrop && record.overflow === 'hidden';
    return record;
  }, viewport);

  await page.goto(formalUrl, {waitUntil: 'load'});
  await waitInteractiveOverview('initial-load');
  await page.bringToFront();
  await page.setViewportSize({width: 1280, height: 800});

  const speedRoute = (await routes()).find(route => route.routeId.endsWith('entry-006--A'));
  await prepareRoute(speedRoute);
  const speedButton = page.frameLocator('#overviewPlayer').locator(`[data-unit="${speedRoute.unit}"]:not([disabled])`);
  await speedButton.waitFor({state: 'visible', timeout: 10000});
  await page.waitForFunction(() => Math.abs(document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor - 1) < .01);
  const beforeTarget = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().targetSpeedFactor);
  await speedButton.hover();
  const enterSamples = [];
  for (const delay of [0, 30, 30, 30, 40]) {
    if (delay) await page.waitForTimeout(delay);
    enterSamples.push(await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor));
  }
  const steadyTarget = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().targetSpeedFactor);
  const transitionA = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor);
  await speedButton.focus();
  const transitionB = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor);
  await page.mouse.move(1270, 10);
  await page.waitForTimeout(20);
  const transitionC = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor);
  await page.waitForTimeout(100);
  const focusHoverOverlapTarget = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().targetSpeedFactor);
  await speedButton.evaluate(element => element.blur());
  await speedButton.focus();
  await speedButton.hover();
  await page.waitForTimeout(130);
  await speedButton.hover();
  await speedButton.evaluate(element => {
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
  await speedButton.evaluate(element => element.blur());
  const grace90Sample = await speedButton.evaluate(
    element => element.ownerDocument.defaultView.__TWINKLE_H2_GRACE90_SAMPLE__,
  );
  const grace90 = grace90Sample.current;
  const grace90Target = grace90Sample.target;
  const grace90ElapsedMs = grace90Sample.elapsedMs;
  await page.waitForTimeout(220);
  const recovered = await page.evaluate(() => document.querySelector('#overviewPlayer').contentWindow.__twinkleA192.snapshot().currentSpeedFactor);
  const hotspotSpeed = {
    beforeTarget, enterDurationMs: 120, steadyTarget, leaveGraceMs: 100, recoveryDurationMs: 180,
    enterSamples, grace90, grace90Target, grace90ElapsedMs, recovered,
    rapidTransitionJumps: [Math.abs(transitionB - transitionA), Math.abs(transitionC - transitionB)],
    focusHoverOverlapTarget,
    focusHoverOverlapPassed: focusHoverOverlapTarget === .67,
  };
  hotspotSpeed.machinePassed = beforeTarget === 1 && steadyTarget === .67
    && grace90Sample.machinePassed && Math.abs(recovered - 1) < .03
    && Math.max(...hotspotSpeed.rapidTransitionJumps) < .03 && hotspotSpeed.focusHoverOverlapPassed;

  const routeSelectionRuns = [];
  const components = {};
  const layoutObservations = [];
  let repeatedTriggerPassed = false;
  let phaseInterruptions = null;
  let evidenceTrusted = true;
  const plannedRoutes = await routes();
  for (const route of plannedRoutes) {
    const isChamberShot = route.routeId.endsWith('entry-006--A');
    const isCondenserShot = route.routeId.endsWith('entry-000--full-quality-candidate');
    try {
      await page.setViewportSize(isChamberShot ? {width: 900, height: 700} : {width: 1280, height: 800});
      await prepareRoute(route);
      if (route.routeId.endsWith('entry-074--full-quality-candidate')) await setPhaseAudit();
      let entered = false;
      if (route.routeId.endsWith('entry-006--A')) {
        const button = page.frameLocator('#overviewPlayer').locator(`[data-unit="${route.unit}"]:not([disabled])`);
        await button.waitFor({state: 'visible', timeout: 10000});
        await button.click();
        entered = true;
      } else if (route.routeId.endsWith('entry-065--B')) {
        entered = await page.evaluate(unit => window.__TWINKLE_H2_FULL_FLOW__.enter(unit), route.unit);
      } else if (route.routeId.endsWith('entry-087--A')) {
        const repeated = await page.evaluate(async unit => {
          const api = window.__TWINKLE_H2_FULL_FLOW__;
          const first = api.enter(unit);
          const second = await api.enter(unit);
          return {first: await first, second};
        }, route.unit);
        entered = repeated.first;
        repeatedTriggerPassed = repeated.first === true && repeated.second === false;
      } else {
        entered = await page.evaluate(unit => window.__TWINKLE_H2_FULL_FLOW__.enter(unit), route.unit);
      }
      await waitPhase('explanation-stable', `route=${route.routeId} forward`);
      const stable = await snapshot();
      let layout = null;
      if (isChamberShot || isCondenserShot) {
        const viewport = isChamberShot ? [900, 700] : [1280, 800];
        layout = await layoutCheck(viewport);
        layoutObservations.push(layout);
        const key = isChamberShot ? 'chamber' : 'condenser';
        await page.screenshot({path: `${captureRoot}/${screenshotNames[key]}`});
        components[key] = {
          machinePassed: stable.phase === 'explanation-stable' && stable.routeId === route.routeId,
          routeId: route.routeId,
          clickToFocusCompleteMs: stable.metrics.clickToFocusCompleteMs,
          completeEnterMs: stable.metrics.completeEnterMs,
        };
      }
      await page.locator('#flowReturn').click();
      await waitPhase('overview', `route=${route.routeId} reverse`);
      const returned = await snapshot();
      if (route.routeId.endsWith('entry-074--full-quality-candidate')) phaseInterruptions = await readPhaseAudit();
      if (isChamberShot || isCondenserShot) {
        const key = isChamberShot ? 'chamber' : 'condenser';
        components[key].returnedOverviewFrame = returned.currentOverviewFrame;
      }
      const geometryOk = values => values && Object.values(values).every(value => value <= .5);
      const forwardPassed = entered === true && stable.phase === 'explanation-stable'
        && stable.routeId === route.routeId && stable.errors.length === 0
        && stable.handoff.frameGapMs < 34 && geometryOk(stable.handoff.referenceDelta);
      const reversePassed = returned.phase === 'overview' && returned.currentOverviewFrame === route.entryFrame
        && returned.errors.length === 0 && returned.handoff.reverseFrameGapMs < 34
        && geometryOk(returned.handoff.reverseReferenceDelta);
      routeSelectionRuns.push({
        startFrame: route.entryFrame, entryFrame: route.entryFrame, unit: route.unit, routeId: route.routeId,
        returnedFrame: returned.currentOverviewFrame,
        handoffFrameGapMs: stable.handoff.frameGapMs,
        reverseHandoffFrameGapMs: returned.handoff.reverseFrameGapMs,
        forwardPassed, reversePassed, machinePassed: forwardPassed && reversePassed,
      });
    } catch (error) {
      const recovery = await boundedRecoverOverview(`route=${route.routeId}`);
      recordOutcome(`route:${route.routeId}`, 'error', {error: String(error), recovery});
      routeSelectionRuns.push({
        startFrame: route.entryFrame, entryFrame: route.entryFrame, unit: route.unit, routeId: route.routeId,
        returnedFrame: null, forwardPassed: false, reversePassed: false, machinePassed: false,
        error: String(error), recovery,
      });
      if (!recovery.recovered) evidenceTrusted = false;
    } finally {
      await resetRouteReadiness(route).catch(() => {});
    }
    if (!evidenceTrusted) break;
  }

  await emulateMediaAndWaitForAutomaticReload('reduce', 'reduced-motion');
  const reducedRoute = (await routes()).find(route => route.routeId.endsWith('entry-000--full-quality-candidate'));
  await prepareRoute(reducedRoute);
  const reducedStarted = Date.now();
  const reducedEntered = await page.evaluate(unit => window.__TWINKLE_H2_FULL_FLOW__.enter(unit), reducedRoute.unit);
  await waitPhase('explanation-stable', `reduced-motion route=${reducedRoute.routeId} forward`);
  const reducedStable = await snapshot();
  const reducedReversed = await page.evaluate(() => window.__TWINKLE_H2_FULL_FLOW__.strictReverse());
  await waitPhase('overview', `reduced-motion route=${reducedRoute.routeId} reverse`);
  const reducedReturned = await snapshot();
  const reducedMotion = {
    stablePhase: reducedStable.phase,
    completeRoundTripMs: Date.now() - reducedStarted,
    returnedOverviewFrame: reducedReturned.currentOverviewFrame,
    machinePassed: reducedEntered === true && reducedReversed === true
      && reducedStable.phase === 'explanation-stable' && reducedReturned.currentOverviewFrame === reducedRoute.entryFrame,
  };
  await emulateMediaAndWaitForAutomaticReload('no-preference', 'normal-motion');

  await page.evaluate(async () => { for (const key of await caches.keys()) await caches.delete(key); });
  let expectedAbortCount = 0;
  const recoveryPattern = `**/${recoveryNeedle}`;
  const abortTarget = async route => {
    expectedAbortCount += 1;
    await route.abort('failed');
  };
  await page.route(recoveryPattern, abortTarget);
  recoveryActive = true;
  await page.reload({waitUntil: 'load'});
  await waitPhase('error', 'resource-recovery expected failure', 120000);
  const failedState = await snapshot();
  await page.unroute(recoveryPattern, abortTarget);
  await page.evaluate(async () => { for (const key of await caches.keys()) await caches.delete(key); });
  await page.reload({waitUntil: 'load'});
  await waitInteractiveOverview('resource-recovery-reload');
  recoveryActive = false;
  const recoveredState = await snapshot();
  const resourceRecovery = {
    abortCount: expectedAbortCount,
    failureObserved: expectedAbortCount >= 1 && failedState.ready === false && failedState.phase === 'error',
    recovered: recoveredState.ready === true && recoveredState.phase === 'overview',
  };
  resourceRecovery.machinePassed = resourceRecovery.failureObserved && resourceRecovery.recovered;

  await page.waitForTimeout(1000);
  const finalRoutes = await routes();
  const focusTiming = {
    settledHoldMs: 100,
    routes: finalRoutes.map(route => [route.routeId, route.oldFocusDurationMs, route.newFocusDurationMs]),
  };
  const hashUrl = relative => page.evaluate(async url => {
    const response = await fetch(url, {cache: 'no-store'});
    if (!response.ok) throw new Error(`hash fetch failed: ${response.status} ${url}`);
    const digest = await crypto.subtle.digest('SHA-256', await response.arrayBuffer());
    return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('').toUpperCase();
  }, `http://127.0.0.1:8765/${relative}`);
  const imageComparison = async (currentUrl, baselineUrl) => page.evaluate(async ([current, baseline]) => {
    const pixels = async url => {
      const bitmap = await createImageBitmap(await (await fetch(url)).blob());
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      const context = canvas.getContext('2d'); context.drawImage(bitmap, 0, 0);
      const data = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      const result = {size: [bitmap.width, bitmap.height], data: Array.from(data)};
      bitmap.close(); return result;
    };
    const a = await pixels(current), b = await pixels(baseline);
    if (a.size[0] !== b.size[0] || a.size[1] !== b.size[1]) return {newSize: a.size, baselineSize: b.size, rmse: Infinity};
    let sum = 0, count = 0;
    for (let index = 0; index < a.data.length; index += 4) {
      for (let channel = 0; channel < 3; channel += 1) {
        const delta = a.data[index + channel] - b.data[index + channel]; sum += delta * delta; count += 1;
      }
    }
    return {newSize: a.size, baselineSize: b.size, rmse: Math.sqrt(sum / count)};
  }, [currentUrl, baselineUrl]);
  const base = 'http://127.0.0.1:8765/';
  const approvedBaselineComparison = {
    condenser: await imageComparison(
      `${base}${captureRelative}/${screenshotNames.condenser}`,
      `${base}output/playwright/twinkle-full-quality-1280-condenser-b.png`,
    ),
    chamber: await imageComparison(
      `${base}${captureRelative}/${screenshotNames.chamber}`,
      `${base}output/playwright/twinkle-full-quality-900-chamber-b.png`,
    ),
  };
  const screenshots = {
    condenser: {name: screenshotNames.condenser, viewport: [1280, 800], sha256: await hashUrl(`${captureRelative}/${screenshotNames.condenser}`)},
    chamber: {name: screenshotNames.chamber, viewport: [900, 700], sha256: await hashUrl(`${captureRelative}/${screenshotNames.chamber}`)},
  };
  const interactionSafety = {
    strictReversePassed: routeSelectionRuns.every(record => record.reversePassed),
    repeatedTriggerPassed,
    entryMethods: {hotspot: routeSelectionRuns[0].forwardPassed, fixedName: routeSelectionRuns[1].forwardPassed, realPointer: routeSelectionRuns[0].forwardPassed},
    phaseInterruptions,
  };
  recordContract('hotspot-speed', hotspotSpeed.machinePassed, hotspotSpeed);
  for (const route of plannedRoutes) {
    const id = `route:${route.routeId}`;
    if (outcomes.some(outcome => outcome.id === id)) continue;
    const observation = routeSelectionRuns.find(record => record.routeId === route.routeId);
    recordContract(id, observation?.machinePassed === true, observation || {routeId: route.routeId}, Boolean(observation));
  }
  const allInterruptionsPassed = interactionSafety.phaseInterruptions
    && Object.values(interactionSafety.phaseInterruptions).every(Boolean);
  const interactionPassed = interactionSafety.strictReversePassed && interactionSafety.repeatedTriggerPassed
    && Object.values(interactionSafety.entryMethods).every(Boolean) && allInterruptionsPassed;
  recordContract('interaction-safety', interactionPassed, interactionSafety);
  recordContract('reduced-motion', reducedMotion.machinePassed, reducedMotion);
  recordContract('resource-recovery', resourceRecovery.machinePassed, resourceRecovery);
  for (const viewport of [[1280, 800], [900, 700]]) {
    const observation = layoutObservations.find(record => record.viewport[0] === viewport[0] && record.viewport[1] === viewport[1]);
    recordContract(`layout:${viewport.join('x')}`, observation?.machinePassed === true, observation || {viewport}, Boolean(observation));
  }
  recordContract('error-closure', Object.values(errors).every(values => values.length === 0), errors);
  recordContract('screenshots', Object.keys(screenshots).length === 2, screenshots, Object.keys(screenshots).length === 2);
  const outcomeSummary = {pass: 0, fail: 0, blocked: 0, error: 0};
  for (const outcome of outcomes) outcomeSummary[outcome.status] += 1;
  const result = {
    schema: 'twinkle-stage5-h2-full-flow-browser-results-v2',
    machinePassed: false,
    failures: [], errors, expectedErrors, outcomes, outcomeSummary,
    viewports: [[1280, 800], [900, 700]],
    closure: {
      reviewManifestSha256: await hashUrl('output/twinkle-stage5-h2-full-flow-review/review-manifest.json'),
      reviewPageSha256: await hashUrl('output/twinkle-stage5-h2-full-flow-review/index.html'),
    },
    approvedSemanticReturnSha256: await hashUrl('output/playwright/twinkle-stage5-h2-full-flow-review/twinkle-v18-semantic-return-review.gif'),
    approvedVisualBaselines: {
      condenser: await hashUrl('output/playwright/twinkle-full-quality-1280-condenser-b.png'),
      chamber: await hashUrl('output/playwright/twinkle-full-quality-900-chamber-b.png'),
    },
    negativeControls: {
      condenser: await hashUrl('output/playwright/twinkle-stage5-h2-full-flow-review/condenser-1280x800-stable.png'),
      chamber: await hashUrl('output/playwright/twinkle-stage5-h2-full-flow-review/chamber-900x700-stable.png'),
    },
    focusTiming,
    routeSelectionCoverage: routeSelectionRuns.map(record => record.routeId),
    routeSelectionRuns,
    components,
    hotspotSpeed,
    interactionSafety,
    reducedMotion,
    resourceRecovery,
    layoutChecks: layoutObservations,
    approvedBaselineComparison,
    screenshots,
    finalErrorObservationMs: 1000,
    diagnosticExpectedNavigationAborts: expectedAbortCount,
  };
  result.machinePassed = result.routeSelectionCoverage.length === 10
    && new Set(result.routeSelectionCoverage).size === 10
    && result.routeSelectionRuns.every(record => record.machinePassed)
    && interactionSafety.strictReversePassed && interactionSafety.repeatedTriggerPassed
    && Object.values(interactionSafety.entryMethods).every(Boolean) && allInterruptionsPassed
    && reducedMotion.machinePassed && resourceRecovery.machinePassed && hotspotSpeed.machinePassed
    && result.layoutChecks.every(record => record.machinePassed)
    && Object.values(errors).every(values => values.length === 0)
    && outcomeSummary.fail === 0 && outcomeSummary.blocked === 0 && outcomeSummary.error === 0;
  result.failures = outcomes
    .filter(outcome => outcome.status !== 'pass')
    .map(outcome => `${outcome.status}:${outcome.id}`);
  return result;
}
