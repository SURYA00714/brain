import { Logger } from '../logger.js';
import { STATE, PRIORITY } from '../character/CharacterState.js';

/**
 * CreatureEngine — Ephemeral world inhabitants (Butterfly, Cat).
 * Strictly bounded:
 * - Max ONE creature at a time.
 * - Maximum lifetime with automatic cleanup timer.
 * - Long cooldowns (3–5 minutes) to prevent event spam.
 * - Zero heavy physics or continuous spawn loops.
 */
export class CreatureEngine {
  constructor(characterController) {
    this._char = characterController;
    this._activeCreature = null;
    this._cleanupTimer = null;
    this._lastSpawnTime = 0;
    this._cooldownMs = 180000; // 3 minutes cooldown
  }

  get activeCreature() { return this._activeCreature; }
  get hasCreature() { return this._activeCreature !== null; }

  /**
   * Try triggering an ephemeral creature event if conditions match.
   */
  trySpawn(emotionalState, dayNight) {
    const now = Date.now();
    if (this._activeCreature || (now - this._lastSpawnTime) < this._cooldownMs) {
      return false;
    }

    // High curiosity or high boredom triggers creature exploration
    if (emotionalState.curiosity < 40 && emotionalState.boredom < 40) {
      return false;
    }

    // Don't spawn during night or when sleeping/sitting
    if (dayNight?.isNight || this._char.state.state === STATE.SLEEPING) {
      return false;
    }

    const type = Math.random() > 0.5 ? 'butterfly' : 'cat';
    this.spawn(type);
    return true;
  }

  spawn(type) {
    this.cleanup();
    this._lastSpawnTime = Date.now();

    const screenW = this._char.desktop.screenW;
    const targetX = Math.round(150 + Math.random() * (screenW - 300));

    this._activeCreature = {
      type,
      desktopX: targetX,
      startTime: Date.now(),
      lifetimeMs: type === 'butterfly' ? 14000 : 20000,
    };

    Logger.info(`[CREATURE] Spawned ${type} at desktop X=${targetX}`);
    this._executeInteraction(this._activeCreature);

    // Auto-cleanup guarantee
    this._cleanupTimer = setTimeout(() => {
      this.cleanup();
    }, this._activeCreature.lifetimeMs);
  }

  async _executeInteraction(creature) {
    try {
      // 1. Notice: Ao turns head towards creature
      this._char.lookAt.setTarget(
        this._char.desktop.desktopXToWorld(creature.desktopX),
        1.0
      );
      this._char.expression.setEmotion('surprised');
      await this._char.wait(1500);

      // 2. Approach: Ao walks toward the creature
      if (this._char.state.transition(STATE.WALKING, PRIORITY.AUTONOMOUS_EVENT)) {
        this._char.walkTo(creature.desktopX);
        await this._char.waitForArrival(10000);
      }

      // 3. React: Playful reaction
      if (this._activeCreature) {
        this._char.playAnimation('confused');
        this._char.expression.setEmotion(creature.type === 'cat' ? 'happy' : 'curious');
        this._char.emotion.onFunEvent();
        await this._char.wait(3000);
      }

      // 4. Return to normal idle
      this._char.idle();
    } catch (e) {
      Logger.warn('[CREATURE] Interaction error:', e);
      this._char.idle();
    }
  }

  cleanup() {
    if (this._cleanupTimer) {
      clearTimeout(this._cleanupTimer);
      this._cleanupTimer = null;
    }
    if (this._activeCreature) {
      Logger.info(`[CREATURE] ${this._activeCreature.type} left the desktop.`);
      this._activeCreature = null;
    }
  }

  dispose() {
    this.cleanup();
  }
}
