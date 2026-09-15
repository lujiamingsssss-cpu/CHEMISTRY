export function createFrameScheduler({ requestFrame, cancelFrame }) {
  const states = new Map();
  let frame = 0;
  let paused = false;

  const runnable = (state) => state.ready && state.visible;
  const hasRunnableJob = () => [...states.values()].some(runnable);
  const cancelPending = () => {
    if (frame) cancelFrame(frame);
    frame = 0;
  };
  const reconcile = () => {
    if (paused || !hasRunnableJob()) {
      cancelPending();
      return;
    }
    if (!frame) frame = requestFrame(tick);
  };
  const tick = (time) => {
    frame = 0;
    if (paused) return;
    states.forEach((state, job) => {
      if (runnable(state)) job.render(time);
    });
    reconcile();
  };

  return {
    add(job, initial = {}) {
      states.set(job, {
        ready: Boolean(initial.ready),
        visible: Boolean(initial.visible),
      });
      reconcile();
    },
    remove(job) {
      states.delete(job);
      reconcile();
    },
    setReady(job, ready) {
      const state = states.get(job);
      if (!state) return;
      state.ready = Boolean(ready);
      reconcile();
    },
    setVisible(job, visible) {
      const state = states.get(job);
      if (!state) return;
      state.visible = Boolean(visible);
      reconcile();
    },
    pause() {
      paused = true;
      cancelPending();
    },
    resume() {
      paused = false;
      reconcile();
    },
    request() {
      reconcile();
    },
  };
}
