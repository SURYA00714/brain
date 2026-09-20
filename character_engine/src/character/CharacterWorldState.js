/**
 * CharacterWorldState — Authoritative Character State representation.
 *
 * Implements Section 47 & 48 of the Master Specification:
 * - There must be ONE authoritative AO world position.
 * - There must be ONE authoritative posture.
 * - All systems read from and write to this authoritative record.
 */
export class CharacterWorldState {
  constructor(worldModel) {
    this._world = worldModel;

    // Authoritative desktop coordinates
    this.desktopX = this._world.homeDesktopX;
    this.desktopY = this._world.screenH;

    // Authoritative world coordinates
    this.worldX = this._world.desktopXToWorld(this.desktopX);
    this.worldY = this._world.groundY;
    this.worldZ = 0;

    // Locomotion & orientation
    this.facingRight = true;
    this.facingAngle = Math.PI; // Face toward camera / viewer by default
    this.velocityX = 0;
    this.velocityY = 0;

    // Posture & Support
    this.posture = 'STANDING';
    this.supportSurface = this._world.groundSurface;
    this.isGrounded = true;

    // Active Action Intent & Execution
    this.currentIntent = null;
    this.isTransitioning = false;
  }

  /**
   * Sets authoritative horizontal position (desktop pixels), updating world coordinates.
   */
  setPosition(desktopX, desktopY = this._world.screenH) {
    this.desktopX = this._world.clampSafeX(desktopX);
    this.desktopY = desktopY;
    this.worldX = this._world.desktopXToWorld(this.desktopX);
    this.worldY = this._world.desktopYToWorld(this.desktopY);
  }

  /**
   * Sets vertical world offset (e.g. jump or elevated platform).
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
   * Update authoritative posture.
   */
  setPosture(newPosture) {
    this.posture = newPosture;
  }
}
