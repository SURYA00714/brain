import { CONFIG } from '../config.js';

/**
 * MovementController — Authoritative position & human-like locomotion.
 *
 * Locomotion Features:
 * - Smooth acceleration and deceleration (ease-in / ease-out)
 * - Turn-before-and-during movement (no moonwalking)
 * - Deceleration zone near arrival
 * - Clean zero-jitter stopping
 */
export class MovementController {
  constructor(vrmAdapter, desktopCoords) {
    this._vrm = vrmAdapter;
    this._desktop = desktopCoords;

    // Authoritative desktop position (X in pixels, along the ground)
    this.desktopX = desktopCoords.screenW / 2;

    // Walk target (null = not walking)
    this._targetX = null;

    // Current horizontal velocity
    this._currentVelocityX = 0;
    this._acceleration = 450;    // pixels/sec²
    this._deceleration = 600;    // pixels/sec²
    this._decelDistance = 80;    // pixels before target to begin braking

    // Jump state
    this._jumpOffsetY = 0;       // world units above ground
    this._velocityY = 0;
    this._isAirborne = false;

    // Facing direction (VRM faces -Z, Math.PI faces camera)
    this._facingRight = true;
    this._currentFacingAngle = Math.PI;
  }

  get isMoving() { return this._targetX !== null || Math.abs(this._currentVelocityX) > 5; }
  get isAirborne() { return this._isAirborne; }
  get currentVelocity() { return this._currentVelocityX; }

  /** Set position immediately (desktop pixels X). */
  setDesktopX(x) {
    this.desktopX = this._desktop.clampX(x);
    this._currentVelocityX = 0;
    this._targetX = null;
    this._applyToVRM();
  }

  /** Walk toward desktop X position. */
  walkTo(targetX) {
    this._targetX = this._desktop.clampX(targetX);
    const dx = this._targetX - this.desktopX;
    if (Math.abs(dx) > CONFIG.character.arrivalDistance) {
      this._facingRight = dx > 0;
    }
  }

  /** Immediate stop. */
  stop() {
    this._targetX = null;
    this._currentVelocityX = 0;
  }

  /** Jump from current position. */
  jump() {
    if (this._isAirborne) return;
    this._isAirborne = true;
    this._velocityY = CONFIG.character.jumpVelocity / this._desktop.screenH * this._desktop.visibleH;
  }

  /** Update each frame with delta time. */
  update(dt) {
    // --- Horizontal locomotion with smooth accel/decel ---
    if (this._targetX !== null) {
      const dx = this._targetX - this.desktopX;
      const distance = Math.abs(dx);
      const direction = Math.sign(dx);

      if (distance <= CONFIG.character.arrivalDistance) {
        // Arrived cleanly
        this.desktopX = this._targetX;
        this._targetX = null;
        this._currentVelocityX = 0;
      } else {
        // Turning toward direction
        this._facingRight = direction > 0;

        // Desired speed based on distance (braking near target)
        let maxSpeed = CONFIG.character.movementSpeed;
        if (distance < this._decelDistance) {
          maxSpeed = Math.max(50, maxSpeed * (distance / this._decelDistance));
        }

        const targetVel = direction * maxSpeed;
        if (this._currentVelocityX < targetVel) {
          this._currentVelocityX = Math.min(targetVel, this._currentVelocityX + this._acceleration * dt);
        } else if (this._currentVelocityX > targetVel) {
          this._currentVelocityX = Math.max(targetVel, this._currentVelocityX - this._deceleration * dt);
        }

        // Apply movement step
        const step = this._currentVelocityX * dt;
        if (Math.abs(step) >= distance) {
          this.desktopX = this._targetX;
          this._targetX = null;
          this._currentVelocityX = 0;
        } else {
          this.desktopX += step;
        }

        this.desktopX = this._desktop.clampX(this.desktopX);
      }
    } else {
      // Decelerate to 0 if stopped
      if (Math.abs(this._currentVelocityX) > 1) {
        this._currentVelocityX -= Math.sign(this._currentVelocityX) * this._deceleration * dt;
      } else {
        this._currentVelocityX = 0;
      }
    }

    // --- Vertical jump/gravity ---
    if (this._isAirborne) {
      const gravityWorld = CONFIG.character.gravity / this._desktop.screenH * this._desktop.visibleH;
      this._velocityY -= gravityWorld * dt;
      this._jumpOffsetY += this._velocityY * dt;
      if (this._jumpOffsetY <= 0) {
        this._jumpOffsetY = 0;
        this._velocityY = 0;
        this._isAirborne = false;
      }
    }

    // --- Smooth natural rotation facing travel direction ---
    // Facing angled slightly toward camera for cute 2.5D appearance (Math.PI ± 0.35)
    const targetAngle = this._facingRight ? Math.PI + 0.35 : Math.PI - 0.35;
    this._currentFacingAngle += (targetAngle - this._currentFacingAngle) * (CONFIG.character.turnLerp || 0.15);

    // Apply to VRM scene
    this._applyToVRM();
  }

  /** Map desktop position to world and set VRM scene position + rotation. */
  _applyToVRM() {
    if (!this._vrm.loaded) return;
    try {
      const worldX = this._desktop.desktopXToWorld(this.desktopX);
      const worldY = this._desktop.groundY + this._jumpOffsetY;
      this._vrm.scene.position.set(worldX, worldY, 0);
      this._vrm.scene.rotation.y = this._currentFacingAngle;
    } catch (e) { /* safe */ }
  }
}
