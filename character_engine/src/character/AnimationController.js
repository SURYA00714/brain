import { Logger } from '../logger.js';

/**
 * AnimationController - procedural bone animations for Ao.
 * Supports: idle, walk, run, jump, land, sit, sleep, wave, stretch, yawn,
 *           read, drink, phone, music, pet, confused.
 * All procedural, lightweight, zero asset loading needed.
 */
export class AnimationController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._currentAnim = 'idle';
    this._time = 0;
    this._walkCycle = 0;
  }

  play(name) {
    if (this._currentAnim === name) return;
    this._currentAnim = name;
    this._time = 0;
    this._walkCycle = 0;
  }

  stop() {
    this._currentAnim = 'idle';
    this._time = 0;
  }

  get current() { return this._currentAnim; }

  update(delta) {
    if (!this._vrm.loaded || !this._vrm.capabilities.humanoid) return;
    this._time += delta;

    try {
      switch (this._currentAnim) {
        case 'idle': this._animIdle(delta); break;
        case 'walk': this._animWalk(delta); break;
        case 'run':  this._animRun(delta); break;
        case 'jump': this._animJump(delta); break;
        case 'land': this._animLand(delta); break;
        case 'sit':  this._animSit(delta); break;
        case 'sleep': this._animSleep(delta); break;
        case 'wave': this._animWave(delta); break;
        case 'stretch': this._animStretch(delta); break;
        case 'yawn': this._animYawn(delta); break;
        case 'read': this._animRead(delta); break;
        case 'drink': this._animDrink(delta); break;
        case 'phone': this._animPhone(delta); break;
        case 'music': this._animMusic(delta); break;
        case 'pet': this._animPet(delta); break;
        case 'confused': this._animConfused(delta); break;
        default: this._animIdle(delta);
      }
    } catch (e) {
      Logger.warn('Animation error:', e);
      this._resetPose();
    }
  }

  _animIdle(delta) {
    // Breathing
    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = Math.sin(this._time * 1.5) * 0.015;

    // Arms at rest
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.1, 0.05);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.1, 0.05);

    // Subtle weight shift
    const hips = this._vrm.getBone('hips');
    if (hips) hips.rotation.z = Math.sin(this._time * 0.4) * 0.01;
  }

  _animWalk(delta) {
    this._walkCycle += delta * 5;
    const swing = Math.sin(this._walkCycle) * 0.4;

    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftArm = this._vrm.getBone('leftUpperArm');
    const rightArm = this._vrm.getBone('rightUpperArm');

    if (leftLeg) leftLeg.rotation.x = swing;
    if (rightLeg) rightLeg.rotation.x = -swing;
    if (leftArm) { leftArm.rotation.z = 1.1; leftArm.rotation.x = -swing * 0.3; }
    if (rightArm) { rightArm.rotation.z = -1.1; rightArm.rotation.x = swing * 0.3; }

    // Body bounce
    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = Math.abs(Math.sin(this._walkCycle * 2)) * 0.02;
  }

  _animRun(delta) {
    this._walkCycle += delta * 8;
    const swing = Math.sin(this._walkCycle) * 0.6;

    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftArm = this._vrm.getBone('leftUpperArm');
    const rightArm = this._vrm.getBone('rightUpperArm');

    if (leftLeg) leftLeg.rotation.x = swing;
    if (rightLeg) rightLeg.rotation.x = -swing;
    if (leftArm) { leftArm.rotation.z = 0.8; leftArm.rotation.x = -swing * 0.5; }
    if (rightArm) { rightArm.rotation.z = -0.8; rightArm.rotation.x = swing * 0.5; }

    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = 0.05 + Math.abs(Math.sin(this._walkCycle * 2)) * 0.03;
  }

  _animJump(delta) {
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.8, 0.15);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.8, 0.15);

    // Tuck legs slightly
    const ll = this._vrm.getBone('leftUpperLeg');
    const rl = this._vrm.getBone('rightUpperLeg');
    if (ll) ll.rotation.x = this._lerp(ll.rotation.x, -0.3, 0.1);
    if (rl) rl.rotation.x = this._lerp(rl.rotation.x, -0.3, 0.1);
  }

  _animLand(delta) {
    const ll = this._vrm.getBone('leftUpperLeg');
    const rl = this._vrm.getBone('rightUpperLeg');
    const llk = this._vrm.getBone('leftLowerLeg');
    const rlk = this._vrm.getBone('rightLowerLeg');
    if (ll) ll.rotation.x = this._lerp(ll.rotation.x, -0.4, 0.2);
    if (rl) rl.rotation.x = this._lerp(rl.rotation.x, -0.4, 0.2);
    if (llk) llk.rotation.x = this._lerp(llk.rotation.x, 0.4, 0.2);
    if (rlk) rlk.rotation.x = this._lerp(rlk.rotation.x, 0.4, 0.2);

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.3, 0.15);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.3, 0.15);
  }

  _animSit(delta) {
    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftLower = this._vrm.getBone('leftLowerLeg');
    const rightLower = this._vrm.getBone('rightLowerLeg');

    if (leftLeg) leftLeg.rotation.x = this._lerp(leftLeg.rotation.x, -1.5, 0.08);
    if (rightLeg) rightLeg.rotation.x = this._lerp(rightLeg.rotation.x, -1.5, 0.08);
    if (leftLower) leftLower.rotation.x = this._lerp(leftLower.rotation.x, 1.5, 0.08);
    if (rightLower) rightLower.rotation.x = this._lerp(rightLower.rotation.x, 1.5, 0.08);

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.8, 0.06);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.8, 0.06);

    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = Math.sin(this._time * 1.2) * 0.01;
  }

  _animSleep(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.x = this._lerp(head.rotation.x, 0.3, 0.03);

    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = Math.sin(this._time * 0.8) * 0.025;

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.9, 0.03);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.9, 0.03);
  }

  _animWave(delta) {
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -2.5, 0.12);
    if (rla) rla.rotation.z = Math.sin(this._time * 6) * 0.3;
  }

  _animStretch(delta) {
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 2.5, 0.08);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -2.5, 0.08);

    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, -0.15, 0.05);
  }

  _animYawn(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.x = this._lerp(head.rotation.x, -0.15, 0.05);

    const ra = this._vrm.getBone('rightUpperArm');
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.8, 0.08);
  }

  _animRead(delta) {
    // Sitting posture with book held in lap/hands
    this._animSit(delta);

    // Head tilted down toward the book
    const head = this._vrm.getBone('head');
    if (head) head.rotation.x = this._lerp(head.rotation.x, 0.25 + Math.sin(this._time * 0.8) * 0.02, 0.08);

    // Hands holding book in front
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.5, 0.08);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.5, 0.08);
    if (lla) lla.rotation.y = this._lerp(lla.rotation.y, 0.8, 0.08);

    // Occasional page turn gesture every ~8 seconds
    const pageTurn = Math.sin(this._time * 0.8);
    if (rla) rla.rotation.y = this._lerp(rla.rotation.y, -0.8 + (pageTurn > 0.95 ? 0.3 : 0), 0.1);
  }

  _animDrink(delta) {
    // Standing or sitting drink animation cycle (takes ~4-5 seconds)
    const cycle = (this._time % 5.0);
    const head = this._vrm.getBone('head');
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (cycle < 2.0) {
      // Raising cup to mouth
      const progress = cycle / 2.0;
      if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.6, progress * 0.1);
      if (rla) rla.rotation.x = this._lerp(rla.rotation.x, -1.2, progress * 0.1);
      if (head) head.rotation.x = this._lerp(head.rotation.x, -0.15, progress * 0.1);
    } else if (cycle < 3.5) {
      // Savoring / sipping
      if (head) head.rotation.x = this._lerp(head.rotation.x, -0.2, 0.08);
    } else {
      // Lowering cup
      if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.1, 0.08);
      if (rla) rla.rotation.x = this._lerp(rla.rotation.x, 0, 0.08);
      if (head) head.rotation.x = this._lerp(head.rotation.x, 0, 0.08);
    }
  }

  _animPhone(delta) {
    // Check phone: right hand held up in front, head angled down
    const head = this._vrm.getBone('head');
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (head) head.rotation.x = this._lerp(head.rotation.x, 0.3, 0.08);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.7, 0.08);
    if (rla) rla.rotation.y = this._lerp(rla.rotation.y, -1.0 + Math.sin(this._time * 3) * 0.05, 0.1);
  }

  _animMusic(delta) {
    // Gentle rhythm sway
    const sway = Math.sin(this._time * 2.5) * 0.06;
    const head = this._vrm.getBone('head');
    const spine = this._vrm.getBone('spine');

    if (head) head.rotation.z = sway;
    if (spine) spine.rotation.z = -sway * 0.5;

    // Relaxed arms
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.0, 0.05);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.0, 0.05);
  }

  _animPet(delta) {
    // Affectionate response to petting
    const head = this._vrm.getBone('head');
    const spine = this._vrm.getBone('spine');

    // Soft head tilt leaning into the touch
    if (head) head.rotation.z = this._lerp(head.rotation.z, 0.15, 0.1);
    if (head) head.rotation.x = this._lerp(head.rotation.x, -0.08, 0.1);
    if (spine) spine.rotation.x = Math.sin(this._time * 1.0) * 0.02;

    // Gentle arm posture
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.9, 0.05);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.9, 0.05);
  }

  _animConfused(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.z = this._lerp(head.rotation.z, -0.25, 0.08);

    const ra = this._vrm.getBone('rightUpperArm');
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.3, 0.08);
  }

  _resetPose() {
    try {
      const la = this._vrm.getBone('leftUpperArm');
      const ra = this._vrm.getBone('rightUpperArm');
      if (la) la.rotation.set(0, 0, 1.1);
      if (ra) ra.rotation.set(0, 0, -1.1);
    } catch (e) { /* safe */ }
  }

  _lerp(current, target, factor) {
    return current + (target - current) * factor;
  }

  dispose() { this._currentAnim = 'idle'; }
}
