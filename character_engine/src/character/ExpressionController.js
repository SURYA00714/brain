import { CONFIG } from '../config.js';

/**
 * ExpressionController — blinking + emotions.
 * Timers only. No loops.
 */
export class ExpressionController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._currentEmotion = 'neutral';
    this._blinkTimer = null;

    this._emotionMap = {
      happy: 'happy', sad: 'sad', angry: 'angry',
      surprised: 'surprised', sleepy: 'relaxed',
      neutral: 'neutral', excited: 'happy', confused: 'neutral',
    };
  }

  start() { this._scheduleBlink(); }

  stop() {
    if (this._blinkTimer) { clearTimeout(this._blinkTimer); this._blinkTimer = null; }
  }

  setEmotion(name) {
    try {
      this._vrm.resetExpressions();
      const expr = this._emotionMap[name] || 'neutral';
      if (expr !== 'neutral' && this._vrm.hasExpression(expr)) {
        this._vrm.setExpression(expr, 1.0);
      }
      this._currentEmotion = name;
    } catch (e) { /* safe */ }
  }

  _scheduleBlink() {
    const delay = CONFIG.behavior.blinkIntervalMs + Math.random() * CONFIG.behavior.blinkVarianceMs;
    this._blinkTimer = setTimeout(() => {
      try {
        if (!this._vrm.loaded) { this._scheduleBlink(); return; }
        this._vrm.setExpression('blink', 1.0);
        setTimeout(() => {
          try { this._vrm.setExpression('blink', 0); } catch (e) { /* ok */ }
          this._scheduleBlink();
        }, 120);
      } catch (e) { this._scheduleBlink(); }
    }, delay);
  }

  dispose() { this.stop(); }
}
