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

/**
 * CharacterController — Central orchestrator for Ao.
 * Human-like behavior:
 * - Logical perception (proximity, head detection)
 * - Petting interaction with emotional feedback
 * - Coherent activities with execution and return paths
 * - Autonomous state machine with priority management
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
    this.idleBehavior = new IdleBehaviorEngine(this);

    this._mouseMode = 'LOOK_ONLY'; // PASSIVE, LOOK_ONLY, FOLLOW
    this._isBeingPetted = false;
    this._petCooldown = 0;
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
      this.idleBehavior.start();
      this._loaded = true;
      console.log('[AO] Loaded. Home at X=' + Math.round(this.desktop.homeX));
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

  // === Core API ===

  idle() {
    this.movement.stop();
    this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
  }

  walkTo(desktopX) {
    if (this.state.transition(STATE.WALKING, PRIORITY.AUTONOMOUS)) {
      this.movement.walkTo(desktopX);
    }
  }

  walkToDesktop(x) { this.walkTo(x); }

  goHome() {
    if (this.state.transition(STATE.RETURNING_HOME, PRIORITY.AUTONOMOUS)) {
      this.movement.walkTo(this.desktop.homeX);
    }
  }

  jump() {
    if (this.state.transition(STATE.JUMPING, PRIORITY.AUTONOMOUS)) {
      this.movement.jump();
    }
  }

  jumpTo(desktopX) {
    if (this.state.transition(STATE.JUMPING, PRIORITY.AUTONOMOUS)) {
      this.movement.walkTo(desktopX);
      this.movement.jump();
    }
  }

  sit() {
    this.movement.stop();
    this.state.transition(STATE.SITTING, PRIORITY.USER_COMMAND);
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

  speak(text) {
    try { this.vrm.setExpression('aa', 0.5); } catch (e) {}
    setTimeout(() => {
      try { this.vrm.setExpression('aa', 0); } catch (e) {}
    }, 2000);
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

  // === MAIN UPDATE LOOP ===

  update(delta) {
    if (!this._loaded) return;
    try {
      const dt = Math.min(delta, CONFIG.performance.maxDeltaTime);

      // 1. Natural autonomous lookAt update (glancing around)
      this.lookAt.update(dt);

      // 4. Follow mouse mode
      if (this._mouseMode === 'FOLLOW') {
        const dx = this.mouse.x - this.movement.desktopX;
        if (Math.abs(dx) > CONFIG.mouse.followDeadZone) {
          this.movement.walkTo(this.mouse.x);
          if (this.state.state === STATE.IDLE || this.state.state === STATE.FOLLOWING_MOUSE) {
            this.state.transition(STATE.WALKING, PRIORITY.INTERACTION);
          }
        }
      }

      // 5. Movement update
      this.movement.update(dt);

      // 6. Auto-transitions
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

      // 7. Animation update
      this.animation.update(dt);

      // 8. VRM update (spring bones etc)
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
      };
      const anim = animMap[next];
      if (anim) this.animation.play(anim);

      // Stop movement on static states
      if ([STATE.IDLE, STATE.SITTING, STATE.SLEEPING, STATE.READING, STATE.LANDING, STATE.DISABLED, STATE.INTERACTING].includes(next)) {
        this.movement.stop();
      }

      // Emotion-linked expressions
      if (next === STATE.SLEEPING) this.expression.setEmotion('sleepy');
      if (next === STATE.WAKING) this.expression.setEmotion('neutral');
    } catch (e) { /* safe */ }
  }

  // === Brain command interface ===
  executeCommand(cmd) {
    try {
      switch (cmd.action) {
        case 'character.idle': this.idle(); break;
        case 'character.walk_to': this.walkTo(cmd.x); break;
        case 'character.jump': this.jump(); break;
        case 'character.sit': this.sit(); break;
        case 'character.sleep': this.sleep(); break;
        case 'character.wake': this.wake(); break;
        case 'character.go_home': this.goHome(); break;
        case 'character.rest': this.rest(); break;
        case 'character.follow_mouse': this.followMouse(); break;
        case 'character.stop': this.stopAction(); break;
        case 'character.emotion': this.setEmotion(cmd.name); break;
        case 'character.animation': this.playAnimation(cmd.name); break;
        case 'character.speak': this.speak(cmd.text); break;
        default: return { success: false, error: 'Unknown command' };
      }
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  dispose() {
    try {
      this.idleBehavior.dispose();
      this.mouse.dispose();
      this.lookAt.dispose();
      this.expression.dispose();
      this.animation.dispose();
      this.vrm.dispose();
    } catch (e) { /* safe */ }
  }
}
