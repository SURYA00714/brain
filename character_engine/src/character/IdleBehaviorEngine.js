import { CONFIG } from '../config.js';
import { ActivityRegistry } from './ActivityRegistry.js';
import { STATE, PRIORITY } from './CharacterState.js';

/**
 * IdleBehaviorEngine — drives autonomous, human-like behavior.
 * Uses emotional state + day/night awareness + activity cooldowns.
 * Timer-based, NOT per-frame expensive.
 */
export class IdleBehaviorEngine {
  constructor(characterController) {
    this._char = characterController;
    this._activities = new ActivityRegistry(characterController);
    this._behaviorTimer = null;
    this._emotionTimer = null;
    this._started = false;
  }

  get activities() { return this._activities; }

  start() {
    if (this._started) return;
    this._started = true;
    this._scheduleBehavior();
    this._scheduleEmotionUpdate();
  }

  stop() {
    this._started = false;
    if (this._behaviorTimer) { clearTimeout(this._behaviorTimer); this._behaviorTimer = null; }
    if (this._emotionTimer) { clearInterval(this._emotionTimer); this._emotionTimer = null; }
    this._activities.stop();
  }

  /** Slow emotion update — once per 20 seconds. */
  _scheduleEmotionUpdate() {
    this._emotionTimer = setInterval(() => {
      try {
        const isActive = this._char.state.state !== STATE.IDLE && this._char.state.state !== STATE.SITTING;
        this._char.dayNight.update();
        this._char.emotion.update(isActive, this._char.dayNight.isNight);
      } catch (e) { /* safe */ }
    }, 20000);
  }

  /** Schedule next autonomous behavior check. */
  _scheduleBehavior() {
    if (!this._started) return;

    const base = CONFIG.behavior.idleActivityMinMs || 15000;
    const variance = CONFIG.behavior.idleActivityVarianceMs || 20000;
    const nightMul = this._char.dayNight?.activityMultiplier || 1.0;
    const delay = (base + Math.random() * variance) / nightMul;

    this._behaviorTimer = setTimeout(async () => {
      try {
        await this._tryAutonomousBehavior();
      } catch (e) { /* safe */ }
      this._scheduleBehavior();
    }, delay);
  }

  async _tryAutonomousBehavior() {
    // Only act when idle or sitting passively with no active activity
    const currentState = this._char.state.state;
    if (currentState !== STATE.IDLE && currentState !== STATE.SITTING) return;
    if (this._activities.isActive) return;

    const emo = this._char.emotion;
    const dayNight = this._char.dayNight;

    // Check if a rare creature event triggers first
    if (this._char.creatures && this._char.creatures.trySpawn(emo, dayNight)) {
      return;
    }

    const context = {
      activeAppCategory: this._char.windowManager?.activeWindow?.category || 'GENERIC',
    };

    // Pick from activity registry with logical Utility AI filtering
    const activity = this._activities.pickActivity(emo, dayNight, context);
    if (!activity) return;

    console.log(`[BEHAVIOR] Starting logical activity: ${activity.name}`);
    await this._activities.execute(activity);
  }

  dispose() {
    this.stop();
    this._activities.dispose();
  }
}
