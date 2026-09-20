import { ANIMATION_CATALOG, getAnimationMetadata } from './AnimationCatalog.js';
import { POSTURE } from './PostureGraph.js';
import { Logger } from '../logger.js';

/**
 * AnimationResolver — Maps high-level intentions to compatible animations.
 *
 * Implements Section 34, 35, 36 of the Master Specification:
 * - Decouples intent from concrete animation clips.
 * - Chooses natural variation based on posture, emotion, energy, and recency.
 * - Prevents repetitive gestures and rejects posture-incompatible animations.
 */
export class AnimationResolver {
  constructor() {
    this._recentHistory = [];
    this._maxHistory = 10;
  }

  /**
   * Resolves an ActionIntent into a concrete animation ID.
   *
   * @param {Object} intent - Semantic intent { type, detail }
   * @param {string} currentPosture - Authoritative POSTURE enum
   * @param {Object} emotionalState - EmotionalState instance
   * @param {number} energy - Energy level 0.0 to 1.0
   * @returns {Object} { animId, metadata }
   */
  resolve(intent, currentPosture, emotionalState, energy = 1.0) {
    if (!intent || !intent.type) {
      return { animId: 'idle', metadata: ANIMATION_CATALOG.idle };
    }

    let candidateIds = [];

    switch (intent.type) {
      case 'GREET':
        // Variation between energetic wave, small wave, or nod
        if (energy > 0.65) {
          candidateIds = ['wave', 'wave_small'];
        } else {
          candidateIds = ['wave_small'];
        }
        break;

      case 'STRETCH':
        candidateIds = energy < 0.4 ? ['yawn', 'stretch'] : ['stretch'];
        break;

      case 'YAWN':
        candidateIds = ['yawn'];
        break;

      case 'THINK':
        candidateIds = ['think', 'confused'];
        break;

      case 'REST':
        candidateIds = ['sit', 'sleep'];
        break;

      case 'SIT':
        candidateIds = ['sit_prepare', 'sit'];
        break;

      case 'WALK':
        candidateIds = energy > 0.8 ? ['run', 'walk'] : ['walk'];
        break;

      case 'PLAYFUL':
        candidateIds = ['bounce', 'music'];
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
        candidateIds = ['read'];
        break;

      case 'SHY':
        candidateIds = ['shy'];
        break;

      case 'IDLE':
      default:
        candidateIds = ['idle', 'idle_sway'];
        break;
    }

    // Filter candidates by posture compatibility
    const compatible = candidateIds.filter(id => {
      const meta = ANIMATION_CATALOG[id];
      return meta && meta.compatiblePostures.includes(currentPosture);
    });

    if (compatible.length === 0) {
      Logger.warn(`[RESOLVER] No compatible animation for intent ${intent.type} in posture ${currentPosture} — falling back to idle`);
      return { animId: 'idle', metadata: ANIMATION_CATALOG.idle };
    }

    // Penalize recent animations to provide lively variation
    let selectedId = compatible[0];
    if (compatible.length > 1) {
      const scored = compatible.map(id => {
        const recencyIndex = this._recentHistory.lastIndexOf(id);
        const penalty = recencyIndex >= 0 ? (this._recentHistory.length - recencyIndex) * 2.0 : 0;
        return { id, score: Math.random() * 5.0 - penalty };
      });
      scored.sort((a, b) => b.score - a.score);
      selectedId = scored[0].id;
    }

    this._recordHistory(selectedId);
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

  clearHistory() {
    this._recentHistory = [];
  }
}
