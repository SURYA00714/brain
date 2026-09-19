import { CONFIG } from '../config.js';

/**
 * DayNightCycle — uses local system time.
 * No heavy effects. Just provides isNight for behavior modulation.
 */
export class DayNightCycle {
  constructor() {
    this._cachedHour = new Date().getHours();
    this._lastCheck = Date.now();
  }

  /** Check every ~60 seconds, not every frame. */
  update() {
    const now = Date.now();
    if (now - this._lastCheck < 60000) return;
    this._lastCheck = now;
    this._cachedHour = new Date().getHours();
  }

  get isNight() {
    const h = this._cachedHour;
    const ns = CONFIG.dayNight.nightStartHour;
    const ne = CONFIG.dayNight.nightEndHour;
    return h >= ns || h < ne;
  }

  get isDaytime() { return !this.isNight; }

  /** Activity frequency multiplier — lower at night. */
  get activityMultiplier() {
    return this.isNight ? CONFIG.dayNight.nightActivityMultiplier : 1.0;
  }

  get hour() { return this._cachedHour; }
}
