/**
 * CharacterWorldState — Authoritative Character State representation.
 *
 * Implements Section 47 & 48 of the Master Specification:
 * - Single authoritative source of truth for position, velocity, facing, posture, and support.
 * - Prevents dual coordinate systems or competing state owners.
 */
export class CharacterWorldState {
  constructor(worldModel) {
    this._world = worldModel;

    // Posture
    this.posture = 'STANDING';

    // Authoritative desktop coordinates (pixels)
    this.desktopX = this._world.homeDesktopX;
    this.desktopY = this._world.screenH;

    // Authoritative world coordinates (meters)
    this.worldX = this._world.desktopXToWorld(this.desktopX);
    this.worldY = this._world.groundY;
    this.worldZ = 0;

    // Kinematics & orientation
    this.velocityX = 0;
    this.velocityY = 0;
    this.facingRight = true;
    this.facingAngle = Math.PI; // Face viewer by default

    // Support surface & contact
    this.supportSurface = this._world.groundSurface;
    this.isGrounded = true;

    // Active Action Lifecycle
    this.activeIntent = null;
    this.actionPhase = 'IDLE'; // IDLE, START, ACTIVE, RECOVERY
    this.isTransitioning = false;
  }

  /**
   * Sets authoritative horizontal position, clamped to safe boundaries for current posture.
   */
  setPosition(desktopX, desktopY = this._world.screenH) {
    this.desktopX = this._world.clampSafeX(desktopX, this.posture);
    this.desktopY = desktopY;
    this.worldX = this._world.desktopXToWorld(this.desktopX);
    this.worldY = this._world.desktopYToWorld(this.desktopY);
  }

  /**
   * Sets vertical world offset (e.g. airborne or elevated window platform).
   */
  setWorldOffset(worldY) {
    this.worldY = worldY;
    this.desktopY = this._world.worldYToDesktop(worldY);
  }

  /**
   * Update orientation facing direction.
   */
  setFacing(isFacingRight, targetAngle) {
    this.facingRight = isFacingRight;
    this.facingAngle = targetAngle;
  }

  /**
   * Update authoritative posture and re-clamp position if envelope changed.
   */
  setPosture(newPosture) {
    this.posture = newPosture;
    // Re-verify safe bounds with new posture envelope
    this.desktopX = this._world.clampSafeX(this.desktopX, this.posture);
    this.worldX = this._world.desktopXToWorld(this.desktopX);
  }

  /**
   * Returns current 3D world bounding box.
   */
  getWorldBounds() {
    const env = this._world.getEnvelope(this.posture);
    return {
      minX: this.worldX - env.width / 2,
      maxX: this.worldX + env.width / 2,
      minY: this.worldY,
      maxY: this.worldY + env.height,
      minZ: -env.depth / 2,
      maxZ: env.depth / 2
    };
  }
}
