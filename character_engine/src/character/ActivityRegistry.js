import { CONFIG } from '../config.js';
import { UtilitySelector } from '../mind/UtilitySelector.js';
import { ATTENTION_TARGET } from './LookAtController.js';

/**
 * ACTIVITIES — Semantic behavior catalog for AO.
 *
 * Implements Section 9, 10, 19, 21, 33 of the Master Specification:
 * - Each activity declares its semantic ActionIntent and physiological conditions.
 * - Actions execute through the character's validation and resolution pipeline.
 */
export const ACTIVITIES = [
  {
    id: 'wave_hello',
    name: 'Friendly Wave',
    duration: [2800, 3600],
    cooldownMs: 25000,
    lastRun: 0,
    priority: 140,
    condition: (emo) => emo.happiness > 0.35 || emo.socialNeed > 0.30,
    createIntent: (char) => ({
      type: 'GREET',
      emotion: 'happy',
      attention: { target: ATTENTION_TARGET.USER, duration: 3.2, intensity: 0.85 }
    })
  },
  {
    id: 'happy_bounce',
    name: 'Joyful Bounce',
    duration: [2200, 3000],
    cooldownMs: 30000,
    lastRun: 0,
    priority: 130,
    condition: (emo) => emo.happiness > 0.55 && emo.energy > 0.40,
    createIntent: (char) => ({
      type: 'PLAYFUL',
      emotion: 'happy',
      attention: { target: ATTENTION_TARGET.FORWARD, duration: 2.5, intensity: 0.8 }
    })
  },
  {
    id: 'stretch_body',
    name: 'Gentle Stretch',
    duration: [3000, 4000],
    cooldownMs: 35000,
    lastRun: 0,
    priority: 120,
    condition: (emo) => emo.boredom > 0.25 || emo.sleepiness > 0.30,
    createIntent: (char) => ({
      type: 'STRETCH',
      emotion: 'happy',
      attention: { target: ATTENTION_TARGET.UP, duration: 3.5, intensity: 0.6 }
    })
  },
  {
    id: 'groove_music',
    name: 'Enjoying Melody',
    duration: [4000, 5500],
    cooldownMs: 40000,
    lastRun: 0,
    priority: 115,
    condition: (emo) => emo.happiness > 0.40 && emo.energy > 0.30,
    createIntent: (char) => ({
      type: 'PLAYFUL',
      emotion: 'happy',
      attention: { target: ATTENTION_TARGET.FORWARD, duration: 4.5, intensity: 0.6 }
    })
  },
  {
    id: 'think_cute',
    name: 'Pondering',
    duration: [3000, 4200],
    cooldownMs: 25000,
    lastRun: 0,
    priority: 110,
    condition: (emo) => emo.curiosity > 0.35,
    createIntent: (char) => ({
      type: 'THINK',
      emotion: 'curious',
      attention: { target: ATTENTION_TARGET.UP, duration: 3.5, intensity: 0.8 }
    })
  },
  {
    id: 'curious_glance',
    name: 'Curious Glance',
    duration: [2500, 3500],
    cooldownMs: 20000,
    lastRun: 0,
    priority: 125,
    condition: (emo) => emo.curiosity > 0.45,
    createIntent: (char) => ({
      type: 'SHY',
      emotion: 'curious',
      attention: { target: ATTENTION_TARGET.RIGHT, duration: 3.0, intensity: 0.85 }
    })
  },
  {
    id: 'shy_fidget',
    name: 'Shy Fidget',
    duration: [2500, 3500],
    cooldownMs: 30000,
    lastRun: 0,
    priority: 105,
    condition: (emo) => emo.socialNeed > 0.40 || emo.affection > 0.35,
    createIntent: (char) => ({
      type: 'SHY',
      emotion: 'embarrassed',
      attention: { target: ATTENTION_TARGET.DOWN, duration: 3.0, intensity: 0.7 }
    })
  },
  {
    id: 'sleepy_yawn',
    name: 'Sleepy Yawn',
    duration: [2800, 3800],
    cooldownMs: 45000,
    lastRun: 0,
    priority: 100,
    condition: (emo) => emo.sleepiness > 0.30 || emo.energy < 0.50,
    createIntent: (char) => ({
      type: 'YAWN',
      emotion: 'sleepy',
      attention: { target: ATTENTION_TARGET.FORWARD, duration: 3.2, intensity: 0.5 }
    })
  },
  {
    id: 'desktop_stroll',
    name: 'Safe Stroll',
    duration: [4000, 6500],
    cooldownMs: 40000,
    lastRun: 0,
    priority: 90,
    condition: (emo) => emo.energy > 0.45 && emo.boredom > 0.25,
    createIntent: (char) => {
      const currentX = char.movement.desktopX;
      const screenW = char.worldModel.screenW;
      const direction = (currentX > screenW - 250) ? -1 : (currentX < 250 ? 1 : (Math.random() > 0.5 ? 1 : -1));
      const distance = 100 + Math.random() * 120;
      const targetX = char.worldModel.clampSafeX(currentX + direction * distance);

      return {
        type: 'WALK',
        targetX,
        emotion: 'neutral',
        attention: {
          target: direction > 0 ? ATTENTION_TARGET.RIGHT : ATTENTION_TARGET.LEFT,
          duration: 4.5,
          intensity: 0.6
        }
      };
    }
  }
];

export class ActivityRegistry {
  constructor(characterController) {
    this._char = characterController;
    this._activities = ACTIVITIES;
    this._currentActivity = null;
    this._utility = new UtilitySelector();
  }

  get currentActivity() {
    return this._currentActivity;
  }

  get isActive() {
    return this._currentActivity !== null;
  }

  /**
   * Pick best activity based on Utility AI scoring and cooldowns.
   */
  pickActivity(emotionalState, dayNight, context = {}) {
    const now = Date.now();
    const candidates = this._activities.filter(a => {
      if (now - a.lastRun < a.cooldownMs) return false;
      return a.condition(emotionalState, dayNight);
    });

    if (candidates.length === 0) return null;

    return this._utility.evaluate(candidates, emotionalState, {
      isNight: dayNight?.isNight,
      appCategory: context.activeAppCategory || 'GENERIC'
    });
  }

  /**
   * Executes an activity through the character's validation and intent pipeline.
   */
  async execute(activity) {
    if (!activity) return;
    this._currentActivity = activity;
    activity.lastRun = Date.now();

    try {
      const intent = activity.createIntent(this._char);
      await this._char.executeActionIntent(intent, activity.duration);
    } catch (e) {
      console.error('[ACTIVITY] Execution error:', e);
    } finally {
      this._currentActivity = null;
    }
  }

  stop() {
    this._currentActivity = null;
  }
}
