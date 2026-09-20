import { Logger } from '../logger.js';
import { ACTION_PRIORITY } from './ActionIntent.js';

/**
 * EVENT_TYPE — Recognized system and environment events (Section 30 of Master Specification).
 */
export const EVENT_TYPE = Object.freeze({
  USER_CLICK: 'USER_CLICK',
  MOUSE_MOVED: 'MOUSE_MOVED',
  WINDOW_OPENED: 'WINDOW_OPENED',
  WINDOW_CLOSED: 'WINDOW_CLOSED',
  WINDOW_MOVED: 'WINDOW_MOVED',
  USER_IDLE: 'USER_IDLE',
  USER_ACTIVE: 'USER_ACTIVE',
  SURFACE_LOST: 'SURFACE_LOST'
});

/**
 * EventDispatcher — Throttled perception and contextual event intake.
 *
 * Implements Sections 30, 31, 41 of the Master Specification:
 * - Event intake pipeline: EVENT → PERCEPTION → CONTEXT → UTILITY → DECISION.
 * - Prevents raw event floods from triggering erratic animations.
 * - Smoothly updates emotional drivers (curiosity, attention, alert level).
 */
export class EventDispatcher {
  constructor(characterController) {
    this._char = characterController;
    this._lastEventTime = 0;
    this._minEventInterval = 250; // Throttle events to max 4 Hz
    this._eventHistory = [];
    this._maxHistory = 20;
  }

  /**
   * Dispatches an external environment or user event.
   */
  dispatch(type, payload = {}) {
    const now = Date.now();
    if (now - this._lastEventTime < this._minEventInterval && type === EVENT_TYPE.MOUSE_MOVED) {
      return; // Filter rapid cursor updates
    }
    this._lastEventTime = now;

    const eventRecord = { type, payload, timestamp: now };
    this._recordEvent(eventRecord);

    switch (type) {
      case EVENT_TYPE.SURFACE_LOST:
        this._handleSurfaceLost(payload);
        break;

      case EVENT_TYPE.WINDOW_CLOSED:
        this._handleWindowClosed(payload);
        break;

      case EVENT_TYPE.USER_CLICK:
        this._char.emotion.onUserInteraction();
        break;

      case EVENT_TYPE.USER_ACTIVE:
        this._char.emotion.attention = Math.min(1.0, this._char.emotion.attention + 0.15);
        break;

      case EVENT_TYPE.USER_IDLE:
        this._char.emotion.attention = Math.max(0.1, this._char.emotion.attention - 0.1);
        this._char.emotion.boredom = Math.min(1.0, this._char.emotion.boredom + 0.05);
        break;

      case EVENT_TYPE.MOUSE_MOVED:
        // Subtle glance trigger if cursor is nearby
        if (Math.random() < 0.15 && this._char.emotion.attention > 0.4) {
          this._char.lookAt.glanceAtCursor(this._char.mouse.x, this._char.mouse.y);
        }
        break;

      default:
        break;
    }
  }

  /**
   * Critical Safety: Surface disappears while sitting/standing on it (Section 10).
   */
  _handleSurfaceLost(payload) {
    Logger.warn('[EVENT] Active support surface lost — initiating immediate recovery');
    if (this._char.postureGraph.current === 'SITTING') {
      this._char.executeActionIntent({
        type: 'RECOVER_TO_FLOOR',
        priority: ACTION_PRIORITY.SAFETY,
        reason: 'Support surface disappeared'
      });
    }
  }

  _handleWindowClosed(payload) {
    if (this._char.worldState.supportSurface?.windowId === payload.windowId) {
      this.dispatch(EVENT_TYPE.SURFACE_LOST, payload);
    }
  }

  _recordEvent(event) {
    this._eventHistory.push(event);
    if (this._eventHistory.length > this._maxHistory) {
      this._eventHistory.shift();
    }
  }

  get recentEvents() {
    return this._eventHistory;
  }
}
