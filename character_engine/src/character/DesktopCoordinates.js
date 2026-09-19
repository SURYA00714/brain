import { CONFIG } from '../config.js';

/**
 * DesktopCoordinates — the SINGLE source of truth for mapping
 * desktop pixels ↔ Three.js world space.
 *
 * Desktop: (0,0) top-left, (screenW, screenH) bottom-right.
 * World:   camera at (0, camY, camZ), looking down -Z.
 *          Visible rect computed from FOV + aspect.
 *
 * Character walks along the BOTTOM of the screen (ground).
 */
export class DesktopCoordinates {
  constructor() {
    this.screenW = window.innerWidth;
    this.screenH = window.innerHeight;
    this._compute();

    window.addEventListener('resize', () => {
      this.screenW = window.innerWidth;
      this.screenH = window.innerHeight;
      this._compute();
    });
  }

  _compute() {
    const fovRad = (CONFIG.camera.fov / 2) * Math.PI / 180;
    const camZ = CONFIG.camera.z;

    // Visible dimensions at z=0 plane
    this.visibleH = 2 * Math.tan(fovRad) * camZ;
    this.visibleW = this.visibleH * (this.screenW / this.screenH);

    // Camera is at y = visibleH/2 so the view spans y: [0, visibleH]
    // Bottom of screen = world y=0, top of screen = world y=visibleH
    // This puts the ground at y=0 which is natural.
    this.camY = this.visibleH / 2;
  }

  /** Desktop pixel X → world X. Left edge = -visibleW/2, right edge = +visibleW/2. */
  desktopXToWorld(px) {
    return ((px / this.screenW) - 0.5) * this.visibleW;
  }

  /** Desktop pixel Y → world Y. Bottom = 0, Top = visibleH. */
  desktopYToWorld(py) {
    // Desktop y=0 is top, y=screenH is bottom.
    // World y=0 is bottom (ground), y=visibleH is top.
    return (1 - py / this.screenH) * this.visibleH;
  }

  /** World X → desktop pixel X. */
  worldXToDesktop(wx) {
    return ((wx / this.visibleW) + 0.5) * this.screenW;
  }

  /** World Y → desktop pixel Y. */
  worldYToDesktop(wy) {
    return (1 - wy / this.visibleH) * this.screenH;
  }

  /** The world Y value that corresponds to the very bottom of the screen (ground). */
  get groundY() { return 0; }

  /** Clamp desktop X to screen bounds with margin. */
  clampX(px) { return Math.max(30, Math.min(this.screenW - 30, px)); }

  /** Home position in desktop pixels — bottom-right with padding. */
  get homeX() { return this.screenW * CONFIG.character.homePositionRatio; }
}
