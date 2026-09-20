import { Logger } from '../logger.js';

/**
 * POSTURE — Standard humanoid posture taxonomy (Section 5 of Master Specification).
 */
export const POSTURE = Object.freeze({
  STANDING: 'STANDING',
  WALK_START: 'WALK_START',
  WALKING: 'WALKING',
  WALK_STOP: 'WALK_STOP',
  TURNING: 'TURNING',
  SIT_PREPARE: 'SIT_PREPARE',
  SITTING: 'SITTING',
  STAND_PREPARE: 'STAND_PREPARE',
  SQUATTING: 'SQUATTING',
  LYING: 'LYING',
  SLEEPY: 'SLEEPY',
  RESTING: 'RESTING',
  SLEEPING: 'SLEEPING',
  WAKING: 'WAKING',
  FALLING: 'FALLING',
  LANDING: 'LANDING'
});

/**
 * PostureGraph — Authoritative legal posture transition graph (Section 37 of Master Specification).
 * Disallows unnatural teleportation or impossible posture jumps.
 */
export class PostureGraph {
  constructor(initialPosture = POSTURE.STANDING) {
    this._current = initialPosture;
    this._listeners = [];

    // Legal transitions mapping
    this._legalTransitions = {
      [POSTURE.STANDING]: [
        POSTURE.WALK_START,
        POSTURE.TURNING,
        POSTURE.SIT_PREPARE,
        POSTURE.SLEEPY,
        POSTURE.RESTING,
        POSTURE.FALLING,
        POSTURE.SQUATTING
      ],
      [POSTURE.WALK_START]: [
        POSTURE.WALKING,
        POSTURE.WALK_STOP,
        POSTURE.STANDING
      ],
      [POSTURE.WALKING]: [
        POSTURE.WALK_STOP,
        POSTURE.TURNING,
        POSTURE.FALLING
      ],
      [POSTURE.WALK_STOP]: [
        POSTURE.STANDING,
        POSTURE.WALK_START
      ],
      [POSTURE.TURNING]: [
        POSTURE.STANDING,
        POSTURE.WALK_START,
        POSTURE.WALKING
      ],
      [POSTURE.SIT_PREPARE]: [
        POSTURE.SITTING,
        POSTURE.STANDING
      ],
      [POSTURE.SITTING]: [
        POSTURE.STAND_PREPARE,
        POSTURE.RESTING,
        POSTURE.SLEEPING
      ],
      [POSTURE.STAND_PREPARE]: [
        POSTURE.STANDING
      ],
      [POSTURE.SQUATTING]: [
        POSTURE.STANDING
      ],
      [POSTURE.LYING]: [
        POSTURE.RESTING,
        POSTURE.STANDING
      ],
      [POSTURE.SLEEPY]: [
        POSTURE.RESTING,
        POSTURE.SLEEPING,
        POSTURE.STANDING
      ],
      [POSTURE.RESTING]: [
        POSTURE.STANDING,
        POSTURE.SITTING,
        POSTURE.SLEEPING
      ],
      [POSTURE.SLEEPING]: [
        POSTURE.WAKING
      ],
      [POSTURE.WAKING]: [
        POSTURE.STANDING,
        POSTURE.RESTING
      ],
      [POSTURE.FALLING]: [
        POSTURE.LANDING
      ],
      [POSTURE.LANDING]: [
        POSTURE.STANDING
      ]
    };
  }

  get current() {
    return this._current;
  }

  /**
   * Checks if a transition from current posture to target posture is valid.
   */
  canTransition(toPosture) {
    if (this._current === toPosture) return true;
    const allowed = this._legalTransitions[this._current];
    return Array.isArray(allowed) && allowed.includes(toPosture);
  }

  /**
   * Transitions to a new posture if legal. Returns boolean indicating success.
   */
  transition(toPosture, context = {}) {
    if (this._current === toPosture) return true;

    if (!this.canTransition(toPosture)) {
      Logger.warn(`[POSTURE] Illegal transition rejected: ${this._current} → ${toPosture}`);
      return false;
    }

    // Sitting requires validated support surface
    if ((toPosture === POSTURE.SIT_PREPARE || toPosture === POSTURE.SITTING) && context.hasSurface === false) {
      Logger.warn(`[POSTURE] Cannot transition to ${toPosture} without support surface`);
      return false;
    }

    const previous = this._current;
    this._current = toPosture;
    Logger.info(`[POSTURE] Transition: ${previous} → ${toPosture}`);

    for (const listener of this._listeners) {
      try {
        listener(previous, toPosture, context);
      } catch (e) {
        Logger.error('[POSTURE] Listener error:', e);
      }
    }
    return true;
  }

  /**
   * Emergency reset to STANDING.
   */
  forceReset(reason = 'emergency') {
    const prev = this._current;
    this._current = POSTURE.STANDING;
    Logger.warn(`[POSTURE] Force reset to STANDING (${reason}) from ${prev}`);
    for (const listener of this._listeners) {
      try {
        listener(prev, POSTURE.STANDING, { forced: true, reason });
      } catch (e) {}
    }
  }

  onTransition(callback) {
    this._listeners.push(callback);
    return () => {
      this._listeners = this._listeners.filter(cb => cb !== callback);
    };
  }
}
