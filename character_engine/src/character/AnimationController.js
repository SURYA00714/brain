import { Logger } from '../logger.js';
import { PhysicalValidator } from './PhysicalValidator.js';
import { getAnimationMetadata } from './AnimationCatalog.js';

/**
 * AnimationController — Layered humanoid animation blender & controller.
 *
 * Implements Sections 13, 14, 15, 45, 46 of the Master Specification:
 * - Layer 0: Base Posture / Locomotion (walk, sit, idle)
 * - Layer 1: Upper Body Gesture (wave, think, stretch, pet)
 * - Layer 2: Procedural Micro-Motion (breathing, weight-shift, subtle head sway)
 * - Smooth crossfade blending between poses
 * - Automatic anatomical joint limit clamping via PhysicalValidator
 */
export class AnimationController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._currentAnim = 'idle';
    this._previousAnim = 'idle';
    this._time = 0;
    this._walkCycle = 0;

    // Crossfading state
    this._blendDuration = 0.4;
    this._blendTimer = 0.4;
    this._blendWeight = 1.0; // 0.0 (prev) -> 1.0 (current)
  }

  play(name, customBlendDuration = null) {
    if (this._currentAnim === name && this._blendWeight >= 1.0) return;

    this._previousAnim = this._currentAnim;
    this._currentAnim = name;
    this._time = 0;

    const meta = getAnimationMetadata(name);
    this._blendDuration = customBlendDuration !== null ? customBlendDuration : (meta.blendDuration || 0.4);
    this._blendTimer = 0;
    this._blendWeight = 0;
  }

  stop() {
    this.play('idle', 0.5);
  }

  get current() {
    return this._currentAnim;
  }

  update(delta) {
    if (!this._vrm.loaded || !this._vrm.capabilities.humanoid) return;
    this._time += delta;

    // Advance crossfading
    if (this._blendTimer < this._blendDuration) {
      this._blendTimer += delta;
      this._blendWeight = Math.min(1.0, this._blendTimer / Math.max(0.01, this._blendDuration));
    } else {
      this._blendWeight = 1.0;
    }

    try {
      // 1. LAYER 0 & 1: Evaluate Active Animation
      this._evaluateAnimation(this._currentAnim, delta);

      // 2. LAYER 2: Procedural Micro-Motion (Breathing & Weight Shift)
      this._applyMicroMotion(delta);

      // 3. PHYSICAL VALIDATOR: Clamp all joints to anatomical limits
      PhysicalValidator.clampAllBones(this._vrm);

    } catch (e) {
      Logger.warn('[ANIMATION] Execution error:', e);
      PhysicalValidator.applySafeIdle(null, this._vrm, null);
    }
  }

  _evaluateAnimation(animName, delta) {
    switch (animName) {
      case 'idle':
      case 'idle_sway':
        this._animIdle(delta);
        break;
      case 'walk':
        this._animWalk(delta);
        break;
      case 'run':
        this._animRun(delta);
        break;
      case 'jump':
        this._animJump(delta);
        break;
      case 'land':
        this._animLand(delta);
        break;
      case 'sit_prepare':
        this._animSitPrepare(delta);
        break;
      case 'sit':
        this._animSit(delta);
        break;
      case 'stand_prepare':
        this._animStandPrepare(delta);
        break;
      case 'sleep':
        this._animSleep(delta);
        break;
      case 'wave':
        this._animWave(delta, 1.0);
        break;
      case 'wave_small':
        this._animWave(delta, 0.6);
        break;
      case 'stretch':
        this._animStretch(delta);
        break;
      case 'yawn':
        this._animYawn(delta);
        break;
      case 'read':
        this._animRead(delta);
        break;
      case 'drink':
        this._animDrink(delta);
        break;
      case 'phone':
        this._animPhone(delta);
        break;
      case 'music':
        this._animMusic(delta);
        break;
      case 'pet':
        this._animPet(delta);
        break;
      case 'confused':
        this._animConfused(delta);
        break;
      case 'think':
        this._animThink(delta);
        break;
      case 'shy':
        this._animShy(delta);
        break;
      case 'bounce':
        this._animBounce(delta);
        break;
      default:
        this._animIdle(delta);
        break;
    }
  }

  // === LAYER 2: PROCEDURAL MICRO-MOTION ===
  _applyMicroMotion(delta) {
    const isLocomoting = this._currentAnim === 'walk' || this._currentAnim === 'run';
    const isSitting = this._currentAnim === 'sit' || this._currentAnim === 'read';

    // 1. Natural thoracic breathing (gentle continuous expansion)
    const breathCycle = Math.sin(this._time * 1.6);
    const chest = this._vrm.getBone('chest') || this._vrm.getBone('spine');
    if (chest) {
      chest.rotation.x += breathCycle * 0.012;
    }

    // 2. Subtle weight-shift sway when standing still
    if (!isLocomoting && !isSitting) {
      const sway = Math.sin(this._time * 0.7);
      const hips = this._vrm.getBone('hips');
      if (hips) {
        hips.rotation.z += sway * 0.018;
        hips.rotation.y += sway * 0.012;
      }
    }
  }

  // === ANIMATIONS ===

  _animIdle(delta) {
    const breath = Math.sin(this._time * 1.5);
    const sway = Math.sin(this._time * 0.7);

    const spine = this._vrm.getBone('spine');
    if (spine) {
      spine.rotation.x = this._lerp(spine.rotation.x, 0.02 + breath * 0.015, 0.08);
      spine.rotation.z = this._lerp(spine.rotation.z, -sway * 0.015, 0.08);
    }

    const head = this._vrm.getBone('head');
    if (head) {
      head.rotation.z = this._lerp(head.rotation.z, Math.sin(this._time * 0.5) * 0.04, 0.08);
      head.rotation.y = this._lerp(head.rotation.y, Math.sin(this._time * 0.35) * 0.04, 0.08);
    }

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    const rla = this._vrm.getBone('rightLowerArm');
    const ll = this._vrm.getBone('leftUpperLeg');
    const rl = this._vrm.getBone('rightUpperLeg');
    const llk = this._vrm.getBone('leftLowerLeg');
    const rlk = this._vrm.getBone('rightLowerLeg');

    if (la) la.rotation.set(0.12, 0.05, this._lerp(la.rotation.z, 1.28 + breath * 0.015, 0.08));
    if (ra) ra.rotation.set(0.12, -0.05, this._lerp(ra.rotation.z, -1.28 - breath * 0.015, 0.08));
    if (lla) lla.rotation.set(0.10, 0, this._lerp(lla.rotation.z, 0.15, 0.08));
    if (rla) rla.rotation.set(0.10, 0, this._lerp(rla.rotation.z, -0.15, 0.08));

    if (ll) ll.rotation.x = this._lerp(ll.rotation.x, 0, 0.1);
    if (rl) rl.rotation.x = this._lerp(rl.rotation.x, 0, 0.1);
    if (llk) llk.rotation.x = this._lerp(llk.rotation.x, 0, 0.1);
    if (rlk) rlk.rotation.x = this._lerp(rlk.rotation.x, 0, 0.1);
  }

  _animWalk(delta) {
    this._walkCycle += delta * 5.5;
    const swing = Math.sin(this._walkCycle) * 0.38;

    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftArm = this._vrm.getBone('leftUpperArm');
    const rightArm = this._vrm.getBone('rightUpperArm');
    const leftLower = this._vrm.getBone('leftLowerLeg');
    const rightLower = this._vrm.getBone('rightLowerLeg');

    // Knees only bend backwards (positive X >= 0 in VRM standard)
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
    this._walkCycle += delta * 8.0;
    const swing = Math.sin(this._walkCycle) * 0.6;

    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftArm = this._vrm.getBone('leftUpperArm');
    const rightArm = this._vrm.getBone('rightUpperArm');
    const leftLower = this._vrm.getBone('leftLowerLeg');
    const rightLower = this._vrm.getBone('rightLowerLeg');

    if (leftLeg) leftLeg.rotation.x = swing;
    if (rightLeg) rightLeg.rotation.x = -swing;
    if (leftLower) leftLower.rotation.x = Math.max(0, -swing * 0.9);
    if (rightLower) rightLower.rotation.x = Math.max(0, swing * 0.9);

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

  // === PREPARE TO SIT (Natural crouching transition) ===
  _animSitPrepare(delta) {
    const leftLeg = this._vrm.getBone('leftUpperLeg');
    const rightLeg = this._vrm.getBone('rightUpperLeg');
    const leftLower = this._vrm.getBone('leftLowerLeg');
    const rightLower = this._vrm.getBone('rightLowerLeg');
    const spine = this._vrm.getBone('spine');

    if (leftLeg) leftLeg.rotation.x = this._lerp(leftLeg.rotation.x, -0.8, 0.08);
    if (rightLeg) rightLeg.rotation.x = this._lerp(rightLeg.rotation.x, -0.8, 0.08);
    if (leftLower) leftLower.rotation.x = this._lerp(leftLower.rotation.x, 0.8, 0.08);
    if (rightLower) rightLower.rotation.x = this._lerp(rightLower.rotation.x, 0.8, 0.08);
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, 0.12, 0.08);
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
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, 0.05, 0.08);
  }

  _animStandPrepare(delta) {
    this._animSitPrepare(delta);
  }

  _animSleep(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.x = this._lerp(head.rotation.x, 0.28, 0.03);

    const spine = this._vrm.getBone('spine');
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, 0.08, 0.03);

    const la = this._vrm.getBone('leftUpperArm');
    const ra = this._vrm.getBone('rightUpperArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 0.95, 0.03);
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -0.95, 0.03);
  }

  _animWave(delta, intensity = 1.0) {
    const la = this._vrm.getBone('leftUpperArm');
    const lla = this._vrm.getBone('leftLowerArm');
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.25, 0.1);
    if (lla) lla.rotation.z = this._lerp(lla.rotation.z, 0.15, 0.1);

    const ra = this._vrm.getBone('rightUpperArm');
    const rla = this._vrm.getBone('rightLowerArm');
    const rh = this._vrm.getBone('rightHand');
    if (ra) {
      ra.rotation.z = this._lerp(ra.rotation.z, -1.75 * intensity, 0.15);
      ra.rotation.x = this._lerp(ra.rotation.x, 0.35 * intensity, 0.15);
    }
    const wave = Math.sin(this._time * 7);
    if (rla) {
      rla.rotation.z = this._lerp(rla.rotation.z, -0.9 + wave * 0.35 * intensity, 0.2);
    }
    if (rh) rh.rotation.z = wave * 0.25 * intensity;

    const head = this._vrm.getBone('head');
    if (head) head.rotation.z = this._lerp(head.rotation.z, 0.14 * intensity, 0.1);
  }

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

    const spine = this._vrm.getBone('spine');
    const head = this._vrm.getBone('head');
    if (spine) spine.rotation.x = this._lerp(spine.rotation.x, -0.16, 0.06);
    if (head) head.rotation.x = this._lerp(head.rotation.x, -0.18, 0.06);
  }

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

  _animConfused(delta) {
    const head = this._vrm.getBone('head');
    if (head) head.rotation.z = this._lerp(head.rotation.z, -0.25, 0.08);

    const ra = this._vrm.getBone('rightUpperArm');
    const la = this._vrm.getBone('leftUpperArm');
    if (ra) ra.rotation.z = this._lerp(ra.rotation.z, -1.15, 0.08);
    if (la) la.rotation.z = this._lerp(la.rotation.z, 1.25, 0.08);
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

  _lerp(current, target, factor) {
    return current + (target - current) * factor;
  }

  dispose() {
    this._currentAnim = 'idle';
  }
}
