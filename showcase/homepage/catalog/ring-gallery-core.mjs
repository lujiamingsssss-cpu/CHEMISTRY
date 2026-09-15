const TAU = Math.PI * 2;

export function circularPosition(index, itemCount, rotation, { radiusX, radiusZ }) {
  const angle = (index / itemCount) * TAU + rotation;
  return {
    angle,
    x: Math.sin(angle) * radiusX,
    z: Math.cos(angle) * radiusZ,
    facing: -angle || 0,
  };
}

export function stepInertia(current, target, easing) {
  return current + (target - current) * easing;
}

export function closestItemIndex(rotation, itemCount) {
  const step = TAU / itemCount;
  return ((Math.round(-rotation / step) % itemCount) + itemCount) % itemCount;
}

export function snapRotation(rotation, itemCount) {
  const step = TAU / itemCount;
  return Math.round(rotation / step) * step;
}

export function arcPosition(x, viewportHalfWidth, bend) {
  if (!bend) return { y: 0, rotation: 0 };
  const depth = Math.abs(bend);
  const radius = (viewportHalfWidth ** 2 + depth ** 2) / (2 * depth);
  const effectiveX = Math.min(Math.abs(x), viewportHalfWidth);
  const arc = radius - Math.sqrt(Math.max(0, radius ** 2 - effectiveX ** 2));
  const sign = bend > 0 ? -1 : 1;
  return {
    y: sign * arc || 0,
    rotation: sign * Math.sign(x) * Math.asin(effectiveX / radius) || 0,
  };
}

export function wrapPosition(x, cycleWidth) {
  return ((((x + cycleWidth / 2) % cycleWidth) + cycleWidth) % cycleWidth) - cycleWidth / 2;
}

export function targetRotationForItem(currentRotation, itemIndex, itemWidth, cycleWidth) {
  const currentX = wrapPosition(itemIndex * itemWidth - currentRotation, cycleWidth);
  return currentRotation + currentX;
}

export function rotationForDrag(
  startTarget,
  dragDistance,
  itemWidth,
  itemPixelWidth,
  touchRatio = 1,
) {
  return startTarget - (dragDistance / Math.max(1, itemPixelWidth)) * itemWidth * touchRatio;
}

export function targetRotationForRelease(
  startTarget,
  dragDistance,
  velocityPxPerMs,
  itemWidth,
  itemPixelWidth,
  { clickThreshold = 6, momentumMs = 180, maxItems = 4 } = {},
) {
  if (Math.abs(dragDistance) <= clickThreshold) return startTarget;
  const direction = Math.sign(dragDistance);
  const alignedVelocity = Math.max(0, velocityPxPerMs * direction);
  const projectedDistance = Math.abs(dragDistance) + alignedVelocity * momentumMs;
  const itemCount = Math.min(
    maxItems,
    Math.max(1, Math.ceil(projectedDistance / Math.max(1, itemPixelWidth))),
  );
  return startTarget - direction * itemWidth * itemCount;
}

export function softenVelocity(rawVelocity, gain = 6, limit = 0.72) {
  return Math.max(-limit, Math.min(limit, rawVelocity * gain));
}
