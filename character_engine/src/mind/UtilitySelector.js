/**
 * UtilitySelector — Mathematical Utility AI decision engine.
 *
 * Evaluates candidates based on:
 * - Internal mind state: energy, boredom, sleepiness, curiosity, playfulness
 * - Contextual cues: day/night, active application
 * - Cooldowns & repetition penalties
 *
 * Returns scored behavior with highest utility value.
 */
export class UtilitySelector {
  constructor() {
    this._recentActions = [];
    this._maxHistory = 5;
  }

  /**
   * Score activities and pick the highest utility candidate.
   */
  evaluate(activities, mindState, context = {}) {
    const scored = activities.map(act => {
      let score = 0;

      // 1. Base emotional motivations
      if (act.id === 'deep_sleep' || act.id === 'sofa_rest') {
        score = (mindState.sleepiness * 0.6) + ((100 - mindState.energy) * 0.4);
        if (context.isNight) score += 30;
      } else if (act.id === 'read_book') {
        score = (mindState.boredom * 0.4) + (mindState.energy * 0.3) + (mindState.curiosity * 0.3);
        if (context.activeAppCategory === 'CODING') score += 20; // Reading near coding
      } else if (act.id === 'drink_tea') {
        score = ((100 - mindState.energy) * 0.5) + (mindState.boredom * 0.3);
      } else if (act.id === 'check_phone') {
        score = (mindState.boredom * 0.6) + (mindState.playfulness * 0.2);
      } else if (act.id === 'listen_music') {
        score = (mindState.happiness * 0.4) + (mindState.boredom * 0.4);
      } else if (act.id === 'stretch_and_yawn') {
        score = (mindState.sleepiness * 0.4) + (mindState.boredom * 0.4);
      } else if (act.id === 'wander_explore') {
        score = (mindState.curiosity * 0.5) + (mindState.energy * 0.3) + (mindState.playfulness * 0.2);
      }

      // 2. Penalize recent actions to prevent repetitive behavior loops
      const repeatIndex = this._recentActions.indexOf(act.id);
      if (repeatIndex !== -1) {
        // More recent = heavier penalty
        const recencyPenalty = (this._maxHistory - repeatIndex) * 15;
        score -= recencyPenalty;
      }

      return {
        activity: act,
        score: Math.max(0, score),
      };
    });

    // Sort descending by score
    scored.sort((a, b) => b.score - a.score);

    const winner = scored[0]?.score > 15 ? scored[0].activity : null;
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
