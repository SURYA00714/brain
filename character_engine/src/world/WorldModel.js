import { CONFIG } from '../config.js';

/**
 * WorldModel — Desktop environment model & spatial ground truth.
 *
 * Implements Section 1, 2, 3, 4 of the Master Specification:
 * - Screen dimensions & safe margins (SAFE_MARGIN_X, SAFE_MARGIN_Y)
 * - Ground truth floor (groundY = 0)
 * - Character 3D bounding box (width, height, depth)
 * - Support surfaces (Ground + Windows)
 * - Strict safe-area clamping so AO's entire body remains inside the screen.
 */
export class WorldModel {
  constructor() {
    this.screenW = typeof window !== 'undefined' ? window.innerWidth : 1366;
    this.screenH = typeof window !== 'undefined' ? window.innerHeight : 768;

    // Screen safety margins (pixels)
    this.SAFE_MARGIN_X = 60;
    this.SAFE_MARGIN_Y = 40;

    // Character approximate physical dimensions (world units)
    this.charWidth = 0.40;   // approx body span with resting arms
    this.charHeight = 1.45;  // head to feet height
    this.charDepth = 0.25;

    // World visible rect calculations
    this._computeWorldMetrics();

    if (typeof window !== 'undefined') {
      window.addEventListener('resize', () => {
        this.screenW = window.innerWidth;
        this.screenH = window.innerHeight;
        this._computeWorldMetrics();
      });
    }

    // Default support surface: the desktop ground floor
    this.groundSurface = {
      id: 'desktop_floor',
      type: 'GROUND',
      desktopY: this.screenH,
      worldY: 0,
      minX: 0,
      maxX: this.screenW,
      isValid: true
    };
  }

  _computeWorldMetrics() {
    const fov = (CONFIG?.camera?.fov || 30) * Math.PI / 360;
    const camZ = CONFIG?.camera?.z || 3.2;

    this.visibleH = 2 * Math.tan(fov) * camZ;
    this.visibleW = this.visibleH * (this.screenW / this.screenH);
    this.camY = this.visibleH / 2;

    // Pixel-to-world conversion factors
    this.pxToWorldX = this.visibleW / this.screenW;
    this.pxToWorldY = this.visibleH / this.screenH;

    // Character half-width in desktop pixels
    this.charHalfWidthPx = (this.charWidth / this.pxToWorldX) / 2;
    this.charHeightPx = this.charHeight / this.pxToWorldY;

    // Safe bounds for character origin (center of feet)
    this.safeMinX = this.SAFE_MARGIN_X + this.charHalfWidthPx;
    this.safeMaxX = this.screenW - this.SAFE_MARGIN_X - this.charHalfWidthPx;
  }

  /** Desktop pixel X → Three.js World X */
  desktopXToWorld(px) {
    return ((px / this.screenW) - 0.5) * this.visibleW;
  }

  /** Desktop pixel Y → Three.js World Y */
  desktopYToWorld(py) {
    return (1 - py / this.screenH) * this.visibleH;
  }

  /** World X → Desktop pixel X */
  worldXToDesktop(wx) {
    return ((wx / this.visibleW) + 0.5) * this.screenW;
  }

  /** World Y → Desktop pixel Y */
  worldYToDesktop(wy) {
    return (1 - wy / this.visibleH) * this.screenH;
  }

  /** Absolute ground world Y (bottom of screen) */
  get groundY() {
    return 0;
  }

  /**
   * Clamps a desktop X position so AO's entire body remains inside the safe screen margin.
   */
  clampSafeX(px) {
    return Math.max(this.safeMinX, Math.min(this.safeMaxX, px));
  }

  /**
   * Validates whether a given desktop coordinate is within the safe area.
   */
  isInsideSafeBounds(px, py = this.screenH) {
    const safeX = px >= this.safeMinX && px <= this.safeMaxX;
    const safeY = py >= this.SAFE_MARGIN_Y && py <= this.screenH;
    return safeX && safeY;
  }

  /** Home position (bottom-right desktop area with safe padding) */
  get homeDesktopX() {
    const ratio = CONFIG?.character?.homePositionRatio || 0.82;
    return this.clampSafeX(this.screenW * ratio);
  }
}
