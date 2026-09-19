import { Logger } from '../logger.js';

// Priority levels (higher = more important)
export const PRIORITY = {
  IDLE: 0,
  AUTONOMOUS: 100,
  ACTIVITY: 300,
  AUTONOMOUS_EVENT: 400,
  INTERACTION: 500,
  WINDOW_EVENT: 600,
  BRAIN_COMMAND: 700,
  USER_COMMAND: 800,
  SYSTEM: 900,
  EMERGENCY: 1000,
};

// All possible character states
export const STATE = {
  IDLE: 'IDLE',
  WALKING: 'WALKING',
  RUNNING: 'RUNNING',
  TURNING: 'TURNING',
  JUMPING: 'JUMPING',
  FALLING: 'FALLING',
  LANDING: 'LANDING',
  SITTING: 'SITTING',
  READING: 'READING',
  SLEEPING: 'SLEEPING',
  WAKING: 'WAKING',
  TALKING: 'TALKING',
  LISTENING: 'LISTENING',
  LOOKING: 'LOOKING',
  FOLLOWING_MOUSE: 'FOLLOWING_MOUSE',
  FOLLOWING_WINDOW: 'FOLLOWING_WINDOW',
  PLAYING: 'PLAYING',
  INTERACTING: 'INTERACTING',
  REACTING: 'REACTING',
  RETURNING_HOME: 'RETURNING_HOME',
  HIDING: 'HIDING',
  TRANSITIONING: 'TRANSITIONING',
  PLAYING_ANIMATION: 'PLAYING_ANIMATION',
  DISABLED: 'DISABLED',
};

// Any state can go to IDLE, DISABLED, or SYSTEM transitions
const UNIVERSAL_TARGETS = [STATE.IDLE, STATE.DISABLED];
const MOVEMENT_TARGETS = [STATE.IDLE, STATE.WALKING, STATE.RUNNING, STATE.JUMPING, STATE.SITTING, STATE.RETURNING_HOME];

// Transition rules
const TRANSITIONS = {
  [STATE.IDLE]: [STATE.WALKING, STATE.RUNNING, STATE.JUMPING, STATE.SITTING, STATE.SLEEPING, STATE.TALKING, STATE.FOLLOWING_MOUSE, STATE.FOLLOWING_WINDOW, STATE.LOOKING, STATE.REACTING, STATE.PLAYING, STATE.INTERACTING, STATE.PLAYING_ANIMATION, STATE.RETURNING_HOME, STATE.READING, STATE.HIDING, STATE.DISABLED],
  [STATE.WALKING]: [STATE.IDLE, STATE.RUNNING, STATE.JUMPING, STATE.SITTING, STATE.TALKING, STATE.FOLLOWING_MOUSE, STATE.REACTING, STATE.RETURNING_HOME, STATE.DISABLED],
  [STATE.RUNNING]: [STATE.IDLE, STATE.WALKING, STATE.JUMPING, STATE.SITTING, STATE.REACTING, STATE.RETURNING_HOME, STATE.DISABLED],
  [STATE.TURNING]: [STATE.IDLE, STATE.WALKING, STATE.RUNNING, STATE.DISABLED],
  [STATE.JUMPING]: [STATE.IDLE, STATE.FALLING, STATE.LANDING, STATE.DISABLED],
  [STATE.FALLING]: [STATE.IDLE, STATE.LANDING, STATE.DISABLED],
  [STATE.LANDING]: [STATE.IDLE, STATE.WALKING, STATE.SITTING, STATE.DISABLED],
  [STATE.SITTING]: [STATE.IDLE, STATE.WALKING, STATE.JUMPING, STATE.TALKING, STATE.READING, STATE.SLEEPING, STATE.LOOKING, STATE.REACTING, STATE.RETURNING_HOME, STATE.DISABLED],
  [STATE.READING]: [STATE.IDLE, STATE.SITTING, STATE.WALKING, STATE.REACTING, STATE.DISABLED],
  [STATE.SLEEPING]: [STATE.WAKING, STATE.DISABLED],
  [STATE.WAKING]: [STATE.IDLE, STATE.DISABLED],
  [STATE.TALKING]: [STATE.IDLE, STATE.WALKING, STATE.SITTING, STATE.LOOKING, STATE.DISABLED],
  [STATE.LISTENING]: [STATE.IDLE, STATE.TALKING, STATE.REACTING, STATE.DISABLED],
  [STATE.FOLLOWING_MOUSE]: [STATE.IDLE, STATE.WALKING, STATE.JUMPING, STATE.REACTING, STATE.DISABLED],
  [STATE.FOLLOWING_WINDOW]: [STATE.IDLE, STATE.WALKING, STATE.JUMPING, STATE.SITTING, STATE.REACTING, STATE.DISABLED],
  [STATE.PLAYING]: [STATE.IDLE, STATE.REACTING, STATE.DISABLED],
  [STATE.INTERACTING]: [STATE.IDLE, STATE.REACTING, STATE.DISABLED],
  [STATE.REACTING]: [STATE.IDLE, STATE.WALKING, STATE.SITTING, STATE.DISABLED],
  [STATE.RETURNING_HOME]: [STATE.IDLE, STATE.SITTING, STATE.SLEEPING, STATE.DISABLED],
  [STATE.HIDING]: [STATE.IDLE, STATE.DISABLED],
  [STATE.TRANSITIONING]: [STATE.IDLE, STATE.WALKING, STATE.SITTING, STATE.DISABLED],
  [STATE.PLAYING_ANIMATION]: [STATE.IDLE, STATE.DISABLED],
  [STATE.LOOKING]: [STATE.IDLE, STATE.WALKING, STATE.JUMPING, STATE.SITTING, STATE.SLEEPING, STATE.DISABLED],
  [STATE.DISABLED]: [STATE.IDLE],
};

export class CharacterStateMachine {
  constructor() {
    this._state = STATE.IDLE;
    this._priority = PRIORITY.IDLE;
    this._listeners = [];
    this._stateStartTime = Date.now();
  }

  get state() { return this._state; }
  get priority() { return this._priority; }
  get stateAge() { return Date.now() - this._stateStartTime; }

  canTransition(newState) {
    if (this._state === newState) return true;
    const allowed = TRANSITIONS[this._state];
    return allowed ? allowed.includes(newState) : false;
  }

  transition(newState, priority = PRIORITY.AUTONOMOUS) {
    try {
      // Emergency/system always succeed
      if (priority >= PRIORITY.EMERGENCY) {
        return this._doTransition(newState, priority);
      }

      // User/system commands can force most transitions
      if (priority >= PRIORITY.USER_COMMAND) {
        // Allow wake from sleep
        if (this._state === STATE.SLEEPING && newState !== STATE.WAKING && newState !== STATE.DISABLED) {
          return false;
        }
        return this._doTransition(newState, priority);
      }

      // Normal priority check
      if (!this.canTransition(newState)) {
        return false;
      }

      // Lower priority cannot override higher priority (except from IDLE)
      if (priority < this._priority && this._state !== STATE.IDLE) {
        return false;
      }

      return this._doTransition(newState, priority);
    } catch (err) {
      Logger.error('State transition error:', err);
      this._state = STATE.IDLE;
      this._priority = PRIORITY.IDLE;
      return false;
    }
  }

  _doTransition(newState, priority) {
    const oldState = this._state;
    if (oldState === newState) return true;
    this._state = newState;
    this._priority = priority;
    this._stateStartTime = Date.now();
    Logger.debug(`State: ${oldState} → ${newState} (p=${priority})`);
    this._notify(oldState, newState);
    return true;
  }

  reset() {
    this._state = STATE.IDLE;
    this._priority = PRIORITY.IDLE;
    this._stateStartTime = Date.now();
  }

  onTransition(callback) {
    this._listeners.push(callback);
  }

  _notify(oldState, newState) {
    for (const cb of this._listeners) {
      try { cb(oldState, newState); } catch (e) { Logger.error('State listener error:', e); }
    }
  }
}
