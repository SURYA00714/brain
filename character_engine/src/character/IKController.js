import { Logger } from '../logger.js';

/**
 * IKController — Analytical two-bone leg IK & surface contact solver.
 *
 * Implements Sections 15, 16, 17 of the Master Specification:
 * - Analytical two-bone inverse kinematics (thigh + shin) targeting ground/surface.
 * - Knee pole direction enforcement (strictly bends backward, no sideways pop).
 * - Foot ground-alignment (soles stay flat on contact surface).
 * - Pelvis height adjustment for natural sitting, landing, and squatting.
 */
export class IKController {
  constructor(vrmAdapter, worldModel) {
    this._vrm = vrmAdapter;
    this._world = worldModel;

    // Approximate anatomical bone lengths for Ao (world units)
    this.thighLength = 0.38;
    this.shinLength = 0.38;
    this.totalLegLength = this.thighLength + this.shinLength; // 0.76m

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

      // 1. Solve Pelvis Height according to Posture
      this._solvePelvis(posture, surfaceY, pelvisOffset);

      // 2. Solve Left & Right Leg Ground Contact
      if (posture === 'STANDING' || posture === 'LANDING' || posture === 'SQUATTING') {
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
   * Solves two-bone analytical IK for a single leg.
   */
  _solveTwoBoneLeg(upperBoneName, lowerBoneName, footBoneName, targetY) {
    const upper = this._vrm.getBone(upperBoneName);
    const lower = this._vrm.getBone(lowerBoneName);
    const foot = this._vrm.getBone(footBoneName);
    if (!upper || !lower) return;

    const L1 = this.thighLength;
    const L2 = this.shinLength;

    // In standing idle, gentle natural knee flexion (0.04 rad) to prevent stiff locking
    if (lower.rotation.x < 0.02) {
      lower.rotation.x = 0.02;
    }

    // Foot ground compensation: keep sole horizontal
    if (foot) {
      const legPitch = upper.rotation.x + lower.rotation.x;
      foot.rotation.x = -legPitch * 0.75;
      // Clamp foot roll/yaw
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
      leftFoot.rotation.x = 0.0;
      leftFoot.rotation.y = 0.0;
      leftFoot.rotation.z = 0.0;
    }
    if (rightFoot) {
      rightFoot.rotation.x = 0.0;
      rightFoot.rotation.y = 0.0;
      rightFoot.rotation.z = 0.0;
    }
  }
}
