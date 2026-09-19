import { Logger } from '../logger.js';

/**
 * WindowManager — Throttled, non-blocking desktop window platform detection.
 * Specifically engineered for Linux X11 (XFCE, GNOME, etc.).
 *
 * Safety Principles:
 * - Polls at LOW frequency (every 2-3 seconds, NEVER per frame).
 * - Async non-blocking child_process with strict 1s timeout.
 * - Graceful fallback to empty/cached list if wmctrl/xdotool not present.
 * - Never blocks the render loop or main thread.
 */
export class WindowManager {
  constructor(desktopCoords) {
    this._desktop = desktopCoords;
    this._windows = [];
    this._activeWindow = null;
    this._pollTimer = null;
    this._isPolling = false;
    this._childProcess = null;

    try {
      this._childProcess = require('child_process');
    } catch (e) {
      Logger.warn('[WINDOW] child_process not available in renderer context.');
    }
  }

  start() {
    if (!this._childProcess) return;
    this._poll();
    this._pollTimer = setInterval(() => this._poll(), 2500);
  }

  stop() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  get windows() { return [...this._windows]; }
  get activeWindow() { return this._activeWindow; }

  /**
   * Find window by category (e.g. 'CODING', 'BROWSER', 'TERMINAL')
   */
  findByCategory(category) {
    return this._windows.find(w => w.category === category) || null;
  }

  /**
   * Safe asynchronous poll of open desktop windows using wmctrl.
   */
  _poll() {
    if (this._isPolling || !this._childProcess) return;
    this._isPolling = true;

    // wmctrl -l -G: List windows with geometry: id, desktop, x, y, w, h, client_machine, title
    this._childProcess.exec('wmctrl -l -G 2>/dev/null', { timeout: 1200 }, (err, stdout) => {
      this._isPolling = false;
      if (err || !stdout) return;

      try {
        const lines = stdout.trim().split('\n');
        const parsed = [];

        for (const line of lines) {
          const parts = line.trim().split(/\s+/);
          if (parts.length < 8) continue;

          const id = parts[0];
          const desk = parseInt(parts[1], 10);
          const x = parseInt(parts[2], 10);
          const y = parseInt(parts[3], 10);
          const w = parseInt(parts[4], 10);
          const h = parseInt(parts[5], 10);
          const title = parts.slice(7).join(' ');

          // Filter out desktop background, panels, docks, and tiny utility windows
          if (w < 200 || h < 150 || title === 'Desktop' || title === 'xfce4-panel') continue;

          const category = this._categorize(title);
          parsed.push({
            id,
            desk,
            x,
            y,
            width: w,
            height: h,
            topEdgeY: y,
            title,
            category,
            // Platform center X for sitting
            platformX: Math.round(x + w / 2),
          });
        }

        this._windows = parsed;
        if (parsed.length > 0) {
          this._activeWindow = parsed[0];
        }
      } catch (e) {
        Logger.warn('[WINDOW] Parse error:', e);
      }
    });
  }

  _categorize(title) {
    const t = title.toLowerCase();
    if (t.includes('code') || t.includes('codium') || t.includes('vim') || t.includes('sublime')) {
      return 'CODING';
    }
    if (t.includes('chrome') || t.includes('firefox') || t.includes('brave') || t.includes('edge') || t.includes('browser')) {
      return 'BROWSER';
    }
    if (t.includes('terminal') || t.includes('bash') || t.includes('zsh') || t.includes('console')) {
      return 'TERMINAL';
    }
    if (t.includes('vlc') || t.includes('spotify') || t.includes('media') || t.includes('music')) {
      return 'MEDIA';
    }
    if (t.includes('thunar') || t.includes('files') || t.includes('folder')) {
      return 'FILE_MANAGER';
    }
    return 'GENERIC';
  }

  dispose() {
    this.stop();
    this._windows = [];
    this._activeWindow = null;
  }
}
