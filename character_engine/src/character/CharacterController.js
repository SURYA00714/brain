import { CONFIG } from '../config.js';
import { CharacterStateMachine, STATE, PRIORITY } from './CharacterState.js';
import { VRMAdapter } from './VRMAdapter.js';
import { AnimationController } from './AnimationController.js';
import { ExpressionController } from './ExpressionController.js';
import { LookAtController, ATTENTION_TARGET } from './LookAtController.js';
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

// Rebuild Subsystems (Master Specification)
import { WorldModel } from '../world/WorldModel.js';
import { CharacterWorldState } from './CharacterWorldState.js';
import { PhysicalValidator } from './PhysicalValidator.js';
import { PostureGraph, POSTURE } from './PostureGraph.js';
import { AnimationResolver } from './AnimationResolver.js';
import { ActionIntent, ACTION_PRIORITY, ACTION_PHASE } from './ActionIntent.js';
import { IKController } from './IKController.js';
import { EventDispatcher } from './EventDispatcher.js';
import { Logger } from '../logger.js';

/**
 * CharacterController — Central orchestrator for AO.
 *
 * Implements the Core Master Architecture:
 * PERCEPTION → WORLD MODEL → INTERNAL STATE → BEHAVIOR DECISION →
 * ACTION INTENT → PHYSICAL VALIDATOR → POSTURE GRAPH →
 * ANIMATION RESOLVER → LAYERED BLENDER → IK SOLVER → VRM
 */
export class CharacterController {
  constructor(scene) {
    this._scene = scene;

    // 1. Authoritative World & Physical Foundations
    this.worldModel = new WorldModel();
    this.worldState = new CharacterWorldState(this.worldModel);
    this.postureGraph = new PostureGraph(POSTURE.STANDING);
    this.animationResolver = new AnimationResolver();

    // Legacy adapter for camera math compatibility
    this.desktop = new DesktopCoordinates();

    // 2. VRM & Animation Body Layer
    this.vrm = new VRMAdapter();
    this.state = new CharacterStateMachine();
    this.animation = new AnimationController(this.vrm);
    this.expression = new ExpressionController(this.vrm);
    this.lookAt = new LookAtController(this.vrm);
    this.movement = new MovementController(this.vrm, this.worldModel, this.worldState);

    // 3. IK & Contact Solver
    this.ik = new IKController(this.vrm, this.worldModel);

    // 4. Perception & Mind
    this.mouse = new MouseTracker(this.desktop);
    this.emotion = new EmotionalState();
    this.dayNight = new DayNightCycle();
    this.windowManager = new WindowManager(this.desktop);
    this.creatures = new CreatureEngine(this);
    this.voice = new VoiceController(this.vrm);
    this.idleBehavior = new IdleBehaviorEngine(this);
    this.behavior = this.idleBehavior;
    this.bridge = new BrainBridge(this);
    this.events = new EventDispatcher(this);

    this._mouseMode = 'LOOK_ONLY';
    this._loaded = false;
    this._activeIntent = null;

    // Synchronize PostureGraph with legacy StateMachine for bridge compatibility
    this.postureGraph.onTransition((prev, next) => this._onPostureChanged(prev, next));
  }

  async load(modelPath) {
    try {
      await this.vrm.load(modelPath || CONFIG.character.modelPath);
      this._scene.add(this.vrm.scene);

      // Start at safe home position
      this.movement.setDesktopX(this.worldModel.homeDesktopX);

      this.expression.start();
      this.mouse.start();
      this.windowManager.start();
      this.idleBehavior.start();
      this.bridge.start();

      this._loaded = true;
      Logger.info(`[AO] Ready. Authoritative home at X=${Math.round(this.worldState.desktopX)}`);
    } catch (err) {
      Logger.error('[AO] Load failed:', err);
    }
  }

  // === PIPELINE: ACTION INTENT EXECUTION & PREEMPTION ===

  /**
   * Executes a semantic ActionIntent through the physical, posture, and IK pipeline.
   */
  async executeActionIntent(rawIntent, durationRange = [2500, 3500]) {
    if (!this._loaded) return false;

    const intent = (rawIntent instanceof ActionIntent)
      ? rawIntent
      : new ActionIntent(rawIntent);

    // Check preemption against active intent
    if (this._activeIntent && this._activeIntent.phase === ACTION_PHASE.ACTIVE) {
      if (!this._activeIntent.canBeInterruptedBy(intent.priority)) {
        Logger.warn(`[INTENT] Action ${intent.type} rejected: active ${this._activeIntent.type} has higher priority`);
        return false;
      }
      // Cancel currently running action
      this._activeIntent.cancel(`Interrupted by ${intent.type}`);
      this.movement.stop();
    }

    this._activeIntent = intent;
    intent.start();

    // 1. PHYSICAL & SPATIAL VALIDATION
    const valResult = PhysicalValidator.validateIntent(intent, this.worldState, this.worldModel);
    if (!valResult.valid) {
      Logger.warn(`[INTENT] Action rejected by PhysicalValidator: ${valResult.reason}`);
      intent.fail(valResult.reason);
      this._activeIntent = null;
      return false;
    }
    const safeIntent = valResult.sanitizedIntent || intent;

    // 2. POSTURE TRANSITION (if required)
    if (safeIntent.type === 'WALK') {
      if (!this.postureGraph.transition(POSTURE.WALK_START)) {
        intent.fail('Illegal posture transition to WALK_START');
        this._activeIntent = null;
        return false;
      }
    } else if (safeIntent.type === 'SIT') {
      if (!this.postureGraph.transition(POSTURE.SIT_PREPARE, { hasSurface: !!safeIntent.surface })) {
        intent.fail('Illegal posture transition to SIT_PREPARE');
        this._activeIntent = null;
        return false;
      }
      this.animation.play('sit_prepare');
      await this.wait(1000);
      this.postureGraph.transition(POSTURE.SITTING, { hasSurface: true });
    }

    intent.setActive();

    // 3. ANIMATION RESOLUTION
    const { animId } = this.animationResolver.resolve(
      safeIntent,
      this.postureGraph.current,
      this.emotion,
      this.emotion.energy
    );

    // 4. MULTI-LAYER DISPATCH
    if (safeIntent.emotion) {
      this.expression.setEmotion(safeIntent.emotion);
    }
    if (safeIntent.attention) {
      this.lookAt.setAttention(
        safeIntent.attention.target,
        safeIntent.attention.duration,
        safeIntent.attention.intensity
      );
    }

    this.animation.play(animId);

    // 5. LOCOMOTION HANDLING
    if (safeIntent.type === 'WALK' && safeIntent.targetX !== undefined) {
      this.postureGraph.transition(POSTURE.WALKING);
      this.movement.walkTo(safeIntent.targetX);
      await this.waitForArrival(7000);
      this.postureGraph.transition(POSTURE.WALK_STOP);
      this.postureGraph.transition(POSTURE.STANDING);
    } else {
      // Duration
      const duration = Array.isArray(durationRange)
        ? durationRange[0] + Math.random() * (durationRange[1] - durationRange[0])
        : (durationRange || intent.duration || 3000);
      await this.wait(duration);
    }

    // 6. FINALIZE & SETTLE
    if (this._activeIntent === intent) {
      intent.complete();
      this._activeIntent = null;
      if (this.postureGraph.current === POSTURE.STANDING) {
        this.idle();
      }
    }
    return true;
  }

  // === USER / BRAIN COMMAND INTERFACE ===

  idle() {
    this.movement.stop();
    this.postureGraph.transition(POSTURE.STANDING);
    this.state.transition(STATE.IDLE, PRIORITY.AUTONOMOUS);
    this.animation.play('idle');
    this.expression.setEmotion('neutral');
    if (this._activeIntent) {
      this._activeIntent.complete();
      this._activeIntent = null;
    }
  }

  walkTo(desktopX) {
    this.executeActionIntent(new ActionIntent({
      type: 'WALK',
      targetX: desktopX,
      priority: ACTION_PRIORITY.USER_COMMAND,
      source: 'USER',
      emotion: 'neutral'
    }));
  }

  walkToDesktop(x) {
    this.walkTo(x);
  }

  goHome() {
    this.executeActionIntent(new ActionIntent({
      type: 'WALK',
      targetX: this.worldModel.homeDesktopX,
      priority: ACTION_PRIORITY.USER_COMMAND,
      source: 'USER',
      emotion: 'neutral'
    }));
  }

  jump() {
    if (this.worldState.isGrounded) {
      this.postureGraph.transition(POSTURE.FALLING);
      this.movement.jump();
      this.animation.play('jump');
    }
  }

  sit() {
    this.executeActionIntent(new ActionIntent({
      type: 'SIT',
      surface: this.worldState.supportSurface || this.worldModel.groundSurface,
      priority: ACTION_PRIORITY.USER_COMMAND,
      source: 'USER',
      emotion: 'neutral',
      duration: 10000
    }));
  }

  sleep() {
    this.executeActionIntent(new ActionIntent({
      type: 'REST',
      priority: ACTION_PRIORITY.USER_COMMAND,
      source: 'USER',
      emotion: 'sleepy',
      duration: 12000
    }));
  }

  wake() {
    if (this.postureGraph.transition(POSTURE.WAKING)) {
      this.animation.play('stretch');
      this.expression.setEmotion('happy');
      setTimeout(() => {
        this.idle();
      }, 2000);
    }
  }

  pet() {
    this.emotion.onPetting();
    this.executeActionIntent(new ActionIntent({
      type: 'PET',
      priority: ACTION_PRIORITY.USER_COMMAND,
      source: 'USER',
      emotion: 'happy',
      duration: 2800,
      attention: { target: ATTENTION_TARGET.USER, duration: 3.0, intensity: 0.9 }
    }));
  }

  stopAction() {
    if (this._activeIntent) {
      this._activeIntent.cancel('Manual user stop');
      this._activeIntent = null;
    }
    this.movement.stop();
    this.idle();
  }

  setEmotion(name) {
    this.expression.setEmotion(name);
  }

  playAnimation(name) {
    this.animation.play(name);
  }

  speak(text, durationMs = null) {
    this.voice.speak(text, durationMs);
  }

  // === ASYNC HELPERS ===

  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  waitForArrival(timeoutMs = 10000) {
    return new Promise(resolve => {
      const start = Date.now();
      const check = setInterval(() => {
        if (!this.movement.isMoving || (Date.now() - start) >= timeoutMs) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });
  }

  // === MAIN UPDATE LOOP (Single RAF Tick) ===

  update(delta) {
    if (!this._loaded) return;

    try {
      const dt = Math.min(delta, CONFIG.performance.maxDeltaTime || 0.033);

      // 1. Natural autonomous gaze
      this.lookAt.update(dt);

      // 2. Authoritative Grounded Movement Update
      this.movement.update(dt);

      // 3. Posture synchronization with locomotion state
      if (this.postureGraph.current === POSTURE.WALKING && !this.movement.isMoving) {
        this.postureGraph.transition(POSTURE.WALK_STOP);
        this.postureGraph.transition(POSTURE.STANDING);
        this.animation.play('idle');
      }

      // 4. Airborne / landing synchronization
      if (this.postureGraph.current === POSTURE.FALLING && this.worldState.isGrounded) {
        this.postureGraph.transition(POSTURE.LANDING);
        this.animation.play('land');
        setTimeout(() => {
          if (this.postureGraph.current === POSTURE.LANDING) {
            this.idle();
          }
        }, 400);
      }

      // 5. Autonomous Behavior Engine update
      this.idleBehavior.update(dt);

      // 6. Layered Animation Blender
      this.animation.update(dt);

      // 7. IK & Foot/Pelvis Ground Alignment Solver
      this.ik.solveLegs(this.postureGraph.current, this.worldState.supportSurface);

      // 8. Anatomical Joint Limit Verification
      PhysicalValidator.clampAllBones(this.vrm);

      // 9. VRM Spring bone simulation
      this.vrm.update(dt);

    } catch (e) {
      Logger.error('[AO] Update error, activating recovery:', e);
      PhysicalValidator.applySafeIdle(this.worldState, this.vrm, this.worldModel);
    }
  }

  _onPostureChanged(prev, next) {
    this.worldState.setPosture(next);
    // Sync with legacy state for IPC/Bridge
    if (next === POSTURE.STANDING) this.state.state = STATE.IDLE;
    if (next === POSTURE.WALKING) this.state.state = STATE.WALKING;
    if (next === POSTURE.SITTING) this.state.state = STATE.SITTING;
    if (next === POSTURE.SLEEPING) this.state.state = STATE.SLEEPING;
  }

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
    } catch (e) {}
  }
}
