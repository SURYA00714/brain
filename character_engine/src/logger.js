import { CONFIG } from './config.js';

const LEVELS = { ERROR: 0, WARN: 1, INFO: 2, DEBUG: 3 };

function getLevel() {
  return LEVELS[CONFIG.debug.logLevel] ?? LEVELS.WARN;
}

export const Logger = {
  error(...args) { if (getLevel() >= LEVELS.ERROR) console.error('[ERROR]', ...args); },
  warn(...args)  { if (getLevel() >= LEVELS.WARN)  console.warn('[WARN]', ...args); },
  info(...args)  { if (getLevel() >= LEVELS.INFO)   console.log('[INFO]', ...args); },
  debug(...args) { if (getLevel() >= LEVELS.DEBUG)  console.log('[DEBUG]', ...args); },
};
