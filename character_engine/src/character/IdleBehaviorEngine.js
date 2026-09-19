import { CONFIG } from '../config.js';
import { ActivityRegistry } from './ActivityRegistry.js';
import { STATE, PRIORITY } from './CharacterState.js';

/**
 * IdleBehaviorEngine — drives autonomous behavior.
 * Uses emotional state + day/night + activity registry.
 * Timer-based, NOT per-frame expensive.
 */
export class IdleBehaviorEngine {
  constructor(characterController) {
    this._char = characterController;
    this._activities = new ActivityRegistry();
    this._behaviorTimer = null;
    this._emotionTimer = null;
    this._started = false;
  }

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

  /** Slow emotion update — once per 30 seconds. */
  _scheduleEmotionUpdate() {
    this._emotionTimer = setInterval(() => {
      try {
        const isActive = this._char.state.state !== STATE.IDLE;
        this._char.dayNight.update();
        this._char.emotion.update(isActive, this._char.dayNight.isNight);
      } catch (e) { /* safe */ }
    }, 30000);
  }

  /** Schedule next autonomous behavior check. */
  _scheduleBehavior() {
    if (!this._started) return;

    const base = CONFIG.behavior.idleActivityMinMs;
    const variance = CONFIG.behavior.idleActivityVarianceMs;
    const nightMul = this._char.dayNight?.activityMultiplier || 1.0;
    const delay = (base + Math.random() * variance) / nightMul;

    this._behaviorTimer = setTimeout(() => {
      try {
        this._tryAutonomousBehavior();
      } catch (e) { /* safe */ }
      this._scheduleBehavior();
    }, delay);
  }

  _tryAutonomousBehavior() {
    // Only act when idle
    if (this._char.state.state !== STATE.IDLE) return;
    if (this._activities.isActive) return;

    const emo = this._char.emotion;

    // Priority checks
    if (emo.shouldSleep) {
      this._char.goHome();
      setTimeout(() => {
        try {
          this._char.sleep();
          emo.onSleep();
        } catch (e) {}
      }, 5000);
      return;
    }

    if (emo.isTired) {
      this._char.goHome();
      emo.onRest();
      return;
    }

    // Pick from activity registry
    const activity = this._activities.pickActivity(emo);
    if (!activity) return;

    this._activities.start(activity);
    emo.onActivity();

    // Execute the activity
    if (activity.needsWalk) {
      // Wander: pick a random desktop X
      const targetX = 100 + Math.random() * (this._char.desktop.screenW - 200);
      this._char.walkTo(targetX);
    } else if (activity.id === 'sit_rest') {
      this._char.sit();
    } else if (activity.id === 'sleep') {
      this._char.goHome();
      setTimeout(() => { try { this._char.sleep(); } catch (e) {} }, 5000);
    } else if (activity.id === 'stretch') {
      this._char.playAnimation('wave');
      setTimeout(() => { try { this._char.idle(); } catch (e) {} }, 3000);
    }
    // look_around is handled by default idle behavior
  }

  dispose() { this.stop(); this._activities.dispose(); }
}
