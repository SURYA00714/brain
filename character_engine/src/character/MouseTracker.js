import { CONFIG } from '../config.js';

/**
 * MouseTracker — polls cursor position at low frequency.
 * Position stored in desktop pixels. Smoothed.
 */
export class MouseTracker {
  constructor(desktopCoords) {
    this._desktop = desktopCoords;
    this._rawX = desktopCoords.screenW / 2;
    this._rawY = desktopCoords.screenH / 2;
    this.x = this._rawX;
    this.y = this._rawY;
    this._enabled = CONFIG.mouse.trackingEnabled;
    this._interval = null;
    this._screenApi = null;
  }

  start() {
    if (!this._enabled) return;
    try {
      this._screenApi = require('electron').screen;
    } catch (e) { /* no screen API */ }

    if (this._screenApi) {
      // Poll at ~20Hz
      this._interval = setInterval(() => {
        try {
          const p = this._screenApi.getCursorScreenPoint();
          this._rawX = p.x;
          this._rawY = p.y;
        } catch (e) { /* safe */ }
      }, 50);
    }
  }

  /** Call from main update loop, NOT its own loop. */
  update(dt) {
    if (!this._enabled) return;
    const s = CONFIG.mouse.smoothing;
    this.x += (this._rawX - this.x) * s;
    this.y += (this._rawY - this.y) * s;
  }

  /** Convert mouse position to world-space lookAt target. */
  getWorldLookTarget() {
    const wx = this._desktop.desktopXToWorld(this.x);
    const wy = this._desktop.desktopYToWorld(this.y);
    return { x: wx, y: wy };
  }

  stop() {
    if (this._interval) { clearInterval(this._interval); this._interval = null; }
  }

  dispose() { this.stop(); }
}
