import { ActivityRegistry } from './ActivityRegistry.js';
import { POSTURE } from './PostureGraph.js';
import { Logger } from '../logger.js';

/**
 * IdleBehaviorEngine — Autonomous mind loop with natural restraint and explainability.
 *
 * Implements Sections 19, 20, 21, 40, 62, 63 of the Master Specification:
 * - Natural restraint: Long periods of calm breathing, blinking, and subtle idle.
 * - Decision interval: 6.0 to 14.0 seconds (no frantic nonstop gestures).
 * - Explainable internal state: logs decision rationale (energy, boredom, recency).
 */
export class IdleBehaviorEngine {
  constructor(characterController) {
    this._char = characterController;
    this._activities = new ActivityRegistry(characterController);

    this._time = 0;
    this._nextDecisionTime = 3.5; // Short initial grace period on launch
    this._started = false;

    // Bounded history to prevent repetitive actions
    this._recentActivities = [];
    this._maxHistory = 10;

    // Debug explainability state (Section 62, 63)
    this._lastDecision = {
      selectedBehavior: 'NONE',
      reason: 'Initialization',
      timestamp: Date.now()
    };
  }

  get activities() {
    return this._activities;
  }

  get lastDecision() {
    return this._lastDecision;
  }

  start() {
    this._started = true;
    this._time = 0;
    this._nextDecisionTime = 3.5;
    Logger.info('[BEHAVIOR] Autonomous engine started with natural restraint');
  }

  stop() {
    this._started = false;
    this._activities.stop();
  }

  /**
   * Main behavior update called synchronously with delta time.
   */
  update(dt) {
    if (!this._started) return;
    this._time += dt;

    // 1. Slow continuous internal state evolution (0.0 to 1.0)
    const isMoving = this._char.movement.isMoving;
    this._char.dayNight?.update();
    this._char.emotion.update(isMoving, this._char.dayNight?.isNight, dt);

    // 2. Only consider autonomous decisions when standing or sitting peacefully
    const currentPosture = this._char.postureGraph.current;
    if (currentPosture !== POSTURE.STANDING && currentPosture !== POSTURE.SITTING) {
      return;
    }

    if (this._activities.isActive) return;

    // 3. Natural Restraint Interval (6.0 to 14.0 seconds)
    if (this._time >= this._nextDecisionTime) {
      this._evaluateNextBehavior();
    }
  }

  async _evaluateNextBehavior() {
    const emo = this._char.emotion;
    const dayNight = this._char.dayNight;

    // Natural Restraint: 40% probability of simply choosing "Quiet Idle"
    if (Math.random() < 0.40) {
      this._lastDecision = {
        selectedBehavior: 'QUIET_IDLE',
        reason: `Restraint: enjoying quiet moment (energy=${emo.energy.toFixed(2)}, boredom=${emo.boredom.toFixed(2)})`,
        timestamp: Date.now()
      };
      // Quiet pause for 6 to 10 seconds
      this._nextDecisionTime = this._time + 6.0 + Math.random() * 4.0;
      return;
    }

    const context = {
      activeAppCategory: this._char.windowManager?.activeWindow?.category || 'GENERIC',
      isNight: dayNight?.isNight,
      userActive: emo.attention > 0.55
    };

    const activity = this._activities.pickActivity(emo, dayNight, context);

    if (activity) {
      this._lastDecision = {
        selectedBehavior: activity.name,
        reason: `Utility match: boredom=${emo.boredom.toFixed(2)}, energy=${emo.energy.toFixed(2)}, priority=${activity.priority}`,
        timestamp: Date.now()
      };
      Logger.info(`[BEHAVIOR] Decision: ${this._lastDecision.selectedBehavior} (${this._lastDecision.reason})`);

      this._recordActivity(activity.id);
      await this._activities.execute(activity);

      // Schedule next check 6.0 to 12.0 seconds after activity completes
      this._nextDecisionTime = this._time + 6.0 + Math.random() * 6.0;
    } else {
      this._lastDecision = {
        selectedBehavior: 'IDLE_WAIT',
        reason: 'All activities currently on cooldown',
        timestamp: Date.now()
      };
      this._nextDecisionTime = this._time + 4.0;
    }
  }

  _recordActivity(activityId) {
    this._recentActivities.push(activityId);
    if (this._recentActivities.length > this._maxHistory) {
      this._recentActivities.shift();
    }
  }

  dispose() {
    this.stop();
  }
}
