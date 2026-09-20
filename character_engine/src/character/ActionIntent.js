/**
 * ACTION_PRIORITY — Strict priority hierarchy (Section 35 of Master Specification).
 * Lower numerical value = higher precedence.
 */
export const ACTION_PRIORITY = Object.freeze({
  EMERGENCY: 0,
  SYSTEM: 1,
  SAFETY: 1, // alias for safety invariants
  USER_COMMAND: 2,
  BRAIN_COMMAND: 3,
  IMPORTANT_REACTION: 4,
  WORLD_EVENT: 5,
  INTERACTION: 6,
  AUTONOMOUS: 7,
  IDLE: 8
});

/**
 * ACTION_PHASE — Explicit Action Lifecycle (Section 36 of Master Specification).
 */
export const ACTION_PHASE = Object.freeze({
  PENDING: 'PENDING',
  START: 'START',
  ACTIVE: 'ACTIVE',
  CANCELLED: 'CANCELLED',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  RECOVERY: 'RECOVERY'
});

/**
 * ActionIntent — Structured, explainable, and interruptible semantic action intent.
 *
 * Implements Sections 34, 35, 36, 51 of the Master Specification.
 */
export class ActionIntent {
  constructor(options = {}) {
    this.id = options.id || `intent_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    this.type = options.type || 'IDLE';
    this.priority = options.priority !== undefined ? options.priority : ACTION_PRIORITY.AUTONOMOUS;
    this.source = options.source || 'AUTONOMOUS';
    this.reason = options.reason || 'Normal routine';

    // Target parameters
    this.targetX = options.targetX;
    this.surface = options.surface || null;
    this.emotion = options.emotion || 'neutral';
    this.attention = options.attention || null;

    // Timing and interruption
    this.duration = options.duration || 3000;
    this.interruptible = options.interruptible !== undefined ? options.interruptible : true;
    this.phase = ACTION_PHASE.PENDING;
    this.startTime = 0;
    this.progress = 0;
  }

  /**
   * Evaluates whether another intent has sufficient priority to interrupt this one.
   */
  canBeInterruptedBy(incomingPriority) {
    if (!this.interruptible && this.phase === ACTION_PHASE.ACTIVE) {
      // Non-interruptible actions can only be preempted by EMERGENCY or SAFETY
      return incomingPriority <= ACTION_PRIORITY.SAFETY;
    }
    return incomingPriority < this.priority;
  }

  start() {
    this.phase = ACTION_PHASE.START;
    this.startTime = Date.now();
  }

  setActive() {
    this.phase = ACTION_PHASE.ACTIVE;
  }

  complete() {
    this.phase = ACTION_PHASE.COMPLETED;
  }

  cancel(reason = 'Interrupted') {
    this.phase = ACTION_PHASE.CANCELLED;
    this.cancelReason = reason;
  }

  fail(reason = 'Validation failure') {
    this.phase = ACTION_PHASE.FAILED;
    this.failReason = reason;
  }

  recover() {
    this.phase = ACTION_PHASE.RECOVERY;
  }
}
