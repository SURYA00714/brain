/**
 * Liqu Desktop Companion - Procedural Motion Reference
 * Source: https://github.com/CameronCodesStuff/liqu-companion
 * Author: CameronCodesStuff
 * File: src/renderer/companion.js (lines 1101-1230)
 * Note: Preserved for algorithmic reference (layered breathing, weight shifting, quaternion slerp).
 */

  Object.entries(POSES).forEach(([key, def]) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = def.label;
    sel.appendChild(opt);
  });
  sel.value = behavior;
})();

function computePoseTargets(t, el) {
  const targets = {};
  TRACKED_BONES.forEach((n) => (targets[n] = { ...BASE_POSE[n] }));

  const def = POSES[behavior] || POSES.idle;
  if (def.freeze) return null;

  const amp = asleep ? 0.4 : 1;

  const breathe = (Math.sin(t * 1.1 * swaySpeed) + Math.sin(t * 1.7 * swaySpeed + 0.6) * 0.4) * 0.022 * amp;
  const sway = (Math.sin(t * 0.45 * swaySpeed) + Math.sin(t * 0.8 * swaySpeed + 1.1) * 0.35) * 0.06 * amp;
  const weight = Math.sin(t * 0.16 * swaySpeed) * 0.1 * amp;
  const weightFast = Math.sin(t * 0.33 * swaySpeed + 0.7) * 0.03 * amp;
  const drift = Math.sin(t * 0.7 + 1.3) * 0.03 * amp;
  const driftSlow = Math.sin(t * 0.27 + 2.4) * 0.04 * amp;
  const microL = (Math.sin(t * 1.9 + 0.5) + Math.sin(t * 3.1 + 1.7) * 0.4) * 0.018 * amp;
  const microR = (Math.sin(t * 1.7 + 2.1) + Math.sin(t * 2.9 + 0.3) * 0.4) * 0.018 * amp;

  add(targets, 'chest', breathe * 0.7, sway * 0.15, breathe + weightFast * 0.3);
  add(targets, 'spine', breathe * 0.35, sway * 0.45, weight * 0.55);
  add(targets, 'hips', weightFast * 0.4, sway * 0.1, weight);

  add(targets, 'leftUpperLeg', 0, 0, weight * 0.5 - weightFast * 0.2);
  add(targets, 'rightUpperLeg', 0, 0, weight * 0.5 + weightFast * 0.2);
  add(targets, 'leftLowerLeg', Math.max(0, -weight) * 0.5, 0, 0);
  add(targets, 'rightLowerLeg', Math.max(0, weight) * 0.5, 0, 0);

  add(targets, 'leftUpperArm', microL + driftSlow * 0.3, drift * 0.5, sway * 0.12 + drift + breathe * 0.5);
  add(targets, 'rightUpperArm', microR - driftSlow * 0.3, -drift * 0.5, -sway * 0.12 - drift - breathe * 0.5);
  add(targets, 'leftLowerArm', microL * 1.5, microL * 2.5 + driftSlow, drift * 0.4);
  add(targets, 'rightLowerArm', microR * 1.5, -microR * 2.5 - driftSlow, -drift * 0.4);
  add(targets, 'leftHand', 0, microL * 3, microL * 2);
  add(targets, 'rightHand', 0, -microR * 3, -microR * 2);

  const eyeYaw = cursorX * 0.4;
  const eyePitch = -cursorY * 0.25;

  if (asleep) {
    add(targets, 'head', 0.35 + breathe, sway * 0.2, 0.1);
  } else {

    add(targets, 'head', breathe * 0.6 + eyePitch + driftSlow * 0.3, sway * 0.7 + eyeYaw - weight * 0.35, weight * 0.45 + sway * 0.1);
  }

  if (!asleep) def.fn(t, el, targets);

  if (!asleep && behavior !== 'idle') {
    const lifeBreathe = Math.sin(t * 1.2) * 0.012;
    const lifeSway = Math.sin(t * 0.5 + 0.8) * 0.018;
    add(targets, 'chest', lifeBreathe, 0, lifeBreathe * 0.5);
    add(targets, 'spine', lifeBreathe * 0.4, lifeSway * 0.3, lifeSway * 0.2);
    add(targets, 'head', lifeBreathe * 0.3, lifeSway * 0.4, 0);
    add(targets, 'leftUpperArm', microL * 0.6, 0, microL * 0.4);
    add(targets, 'rightUpperArm', microR * 0.6, 0, -microR * 0.4);
  }

  return targets;
}

let reactionUntil = 0;
stage.addEventListener('mousedown', () => {
  reactionUntil = performance.now() + 260;
  lastInteractionTime = performance.now();
  if (asleep) wakeUp();
  flashExpression('surprised', 700);
});

function wakeUp() {
  asleep = false;
  showBubble('*wakes up*');
}

const clock = new THREE.Clock();
const SMOOTH = 9;

const BONE_EASE = {
  hips: 4, spine: 5, chest: 6,
  head: 8,
  leftUpperArm: 6, rightUpperArm: 6,
  leftLowerArm: 9, rightLowerArm: 9,
  leftHand: 12, rightHand: 12,
  leftUpperLeg: 5, rightUpperLeg: 5,
  leftLowerLeg: 8, rightLowerLeg: 8,
};

function applyPoseSmoothed(dt, t) {
  if (!currentVrm?.humanoid) return;

  const el = t - poseStartTime;

  if (!['dance', 'jump', 'kneel', 'walk'].includes(behavior)) {
    modelGroup.position.y = THREE.MathUtils.lerp(modelGroup.position.y, 0, 1 - Math.exp(-6 * dt));
  }

  const targets = computePoseTargets(t, el);
  if (!targets) return;

  TRACKED_BONES.forEach((name) => {
    const b = bone(name);
    if (!b) return;
    const target = targets[name];
    _targetEuler.set(target.x, target.y, target.z, 'XYZ');
    _targetQuat.setFromEuler(_targetEuler);

    const speed = BONE_EASE[name] || SMOOTH;
    b.quaternion.slerp(_targetQuat, 1 - Math.exp(-speed * dt));
  });

  const now = performance.now();
  const squish = now < reactionUntil ? 0.92 : 1.0;
  const targetScale = (Number($('sizeSlider').value) / 100) * squish;
  modelGroup.scale.setScalar(THREE.MathUtils.lerp(modelGroup.scale.x, targetScale, 1 - Math.exp(-20 * dt)));

  if (currentVrm && !['dance', 'jump', 'kneel'].includes(behavior)) {
    currentVrm.scene.position.y = asleep ? 0 : Math.sin(t * 1.2 * swaySpeed) * 0.01;
  }
}

function applyAmbientWind(t) {
  const manager = currentVrm?.springBoneManager;
  if (!manager?.joints) return;