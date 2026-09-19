import { CONFIG } from '../config.js';

/**
 * ActivityRegistry — manages idle activities AO can perform.
 * Each activity has conditions, duration, animation, and exit logic.
 * Lightweight timer-based, NOT per-frame expensive.
 */

const ACTIVITIES = [
  {
    id: 'sit_rest',
    duration: [8000, 15000],
    priority: 100,
    states: ['sit'],
    condition: (emo) => emo.energy < 60,
  },
  {
    id: 'look_around',
    duration: [3000, 6000],
    priority: 50,
    states: ['idle'],
    condition: () => true,
  },
  {
    id: 'stretch',
    duration: [2000, 4000],
    priority: 50,
    states: ['wave'],  // reuse wave anim for stretch
    condition: (emo) => emo.boredom > 30,
  },
  {
    id: 'sleep',
    duration: [20000, 60000],
    priority: 200,
    states: ['sleep'],
    condition: (emo) => emo.shouldSleep,
  },
  {
    id: 'wander',
    duration: [5000, 10000],
    priority: 80,
    states: ['walk'],
    condition: (emo) => emo.isBored && emo.energy > 30,
    needsWalk: true,
  },
];

export class ActivityRegistry {
  constructor() {
    this._activities = ACTIVITIES;
    this._currentActivity = null;
    this._activityTimer = null;
  }

  get currentActivity() { return this._currentActivity; }
  get isActive() { return this._currentActivity !== null; }

  /** Pick a suitable activity based on emotional state. */
  pickActivity(emotionalState) {
    const candidates = this._activities
      .filter(a => a.condition(emotionalState))
      .sort((a, b) => b.priority - a.priority);
    if (candidates.length === 0) return null;

    // Weighted random from top candidates
    const topN = candidates.slice(0, 3);
    return topN[Math.floor(Math.random() * topN.length)];
  }

  /** Start an activity. Returns the activity object or null. */
  start(activity) {
    if (!activity) return null;
    this.stop();
    this._currentActivity = activity;
    const [minDur, maxDur] = activity.duration;
    const dur = minDur + Math.random() * (maxDur - minDur);
    this._activityTimer = setTimeout(() => {
      this._currentActivity = null;
      this._activityTimer = null;
    }, dur);
    return activity;
  }

  stop() {
    if (this._activityTimer) {
      clearTimeout(this._activityTimer);
      this._activityTimer = null;
    }
    this._currentActivity = null;
  }

  dispose() { this.stop(); }
}
