import * as THREE from 'three';
import { CONFIG } from '../config.js';

/**
 * LookAtController — smooth head/eye tracking.
 * Target is set in world space. Interpolates smoothly.
 */
export class LookAtController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._target = new THREE.Object3D();
    this._enabled = true;
    this._currentX = 0;
    this._currentY = 1.0;
    this._desiredX = 0;
    this._desiredY = 1.0;
  }

  get target() { return this._target; }
  enable() { this._enabled = true; }
  disable() { this._enabled = false; }

  setTarget(x, y) {
    this._desiredX = x;
    this._desiredY = y;
  }

  update(dt) {
    if (!this._enabled || !this._vrm.loaded) return;
    try {
      const s = CONFIG.mouse.smoothing;
      this._currentX += (this._desiredX - this._currentX) * s;
      this._currentY += (this._desiredY - this._currentY) * s;

      // Clamp
      this._currentX = Math.max(-2, Math.min(2, this._currentX));
      this._currentY = Math.max(-1, Math.min(3, this._currentY));

      this._target.position.set(this._currentX, this._currentY, 2.0);
      this._vrm.setLookAt(this._target);
    } catch (e) { /* safe */ }
  }

  dispose() { this._enabled = false; }
}
