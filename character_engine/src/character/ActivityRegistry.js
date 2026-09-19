import { CONFIG } from '../config.js';
import { STATE, PRIORITY } from './CharacterState.js';
import { ATTENTION_TARGET } from './LookAtController.js';
import { UtilitySelector } from '../mind/UtilitySelector.js';

/**
 * ActivityRegistry — Modular behavior catalog for Ao.
 * References:
 * - OpenPet: action definition contract with conditions, execution phases, and cleanup.
 * - Liqu: procedural anime actions with fluid durations and natural gestures.
 * - Desktop Virtual Buddy: priority-driven state transitions and cooldown prevention.
 */
export const ACTIVITIES = [
  {
    id: 'wave_hello',
    name: 'Cheerful Wave',
    duration: [2800, 3800],
    cooldownMs: 15000,
    lastRun: 0,
    priority: 150,
    requiresHome: false,
    condition: (emo) => emo.happiness > 0.30 || emo.socialNeed > 0.20,
    run: async (char) => {
      char.state.transition(STATE.PLAYFUL, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('happy');
      char.playAnimation('wave');
      char.lookAt.setAttention(ATTENTION_TARGET.USER, 3.5, 0.9);
      await char.wait(3200);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onUserInteraction();
    }
  },
  {
    id: 'happy_bounce',
    name: 'Joyful Bounce',
    duration: [2200, 3200],
    cooldownMs: 20000,
    lastRun: 0,
    priority: 140,
    requiresHome: false,
    condition: (emo) => emo.happiness > 0.50 && emo.energy > 0.35,
    run: async (char) => {
      char.state.transition(STATE.HAPPY_REACTION, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('happy');
      char.playAnimation('bounce');
      char.lookAt.setAttention(ATTENTION_TARGET.FORWARD, 2.5, 0.8);
      await char.wait(2600);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onFunEvent();
    }
  },
  {
    id: 'stretch_body',
    name: 'Morning Stretch',
    duration: [3000, 4200],
    cooldownMs: 25000,
    lastRun: 0,
    priority: 120,
    requiresHome: false,
    condition: (emo) => emo.boredom > 0.20 || emo.sleepiness > 0.25,
    run: async (char) => {
      char.state.transition(STATE.STRETCHING, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('happy');
      char.playAnimation('stretch');
      char.lookAt.setAttention(ATTENTION_TARGET.UP, 3.5, 0.7);
      await char.wait(3500);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
    }
  },
  {
    id: 'listen_music',
    name: 'Grooving to Music',
    duration: [4000, 6000],
    cooldownMs: 30000,
    lastRun: 0,
    priority: 130,
    requiresHome: false,
    condition: (emo) => emo.happiness > 0.35,
    run: async (char) => {
      char.state.transition(STATE.PLAYFUL, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('happy');
      char.playAnimation('music');
      char.lookAt.setAttention(ATTENTION_TARGET.FORWARD, 4.5, 0.6);
      await char.wait(4500);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
    }
  },
  {
    id: 'check_phone',
    name: 'Checking Phone',
    duration: [3500, 5000],
    cooldownMs: 28000,
    lastRun: 0,
    priority: 110,
    requiresHome: false,
    condition: (emo) => emo.boredom > 0.20 || emo.socialNeed > 0.30,
    run: async (char) => {
      char.movement.stop();
      char.playAnimation('phone');
      char.expression.setEmotion('happy');
      char.lookAt.setAttention(ATTENTION_TARGET.DOWN, 4.0, 0.7);
      await char.wait(2200);
      char.expression.setEmotion('surprised');
      await char.wait(1800);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
    }
  },
  {
    id: 'think_cute',
    name: 'Thinking Pose',
    duration: [2800, 3800],
    cooldownMs: 18000,
    lastRun: 0,
    priority: 115,
    requiresHome: false,
    condition: (emo) => emo.curiosity > 0.30,
    run: async (char) => {
      char.state.transition(STATE.THINKING, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('curious');
      char.playAnimation('think');
      char.lookAt.setAttention(ATTENTION_TARGET.UP, 3.2, 0.85);
      await char.wait(3000);
    },
    exit: (char) => {
      char.idle();
    }
  },
  {
    id: 'curious_look',
    name: 'Curious Glance',
    duration: [2500, 3500],
    cooldownMs: 16000,
    lastRun: 0,
    priority: 125,
    requiresHome: false,
    condition: (emo) => emo.curiosity > 0.40,
    run: async (char) => {
      char.state.transition(STATE.CURIOUS, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('curious');
      char.playAnimation('confused');
      char.lookAt.setAttention(ATTENTION_TARGET.RIGHT, 3.0, 0.85);
      await char.wait(2800);
    },
    exit: (char) => {
      char.idle();
    }
  },
  {
    id: 'shy_fidget',
    name: 'Shy Blushing',
    duration: [2500, 3500],
    cooldownMs: 25000,
    lastRun: 0,
    priority: 105,
    requiresHome: false,
    condition: (emo) => emo.socialNeed > 0.35 || emo.affection > 0.30,
    run: async (char) => {
      char.state.transition(STATE.SHY_REACTION, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('embarrassed');
      char.playAnimation('shy');
      char.lookAt.setAttention(ATTENTION_TARGET.DOWN, 3.0, 0.7);
      await char.wait(2800);
    },
    exit: (char) => {
      char.idle();
    }
  },
  {
    id: 'yawn_sleepy',
    name: 'Sleepy Yawn',
    duration: [2800, 3800],
    cooldownMs: 35000,
    lastRun: 0,
    priority: 95,
    requiresHome: false,
    condition: (emo) => emo.sleepiness > 0.25 || emo.energy < 0.60,
    run: async (char) => {
      char.state.transition(STATE.YAWNING, PRIORITY.AUTONOMOUS);
      char.expression.setEmotion('sleepy');
      char.playAnimation('yawn');
      char.lookAt.setAttention(ATTENTION_TARGET.FORWARD, 3.2, 0.5);
      await char.wait(3200);
    },
    exit: (char) => {
      char.idle();
      char.emotion.onRest();
    }
  },
  {
    id: 'desktop_stroll',
    name: 'Desktop Stroll',
    duration: [4000, 6500],
    cooldownMs: 30000,
    lastRun: 0,
    priority: 110,
    requiresHome: false,
    condition: (emo) => emo.energy > 0.40 && emo.boredom > 0.15,
    run: async (char) => {
      const screenW = char.desktop.screenW;
      const currentX = char.movement.desktopX;
      // Stroll 120-250px away
      const direction = (currentX > screenW - 250) ? -1 : (currentX < 250 ? 1 : (Math.random() > 0.5 ? 1 : -1));
      const distance = 120 + Math.random() * 150;
      const targetX = Math.max(80, Math.min(screenW - 80, currentX + direction * distance));

      char.walkTo(targetX);
      char.expression.setEmotion('happy');
      char.lookAt.setAttention(direction > 0 ? ATTENTION_TARGET.RIGHT : ATTENTION_TARGET.LEFT, 4.5);
      await char.waitForArrival(6000);
      char.idle();
    },
    exit: (char) => {
      char.idle();
      char.emotion.onActivity();
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
    this._utility = new UtilitySelector();
  }

  get currentActivity() { return this._currentActivity; }
  get isActive() { return this._currentActivity !== null; }
  get utility() { return this._utility; }

  /**
   * Pick best activity based on Utility AI scoring and cooldowns (Vela & DVB style).
   */
  pickActivity(emotionalState, dayNight, context = {}) {
    const now = Date.now();
    const candidates = this._activities.filter(a => {
      if (now - a.lastRun < a.cooldownMs) return false;
      return a.condition(emotionalState, dayNight);
    });

    if (candidates.length === 0) return null;

    // Use mathematical Utility AI evaluation
    return this._utility.evaluate(candidates, emotionalState, {
      isNight: dayNight?.isNight,
      activeAppCategory: context.activeAppCategory,
      userActive: context.userActive,
    });
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

    // Failsafe timeout to guarantee activity always finishes
    this._activityTimeout = setTimeout(() => {
      this.finish();
    }, duration + 1000);

    try {
      if (activity.run) {
        await activity.run(this._char);
      }
    } catch (err) {
      console.warn(`[ACTIVITY] ${activity.name} interrupted or failed:`, err);
    } finally {
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
