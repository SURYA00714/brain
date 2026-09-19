import { CONFIG } from '../config.js';

/**
 * EmotionalState — lightweight emotional simulation.
 * Simple bounded values. No AI psychology system.
 * Updated slowly (per-minute scale, not per-frame).
 */
export class EmotionalState {
  constructor() {
    const e = CONFIG.emotion;
    this.energy = e.defaultEnergy;
    this.happiness = e.defaultHappiness;
    this.curiosity = e.defaultCuriosity;
    this.boredom = e.defaultBoredom;
    this.sleepiness = e.defaultSleepiness;
    this.playfulness = e.defaultPlayfulness;
    this.attention = 50;
    this.affection = 40;

    this._lastUpdate = Date.now();
    this._inactiveTime = 0;
  }

  /** Call once per second or so, NOT per frame. */
  update(isActive, isNight) {
    const now = Date.now();
    const dtMin = (now - this._lastUpdate) / 60000; // minutes
    this._lastUpdate = now;

    if (dtMin <= 0 || dtMin > 5) return; // skip huge gaps

    const e = CONFIG.emotion;
    const nightMul = isNight ? CONFIG.dayNight.nightSleepinessBonus : 1.0;

    // Energy decays slowly
    this.energy = this._clamp(this.energy - e.energyDecayRate * dtMin);

    // Sleepiness grows
    this.sleepiness = this._clamp(this.sleepiness + e.sleepinessGrowthRate * dtMin * nightMul);

    if (!isActive) {
      // Boredom grows during inactivity
      this.boredom = this._clamp(this.boredom + e.boredomGrowthRate * dtMin);
      this.attention = this._clamp(this.attention - 0.5 * dtMin);
    } else {
      // Activity reduces boredom
      this.boredom = this._clamp(this.boredom - 2.0 * dtMin);
      this.attention = this._clamp(this.attention + 1.0 * dtMin);
    }

    // Playfulness from energy
    this.playfulness = this._clamp((this.energy - 30) * 0.8);
  }

  // --- Events that affect emotion ---

  onUserInteraction() {
    this.attention = this._clamp(this.attention + 15);
    this.boredom = this._clamp(this.boredom - 10);
    this.happiness = this._clamp(this.happiness + 5);
  }

  onActivity() {
    this.boredom = this._clamp(this.boredom - 20);
    this.energy = this._clamp(this.energy - 5);
  }

  onRest() {
    this.energy = this._clamp(this.energy + 30);
    this.sleepiness = this._clamp(this.sleepiness - 20);
  }

  onSleep() {
    this.energy = this._clamp(this.energy + 50);
    this.sleepiness = 0;
    this.boredom = 0;
  }

  onFunEvent() {
    this.happiness = this._clamp(this.happiness + 15);
    this.curiosity = this._clamp(this.curiosity + 10);
    this.boredom = this._clamp(this.boredom - 15);
  }

  boostEnergy(amount) {
    this.energy = this._clamp(this.energy + amount);
    this.sleepiness = this._clamp(this.sleepiness - amount * 0.5);
  }

  onPetting() {
    this.happiness = this._clamp(this.happiness + 10);
    this.affection = this._clamp(this.affection + 5);
    this.attention = this._clamp(this.attention + 15);
    this.boredom = this._clamp(this.boredom - 15);
  }

  // --- Queries ---

  get shouldSleep() { return this.sleepiness >= CONFIG.emotion.sleepThreshold; }
  get isBored() { return this.boredom >= CONFIG.emotion.boredomThreshold; }
  get isTired() { return this.energy <= CONFIG.emotion.lowEnergyThreshold; }
  get isPlayful() { return this.playfulness > 50 && this.energy > 40; }

  /** Get the dominant emotion name for expression mapping. */
  get dominantEmotion() {
    if (this.sleepiness > 70) return 'sleepy';
    if (this.happiness > 75) return 'happy';
    if (this.boredom > 60) return 'bored';
    if (this.energy < 25) return 'tired';
    if (this.curiosity > 70) return 'curious';
    if (this.playfulness > 60) return 'playful';
    return 'neutral';
  }

  _clamp(v) { return Math.max(0, Math.min(100, v)); }

  toJSON() {
    return {
      energy: Math.round(this.energy),
      happiness: Math.round(this.happiness),
      curiosity: Math.round(this.curiosity),
      boredom: Math.round(this.boredom),
      sleepiness: Math.round(this.sleepiness),
      playfulness: Math.round(this.playfulness),
      attention: Math.round(this.attention),
      dominant: this.dominantEmotion,
    };
  }
}
