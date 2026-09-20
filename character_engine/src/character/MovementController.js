import { CONFIG } from '../config.js';

/**
 * MovementController — Authoritative position & human-like grounded locomotion.
 *
 * Implements Sections 28, 29, 30, 46, 47 of the Master Specification:
 * - Turn-before-and-during movement (zero moonwalking)
 * - Safe boundary containment via WorldModel dynamic posture envelope
 * - Smooth acceleration, deceleration braking, and clean zero-jitter stopping
 * - Synchronizes with single authoritative CharacterWorldState
 */
export class MovementController {
  constructor(vrmAdapter, worldModel, characterWorldState) {
    this._vrm = vrmAdapter;
    this._world = worldModel;
    this._worldState = characterWorldState;

    // Target (null = not walking)
    this._targetX = null;

    // Current horizontal velocity (pixels / sec)
    this._currentVelocityX = 0;
    this._acceleration = 450;    // pixels/sec²
    this._deceleration = 600;    // pixels/sec²
    this._decelDistance = 80;    // pixels before target to begin braking

    // Jump / airborne physics
    this._jumpOffsetY = 0;       // world units above ground
    this._velocityY = 0;
    this._isAirborne = false;

    // Orientation (facing angle)
    this._facingRight = true;
    this._currentFacingAngle = Math.PI; // Face viewer/camera initially
    this._isTurning = false;
  }

  get desktopX() {
    return this._worldState.desktopX;
  }

  get isMoving() {
    return this._targetX !== null || Math.abs(this._currentVelocityX) > 5;
  }

  get isAirborne() {
    return this._isAirborne;
  }

  get currentVelocity() {
    return this._currentVelocityX;
  }

  /**
   * Immediately set desktop position (clamped to safe margins for current posture).
   */
  setDesktopX(x) {
    const clamped = this._world.clampSafeX(x, this._worldState.posture);
    this._currentVelocityX = 0;
    this._targetX = null;
    this._worldState.setPosition(clamped);
    this._applyToVRM();
  }

  /**
   * Request walking to target desktop X.
   */
  walkTo(targetX) {
    const safeTarget = this._world.clampSafeX(targetX, 'WALKING');
    const dx = safeTarget - this.desktopX;

    if (Math.abs(dx) <= (CONFIG.character.arrivalDistance || 15)) {
      this.stop();
      return;
    }

    this._targetX = safeTarget;
    this._facingRight = dx > 0;
    this._isTurning = true;
  }

  /**
   * Immediate stop.
   */
  stop() {
    this._targetX = null;
    this._currentVelocityX = 0;
    this._isTurning = false;
  }

  /**
   * Jump from current position.
   */
  jump() {
    if (this._isAirborne) return;
    this._isAirborne = true;
    this._velocityY = (CONFIG.character.jumpVelocity || 450) / this._world.screenH * this._world.visibleH;
  }

  /**
   * Frame update with delta time.
   */
  update(dt) {
    // 1. HORIZONTAL LOCOMOTION
    if (this._targetX !== null) {
      const dx = this._targetX - this.desktopX;
      const distance = Math.abs(dx);
      const direction = Math.sign(dx);

      // Facing orientation: turn before full speed walk (no moonwalking)
      this._facingRight = direction > 0;
      const desiredAngle = this._facingRight ? Math.PI + 0.35 : Math.PI - 0.35;
      const angleDiff = Math.abs(desiredAngle - this._currentFacingAngle);

      // Settle if arrived
      if (distance <= (CONFIG.character.arrivalDistance || 15)) {
        this._worldState.setPosition(this._targetX);
        this._targetX = null;
        this._currentVelocityX = 0;
        this._isTurning = false;
      } else {
        // Turning first: if facing angle is still far off, accelerate more gently
        const turnReadiness = angleDiff > 0.4 ? 0.3 : 1.0;

        // Deceleration curve when approaching target
        let maxSpeed = (CONFIG.character.movementSpeed || 140) * turnReadiness;
        if (distance < this._decelDistance) {
          maxSpeed = Math.max(40, maxSpeed * (distance / this._decelDistance));
        }

        const targetVel = direction * maxSpeed;
        if (this._currentVelocityX < targetVel) {
          this._currentVelocityX = Math.min(targetVel, this._currentVelocityX + this._acceleration * dt);
        } else if (this._currentVelocityX > targetVel) {
          this._currentVelocityX = Math.max(targetVel, this._currentVelocityX - this._deceleration * dt);
        }

        // Apply movement step clamped within safe bounds
        const step = this._currentVelocityX * dt;
        if (Math.abs(step) >= distance) {
          this._worldState.setPosition(this._targetX);
          this._targetX = null;
          this._currentVelocityX = 0;
        } else {
          this._worldState.setPosition(this.desktopX + step);
        }
      }
    } else {
      // Natural deceleration to zero
      if (Math.abs(this._currentVelocityX) > 1) {
        this._currentVelocityX -= Math.sign(this._currentVelocityX) * this._deceleration * dt;
      } else {
        this._currentVelocityX = 0;
      }
    }

    // 2. VERTICAL JUMP & GRAVITY
    if (this._isAirborne) {
      const gravityWorld = (CONFIG.character.gravity || 980) / this._world.screenH * this._world.visibleH;
      this._velocityY -= gravityWorld * dt;
      this._jumpOffsetY += this._velocityY * dt;

      if (this._jumpOffsetY <= 0) {
        this._jumpOffsetY = 0;
        this._velocityY = 0;
        this._isAirborne = false;
        this._worldState.isGrounded = true;
      } else {
        this._worldState.isGrounded = false;
      }
    }

    // 3. FACING ANGLE INTERPOLATION
    const targetAngle = this._facingRight ? Math.PI + 0.35 : Math.PI - 0.35;
    this._currentFacingAngle += (targetAngle - this._currentFacingAngle) * (CONFIG.character.turnLerp || 0.15);

    this._worldState.setFacing(this._facingRight, this._currentFacingAngle);
    this._worldState.velocityX = this._currentVelocityX;

    // Apply to Three.js VRM scene
    this._applyToVRM();
  }

  /**
   * Synchronize position and rotation to VRM scene.
   */
  _applyToVRM() {
    if (!this._vrm.loaded || !this._vrm.scene) return;
    try {
      const worldY = this._worldState.worldY + this._jumpOffsetY;
      this._vrm.scene.position.set(this._worldState.worldX, worldY, 0);
      this._vrm.scene.rotation.y = this._currentFacingAngle;
    } catch (e) {}
  }
}
