/**
 * MouseTracker — Passive & safe cursor tracker.
 *
 * CRITICAL LINUX STABILITY FIX:
 * Polling `screen.getCursorScreenPoint()` via synchronous X11 calls in an
 * interval causes X11 pointer grab deadlocks and freezes the desktop during clicks.
 *
 * This module is completely passive: zero X11 polling, zero timers, zero IPC locks.
 */
export class MouseTracker {
  constructor(desktopCoords) {
    this._desktop = desktopCoords;
    this.x = desktopCoords.screenW / 2;
    this.y = desktopCoords.screenH / 2;
    this._enabled = false;
  }

  start() {
    // Intentionally no-op: no polling to prevent X11 deadlocks
  }

  update(dt) {
    // Pure in-memory update, no OS/X11 calls
  }

  setCursor(x, y) {
    this.x = x;
    this.y = y;
  }

  getWorldLookTarget() {
    const wx = this._desktop.desktopXToWorld(this.x);
    const wy = this._desktop.desktopYToWorld(this.y);
    return { x: wx, y: wy };
  }

  stop() {}
  dispose() {}
}
