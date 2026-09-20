import { Logger } from '../logger.js';
import { ActionIntent, ACTION_PRIORITY } from '../character/ActionIntent.js';

/**
 * BrainBridge — ARPA-Style Local Loopback Agent Bus (Sections 11, 12, 18 of Master Specification).
 *
 * Connects Brain AI & local callers to Ao through a strict ActionIntent priority hierarchy:
 * EMERGENCY > SYSTEM > USER COMMAND > BRAIN COMMAND > IMPORTANT REACTION > WORLD EVENT > INTERACTION > AUTONOMOUS > IDLE
 *
 * Security & Physical Integrity:
 * - Binds strictly to 127.0.0.1 (loopback only).
 * - Commands never mutate raw transforms (worldX/Y/Z, posture) directly.
 * - All actions routed through ActionIntent validator and PostureGraph.
 */
export class BrainBridge {
  constructor(characterController, port = 3737) {
    this._char = characterController;
    this._port = port;
    this._server = null;
    this._http = null;

    // Build the ARPA-style character agent bus API
    this.character = this._buildAgentBus();

    // Expose on global window if in renderer
    if (typeof window !== 'undefined') {
      window.character = this.character;
    }

    try {
      this._http = require('http');
    } catch (e) {
      Logger.warn('[BRIDGE] http module not available in renderer context.');
    }
  }

  /**
   * Constructs the semantic command interface conforming to Section 12:
   * character.idle(), character.walkTo(x, y), character.lookAtMouse(), character.emotion(e),
   * character.animation(a), character.speak(text), character.followMouse(), character.sleep(),
   * character.wake(), character.jump(), character.react(emotion), character.stop(),
   * character.jumpToWindow(win), character.sitOnWindow(win), character.followCursor(), character.goHome()
   */
  _buildAgentBus() {
    return {
      idle: () => {
        this._char.idle();
        return { success: true, action: 'idle' };
      },

      walkTo: (x, y) => {
        const targetX = typeof x === 'number' ? x : parseFloat(x);
        if (isNaN(targetX)) return { success: false, error: 'Invalid x coordinate' };

        this._char.executeActionIntent(new ActionIntent({
          type: 'WALK',
          targetX: targetX,
          priority: ACTION_PRIORITY.BRAIN_COMMAND,
          source: 'BRAIN_BUS',
          emotion: 'neutral'
        }));
        return { success: true, action: 'walkTo', targetX };
      },

      lookAtMouse: () => {
        if (this._char.lookAt) {
          this._char.lookAt.setAttention('CURSOR', 5.0, 0.85);
          return { success: true, action: 'lookAtMouse' };
        }
        return { success: false, error: 'LookAt controller not ready' };
      },

      emotion: (emotionName) => {
        if (!emotionName) return { success: false, error: 'Missing emotion' };
        this._char.setEmotion(emotionName);
        return { success: true, action: 'emotion', emotion: emotionName };
      },

      animation: (animName) => {
        if (!animName) return { success: false, error: 'Missing animation name' };
        this._char.executeActionIntent(new ActionIntent({
          type: 'GESTURE',
          priority: ACTION_PRIORITY.BRAIN_COMMAND,
          source: 'BRAIN_BUS',
          reason: animName,
          duration: 3500
        }));
        return { success: true, action: 'animation', animation: animName };
      },

      speak: (text) => {
        if (typeof text !== 'string') return { success: false, error: 'Missing speak text' };
        this._char.speak(text);
        return { success: true, action: 'speak', text };
      },

      followMouse: () => {
        if (this._char.mouse && this._char.mouse.desktopX !== undefined) {
          this._char.executeActionIntent(new ActionIntent({
            type: 'WALK',
            targetX: this._char.mouse.desktopX,
            priority: ACTION_PRIORITY.BRAIN_COMMAND,
            source: 'BRAIN_BUS',
            emotion: 'curious'
          }));
          return { success: true, action: 'followMouse', targetX: this._char.mouse.desktopX };
        }
        return { success: false, error: 'Mouse position unavailable' };
      },

      followCursor: () => {
        return this.character.followMouse();
      },

      sleep: () => {
        this._char.executeActionIntent(new ActionIntent({
          type: 'REST',
          priority: ACTION_PRIORITY.BRAIN_COMMAND,
          source: 'BRAIN_BUS',
          emotion: 'sleepy',
          duration: 12000
        }));
        return { success: true, action: 'sleep' };
      },

      wake: () => {
        this._char.wake();
        return { success: true, action: 'wake' };
      },

      jump: () => {
        this._char.jump();
        return { success: true, action: 'jump' };
      },

      react: (emotion) => {
        const emo = emotion || 'surprised';
        this._char.executeActionIntent(new ActionIntent({
          type: 'REACTION',
          priority: ACTION_PRIORITY.IMPORTANT_REACTION,
          source: 'BRAIN_BUS',
          emotion: emo,
          duration: 2500
        }));
        return { success: true, action: 'react', emotion: emo };
      },

      stop: () => {
        this._char.stopAction();
        return { success: true, action: 'stop' };
      },

      jumpToWindow: (windowQuery) => {
        const win = this._findWindow(windowQuery);
        if (!win) return { success: false, error: `Window not found: ${windowQuery}` };

        this._char.executeActionIntent(new ActionIntent({
          type: 'WALK',
          targetX: win.platformX,
          priority: ACTION_PRIORITY.BRAIN_COMMAND,
          source: 'BRAIN_BUS',
          emotion: 'curious'
        }));
        return { success: true, action: 'jumpToWindow', window: win.title, targetX: win.platformX };
      },

      sitOnWindow: (windowQuery) => {
        const win = this._findWindow(windowQuery);
        if (!win) return { success: false, error: `Window not found: ${windowQuery}` };

        // Create support surface from window top edge
        const surface = {
          id: `win_${win.id}`,
          worldY: this._char.worldModel.desktopToWorldY(win.topEdgeY),
          leftX: this._char.worldModel.desktopToWorldX(win.x),
          rightX: this._char.worldModel.desktopToWorldX(win.x + win.width),
          type: 'WINDOW',
          title: win.title
        };

        this._char.executeActionIntent(new ActionIntent({
          type: 'SIT',
          surface: surface,
          priority: ACTION_PRIORITY.BRAIN_COMMAND,
          source: 'BRAIN_BUS',
          emotion: 'neutral',
          duration: 10000
        }));
        return { success: true, action: 'sitOnWindow', window: win.title };
      },

      goHome: () => {
        this._char.goHome();
        return { success: true, action: 'goHome' };
      }
    };
  }

  _findWindow(query) {
    if (!this._char.windowManager || !this._char.windowManager.windows) return null;
    const q = String(query).toLowerCase();
    return this._char.windowManager.windows.find(w =>
      (w.title && w.title.toLowerCase().includes(q)) ||
      (w.category && w.category.toLowerCase().includes(q))
    ) || null;
  }

  start() {
    if (!this._http || this._server) return;

    try {
      this._server = this._http.createServer((req, res) => {
        res.setHeader('Content-Type', 'application/json');

        if (req.method === 'GET' && req.url === '/status') {
          res.writeHead(200);
          res.end(JSON.stringify({
            status: 'ok',
            character: {
              state: this._char.state?.state,
              posture: this._char.postureGraph?.current,
              desktopX: Math.round(this._char.movement?.desktopX || 0),
              emotions: this._char.emotion?.toJSON ? this._char.emotion.toJSON() : this._char.emotion,
            }
          }));
          return;
        }

        if (req.method === 'POST' && (req.url === '/command' || req.url?.startsWith('/character/'))) {
          let body = '';
          req.on('data', chunk => { body += chunk; });
          req.on('end', () => {
            try {
              let cmd = {};
              if (body) {
                cmd = JSON.parse(body);
              }
              // Allow action in URL path, e.g. POST /character/idle
              if (req.url.startsWith('/character/')) {
                cmd.action = req.url.replace('/character/', '');
              }
              const result = this._executeSemanticCommand(cmd);
              res.writeHead(result.success ? 200 : 400);
              res.end(JSON.stringify(result));
            } catch (err) {
              res.writeHead(400);
              res.end(JSON.stringify({ success: false, error: 'Invalid JSON command or URL' }));
            }
          });
          return;
        }

        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Endpoint not found' }));
      });

      this._server.listen(this._port, '127.0.0.1', () => {
        Logger.info(`[BRIDGE] BrainBridge ARPA agent bus listening on http://127.0.0.1:${this._port}`);
      });

      this._server.on('error', (err) => {
        Logger.warn('[BRIDGE] Server error (likely port in use):', err.message);
      });
    } catch (e) {
      Logger.warn('[BRIDGE] Setup error:', e);
    }
  }

  _executeSemanticCommand(cmd) {
    if (!cmd || typeof cmd.action !== 'string') {
      return { success: false, error: 'Missing action field' };
    }

    const action = cmd.action.toLowerCase().replace(/[-_]/g, '');

    switch (action) {
      case 'idle':
        return this.character.idle();

      case 'walkto':
      case 'walk':
        return this.character.walkTo(cmd.x !== undefined ? cmd.x : cmd.targetX, cmd.y);

      case 'lookatmouse':
      case 'lookmouse':
        return this.character.lookAtMouse();

      case 'emotion':
        return this.character.emotion(cmd.name || cmd.emotion);

      case 'animation':
        return this.character.animation(cmd.name || cmd.animation);

      case 'speak':
        return this.character.speak(cmd.text || cmd.message || '...');

      case 'followmouse':
      case 'followcursor':
        return this.character.followMouse();

      case 'sleep':
      case 'rest':
        return this.character.sleep();

      case 'wake':
        return this.character.wake();

      case 'jump':
        return this.character.jump();

      case 'react':
        return this.character.react(cmd.emotion || cmd.name);

      case 'stop':
        return this.character.stop();

      case 'jumptowindow':
        return this.character.jumpToWindow(cmd.window || cmd.title || cmd.windowId);

      case 'sitonwindow':
        return this.character.sitOnWindow(cmd.window || cmd.title || cmd.windowId);

      case 'gohome':
      case 'home':
        return this.character.goHome();

      case 'sit':
        this._char.sit();
        return { success: true, action: 'sit' };

      case 'pet':
        this._char.pet();
        return { success: true, action: 'pet' };

      default:
        return { success: false, error: `Unknown semantic command: ${cmd.action}` };
    }
  }

  stop() {
    if (this._server) {
      try { this._server.close(); } catch (e) {}
      this._server = null;
    }
  }

  dispose() {
    this.stop();
  }
}

