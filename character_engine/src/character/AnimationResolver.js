import { ANIMATION_CATALOG, getAnimationMetadata, getAnimationsByFamily } from './AnimationCatalog.js';
import { POSTURE } from './PostureGraph.js';
import { Logger } from '../logger.js';

/**
 * AnimationResolver — Maps high-level intentions to compatible animations.
 *
 * Implements Section 14, 15, 16, 17 of the Master Specification:
 * - Semantic animation families (idles, gestures, micro-actions, emotions, postures, locomotion)
 * - Anti-repetition memory & cooldown penalties (preventing repetitive looping)
 * - Internal psychological drives integration (energy, boredom, happiness, curiosity, sleepiness)
 * - Strict posture compatibility and fail-safe fallback to idle
 */
export class AnimationResolver {
  constructor() {
    this._recentHistory = [];
    this._maxHistory = 8;
    this._cooldowns = new Map(); // animId -> timestampMs
  }

  /**
   * Resolves an ActionIntent into a concrete animation ID.
   *
   * @param {Object} intent - Semantic intent { type, detail, targetX, emotion }
   * @param {string} currentPosture - Authoritative POSTURE enum
   * @param {Object} emotionalState - EmotionalState or drives object
   * @param {number} energy - Energy level 0.0 to 1.0
   * @returns {Object} { animId, metadata }
   */
  resolve(intent, currentPosture = POSTURE.STANDING, emotionalState = null, energy = 1.0) {
    if (!intent || !intent.type) {
      return { animId: 'idle', metadata: ANIMATION_CATALOG.idle };
    }

    // Extract psychological drives with safe defaults
    const boredom = emotionalState?.boredom ?? emotionalState?.defaultBoredom ?? 0.2;
    const happiness = emotionalState?.happiness ?? emotionalState?.defaultHappiness ?? 0.5;
    const curiosity = emotionalState?.curiosity ?? emotionalState?.defaultCuriosity ?? 0.5;
    const sleepiness = emotionalState?.sleepiness ?? emotionalState?.defaultSleepiness ?? 0.1;

    let candidateIds = [];

    switch (intent.type) {
      case 'GREET':
        candidateIds = energy > 0.65
          ? ['vroid_greet', 'wave', 'vroid_peace']
          : ['wave', 'overte_nod'];
        break;

      case 'AGREE':
      case 'NOD':
        candidateIds = ['overte_nod'];
        break;

      case 'DISAGREE':
      case 'SHAKE':
        candidateIds = ['overte_shake', 'overte_angry', 'rb_angry'];
        break;

      case 'THINK':
        candidateIds = curiosity > 0.6
          ? ['overte_think', 'think', 'confused']
          : ['think', 'overte_think'];
        break;

      case 'STRETCH':
        candidateIds = (energy < 0.4 || sleepiness > 0.5)
          ? ['yawn', 'overte_relaxed', 'stretch']
          : ['stretch', 'overte_relaxed'];
        break;

      case 'YAWN':
        candidateIds = ['yawn', 'overte_relaxed'];
        break;

      case 'MICRO':
      case 'FIDGET':
        candidateIds = ['overte_relaxed', 'overte_relaxed_2', 'idle_sway'];
        break;

      case 'REST':
        candidateIds = currentPosture === POSTURE.SITTING
          ? ['overte_sit_idle', 'sit', 'sleep']
          : ['quaternius_sit_enter', 'sit_prepare', 'overte_relaxed', 'sleep'];
        break;

      case 'SIT':
        candidateIds = currentPosture === POSTURE.SITTING
          ? ['overte_sit_idle', 'sit']
          : ['quaternius_sit_enter', 'sit_prepare', 'overte_sit_idle', 'sit'];
        break;

      case 'STAND':
        candidateIds = ['quaternius_sit_exit', 'stand_prepare', 'idle'];
        break;

      case 'WALK':
        candidateIds = energy > 0.75
          ? ['overte_walk', 'walk']
          : ['overte_walk_slow', 'walk'];
        break;

      case 'PLAYFUL':
        candidateIds = ['vroid_shoot', 'vroid_peace', 'vroid_spin', 'vroid_model_pose'];
        break;

      case 'LISTEN':
        candidateIds = ['rb_listen', 'idle'];
        break;

      case 'HAPPY':
        candidateIds = ['overte_happy', 'rb_happy'];
        break;

      case 'SAD':
        candidateIds = ['overte_sad', 'rb_sad'];
        break;

      case 'ANGRY':
        candidateIds = ['overte_angry', 'rb_angry'];
        break;

      case 'PET':
        candidateIds = ['pet'];
        break;

      case 'PHONE':
        candidateIds = ['phone'];
        break;

      case 'DRINK':
        candidateIds = ['drink'];
        break;

      case 'READ':
        candidateIds = ['read', 'overte_sit_idle'];
        break;

      case 'SHY':
        candidateIds = ['shy', 'overte_neutral'];
        break;

      case 'IDLE':
      default:
        // Dynamic idle variation based on energy and boredom
        if (currentPosture === POSTURE.SITTING) {
          candidateIds = ['overte_sit_idle', 'overte_sit_talking', 'sit'];
        } else if (boredom > 0.6) {
          candidateIds = ['overte_relaxed_2', 'overte_relaxed', 'idle_sway', 'idle-3', 'overte_idle_3'];
        } else if (energy > 0.7) {
          candidateIds = ['overte_idle', 'overte_idle_2', 'rb_idle', 'idle'];
        } else {
          candidateIds = ['idle', 'overte_idle_4', 'overte_relaxed'];
        }
        break;
    }

    // Filter candidates strictly by posture compatibility
    const compatible = candidateIds.filter(id => {
      const meta = ANIMATION_CATALOG[id];
      return meta && meta.compatiblePostures.includes(currentPosture);
    });

    if (compatible.length === 0) {
      Logger.warn(`[RESOLVER] No compatible animation for intent ${intent.type} in posture ${currentPosture} — falling back to idle`);
      const fallbackId = currentPosture === POSTURE.SITTING ? 'overte_sit_idle' : 'idle';
      const meta = ANIMATION_CATALOG[fallbackId] || ANIMATION_CATALOG.idle;
      return { animId: meta.id, metadata: meta };
    }

    // Weighted selection with anti-repetition memory & cooldown penalties
    const now = Date.now();
    const scored = compatible.map(id => {
      const meta = ANIMATION_CATALOG[id];
      let weight = (meta.weight || 1.0) * (1.0 + Math.random() * 0.4);

      // 1. Recency Penalty (anti-repetition queue)
      const recencyIndex = this._recentHistory.lastIndexOf(id);
      if (recencyIndex >= 0) {
        const stepsAgo = this._recentHistory.length - recencyIndex;
        if (stepsAgo === 1) {
          weight *= 0.05; // Played immediately before
        } else if (stepsAgo <= 3) {
          weight *= 0.20; // Played recently
        } else {
          weight *= 0.60;
        }
      }

      // 2. Cooldown check
      const lastPlayed = this._cooldowns.get(id) || 0;
      const cooldownPeriod = meta.loop ? 5000 : 12000;
      if (now - lastPlayed < cooldownPeriod) {
        weight *= 0.25;
      }

      // 3. Drive-based bias
      if (energy < 0.35 && meta.category === 'GESTURE') {
        weight *= 0.4;
      }
      if (happiness > 0.7 && meta.family === 'happy') {
        weight *= 1.8;
      }

      return { id, meta, score: weight };
    });

    scored.sort((a, b) => b.score - a.score);
    const selectedId = scored[0].id;

    this._recordHistory(selectedId);
    this._cooldowns.set(selectedId, now);

    return {
      animId: selectedId,
      metadata: getAnimationMetadata(selectedId)
    };
  }

  _recordHistory(animId) {
    this._recentHistory.push(animId);
    if (this._recentHistory.length > this._maxHistory) {
      this._recentHistory.shift();
    }
  }

  get recentHistory() {
    return [...this._recentHistory];
  }

  clearHistory() {
    this._recentHistory = [];
    this._cooldowns.clear();
  }
}
