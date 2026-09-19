import { Logger } from '../logger.js';

/**
 * VoiceController — Semantic speech coordination and viseme-based lip-sync.
 * Coordinates:
 * - Viseme mouth blendshapes ('aa', 'ih', 'ou', 'ee', 'oh')
 * - Facial expression
 * - Natural head gestures while speaking
 * - Automatic timeout cleanup
 */
export class VoiceController {
  constructor(vrmAdapter) {
    this._vrm = vrmAdapter;
    this._isSpeaking = false;
    this._speechTimer = null;
    this._visemeInterval = null;
  }

  get isSpeaking() { return this._isSpeaking; }

  speak(text, durationMs = null) {
    if (!this._vrm.loaded) return;
    this.stop();

    this._isSpeaking = true;
    // Estimate speech duration from text length: ~65ms per character, min 1.5s, max 8s
    const dur = durationMs || Math.min(8000, Math.max(1500, (text || '').length * 65));

    Logger.info(`[VOICE] Speaking: "${text}" (~${dur}ms)`);

    // Procedural viseme cycle
    const visemes = ['aa', 'ih', 'ou', 'ee', 'oh'].filter(v => this._vrm.hasExpression(v));
    const activeVisemes = visemes.length > 0 ? visemes : ['aa'];

    let index = 0;
    this._visemeInterval = setInterval(() => {
      try {
        const v = activeVisemes[index % activeVisemes.length];
        this._vrm.setExpression(v, 0.4 + Math.random() * 0.4);
        index++;
      } catch (e) { /* safe */ }
    }, 120);

    // End speech
    this._speechTimer = setTimeout(() => {
      this.stop();
    }, dur);
  }

  stop() {
    this._isSpeaking = false;
    if (this._visemeInterval) {
      clearInterval(this._visemeInterval);
      this._visemeInterval = null;
    }
    if (this._speechTimer) {
      clearTimeout(this._speechTimer);
      this._speechTimer = null;
    }

    try {
      // Reset mouth blendshapes
      ['aa', 'ih', 'ou', 'ee', 'oh'].forEach(v => {
        if (this._vrm.hasExpression(v)) this._vrm.setExpression(v, 0);
      });
    } catch (e) { /* safe */ }
  }

  dispose() {
    this.stop();
  }
}
