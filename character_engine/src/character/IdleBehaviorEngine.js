import { CONFIG } from '../config.js';
import { ActivityRegistry } from './ActivityRegistry.js';
import { STATE, PRIORITY } from './CharacterState.js';
import { ATTENTION_TARGET } from './LookAtController.js';
import { Logger } from '../logger.js';

/**
 * IdleBehaviorEngine — Autonomous mind loop following the living character rhythm.
 *
 * References:
 * - Liqu Desktop Companion: Layered procedural animation blending and settling phases.
 * - YUI: Clean separation of perception, internal state, utility choice, and body execution.
 * - Desktop Virtual Buddy: Finite state machine with cooldowns and recency penalties.
 * - ARPA Avatar: Semantic VRM character control abstraction.
 * - Vela: Personality traits and gradual normalized emotional drift.
 * - V-Lucent: Ambient desktop awareness.
 * - Tsuma: Semantic action contract.
 * - OpenPet: Modular behavior catalog.
 */
export class IdleBehaviorEngine {
  constructor(characterController) {
    this._char = characterController;
    this._activities = new ActivityRegistry(characterController);

    this._time = 0;
    this._nextDecisionTime = 2.0; // Quick initial action on launch
    this._isSettling = false;
    this._started = false;

    // Bounded event memory (YUI & Vela pattern)
    this._recentEvents = [];
    this._maxEvents = 20;
  }

  get activities() { return this._activities; }
  get isSettling() { return this._isSettling; }

  start(mode = 'normal') {
    this._started = true;
    this._time = 0;
    this._nextDecisionTime = 2.0;
    this._isSettling = false;
    Logger.info(`[BEHAVIOR] Engine started in mode: ${mode}`);
  }

  stop() {
    this._started = false;
    this._activities.stop();
  }

  /**
   * Main behavior update called synchronously from CharacterController.update(dt).
   * 100% time-delta driven — zero loose timers, zero frame lag.
   */
  update(dt) {
    if (!this._started) return;
    this._time += dt;

    // 1. FEEL: Smooth continuous internal state evolution (Vela pattern)
    const isActive = this._char.state.state !== STATE.IDLE && this._char.state.state !== STATE.SITTING;
    this._char.dayNight?.update();
    this._char.emotion.update(isActive, this._char.dayNight?.isNight, dt);

    // 2. Only consider autonomous decisions when standing idle and no active activity running
    const currentState = this._char.state.state;
    if (currentState !== STATE.IDLE && currentState !== STATE.SITTING) return;
    if (this._activities.isActive || this._isSettling) return;

    // 3. Periodic lively decision interval (every 3.5 to 5.5 seconds)
    if (this._time >= this._nextDecisionTime) {
      this._evaluateNextBehavior();
    }
  }

  /**
   * PERCEIVE → FEEL → CONSIDER → CHOOSE → ACT → SETTLE (Master Bible Cycle)
   */
  async _evaluateNextBehavior() {
    const emo = this._char.emotion;
    const dayNight = this._char.dayNight;

    // Context for Utility AI (YUI / V-Lucent pattern)
    const context = {
      activeAppCategory: this._char.windowManager?.activeWindow?.category || 'GENERIC',
      isNight: dayNight?.isNight,
      userActive: emo.attention > 0.55,
    };

    // Pick candidate activity via Utility AI
    const activity = this._activities.pickActivity(emo, dayNight, context);

    if (activity) {
      Logger.info(`[BEHAVIOR] Chosen activity: ${activity.name}`);
      await this._activities.execute(activity);
      await this._settleToIdle();
    } else {
      // Gentle micro-gesture if all activities on cooldown
      await this._settleToIdle();
    }
  }

  /**
   * SETTLE: Clean organic transition back to natural resting anime pose (Liqu pattern).
   */
  async _settleToIdle() {
    this._isSettling = true;
    try {
      this._char.state.transition(STATE.RETURN_TO_IDLE, PRIORITY.AUTONOMOUS);
      this._char.playAnimation('idle');
      this._char.expression.setEmotion('neutral');
      this._char.lookAt.setAttention(ATTENTION_TARGET.FORWARD, 2.0, 0.4);

      // Next action occurs 2.5 to 4.5 seconds after settling
      this._nextDecisionTime = this._time + 2.5 + Math.random() * 2.0;

      await this._char.wait(600);
      this._char.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
    } catch (e) {
      this._char.idle();
    } finally {
      this._isSettling = false;
    }
  }

  // --- External Reactions (Tsuma / ARPA Avatar Contract) ---

  reactHappy() {
    const wave = this._activities._activities.find(a => a.id === 'wave_hello');
    if (wave && !this._activities.isActive) {
      this._activities.execute(wave);
    }
  }

  reactCurious() {
    const cur = this._activities._activities.find(a => a.id === 'curious_look');
    if (cur && !this._activities.isActive) {
      this._activities.execute(cur);
    }
  }

  reactSurprised() {
    const b = this._activities._activities.find(a => a.id === 'happy_bounce');
    if (b && !this._activities.isActive) {
      this._activities.execute(b);
    }
  }

  reactShy() {
    const s = this._activities._activities.find(a => a.id === 'shy_fidget');
    if (s && !this._activities.isActive) {
      this._activities.execute(s);
    }
  }

  // --- Perception Event Input (YUI / V-Lucent Pattern) ---

  handleEvent(eventType, data = {}) {
    this._recordEvent(eventType);

    switch (eventType) {
      case 'USER_ACTIVE':
        this._char.emotion.attention = Math.min(1.0, this._char.emotion.attention + 0.15);
        this._char.emotion.boredom = Math.max(0.0, this._char.emotion.boredom - 0.10);
        break;

      case 'USER_IDLE':
        this._char.emotion.boredom = Math.min(1.0, this._char.emotion.boredom + 0.15);
        break;

      case 'USER_RETURNED':
        this._char.emotion.onUserInteraction();
        this.reactHappy();
        break;

      case 'CURSOR_NEAR':
        if (!this._activities.isActive) {
          this._char.emotion.curiosity = Math.min(1.0, this._char.emotion.curiosity + 0.10);
          this._char.lookAt.setAttention(ATTENTION_TARGET.CURSOR, 2.0, 0.85);
          if (Math.random() < 0.45) {
            this.reactHappy();
          }
        }
        break;

      case 'CURSOR_MOVED':
        this._char.emotion.attention = Math.min(1.0, this._char.emotion.attention + 0.02);
        break;

      case 'WINDOW_FOCUSED':
        this._char.emotion.curiosity = Math.min(1.0, this._char.emotion.curiosity + 0.08);
        break;

      case 'BRAIN_MESSAGE':
        this._char.emotion.onUserInteraction();
        this.reactHappy();
        break;

      default:
        break;
    }
  }

  _recordEvent(eventType) {
    this._recentEvents.unshift({ type: eventType, time: Date.now() });
    if (this._recentEvents.length > this._maxEvents) {
      this._recentEvents.pop();
    }
  }

  getCurrent() {
    return this._activities.currentActivity?.id || this._char.state.state;
  }

  getState() {
    return this._char.state.state;
  }

  getMood() {
    return this._char.emotion.dominantEmotion;
  }

  getNeeds() {
    return this._char.emotion.toJSON();
  }

  getDebugState() {
    return {
      activeActivity: this._activities.currentActivity?.name || 'idle',
      mood: this._char.emotion.dominantEmotion,
      energy: (this._char.emotion.energy * 100).toFixed(0) + '%',
      boredom: (this._char.emotion.boredom * 100).toFixed(0) + '%',
      recentActions: this._activities.utility.recentHistory,
      recentEvents: this._recentEvents.slice(0, 5).map(e => e.type),
    };
  }

  dispose() {
    this.stop();
    this._activities.dispose();
  }
}
