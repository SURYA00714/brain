import { CONFIG } from '../config.js';
import { CharacterStateMachine, STATE, PRIORITY } from './CharacterState.js';
import { VRMAdapter } from './VRMAdapter.js';
import { AnimationController } from './AnimationController.js';
import { ExpressionController } from './ExpressionController.js';
import { LookAtController } from './LookAtController.js';
import { MovementController } from './MovementController.js';
import { MouseTracker } from './MouseTracker.js';
import { DesktopCoordinates } from './DesktopCoordinates.js';
import { IdleBehaviorEngine } from './IdleBehaviorEngine.js';
import { EmotionalState } from './EmotionalState.js';
import { DayNightCycle } from './DayNightCycle.js';
import { WindowManager } from '../world/WindowManager.js';
import { CreatureEngine } from '../world/CreatureEngine.js';
import { VoiceController } from '../mind/VoiceController.js';
import { BrainBridge } from '../bridge/BrainBridge.js';

/**
 * CharacterController — Central orchestrator for Ao.
 * Architecture:
 * - Body: VRM, Movement, Animation, Expressions, LookAt, Physics
 * - Mind: EmotionalState, Utility AI decision-making, Voice, DayNightCycle
 * - World: DesktopCoordinates, WindowManager, CreatureEngine, Home
 * - Bridge: BrainBridge loopback API
 */
export class CharacterController {
  constructor(scene) {
    this._scene = scene;
    this.desktop = new DesktopCoordinates();
    this.vrm = new VRMAdapter();
    this.state = new CharacterStateMachine();
    this.animation = new AnimationController(this.vrm);
    this.expression = new ExpressionController(this.vrm);
    this.lookAt = new LookAtController(this.vrm);
    this.movement = new MovementController(this.vrm, this.desktop);
    this.mouse = new MouseTracker(this.desktop);
    this.emotion = new EmotionalState();
    this.dayNight = new DayNightCycle();
    this.windowManager = new WindowManager(this.desktop);
    this.creatures = new CreatureEngine(this);
    this.voice = new VoiceController(this.vrm);
    this.idleBehavior = new IdleBehaviorEngine(this);
    this.behavior = this.idleBehavior;
    this.bridge = new BrainBridge(this);

    this._mouseMode = 'LOOK_ONLY';
    this._currentWindowAnchor = null;
    this._loaded = false;

    this.state.onTransition((old, next) => this._onStateChange(old, next));
  }

  async load(modelPath) {
    try {
      await this.vrm.load(modelPath || CONFIG.character.modelPath);
      this._scene.add(this.vrm.scene);

      // Start at home position
      this.movement.setDesktopX(this.desktop.homeX);

      this.expression.start();
      this.mouse.start();
      this.windowManager.start();
      this.idleBehavior.start();
      this.bridge.start();

      this._loaded = true;
      console.log('[AO] Fully loaded. Home at X=' + Math.round(this.desktop.homeX));
    } catch (err) {
      console.error('[AO] Load failed:', err);
    }
  }

  // === Async Activity Helpers ===
  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  waitForArrival(timeoutMs = 10000) {
    return new Promise(resolve => {
      const startTime = Date.now();
      const check = setInterval(() => {
        if (!this.movement.isMoving || (Date.now() - startTime) >= timeoutMs) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });
  }

  // === Core Actions API ===

  idle() {
    this.movement.stop();
    this._currentWindowAnchor = null;
    this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
  }

  walkTo(desktopX) {
    this._currentWindowAnchor = null;
    if (this.state.transition(STATE.WALKING, PRIORITY.AUTONOMOUS)) {
      this.movement.walkTo(desktopX);
    }
  }

  walkToDesktop(x) { this.walkTo(x); }

  goHome() {
    this._currentWindowAnchor = null;
    if (this.state.transition(STATE.RETURNING_HOME, PRIORITY.AUTONOMOUS)) {
      this.movement.walkTo(this.desktop.homeX);
    }
  }

  jump() {
    if (this.state.transition(STATE.JUMPING, PRIORITY.AUTONOMOUS)) {
      this.movement.jump();
    }
  }

  sit() {
    this.movement.stop();
    this.state.transition(STATE.SITTING, PRIORITY.USER_COMMAND);
  }

  /**
   * Sit on top edge of a desktop window.
   */
  async sitOnWindow(windowId = null) {
    let win = null;
    if (windowId) {
      win = this.windowManager.windows.find(w => w.id === windowId);
    }
    if (!win) {
      win = this.windowManager.activeWindow || this.windowManager.windows[0];
    }

    if (!win) {
      this.sit(); // Fallback to ground sitting if no window
      return false;
    }

    this._currentWindowAnchor = win;
    // Walk to window center
    this.walkTo(win.platformX);
    await this.waitForArrival(8000);

    // Transition to sitting on top edge
    this.sit();
    this.expression.setEmotion('happy');
    return true;
  }

  sleep() {
    this.movement.stop();
    this.state.transition(STATE.SLEEPING, PRIORITY.AUTONOMOUS);
  }

  wake() {
    this.state.transition(STATE.WAKING, PRIORITY.USER_COMMAND);
    this.emotion.onRest();
    setTimeout(() => {
      try { this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS); } catch (e) {}
    }, 1500);
  }

  rest() {
    this.goHome();
    this.emotion.onRest();
  }

  followMouse() {
    this._mouseMode = 'FOLLOW';
    this.state.transition(STATE.FOLLOWING_MOUSE, PRIORITY.INTERACTION);
  }

  stopFollowingMouse() {
    this._mouseMode = 'LOOK_ONLY';
    this.movement.stop();
    if (this.state.state === STATE.FOLLOWING_MOUSE) {
      this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
    }
  }

  lookAtMouse() { this._mouseMode = 'LOOK_ONLY'; }

  setEmotion(name) { this.expression.setEmotion(name); }
  playAnimation(name) { this.animation.play(name); }

  stopAction() {
    this.movement.stop();
    this.animation.play('idle');
    this.state.transition(STATE.IDLE, PRIORITY.USER_COMMAND);
  }

  speak(text, durationMs = null) {
    this.voice.speak(text, durationMs);
  }

  pet() {
    this.emotion.onPetting();
    this.state.transition(STATE.INTERACTING, PRIORITY.INTERACTION);
    this.animation.play('pet');
    this.expression.setEmotion('happy');
    setTimeout(() => {
      if (this.state.state === STATE.INTERACTING) {
        this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
        this.expression.setEmotion('neutral');
      }
    }, 2500);
  }

  // === MAIN UPDATE LOOP (Called once from renderer.js animate) ===

  update(delta) {
    if (!this._loaded) return;
    try {
      const dt = Math.min(delta, CONFIG.performance.maxDeltaTime);

      // 1. Natural autonomous lookAt update (glancing around)
      this.lookAt.update(dt);

      // 2. Follow mouse mode (if explicitly enabled)
      if (this._mouseMode === 'FOLLOW') {
        const dx = this.mouse.x - this.movement.desktopX;
        if (Math.abs(dx) > CONFIG.mouse.followDeadZone) {
          this.movement.walkTo(this.mouse.x);
          if (this.state.state === STATE.IDLE || this.state.state === STATE.FOLLOWING_MOUSE) {
            this.state.transition(STATE.WALKING, PRIORITY.INTERACTION);
          }
        }
      }

      // 3. Movement update
      this.movement.update(dt);

      // 4. Auto-transitions
      const st = this.state.state;
      if (st === STATE.WALKING && !this.movement.isMoving) {
        this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
      }
      if (st === STATE.RETURNING_HOME && !this.movement.isMoving) {
        this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
      }
      if (st === STATE.JUMPING && !this.movement.isAirborne && !this.movement.isMoving) {
        this.state.transition(STATE.LANDING, PRIORITY.AUTONOMOUS);
        this.animation.play('land');
        setTimeout(() => {
          try { this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS); } catch (e) {}
        }, 400);
      }

      // 5. Autonomous Behavior Engine update (Spec Section 37)
      this.idleBehavior.update(dt);

      // 6. Animation update
      this.animation.update(dt);

      // 7. VRM update (spring bones etc)
      this.vrm.update(dt);
    } catch (e) {
      console.error('[AO] Update error:', e);
    }
  }

  _onStateChange(old, next) {
    try {
      const animMap = {
        [STATE.IDLE]: 'idle',
        [STATE.WALKING]: 'walk',
        [STATE.RUNNING]: 'run',
        [STATE.JUMPING]: 'jump',
        [STATE.FALLING]: 'jump',
        [STATE.LANDING]: 'land',
        [STATE.SITTING]: 'sit',
        [STATE.READING]: 'read',
        [STATE.SLEEPING]: 'sleep',
        [STATE.WAKING]: 'idle',
        [STATE.RETURNING_HOME]: 'walk',
        [STATE.FOLLOWING_MOUSE]: 'idle',
        [STATE.INTERACTING]: 'pet',
        [STATE.THINKING]: 'think',
        [STATE.CURIOUS]: 'confused',
        [STATE.STRETCHING]: 'stretch',
        [STATE.YAWNING]: 'yawn',
        [STATE.SLEEPY]: 'sleep',
        [STATE.RESTING]: 'sit',
        [STATE.SHY_REACTION]: 'shy',
        [STATE.HAPPY_REACTION]: 'bounce',
        [STATE.CONFUSED_REACTION]: 'confused',
        [STATE.SURPRISED_REACTION]: 'wave',
        [STATE.PLAYFUL]: 'bounce',
        [STATE.RETURN_TO_IDLE]: 'idle',
      };
      const anim = animMap[next];
      if (anim) this.animation.play(anim);

      // Stop movement on static states
      if ([
        STATE.IDLE, STATE.SITTING, STATE.SLEEPING, STATE.READING, STATE.LANDING,
        STATE.DISABLED, STATE.INTERACTING, STATE.THINKING, STATE.CURIOUS,
        STATE.STRETCHING, STATE.YAWNING, STATE.SLEEPY, STATE.RESTING,
        STATE.SHY_REACTION, STATE.RETURN_TO_IDLE
      ].includes(next)) {
        this.movement.stop();
      }

      // Emotion-linked expressions
      if (next === STATE.SLEEPING) this.expression.setEmotion('sleepy');
      if (next === STATE.WAKING) this.expression.setEmotion('neutral');
    } catch (e) { /* safe */ }
  }

  // === Brain semantic command dispatcher ===
  executeCommand(cmd) {
    return this.bridge._executeSemanticCommand(cmd);
  }

  dispose() {
    try {
      this.bridge.dispose();
      this.windowManager.dispose();
      this.creatures.dispose();
      this.voice.dispose();
      this.idleBehavior.dispose();
      this.mouse.dispose();
      this.lookAt.dispose();
      this.expression.dispose();
      this.animation.dispose();
      this.vrm.dispose();
    } catch (e) { /* safe */ }
  }
}
