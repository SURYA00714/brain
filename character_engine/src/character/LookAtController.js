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
  [ATTENTION_TARGET.LEFT]:    { x: -0.65, y: 1.20 },
  [ATTENTION_TARGET.RIGHT]:   { x: 0.65, y: 1.20 },
  [ATTENTION_TARGET.UP]:      { x: 0.0, y: 1.65 },
  [ATTENTION_TARGET.DOWN]:    { x: 0.0, y: 0.75 },
  [ATTENTION_TARGET.USER]:    { x: 0.0, y: 1.30 },
};

/**
 * LookAtController — Lifelike Attention Model & Eye/Head Motion.
 * Spec Section 13, 14:
 * - currentAttentionTarget, attentionStrength, attentionDuration
 * - Natural rhythm: glance -> hold -> fade -> settle -> quiet pause
 * - Completely local, zero OS/X11 calls
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

  /**
   * Set specific semantic attention target with duration.
   */
  setAttention(targetName, durationSeconds = 3.5, strength = 1.0) {
    this.currentAttentionTarget = targetName;
    this.attentionDuration = durationSeconds;
    this.attentionStrength = strength;

    const coords = TARGET_COORDINATES[targetName] || TARGET_COORDINATES[ATTENTION_TARGET.FORWARD];
    this._desiredX = coords.x * strength;
    this._desiredY = coords.y;

    // Next autonomous glance postponed until after this attention period
    this._nextGlanceTime = this._time + durationSeconds + 3.0 + Math.random() * 3.0;
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

    // Autonomous human glance rhythm with quiet pauses
    if (this._time >= this._nextGlanceTime) {
      this._scheduleNextGlance();
    }

    try {
      // Smooth interpolation (prevent snapping)
      const s = CONFIG.mouse.smoothing || 0.05;
      this._currentX += (this._desiredX - this._currentX) * s;
      this._currentY += (this._desiredY - this._currentY) * s;

      // Safe bounds clamping
      this._currentX = Math.max(-1.5, Math.min(1.5, this._currentX));
      this._currentY = Math.max(0.5, Math.min(2.0, this._currentY));

      this._target.position.set(this._currentX, this._currentY, 2.5);
      this._vrm.setLookAt(this._target);
    } catch (e) { /* safe */ }
  }

  _scheduleNextGlance() {
    // Spec Section 10: quiet pause periods are required.
    // 60% chance to settle forward, 40% chance to glance gently left/right/up/down
    const rand = Math.random();

    if (rand < 0.60) {
      // Settle forward towards user (quiet presence)
      this.currentAttentionTarget = ATTENTION_TARGET.FORWARD;
      this._desiredX = (Math.random() - 0.5) * 0.15;
      this._desiredY = 1.25;
      // Hold forward longer (5 to 10 seconds quiet pause)
      this._nextGlanceTime = this._time + 5.0 + Math.random() * 5.0;
    } else if (rand < 0.80) {
      // Glance left or right
      const isLeft = Math.random() > 0.5;
      this.currentAttentionTarget = isLeft ? ATTENTION_TARGET.LEFT : ATTENTION_TARGET.RIGHT;
      this._desiredX = isLeft ? -0.45 : 0.45;
      this._desiredY = 1.20 + (Math.random() - 0.5) * 0.15;
      // Brief glance (2 to 4 seconds)
      this._nextGlanceTime = this._time + 2.5 + Math.random() * 2.0;
    } else {
      // Glance slightly down or up
      const isDown = Math.random() > 0.5;
      this.currentAttentionTarget = isDown ? ATTENTION_TARGET.DOWN : ATTENTION_TARGET.UP;
      this._desiredX = (Math.random() - 0.5) * 0.2;
      this._desiredY = isDown ? 0.95 : 1.50;
      this._nextGlanceTime = this._time + 2.0 + Math.random() * 2.0;
    }
  }

  dispose() { this._enabled = false; }
}
