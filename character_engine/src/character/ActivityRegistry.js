import { CONFIG } from '../config.js';
import { STATE, PRIORITY } from './CharacterState.js';

/**
 * ActivityRegistry — manages logical human-like activities for Ao.
 * Every activity has:
 *  - Conditions (energy, boredom, time, location)
 *  - Preparation / Path (e.g. walk home, sit down)
 *  - Action phases (entry, active, reaction)
 *  - Exit transition / Return path
 *  - Cooldown to prevent repetitive behavior spam
 */

export const ACTIVITIES = [
  {
    id: 'read_book',
    name: 'Reading Book',
    duration: [15000, 30000],
    cooldownMs: 60000,
    lastRun: 0,
    priority: 120,
    requiresHome: true,
    condition: (emo, dayNight) => emo.energy > 25 && emo.boredom > 15 && !dayNight?.isNight,
    run: async (char) => {
      // 1. Move to home if not already there
      char.goHome();
      await char.waitForArrival(10000);
      // 2. Sit down
      char.sit();
      await char.wait(1200);
      // 3. Open book & read
      char.state.transition(STATE.READING, PRIORITY.ACTIVITY);
      char.expression.setEmotion('neutral');
      char.playAnimation('read');
      // 4. Halfway page turn or glance
      await char.wait(8000);
      if (char.state.state === STATE.READING) {
        char.expression.setEmotion('happy');
      }
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
    }
  },
  {
    id: 'drink_tea',
    name: 'Drinking Tea',
    duration: [8000, 14000],
    cooldownMs: 90000,
    lastRun: 0,
    priority: 100,
    requiresHome: true,
    condition: (emo) => emo.energy < 75 && emo.boredom > 10,
    run: async (char) => {
      char.goHome();
      await char.waitForArrival(8000);
      char.playAnimation('drink');
      await char.wait(3000);
      char.expression.setEmotion('happy');
      await char.wait(4000);
      char.emotion.boostEnergy(15);
    },
    exit: (char) => {
      char.idle();
      char.expression.setEmotion('neutral');
    }
  },
  {
    id: 'check_phone',
    name: 'Checking Phone',
    duration: [6000, 12000],
    cooldownMs: 45000,
    lastRun: 0,
    priority: 80,
    requiresHome: false,
    condition: (emo) => emo.boredom > 35,
    run: async (char) => {
      char.movement.stop();
      char.playAnimation('phone');
      await char.wait(2500);
      char.expression.setEmotion('happy');
      await char.wait(3500);
      char.expression.setEmotion('surprised');
    },
    exit: (char) => {
      char.idle();
      char.expression.setEmotion('neutral');
      char.emotion.onActivity();
    }
  },
  {
    id: 'listen_music',
    name: 'Listening to Music',
    duration: [12000, 24000],
    cooldownMs: 80000,
    lastRun: 0,
    priority: 90,
    requiresHome: false,
    condition: (emo) => emo.happiness > 40 && emo.boredom > 20,
    run: async (char) => {
      char.playAnimation('music');
      char.expression.setEmotion('happy');
      await char.wait(8000);
    },
    exit: (char) => {
      char.idle();
      char.expression.setEmotion('neutral');
    }
  },
  {
    id: 'stretch_and_yawn',
    name: 'Stretching & Yawning',
    duration: [5000, 8000],
    cooldownMs: 40000,
    lastRun: 0,
    priority: 110,
    requiresHome: false,
    condition: (emo) => emo.sleepiness > 40 || emo.boredom > 50,
    run: async (char) => {
      char.playAnimation('stretch');
      await char.wait(3000);
      char.playAnimation('yawn');
      char.expression.setEmotion('sleepy');
      await char.wait(3000);
    },
    exit: (char) => {
      char.idle();
      char.expression.setEmotion('neutral');
    }
  },
  {
    id: 'wander_explore',
    name: 'Wandering Desktop',
    duration: [10000, 18000],
    cooldownMs: 50000,
    lastRun: 0,
    priority: 70,
    requiresHome: false,
    condition: (emo) => emo.energy > 45 && emo.boredom > 30,
    run: async (char) => {
      // Pick a logical target on the desktop away from current position
      const screenW = char.desktop.screenW;
      const minX = 150;
      const maxX = screenW - 150;
      const currentX = char.movement.desktopX;
      // Target at least 250px away
      let targetX = minX + Math.random() * (maxX - minX);
      if (Math.abs(targetX - currentX) < 200) {
        targetX = currentX > screenW / 2 ? minX + 100 : maxX - 100;
      }
      char.walkTo(targetX);
      await char.waitForArrival(12000);
      // Look around curiously
      char.idle();
      char.playAnimation('idle');
      char.expression.setEmotion('neutral');
      await char.wait(3000);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
    }
  },
  {
    id: 'sofa_rest',
    name: 'Resting on Sofa',
    duration: [15000, 30000],
    cooldownMs: 60000,
    lastRun: 0,
    priority: 140,
    requiresHome: true,
    condition: (emo) => emo.energy < 40 || emo.sleepiness > 60,
    run: async (char) => {
      char.goHome();
      await char.waitForArrival(8000);
      char.sit();
      char.expression.setEmotion('sleepy');
      char.emotion.onRest();
      await char.wait(10000);
    },
    exit: (char) => {
      char.idle();
      char.expression.setEmotion('neutral');
    }
  },
  {
    id: 'deep_sleep',
    name: 'Deep Sleep',
    duration: [40000, 90000],
    cooldownMs: 120000,
    lastRun: 0,
    priority: 250,
    requiresHome: true,
    condition: (emo, dayNight) => emo.shouldSleep || (dayNight?.isNight && emo.energy < 50),
    run: async (char) => {
      char.goHome();
      await char.waitForArrival(8000);
      char.sleep();
      char.emotion.onSleep();
      await char.wait(20000);
    },
    exit: (char) => {
      if (char.state.state === STATE.SLEEPING) {
        char.wake();
      }
    }
  }
];

export class ActivityRegistry {
  constructor(characterController) {
    this._char = characterController;
    this._activities = ACTIVITIES;
    this._currentActivity = null;
    this._activityTimeout = null;
    this._aborted = false;
  }

  get currentActivity() { return this._currentActivity; }
  get isActive() { return this._currentActivity !== null; }

  /**
   * Pick suitable activity based on emotions, cooldowns, and time of day.
   */
  pickActivity(emotionalState, dayNight) {
    const now = Date.now();
    const candidates = this._activities.filter(a => {
      if (now - a.lastRun < a.cooldownMs) return false;
      return a.condition(emotionalState, dayNight);
    });

    if (candidates.length === 0) return null;

    // Sort by priority descending
    candidates.sort((a, b) => b.priority - a.priority);

    // Pick from top candidates
    const topPool = candidates.slice(0, 2);
    return topPool[Math.floor(Math.random() * topPool.length)];
  }

  /**
   * Execute an activity safely with human logic and clean return.
   */
  async execute(activity) {
    if (!activity || this.isActive) return false;

    this._currentActivity = activity;
    this._aborted = false;
    activity.lastRun = Date.now();

    const [minDur, maxDur] = activity.duration;
    const duration = minDur + Math.random() * (maxDur - minDur);

    // Safety timeout to guarantee activity always ends
    this._activityTimeout = setTimeout(() => {
      this.finish();
    }, duration);

    try {
      if (activity.run) {
        await activity.run(this._char);
      }
    } catch (err) {
      console.warn(`[ACTIVITY] ${activity.name} interrupted or failed:`, err);
    } finally {
      // Natural finish if not already stopped
      if (!this._aborted) {
        this.finish();
      }
    }

    return true;
  }

  finish() {
    if (this._activityTimeout) {
      clearTimeout(this._activityTimeout);
      this._activityTimeout = null;
    }

    if (this._currentActivity) {
      const act = this._currentActivity;
      this._currentActivity = null;
      try {
        if (act.exit) act.exit(this._char);
      } catch (e) { /* safe */ }
    }
  }

  stop() {
    this._aborted = true;
    this.finish();
  }

  dispose() {
    this.stop();
  }
}
