import { CONFIG } from '../config.js';

/**
 * EmotionalState — Internal living mind state for Ao.
 * Spec Section 6, 7, 19:
 * Normalized 0.0 → 1.0 representation.
 * Changes gradually over time. No sudden random jumps.
 */
export class EmotionalState {
  constructor() {
    // Internal needs & feelings (0.0 to 1.0)
    this.energy = 0.80;
    this.sleepiness = 0.10;
    this.happiness = 0.65;
    this.curiosity = 0.75;
    this.boredom = 0.05;
    this.playfulness = 0.60;
    this.attention = 0.50;
    this.socialNeed = 0.40;
    this.calmness = 0.70;
    this.affection = 0.50;

    // Spec Section 19: Base personality weights
    this.personality = {
      cute: 0.70,
      curious: 0.80,
      playful: 0.65,
      mischievous: 0.45,
      calm: 0.60,
      social: 0.55,
      lazy: 0.30,
      dramatic: 0.25,
    };

    this._lastUpdate = Date.now();
  }

  /**
   * Delta-time based gradual internal update.
   * Can be called per-frame or per-interval smoothly.
   */
  update(isActive, isNight, dtSeconds = null) {
    const now = Date.now();
    const dt = dtSeconds !== null ? dtSeconds : Math.min(10, (now - this._lastUpdate) / 1000);
    this._lastUpdate = now;

    if (dt <= 0) return;
    const dtMin = dt / 60; // elapsed in minutes

    const nightMul = isNight ? (CONFIG.dayNight?.nightSleepinessBonus || 2.0) : 1.0;

    // Energy slowly decays (approx 5% per 10 minutes active, 2% if resting)
    const energyDecay = isActive ? 0.005 * dtMin : 0.002 * dtMin;
    this.energy = this._clamp(this.energy - energyDecay);

    // Sleepiness increases gradually, accelerated at night
    const sleepRate = 0.004 * dtMin * nightMul;
    this.sleepiness = this._clamp(this.sleepiness + sleepRate);

    // Boredom increases when inactive
    if (!isActive) {
      this.boredom = this._clamp(this.boredom + 0.015 * dtMin);
      this.socialNeed = this._clamp(this.socialNeed + 0.008 * dtMin);
      this.attention = this._clamp(this.attention - 0.02 * dtMin);
      this.calmness = this._clamp(this.calmness + 0.01 * dtMin);
    } else {
      this.boredom = this._clamp(this.boredom - 0.04 * dtMin);
      this.attention = this._clamp(this.attention + 0.03 * dtMin);
    }

    // Playfulness derived from energy & boredom
    this.playfulness = this._clamp(this.energy * 0.7 + (1 - this.sleepiness) * 0.3);
  }

  // --- External Stimuli & Interaction ---

  onUserInteraction() {
    this.attention = this._clamp(this.attention + 0.30);
    this.boredom = this._clamp(this.boredom - 0.25);
    this.happiness = this._clamp(this.happiness + 0.15);
    this.socialNeed = this._clamp(this.socialNeed - 0.20);
  }

  onPetting() {
    this.happiness = this._clamp(this.happiness + 0.20);
    this.affection = this._clamp(this.affection + 0.15);
    this.attention = this._clamp(this.attention + 0.25);
    this.boredom = this._clamp(this.boredom - 0.20);
    this.calmness = this._clamp(this.calmness + 0.15);
  }

  onActivity() {
    this.boredom = this._clamp(this.boredom - 0.30);
    this.energy = this._clamp(this.energy - 0.08);
    this.calmness = this._clamp(this.calmness + 0.10);
  }

  onRest() {
    this.energy = this._clamp(this.energy + 0.25);
    this.sleepiness = this._clamp(this.sleepiness - 0.15);
    this.calmness = this._clamp(this.calmness + 0.25);
  }

  onSleep() {
    this.energy = this._clamp(this.energy + 0.60);
    this.sleepiness = 0.0;
    this.boredom = 0.0;
  }

  onFunEvent() {
    this.happiness = this._clamp(this.happiness + 0.25);
    this.curiosity = this._clamp(this.curiosity + 0.20);
    this.boredom = this._clamp(this.boredom - 0.25);
  }

  boostEnergy(amountNormalized) {
    const val = amountNormalized > 1 ? amountNormalized / 100 : amountNormalized;
    this.energy = this._clamp(this.energy + val);
    this.sleepiness = this._clamp(this.sleepiness - val * 0.5);
  }

  // --- Queries ---

  get shouldSleep() { return this.sleepiness >= 0.80; }
  get isBored() { return this.boredom >= 0.65; }
  get isTired() { return this.energy <= 0.25; }
  get isPlayful() { return this.playfulness > 0.55 && this.energy > 0.40; }

  /** Dominant emotion for facial expression mapping */
  get dominantEmotion() {
    if (this.sleepiness > 0.70) return 'sleepy';
    if (this.happiness > 0.70) return 'happy';
    if (this.boredom > 0.65) return 'curious';
    if (this.curiosity > 0.70) return 'curious';
    if (this.energy < 0.25) return 'sleepy';
    if (this.playfulness > 0.65) return 'happy';
    return 'neutral';
  }

  _clamp(v) { return Math.max(0.0, Math.min(1.0, v)); }

  toJSON() {
    return {
      energy: Math.round(this.energy * 100),
      happiness: Math.round(this.happiness * 100),
      curiosity: Math.round(this.curiosity * 100),
      boredom: Math.round(this.boredom * 100),
      sleepiness: Math.round(this.sleepiness * 100),
      playfulness: Math.round(this.playfulness * 100),
      attention: Math.round(this.attention * 100),
      socialNeed: Math.round(this.socialNeed * 100),
      calmness: Math.round(this.calmness * 100),
      dominant: this.dominantEmotion,
    };
  }
}
