import { CONFIG } from '../config.js';

/**
 * MovementController — ONE source of truth for character position.
 *
 * Position is stored in DESKTOP PIXELS (desktopX).
 * jumpOffsetY is a world-space offset above the ground (0 = on ground).
 * Every frame, the final world position is computed and applied to the VRM scene.
 */
export class MovementController {
  constructor(vrmAdapter, desktopCoords) {
    this._vrm = vrmAdapter;
    this._desktop = desktopCoords;

    // Authoritative desktop position (X in pixels, along the ground)
    this.desktopX = desktopCoords.screenW / 2;

    // Walk target (null = not walking)
    this._targetX = null;

    // Jump state
    this._jumpOffsetY = 0;   // world units above ground
    this._velocityY = 0;
    this._isAirborne = false;

    // Facing direction
    this._facingRight = true;
    this._currentFacingAngle = Math.PI; // VRM faces -Z, we rotate to face camera
  }

  get isMoving() { return this._targetX !== null; }
  get isAirborne() { return this._isAirborne; }

  /** Set position immediately (desktop pixels X). */
  setDesktopX(x) {
    this.desktopX = this._desktop.clampX(x);
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
  }

  /** Jump from current position. */
  jump() {
    if (this._isAirborne) return;
    this._isAirborne = true;
    this._velocityY = CONFIG.character.jumpVelocity / this._desktop.screenH * this._desktop.visibleH;
  }

  /** Update each frame. */
  update(dt) {
    let changed = false;

    // --- Horizontal walk ---
    if (this._targetX !== null) {
      const dx = this._targetX - this.desktopX;
      if (Math.abs(dx) <= CONFIG.character.arrivalDistance) {
        this.desktopX = this._targetX;
        this._targetX = null;
      } else {
        const step = Math.sign(dx) * CONFIG.character.movementSpeed * dt;
        if (Math.abs(step) > Math.abs(dx)) {
          this.desktopX = this._targetX;
          this._targetX = null;
        } else {
          this.desktopX += step;
        }
        this.desktopX = this._desktop.clampX(this.desktopX);
      }
      changed = true;
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
      changed = true;
    }

    // --- Apply facing ---
    const targetAngle = this._facingRight ? Math.PI + 0.25 : Math.PI - 0.25;
    this._currentFacingAngle += (targetAngle - this._currentFacingAngle) * CONFIG.character.turnLerp;

    // Always apply position to VRM
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
