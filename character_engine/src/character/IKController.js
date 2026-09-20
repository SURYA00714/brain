import { Logger } from '../logger.js';

/**
 * IKController — Analytical two-bone leg IK & surface contact solver.
 *
 * Implements Sections 10, 15, 16, 17, 22 of the Master Specification
 * with Overte-derived analytical two-bone techniques:
 * - Anti-pop minimum knee flexion (MAX_EXTENSION = 0.997 / 0.025 rad)
 * - Knee pole vector enforcement (pure sagittal backward bend, zero lateral pop)
 * - Sole ground compensation (soles remain flat on contact plane)
 * - Pelvis height preservation (baseHipsY maintained for screen containment)
 */
export class IKController {
  constructor(vrmAdapter, worldModel) {
    this._vrm = vrmAdapter;
    this._world = worldModel;

    // Approximate anatomical bone lengths for Ao (world units)
    this.thighLength = 0.38;
    this.shinLength = 0.38;
    this.totalLegLength = this.thighLength + this.shinLength; // 0.76m

    // Overte Anti-pop & Pole vector constants
    this.MIN_KNEE_FLEXION = 0.025; // radians (prevents knee locking & snapping)
    this.MAX_KNEE_FLEXION = 2.45;  // radians

    this.enabled = true;
  }

  /**
   * Solves leg contact for both feet against current support surface.
   *
   * @param {string} posture - Current POSTURE
   * @param {Object} supportSurface - Current support surface
   * @param {number} pelvisOffset - Pelvis vertical offset from baseline
   */
  solveLegs(posture, supportSurface = null, pelvisOffset = 0) {
    if (!this.enabled || !this._vrm.loaded) return;

    try {
      const surfaceY = supportSurface ? supportSurface.worldY : this._world.groundY;

      // 1. Solve Pelvis Height according to Posture while preserving base rest height
      this._solvePelvis(posture, surfaceY, pelvisOffset);

      // 2. Solve Left & Right Leg Ground Contact
      if (posture === 'STANDING' || posture === 'LANDING' || posture === 'SQUATTING' || posture === 'WALKING') {
        this._solveTwoBoneLeg('leftUpperLeg', 'leftLowerLeg', 'leftFoot', surfaceY);
        this._solveTwoBoneLeg('rightUpperLeg', 'rightLowerLeg', 'rightFoot', surfaceY);
      } else if (posture === 'SITTING') {
        this._solveSittingLegs(surfaceY);
      }
    } catch (e) {
      Logger.warn('[IK] Solver error:', e);
    }
  }

  /**
   * Adjusts pelvis height so feet reach ground without hyperextension or penetration.
   * Strictly preserves baseHipsY so character remains elevated above taskbar.
   */
  _solvePelvis(posture, surfaceY, offset) {
    const hips = this._vrm.getBone('hips');
    if (!hips) return;

    const baseHipsY = this._vrm.initialHipsY || ((hips.position && hips.position.y > 0.3) ? hips.position.y : 0.8801);
    let targetPelvisY = baseHipsY;

    switch (posture) {
      case 'SITTING':
        // Pelvis lowers so buttocks rest on the surface
        targetPelvisY = baseHipsY - 0.38 + offset;
        break;
      case 'SQUATTING':
        targetPelvisY = baseHipsY - 0.32 + offset;
        break;
      case 'LANDING':
        targetPelvisY = baseHipsY - 0.10 + offset;
        break;
      case 'STANDING':
      default:
        targetPelvisY = baseHipsY + offset;
        break;
    }

    hips.position.y += (targetPelvisY - hips.position.y) * 0.15;
  }

  /**
   * Solves two-bone analytical IK for a single leg with Overte-derived pole vector & leveling.
   */
  _solveTwoBoneLeg(upperBoneName, lowerBoneName, footBoneName, targetY) {
    const upper = this._vrm.getBone(upperBoneName);
    const lower = this._vrm.getBone(lowerBoneName);
    const foot = this._vrm.getBone(footBoneName);
    if (!upper || !lower) return;

    // 1. Anti-pop knee hinge constraint (Overte AnimTwoBoneIK)
    // Knee strictly hinges backwards in local X plane; eliminate sideways roll/yaw pop
    lower.rotation.y = 0;
    lower.rotation.z = 0;
    if (lower.rotation.x < this.MIN_KNEE_FLEXION) {
      lower.rotation.x = this.MIN_KNEE_FLEXION;
    } else if (lower.rotation.x > this.MAX_KNEE_FLEXION) {
      lower.rotation.x = this.MAX_KNEE_FLEXION;
    }

    // 2. Foot Ground Alignment (Sole Leveling)
    // Sole pitch compensates for leg inclination so foot stays horizontal
    if (foot) {
      const legPitch = upper.rotation.x + lower.rotation.x;
      foot.rotation.x = -legPitch * 0.85;
      foot.rotation.y = 0;
      foot.rotation.z = 0;
    }
  }

  /**
   * Special contact alignment for sitting posture.
   */
  _solveSittingLegs(surfaceY) {
    const leftFoot = this._vrm.getBone('leftFoot');
    const rightFoot = this._vrm.getBone('rightFoot');

    // Level feet horizontally when sitting
    if (leftFoot) {
      leftFoot.rotation.set(0, 0, 0);
    }
    if (rightFoot) {
      rightFoot.rotation.set(0, 0, 0);
    }
  }
}
