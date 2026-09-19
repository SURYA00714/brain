import { Logger } from '../logger.js';

/**
 * BrainBridge — Controlled loopback API server connecting Brain AI to Ao.
 *
 * Security & Design:
 * - Binds strictly to 127.0.0.1 (loopback only).
 * - Strict command validation & allowlists.
 * - Rejects any raw shell commands or filesystem access.
 * - Dispatches semantic actions cleanly to CharacterController.
 */
export class BrainBridge {
  constructor(characterController, port = 3737) {
    this._char = characterController;
    this._port = port;
    this._server = null;
    this._http = null;

    try {
      this._http = require('http');
    } catch (e) {
      Logger.warn('[BRIDGE] http module not available in renderer context.');
    }
  }

  start() {
    if (!this._http || this._server) return;

    try {
      this._server = this._http.createServer((req, res) => {
        // Only accept POST to /command or GET to /status
        res.setHeader('Content-Type', 'application/json');

        if (req.method === 'GET' && req.url === '/status') {
          res.writeHead(200);
          res.end(JSON.stringify({
            status: 'ok',
            character: {
              state: this._char.state.state,
              desktopX: Math.round(this.movement?.desktopX || 0),
              emotions: this._char.emotion.toJSON(),
            }
          }));
          return;
        }

        if (req.method === 'POST' && req.url === '/command') {
          let body = '';
          req.on('data', chunk => { body += chunk; });
          req.on('end', () => {
            try {
              const cmd = JSON.parse(body);
              const result = this._executeSemanticCommand(cmd);
              res.writeHead(result.success ? 200 : 400);
              res.end(JSON.stringify(result));
            } catch (err) {
              res.writeHead(400);
              res.end(JSON.stringify({ success: false, error: 'Invalid JSON command' }));
            }
          });
          return;
        }

        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Endpoint not found' }));
      });

      this._server.listen(this._port, '127.0.0.1', () => {
        Logger.info(`[BRIDGE] BrainBridge listening on http://127.0.0.1:${this._port}`);
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

    // Allowed command whitelist
    switch (cmd.action) {
      case 'walk_to':
        if (typeof cmd.x === 'number') {
          this._char.walkTo(cmd.x);
          return { success: true };
        }
        break;
      case 'jump':
        this._char.jump();
        return { success: true };
      case 'sit':
        this._char.sit();
        return { success: true };
      case 'sleep':
        this._char.sleep();
        return { success: true };
      case 'wake':
        this._char.wake();
        return { success: true };
      case 'go_home':
        this._char.goHome();
        return { success: true };
      case 'rest':
        this._char.rest();
        return { success: true };
      case 'pet':
        this._char.pet();
        return { success: true };
      case 'emotion':
        if (typeof cmd.name === 'string') {
          this._char.setEmotion(cmd.name);
          return { success: true };
        }
        break;
      case 'animation':
        if (typeof cmd.name === 'string') {
          this._char.playAnimation(cmd.name);
          return { success: true };
        }
        break;
      case 'speak':
        if (typeof cmd.text === 'string') {
          this._char.speak(cmd.text);
          return { success: true };
        }
        break;
      case 'sit_on_window':
        if (cmd.windowId && this._char.sitOnWindow) {
          this._char.sitOnWindow(cmd.windowId);
          return { success: true };
        }
        break;
    }

    return { success: false, error: `Invalid command or arguments: ${cmd.action}` };
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
