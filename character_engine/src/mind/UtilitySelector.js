/**
 * UtilitySelector — Mathematical Utility AI decision engine for Ao.
 *
 * References:
 * - Vela: Personality dimensions (cute, curious, playful, mischievous, calm, social, lazy)
 *         and normalized needs driving behavior.
 * - Desktop Virtual Buddy: Recency penalty buffer and utility thresholding.
 */
export class UtilitySelector {
  constructor() {
    this._recentActions = [];
    this._maxHistory = 6;
  }

  get recentHistory() { return [...this._recentActions]; }

  /**
   * Score candidates and select best behavior based on Vela-style personality and needs.
   */
  evaluate(candidates, mindState, context = {}) {
    if (!candidates || candidates.length === 0) return null;

    const p = mindState.personality || {
      cute: 0.70, curious: 0.80, playful: 0.65, mischievous: 0.45,
      calm: 0.60, social: 0.55, lazy: 0.30, dramatic: 0.25,
    };

    const scored = candidates.map(item => {
      let score = 30; // Base baseline
      const id = item.id;

      switch (id) {
        case 'wave_hello':
          score = (mindState.socialNeed * 40) + (mindState.happiness * 35) + (p.cute * 30);
          if (context.userActive) score += 20; // Greet user when user is active
          break;

        case 'happy_bounce':
          score = (mindState.happiness * 45) + (mindState.energy * 35) + (p.playful * 30);
          break;

        case 'stretch_body':
          score = (mindState.boredom * 35) + (mindState.sleepiness * 30) + (p.lazy * 20);
          break;

        case 'listen_music':
          score = (mindState.happiness * 35) + (p.playful * 30) + (mindState.boredom * 20);
          break;

        case 'check_phone':
          score = (mindState.boredom * 40) + (mindState.socialNeed * 35) + (p.mischievous * 20);
          break;

        case 'think_cute':
          score = (mindState.curiosity * 45) + (p.calm * 25) + (p.curious * 25);
          break;

        case 'curious_look':
          score = (mindState.curiosity * 50) + (p.curious * 30);
          break;

        case 'shy_fidget':
          score = (mindState.socialNeed * 30) + (mindState.affection * 30) + (p.cute * 30);
          break;

        case 'yawn_sleepy':
          score = (mindState.sleepiness * 55) + ((1.0 - mindState.energy) * 35);
          if (context.isNight) score += 25;
          break;

        case 'desktop_stroll':
          score = (mindState.energy * 40) + (mindState.curiosity * 35) + (p.playful * 20);
          if (context.userActive) score -= 15; // Less strolling when user is actively working
          break;

        default:
          score = 25;
          break;
      }

      // Repetition penalty (Desktop Virtual Buddy pattern)
      const repeatIndex = this._recentActions.indexOf(id);
      if (repeatIndex !== -1) {
        const penalty = (this._maxHistory - repeatIndex) * 20;
        score -= penalty;
      }

      return {
        item,
        score: Math.max(5, score),
      };
    });

    // Sort descending by score
    scored.sort((a, b) => b.score - a.score);

    // Pick best scoring candidate
    const winner = scored[0] ? scored[0].item : null;
    if (winner) {
      this._recordAction(winner.id);
    }
    return winner;
  }

  _recordAction(actionId) {
    this._recentActions.unshift(actionId);
    if (this._recentActions.length > this._maxHistory) {
      this._recentActions.pop();
    }
  }

  reset() {
    this._recentActions = [];
  }
}
