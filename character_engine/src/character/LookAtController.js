import * as THREE from 'three';
import { CONFIG } from '../config.js';

export const ATTENTION_TARGET = {
  FORWARD: 'FORWARD',
  LEFT: 'LEFT',
  RIGHT: 'RIGHT',
  UP: 'UP',
  DOWN: 'DOWN',
  USER: 'USER',
  CUSTOM: 'CUSTOM',
};

const TARGET_COORDINATES = {
  [ATTENTION_TARGET.FORWARD]: { x: 0.0, y: 1.25 },
  [ATTENTION_TARGET.LEFT]:    { x: -0.15, y: 1.25 },
  [ATTENTION_TARGET.RIGHT]:   { x: 0.15, y: 1.25 },
  [ATTENTION_TARGET.UP]:      { x: 0.0, y: 1.45 },
  [ATTENTION_TARGET.DOWN]:    { x: 0.0, y: 1.05 },
  [ATTENTION_TARGET.USER]:    { x: 0.0, y: 1.25 },
};

/**
 * LookAtController — Attention Model keeping character facing straight forward.
 */
export class LookAtController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._target = new THREE.Object3D();
    this._enabled = true;

    this.currentAttentionTarget = ATTENTION_TARGET.FORWARD;
    this.attentionStrength = 1.0;
    this.attentionDuration = 4.0;

    this._currentX = 0;
    this._currentY = 1.25;
    this._desiredX = 0;
    this._desiredY = 1.25;

    this._time = 0;
    this._nextGlanceTime = 4.0;
  }

  get target() { return this._target; }
  enable() { this._enabled = true; }
  disable() { this._enabled = false; }

  setAttention(targetName, durationSeconds = 3.5, strength = 1.0) {
    this.currentAttentionTarget = targetName;
    this.attentionDuration = durationSeconds;
    this.attentionStrength = strength;

    const coords = TARGET_COORDINATES[targetName] || TARGET_COORDINATES[ATTENTION_TARGET.FORWARD];
    this._desiredX = coords.x * strength;
    this._desiredY = coords.y;

    this._nextGlanceTime = this._time + durationSeconds + 4.0;
  }

  setTarget(x, y) {
    this.currentAttentionTarget = ATTENTION_TARGET.CUSTOM;
    this._desiredX = x;
    this._desiredY = y;
    this._nextGlanceTime = this._time + 5.0;
  }

  update(dt) {
    if (!this._enabled || !this._vrm.loaded) return;
    this._time += dt;

    if (this._time >= this._nextGlanceTime) {
      this._scheduleNextGlance();
    }

    try {
      const s = CONFIG.mouse.smoothing || 0.05;
      this._currentX += (this._desiredX - this._currentX) * s;
      this._currentY += (this._desiredY - this._currentY) * s;

      // Tight clamp keeping face straight forward
      this._currentX = Math.max(-0.25, Math.min(0.25, this._currentX));
      this._currentY = Math.max(0.8, Math.min(1.6, this._currentY));

      this._target.position.set(this._currentX, this._currentY, 3.0);
      this._vrm.setLookAt(this._target);
    } catch (e) {}
  }

  _scheduleNextGlance() {
    // 85% forward looking straight at user, 15% subtle eye shift
    if (Math.random() < 0.85) {
      this.currentAttentionTarget = ATTENTION_TARGET.FORWARD;
      this._desiredX = 0;
      this._desiredY = 1.25;
      this._nextGlanceTime = this._time + 6.0 + Math.random() * 6.0;
    } else {
      this._desiredX = (Math.random() - 0.5) * 0.12;
      this._desiredY = 1.25 + (Math.random() - 0.5) * 0.1;
      this._nextGlanceTime = this._time + 2.0 + Math.random() * 2.0;
    }
  }

  dispose() { this._enabled = false; }
}
