import { CONFIG } from '../config.js';

/**
 * WorldModel — Desktop environment model & spatial ground truth.
 *
 * Implements Section 1, 2, 3, 4 of the Master Specification:
 * - Dynamic posture-aware 3D bounding envelope (standing, walking, sitting, sleeping)
 * - Conservative screen safety margins (SAFE_MARGIN_X, SAFE_MARGIN_Y)
 * - Ground floor (groundY = 0)
 * - Single deterministic conversion between desktop pixels and Three.js world units
 * - Strict full-body containment so no limb, gesture, or head ever visually leaves the screen
 */
export class WorldModel {
  constructor() {
    this.screenW = typeof window !== 'undefined' ? window.innerWidth : 1366;
    this.screenH = typeof window !== 'undefined' ? window.innerHeight : 768;

    // Minimum boundary margin from physical display edges (pixels)
    this.SAFE_MARGIN_X = 60;
    this.SAFE_MARGIN_Y = 40;

    // Posture-specific 3D bounding envelopes (meters / world units)
    this.ENVELOPES = Object.freeze({
      STANDING: { width: 0.42, height: 1.45, depth: 0.28 },
      WALKING: { width: 0.48, height: 1.45, depth: 0.40 },
      SITTING: { width: 0.42, height: 0.95, depth: 0.50 },
      SQUATTING: { width: 0.45, height: 0.85, depth: 0.45 },
      SLEEPING: { width: 0.70, height: 0.45, depth: 0.50 },
      RESTING: { width: 0.45, height: 1.10, depth: 0.45 }
    });

    this._computeWorldMetrics();

    if (typeof window !== 'undefined') {
      window.addEventListener('resize', () => {
        this.screenW = window.innerWidth;
        this.screenH = window.innerHeight;
        this._computeWorldMetrics();
      });
    }

    // Default ground support surface
    this.groundSurface = Object.freeze({
      id: 'desktop_floor',
      type: 'GROUND',
      desktopY: this.screenH,
      worldY: 0,
      minX: 0,
      maxX: this.screenW,
      isValid: true
    });
  }

  _computeWorldMetrics() {
    const fov = (CONFIG?.camera?.fov || 30) * Math.PI / 360;
    const camZ = CONFIG?.camera?.z || 3.2;

    this.visibleH = 2 * Math.tan(fov) * camZ;
    this.visibleW = this.visibleH * (this.screenW / this.screenH);
    this.camY = this.visibleH / 2;

    this.pxToWorldX = this.visibleW / this.screenW;
    this.pxToWorldY = this.visibleH / this.screenH;
  }

  /**
   * Retrieves the physical 3D envelope and pixel dimensions for a given posture.
   */
  getEnvelope(posture = 'STANDING') {
    const env = this.ENVELOPES[posture] || this.ENVELOPES.STANDING;
    const halfWidthPx = (env.width / this.pxToWorldX) / 2;
    const heightPx = env.height / this.pxToWorldY;
    const depthPx = env.depth / this.pxToWorldX;
    return {
      ...env,
      halfWidthPx,
      heightPx,
      depthPx
    };
  }

  /**
   * Gets the safe desktop X boundary range for a specific posture.
   */
  getSafeXBounds(posture = 'STANDING') {
    const { halfWidthPx } = this.getEnvelope(posture);
    const minX = this.SAFE_MARGIN_X + halfWidthPx;
    const maxX = this.screenW - this.SAFE_MARGIN_X - halfWidthPx;
    return { minX, maxX };
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
   * Clamps a desktop X position so the full body envelope remains strictly inside safe margins.
   */
  clampSafeX(px, posture = 'STANDING') {
    const { minX, maxX } = this.getSafeXBounds(posture);
    return Math.max(minX, Math.min(maxX, px));
  }

  /**
   * Validates whether an entire character envelope fits within the screen's safe boundaries.
   */
  isInsideSafeBounds(px, py = this.screenH, posture = 'STANDING') {
    const { minX, maxX } = this.getSafeXBounds(posture);
    const { heightPx } = this.getEnvelope(posture);
    const safeX = px >= minX && px <= maxX;
    const safeY = (py - heightPx) >= this.SAFE_MARGIN_Y && py <= (this.screenH + 5);
    return safeX && safeY;
  }

  /** Safe home desktop X position */
  get homeDesktopX() {
    const ratio = CONFIG?.character?.homePositionRatio || 0.82;
    return this.clampSafeX(this.screenW * ratio, 'STANDING');
  }
}
