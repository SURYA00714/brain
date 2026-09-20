import { POSTURE } from './PostureGraph.js';

/**
 * AnimationCatalog — Asset & procedural motion metadata catalog.
 *
 * Implements Section 9 & 10 of the Master Specification:
 * - Decouples animation definitions from behavior logic.
 * - Enforces posture compatibility, blend duration, priority, and energy cost.
 */
export const ANIMATION_CATALOG = Object.freeze({
  // === BASE / IDLE ===
  idle: {
    id: 'idle',
    category: 'BASE',
    duration: 0, // continuous
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.STAND_PREPARE, POSTURE.WALK_STOP, POSTURE.TURNING],
    blendDuration: 0.4,
    priority: 1
  },
  idle_sway: {
    id: 'idle_sway',
    category: 'BASE',
    duration: 4.0,
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING],
    blendDuration: 0.5,
    priority: 1
  },

  // === LOCOMOTION ===
  walk: {
    id: 'walk',
    category: 'LOCOMOTION',
    duration: 0,
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.WALKING, POSTURE.WALK_START],
    blendDuration: 0.35,
    priority: 2
  },
  run: {
    id: 'run',
    category: 'LOCOMOTION',
    duration: 0,
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.WALKING],
    blendDuration: 0.3,
    priority: 2
  },

  // === POSTURE TRANSITIONS ===
  sit_prepare: {
    id: 'sit_prepare',
    category: 'POSTURE',
    duration: 1.2,
    loop: false,
    interruptible: false,
    compatiblePostures: [POSTURE.SIT_PREPARE, POSTURE.STANDING],
    blendDuration: 0.8,
    priority: 3
  },
  sit: {
    id: 'sit',
    category: 'POSTURE',
    duration: 0,
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.SITTING, POSTURE.RESTING],
    blendDuration: 0.8,
    priority: 2
  },
  stand_prepare: {
    id: 'stand_prepare',
    category: 'POSTURE',
    duration: 1.0,
    loop: false,
    interruptible: false,
    compatiblePostures: [POSTURE.STAND_PREPARE, POSTURE.SITTING],
    blendDuration: 0.7,
    priority: 3
  },
  sleep: {
    id: 'sleep',
    category: 'POSTURE',
    duration: 0,
    loop: true,
    interruptible: true,
    compatiblePostures: [POSTURE.SLEEPING, POSTURE.RESTING],
    blendDuration: 1.0,
    priority: 2
  },

  // === GESTURES & ACTIVITIES ===
  wave: {
    id: 'wave',
    category: 'GESTURE',
    duration: 2.4,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.4,
    priority: 2
  },
  wave_small: {
    id: 'wave_small',
    category: 'GESTURE',
    duration: 1.8,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.3,
    priority: 2
  },
  stretch: {
    id: 'stretch',
    category: 'GESTURE',
    duration: 3.5,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING],
    blendDuration: 0.6,
    priority: 2
  },
  yawn: {
    id: 'yawn',
    category: 'GESTURE',
    duration: 3.0,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING, POSTURE.SLEEPY],
    blendDuration: 0.5,
    priority: 2
  },
  think: {
    id: 'think',
    category: 'GESTURE',
    duration: 4.0,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.5,
    priority: 2
  },
  shy: {
    id: 'shy',
    category: 'GESTURE',
    duration: 3.2,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.4,
    priority: 2
  },
  confused: {
    id: 'confused',
    category: 'GESTURE',
    duration: 2.5,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.3,
    priority: 2
  },
  bounce: {
    id: 'bounce',
    category: 'GESTURE',
    duration: 2.2,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING],
    blendDuration: 0.3,
    priority: 2
  },
  read: {
    id: 'read',
    category: 'GESTURE',
    duration: 6.0,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.SITTING],
    blendDuration: 0.6,
    priority: 2
  },
  drink: {
    id: 'drink',
    category: 'GESTURE',
    duration: 4.5,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.5,
    priority: 2
  },
  phone: {
    id: 'phone',
    category: 'GESTURE',
    duration: 5.0,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.5,
    priority: 2
  },
  music: {
    id: 'music',
    category: 'GESTURE',
    duration: 5.0,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.4,
    priority: 2
  },
  pet: {
    id: 'pet',
    category: 'GESTURE',
    duration: 2.8,
    loop: false,
    interruptible: true,
    compatiblePostures: [POSTURE.STANDING, POSTURE.SITTING],
    blendDuration: 0.3,
    priority: 3
  }
});

/**
 * Helper to get animation metadata or safe fallback.
 */
export function getAnimationMetadata(id) {
  return ANIMATION_CATALOG[id] || ANIMATION_CATALOG.idle;
}
