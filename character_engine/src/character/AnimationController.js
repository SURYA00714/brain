import { Logger } from '../logger.js';

/**
 * AnimationController - Procedural humanoid bone animations for Ao.
 *
 * Implements lively, fluid, anime-style character behaviors:
 * idle, walk, run, jump, land, sit, sleep, wave, stretch, yawn,
 * read, drink, phone, music, pet, confused, think, shy, bounce.
 *
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
        case 'think': this._animThink(delta); break;
        case 'shy': this._animShy(delta); break;
        case 'bounce': this._animBounce(delta); break;
        default: this._animIdle(delta);
      }
    } catch (e) {
      Logger.warn('Animation error:', e);
      this._resetPose();
    }
  }

  // === 1. LIVELY ANIME IDLE POSE (NOT STIFF T/A-POSE) ===
  _animIdle(delta) {
    const breathCycle = Math.sin(this._time * 1.5);
    const sway = Math.sin(this._time * 0.7);

    // 1. Spine & Chest breathing
    const spine = this._vrm.getBone('spine');
    if (spine) {
      spine.rotation.x = 0.02 + breathCycle * 0.018;
      spine.rotation.z = -sway * 0.015;
    }

    // 2. Cute hip weight-shift (feminine anime stance)
    const hips = this._vrm.getBone('hips');
    if (hips) {
      hips.rotation.z = sway * 0.03;
      hips.rotation.y = sway * 0.018;
    }

    // 3. Gentle head motion
    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.z = Math.sin(this._time * 0.5) * 0.04;
      head.rotation.y = Math.sin(this._time * 0.35) * 0.05;
    }

    // 4. Relaxed natural arms alongside body with soft elbow bend
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) {
      la.rotation.z = this._lerp(la.rotation.z, 1.28 + breathCycle * 0.015, 0.08);
      la.rotation.x = this._lerp(la.rotation.x, 0.12, 0.08);
      la.rotation.y = this._lerp(la.rotation.y, 0.05, 0.08);
    }
    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -1.28 - breathCycle * 0.015, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.12, 0.08);
      ra.rotation.y = this._lerp(ra.rotation.y, -0.05, 0.08);
    }
    if (lla) {
      lla.rotation.z = this._lerp(lla.rotation.z, 0.15, 0.08);
      lla.rotation.x = this._lerp(lla.rotation.x, 0.10, 0.08);
    }
    if (rla) {
      rla.rotation.z = this._lerp(rla.rotation.z, -0.15, 0.08);
      rla.rotation.x = this._lerp(rla.rotation.x, 0.10, 0.08);
    }
  }

  // === 2. CHEERFUL ANIME WAVE ===
  _animWave(delta) {
    // Left arm relaxed
    const la = this._vrm.getBone('leftUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    if (la) {
      la.rotation.z = this._lerp(la.rotation.z, 1.25, 0.1);
      la.rotation.x = this._lerp(la.rotation.x, 0.12, 0.1);
    }
    if (lla) lla.rotation.z = this._lerp(lla.rotation.z, 0.15, 0.1);

    // Right arm raised high waving side-to-side
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');
    const rh = this._vrm.getBone('rightHand');
    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -1.75, 0.15);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.35, 0.15);
    }
    const wave = Math.sin(this._time * 7);
    if (rla) {
      rla.rotation.z = this._lerp(rla.rotation.z, -0.9 + wave * 0.35, 0.2);
    }
    if (rh) rh.rotation.z = wave * 0.25;

    // Cute head tilt and cheerful sway
    const head = this._vrm.getBone('head');
    const spine = this._vrm.getBone('spine');
    if (head) head.rotation.z = this._lerp(head.rotation.z, 0.14, 0.1);
    if (spine) spine.rotation.x = Math.sin(this._time * 3.5) * 0.02;
  }

  // === 3. CUTE MORNING STRETCH ===
  _animStretch(delta) {
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) {
      la.rotation.z = this._lerp(la.rotation.z, 2.6, 0.08);
      la.rotation.x = this._lerp(la.rotation.x, -0.18, 0.08);
    }
    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -2.6, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, -0.18, 0.08);
    }
    if (lla) lla.rotation.z = this._lerp(lla.rotation.z, 0.25, 0.08);
    if (rla) rla.rotation.z = this._lerp(rla.rotation.z, -0.25, 0.08);

    // Arching spine & relaxed head tilt back
    const spine = this._vrm.getBone('spine');
    const head = this._vrm.getBone('head');
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, -0.16, 0.06);
    if (head) head.rotation.x = this._lerp(head.rotation.x, -0.18, 0.06);
  }

  // === 4. JOYFUL ANIME BOUNCE ===
  _animBounce(delta) {
    const bounce = Math.abs(Math.sin(this._time * 6));
    const hips = this._vrm.getBone('hips');
    const spine = this._vrm.getBone('spine');
    const head = this._vrm.getBone('head');

    if (hips) hips.position.y = bounce * 0.035;
    if (spine) spine.rotation.x = bounce * 0.03;
    if (head) head.rotation.z = Math.sin(this._time * 3) * 0.08;

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.15 - bounce * 0.15, 0.15);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.15 + bounce * 0.15, 0.15);
    if (lla) lla.rotation.z = 0.25 + bounce * 0.15;
    if (rla) rla.rotation.z = -0.25 - bounce * 0.15;
  }

  // === 5. CUTE PHONE TAPPING ===
  _animPhone(delta) {
    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.x = this._lerp(head.rotation.x, 0.32, 0.08);
      head.rotation.z = this._lerp(head.rotation.z, 0.08, 0.08);
    }
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');
    const rh = this._vrm.getBone('rightHand');

    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -0.80, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.65, 0.08);
    }
    if (rla) {
      rla.rotation.x = this._lerp(rla.rotation.x, -1.25, 0.08);
      rla.rotation.y = this._lerp(rla.rotation.y, 0.35, 0.08);
    }
    const tap = Math.sin(this._time * 5);
    if (rh) rh.rotation.x = tap * 0.12;

    const la = this._vrm.getBone('leftUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.25, 0.08);
    if (lla) lla.rotation.z = 0.15;
  }

  // === 6. RHYTHMIC MUSIC GROOVE ===
  _animMusic(delta) {
    const beat = Math.sin(this._time * 4.0);
    const head = this._vrm.getBone('head');
    const spine = this._vrm.getBone('spine');
    const hips = this._vrm.getBone('hips');

    if (head) {
      head.rotation.x = 0.05 + Math.abs(beat) * 0.08;
      head.rotation.z = beat * 0.08;
    }
    if (hips) hips.rotation.z = beat * 0.05;
    if (spine) spine.rotation.z = -beat * 0.03;

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.15 + beat * 0.08, 0.1);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.15 + beat * 0.08, 0.1);
    if (lla) lla.rotation.z = 0.25;
    if (rla) rla.rotation.z = -0.25;
  }

  // === 7. THOUGHTFUL ANIME POSE ===
  _animThink(delta) {
    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.z = this._lerp(head.rotation.z, 0.22, 0.08);
      head.rotation.x = this._lerp(head.rotation.x, -0.12, 0.08);
    }
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');
    const rh = this._vrm.getBone('rightHand');

    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -0.85, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.8, 0.08);
    }
    if (rla) {
      rla.rotation.x = this._lerp(rla.rotation.x, -1.4, 0.08);
      rla.rotation.y = this._lerp(rla.rotation.y, 0.5, 0.08);
    }
    if (rh) rh.rotation.x = this._lerp(rh.rotation.x, 0.2, 0.08);

    const la = this._vrm.getBone('leftUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    if (la) {
      la.rotation.z = this._lerp(la.rotation.z, 1.15, 0.08);
      la.rotation.x = this._lerp(la.rotation.x, 0.3, 0.08);
    }
    if (lla) lla.rotation.y = this._lerp(lla.rotation.y, 0.6, 0.08);
  }

  // === 8. SHY BLUSHING FIDGET ===
  _animShy(delta) {
    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.z = this._lerp(head.rotation.z, -0.15, 0.08);
      head.rotation.x = this._lerp(head.rotation.x, 0.18, 0.08);
    }
    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) {
      la.rotation.z = this._lerp(la.rotation.z, 0.95, 0.08);
      la.rotation.x = this._lerp(la.rotation.x, 0.4, 0.08);
    }
    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -0.95, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.4, 0.08);
    }
    if (lla) {
      lla.rotation.y = this._lerp(lla.rotation.y, 0.6, 0.08);
      lla.rotation.z = this._lerp(lla.rotation.z, 0.3, 0.08);
    }
    if (rla) {
      rla.rotation.y = this._lerp(rla.rotation.y, -0.6, 0.08);
      rla.rotation.z = this._lerp(rla.rotation.z, -0.3, 0.08);
    }
    const hips = this._vrm.getBone('hips');
    if (hips) hips.rotation.z = Math.sin(this._time * 1.5) * 0.02;
  }

  // === 9. SLEEPY YAWN ===
  _animYawn(delta) {
    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.x = this._lerp(head.rotation.x, -0.20, 0.06);
      head.rotation.z = this._lerp(head.rotation.z, 0.10, 0.06);
    }
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -0.7, 0.08);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.9, 0.08);
    }
    if (rla) {
      rla.rotation.x = this._lerp(rla.rotation.x, -1.6, 0.08);
      rla.rotation.y = this._lerp(rla.rotation.y, 0.4, 0.08);
    }
    const la = this._vrm.getBone('leftUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.28, 0.08);
  }

  // === 10. CURIOUS / CONFUSED HEAD TILT ===
  _animConfused(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.z = this._lerp(head.rotation.z, -0.25, 0.08);

    const ra = this._vrm.getBone('rightUpperArm');
    const la = this._vrm.getBone('leftUpperArm');
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.15, 0.08);
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.25, 0.08);
  }

  // === 11. BOUNCY ANIME WALK ===
  _animWalk(delta) {
    this._walkCycle += delta * 5.5;
    const swing = Math.sin(this._walkCycle) * 0.38;

    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftArm = this._vrm.getBone('leftUpperArm');
    const rightArm = this._vrm.getBone('rightUpperArm');
    const leftLower = this._vrm.getBone('leftLowerLeg');
    const rightLower = this._vrm.getBone('rightLowerLeg');

    if (leftLeg) leftLeg.rotation.x = swing;
    if (rightLeg) rightLeg.rotation.x = -swing;
    if (leftLower) leftLower.rotation.x = Math.max(0, -swing * 0.7);
    if (rightLower) rightLower.rotation.x = Math.max(0, swing * 0.7);

    if (leftArm) {
      leftArm.rotation.z = 1.22;
      leftArm.rotation.x = -swing * 0.4 + 0.1;
    }
    if (rightArm) {
      rightArm.rotation.z = -1.22;
      rightArm.rotation.x = swing * 0.4 + 0.1;
    }

    const spine = this._vrm.getBone('spine');
    const hips = this._vrm.getBone('hips');
    if (spine) spine.rotation.x = Math.abs(Math.sin(this._walkCycle * 2)) * 0.03;
    if (hips) hips.rotation.z = Math.sin(this._walkCycle) * 0.03;
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

  _animRead(delta) {
    this._animSit(delta);
    const head = this._vrm.getBone('head');
    if (head) head.rotation.x = this._lerp(head.rotation.x, 0.25 + Math.sin(this._time * 0.8) * 0.02, 0.08);

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.5, 0.08);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.5, 0.08);
    if (lla) lla.rotation.y = this._lerp(lla.rotation.y, 0.8, 0.08);
    const pageTurn = Math.sin(this._time * 0.8);
    if (rla) rla.rotation.y = this._lerp(rla.rotation.y, -0.8 + (pageTurn > 0.95 ? 0.3 : 0), 0.1);
  }

  _animDrink(delta) {
    const cycle = (this._time % 5.0);
    const head = this._vrm.getBone('head');
    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');

    if (cycle < 2.0) {
      const progress = cycle / 2.0;
      if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.6, progress * 0.1);
      if (rla) rla.rotation.x = this._lerp(rla.rotation.x, -1.2, progress * 0.1);
      if (head) head.rotation.x = this._lerp(head.rotation.x, -0.15, progress * 0.1);
    } else if (cycle < 3.5) {
      if (head) head.rotation.x = this._lerp(head.rotation.x, -0.2, 0.08);
    } else {
      if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.25, 0.08);
      if (rla) rla.rotation.x = this._lerp(rla.rotation.x, 0, 0.08);
      if (head) head.rotation.x = this._lerp(head.rotation.x, 0, 0.08);
    }
  }

  _animPet(delta) {
    const head = this._vrm.getBone('head');
    const spine = this._vrm.getBone('spine');

    if (head) {
      head.rotation.z = this._lerp(head.rotation.z, 0.18, 0.1);
      head.rotation.x = this._lerp(head.rotation.x, -0.08, 0.1);
    }
    if (spine) spine.rotation.x = Math.sin(this._time * 1.0) * 0.02;

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.15, 0.05);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.15, 0.05);
  }

  _resetPose() {
    try {
      const la = this._vrm.getBone('leftUpperArm');
      const ra = this._vrm.getBone('rightUpperArm');
      const lla = this._vrm.getBone('leftLowerArm');
      const rla = this._vrm.getBone('rightLowerArm');
      if (la) la.rotation.set(0.12, 0.05, 1.28);
      if (ra) ra.rotation.set(0.12, -0.05, -1.28);
      if (lla) lla.rotation.set(0.10, 0, 0.15);
      if (rla) rla.rotation.set(0.10, 0, -0.15);
    } catch (e) { /* safe */ }
  }

  _lerp(current, target, factor) {
    return current + (target - current) * factor;
  }

  dispose() { this._currentAnim = 'idle'; }
}
