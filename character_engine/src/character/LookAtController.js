import * as THREE from 'three';
import { CONFIG } from '../config.js';

/**
 * LookAtController — Smooth, natural autonomous head/eye movement.
 * Zero X11 calls. Completely local and safe.
 *
 * Implements lifelike human glancing:
 * - Glancing forward toward the user
 * - Subtle natural shifts (left, right, slight downward)
 * - Controlled smoothly via interpolation
 */
export class LookAtController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._target = new THREE.Object3D();
    this._enabled = true;

    this._currentX = 0;
    this._currentY = 1.2;
    this._desiredX = 0;
    this._desiredY = 1.2;

    this._nextGlanceTime = 3.0;
    this._time = 0;
  }

  get target() { return this._target; }
  enable() { this._enabled = true; }
  disable() { this._enabled = false; }

  setTarget(x, y) {
    this._desiredX = x;
    this._desiredY = y;
    // Reset glance timer when an explicit target is set
    this._nextGlanceTime = this._time + 5.0;
  }

  update(dt) {
    if (!this._enabled || !this._vrm.loaded) return;
    this._time += dt;

    // Autonomous subtle natural glancing
    if (this._time >= this._nextGlanceTime) {
      this._scheduleNextGlance();
    }

    try {
      const s = CONFIG.mouse.smoothing || 0.05;
      this._currentX += (this._desiredX - this._currentX) * s;
      this._currentY += (this._desiredY - this._currentY) * s;

      // Clamp to safe angles
      this._currentX = Math.max(-1.5, Math.min(1.5, this._currentX));
      this._currentY = Math.max(0.5, Math.min(2.0, this._currentY));

      this._target.position.set(this._currentX, this._currentY, 2.5);
      this._vrm.setLookAt(this._target);
    } catch (e) { /* safe */ }
  }

  _scheduleNextGlance() {
    this._nextGlanceTime = this._time + 3.0 + Math.random() * 4.0;
    // Small natural glance deviation (-0.3 to +0.3 rad horizontally, 1.0 to 1.4 vertically)
    const glanceX = (Math.random() - 0.5) * 0.6;
    const glanceY = 1.1 + Math.random() * 0.3;
    this._desiredX = glanceX;
    this._desiredY = glanceY;
  }

  dispose() { this._enabled = false; }
}
