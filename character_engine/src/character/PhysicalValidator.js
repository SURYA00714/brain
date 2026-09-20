import { Logger } from '../logger.js';

/**
 * PhysicalValidator — Enforces physical, spatial, and anatomical correctness.
 *
 * Implements Sections 6, 7, 22, 25, 50, 51 of the Master Specification:
 * - Spatial target validation & boundary enforcement
 * - Humanoid joint limit clamping (knees only bend backwards, elbows hinge correctly)
 * - Support surface validation (no sitting in mid-air)
 * - Fail-safe recovery returning to SAFE_IDLE
 */
export class PhysicalValidator {
  /** Humanoid bone anatomical Euler angle limits (radians) */
  static JOINT_LIMITS = {
    hips: {
      minX: -0.3, maxX: 0.3,
      minY: -0.2, maxY: 0.2,
      minZ: -0.15, maxZ: 0.15
    },
    spine: {
      minX: -0.35, maxX: 0.45,
      minY: -0.35, maxY: 0.35,
      minZ: -0.25, maxZ: 0.25
    },
    chest: {
      minX: -0.25, maxX: 0.35,
      minY: -0.3, maxY: 0.3,
      minZ: -0.2, maxZ: 0.2
    },
    neck: {
      minX: -0.35, maxX: 0.35,
      minY: -0.6, maxY: 0.6,
      minZ: -0.3, maxZ: 0.3
    },
    head: {
      minX: -0.4, maxX: 0.4,
      minY: -0.7, maxY: 0.7,
      minZ: -0.35, maxZ: 0.35
    },
    leftUpperArm: {
      minX: -1.6, maxX: 1.6,
      minY: -1.2, maxY: 1.2,
      minZ: 0.05, maxZ: 2.85 // alongside body to raised overhead
    },
    rightUpperArm: {
      minX: -1.6, maxX: 1.6,
      minY: -1.2, maxY: 1.2,
      minZ: -2.85, maxZ: -0.05
    },
    leftLowerArm: {
      // 1-DOF elbow hinge: flex inward
      minX: -1.8, maxX: 0.8,
      minY: -0.4, maxY: 1.2,
      minZ: 0.0, maxZ: 2.4
    },
    rightLowerArm: {
      // 1-DOF elbow hinge: flex inward
      minX: -1.8, maxX: 0.8,
      minY: -1.2, maxY: 0.4,
      minZ: -2.4, maxZ: 0.0
    },
    leftUpperLeg: {
      minX: -1.8, maxX: 0.6,
      minY: -0.35, maxY: 0.35,
      minZ: -0.35, maxZ: 0.6
    },
    rightUpperLeg: {
      minX: -1.8, maxX: 0.6,
      minY: -0.35, maxY: 0.35,
      minZ: -0.6, maxZ: 0.35
    },
    leftLowerLeg: {
      // Human knee hinge: ONLY bends backwards (X >= 0 in standard VRM rig)
      // NEVER allow negative X rotation (forward knee hyperextension)
      minX: 0.0, maxX: 2.6,
      minY: -0.08, maxY: 0.08,
      minZ: -0.08, maxZ: 0.08
    },
    rightLowerLeg: {
      // Human knee hinge: ONLY bends backwards (X >= 0 in standard VRM rig)
      minX: 0.0, maxX: 2.6,
      minY: -0.08, maxY: 0.08,
      minZ: -0.08, maxZ: 0.08
    },
    leftFoot: {
      minX: -0.5, maxX: 0.5,
      minY: -0.2, maxY: 0.2,
      minZ: -0.2, maxZ: 0.2
    },
    rightFoot: {
      minX: -0.5, maxX: 0.5,
      minY: -0.2, maxY: 0.2,
      minZ: -0.2, maxZ: 0.2
    }
  };

  /**
   * Validates and clamps a spatial target inside safe screen margins.
   */
  static validateSpatialTarget(targetX, worldModel) {
    if (typeof targetX !== 'number' || isNaN(targetX)) {
      return { valid: false, clampedX: worldModel.homeDesktopX, reason: 'Invalid target coordinate' };
    }
    const clamped = worldModel.clampSafeX(targetX);
    const wasClamped = Math.abs(clamped - targetX) > 1;
    return {
      valid: true,
      clampedX: clamped,
      wasClamped,
      reason: wasClamped ? 'Target clamped to safe screen bounds' : 'Target within safe bounds'
    };
  }

  /**
   * Validates whether a support surface is physically valid for sitting or resting.
   */
  static validateSupportSurface(surface, worldModel) {
    if (!surface || !surface.isValid) {
      return { valid: false, reason: 'No valid support surface specified' };
    }
    // Surface must be inside screen bounds and have minimum width
    const width = (surface.maxX || 0) - (surface.minX || 0);
    if (width < 60) {
      return { valid: false, reason: `Surface width too narrow: ${width}px < 60px` };
    }
    if (surface.desktopY < worldModel.SAFE_MARGIN_Y || surface.desktopY > worldModel.screenH + 10) {
      return { valid: false, reason: `Surface desktop Y out of bounds: ${surface.desktopY}` };
    }
    return { valid: true, surface };
  }

  /**
   * Validates whether an Action Intent is physically possible given current state and world.
   */
  static validateIntent(intent, characterWorldState, worldModel) {
    if (!intent || !intent.type) {
      return { valid: false, reason: 'Empty or malformed intent' };
    }

    switch (intent.type) {
      case 'WALK': {
        const check = this.validateSpatialTarget(intent.targetX, worldModel);
        if (!check.valid) return check;
        return { valid: true, sanitizedIntent: { ...intent, targetX: check.clampedX } };
      }
      case 'SIT': {
        const surface = intent.surface || characterWorldState.supportSurface || worldModel.groundSurface;
        const surfCheck = this.validateSupportSurface(surface, worldModel);
        if (!surfCheck.valid) {
          return { valid: false, reason: `Cannot sit: ${surfCheck.reason}` };
        }
        return { valid: true, sanitizedIntent: { ...intent, surface: surfCheck.surface } };
      }
      case 'JUMP': {
        if (!characterWorldState.isGrounded) {
          return { valid: false, reason: 'Cannot jump while airborne' };
        }
        return { valid: true, sanitizedIntent: intent };
      }
      case 'SLEEP':
      case 'REST': {
        if (characterWorldState.posture !== 'STANDING' && characterWorldState.posture !== 'SITTING') {
          return { valid: false, reason: `Cannot sleep from posture: ${characterWorldState.posture}` };
        }
        return { valid: true, sanitizedIntent: intent };
      }
      default:
        return { valid: true, sanitizedIntent: intent };
    }
  }

  /**
   * Applies anatomical joint limit clamping to a bone's Euler rotations.
   * Modifies bone rotation in-place if limits are exceeded.
   */
  static clampBoneRotation(boneName, rotation) {
    const limits = this.JOINT_LIMITS[boneName];
    if (!limits || !rotation) return;

    if (limits.minX !== undefined) rotation.x = Math.max(limits.minX, Math.min(limits.maxX, rotation.x));
    if (limits.minY !== undefined) rotation.y = Math.max(limits.minY, Math.min(limits.maxY, rotation.y));
    if (limits.minZ !== undefined) rotation.z = Math.max(limits.minZ, Math.min(limits.maxZ, rotation.z));
  }

  /**
   * Clamps all active humanoid bones on a VRM model.
   */
  static clampAllBones(vrmAdapter) {
    if (!vrmAdapter || !vrmAdapter.loaded) return;
    for (const boneName of Object.keys(this.JOINT_LIMITS)) {
      const bone = vrmAdapter.getBone(boneName);
      if (bone && bone.rotation) {
        this.clampBoneRotation(boneName, bone.rotation);
      }
    }
  }

  /**
   * SAFE_IDLE: Fail-safe recovery state.
   */
  static applySafeIdle(characterWorldState, vrmAdapter, worldModel) {
    Logger.warn('[PHYSICAL] Emergency recovery triggered — resetting to SAFE_IDLE');
    characterWorldState.setPosition(worldModel.clampSafeX(characterWorldState.desktopX));
    characterWorldState.setPosture('STANDING');
    characterWorldState.supportSurface = worldModel.groundSurface;
    characterWorldState.isGrounded = true;
    characterWorldState.velocityX = 0;
    characterWorldState.velocityY = 0;

    if (vrmAdapter && vrmAdapter.loaded) {
      const la = vrmAdapter.getBone('leftUpperArm');
      const ra = vrmAdapter.getBone('rightUpperArm');
      const lla = vrmAdapter.getBone('leftLowerArm');
      const rla = vrmAdapter.getBone('rightLowerArm');
      const ll = vrmAdapter.getBone('leftUpperLeg');
      const rl = vrmAdapter.getBone('rightUpperLeg');
      const llk = vrmAdapter.getBone('leftLowerLeg');
      const rlk = vrmAdapter.getBone('rightLowerLeg');
      const spine = vrmAdapter.getBone('spine');
      const head = vrmAdapter.getBone('head');

      if (la) la.rotation.set(0.12, 0.05, 1.28);
      if (ra) ra.rotation.set(0.12, -0.05, -1.28);
      if (lla) lla.rotation.set(0.10, 0, 0.15);
      if (rla) rla.rotation.set(0.10, 0, -0.15);
      if (ll) ll.rotation.set(0, 0, 0);
      if (rl) rl.rotation.set(0, 0, 0);
      if (llk) llk.rotation.set(0, 0, 0);
      if (rlk) rlk.rotation.set(0, 0, 0);
      if (spine) spine.rotation.set(0, 0, 0);
      if (head) head.rotation.set(0, 0, 0);
    }
  }
}
