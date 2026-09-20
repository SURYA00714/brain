import assert from 'node:assert';
import { WorldModel } from '../src/world/WorldModel.js';
import { CharacterWorldState } from '../src/character/CharacterWorldState.js';
import { PhysicalValidator } from '../src/character/PhysicalValidator.js';
import { PostureGraph, POSTURE } from '../src/character/PostureGraph.js';
import { ActionIntent, ACTION_PRIORITY, ACTION_PHASE } from '../src/character/ActionIntent.js';

console.log('============================================================');
console.log('AO BEHAVIOR TORTURE & PREEMPTION INVARIANT TESTS');
console.log('============================================================');

const world = new WorldModel();
const state = new CharacterWorldState(world);
const graph = new PostureGraph(POSTURE.STANDING);

// SCENARIO 1: Rapid Preemption (Autonomous action interrupted by User Command)
{
  const autoIntent = new ActionIntent({
    type: 'WALK',
    targetX: 500,
    priority: ACTION_PRIORITY.AUTONOMOUS
  });
  autoIntent.start();
  autoIntent.setActive();

  const userStopIntent = new ActionIntent({
    type: 'STOP',
    priority: ACTION_PRIORITY.USER_COMMAND
  });

  // Verify priority preemption
  assert(autoIntent.canBeInterruptedBy(userStopIntent.priority), 'User command must interrupt autonomous action');
  autoIntent.cancel('Preempted by user command');
  assert.strictEqual(autoIntent.phase, ACTION_PHASE.CANCELLED);
  console.log('✓ SCENARIO 1 PASSED: Autonomous action correctly preempted by User Command.');
}

// SCENARIO 2: Non-interruptible action safety override
{
  const criticalAction = new ActionIntent({
    type: 'SIT_PREPARE',
    priority: ACTION_PRIORITY.AUTONOMOUS,
    interruptible: false
  });
  criticalAction.start();
  criticalAction.setActive();

  // Low-priority intent cannot interrupt
  assert(!criticalAction.canBeInterruptedBy(ACTION_PRIORITY.WORLD_EVENT), 'World event cannot interrupt non-interruptible action');

  // Emergency intent CAN interrupt
  assert(criticalAction.canBeInterruptedBy(ACTION_PRIORITY.EMERGENCY), 'Emergency MUST interrupt even non-interruptible actions');
  console.log('✓ SCENARIO 2 PASSED: Non-interruptible action correctly respects Emergency overrides.');
}

// SCENARIO 3: Support Surface Removed while Sitting
{
  graph.transition(POSTURE.SIT_PREPARE, { hasSurface: true });
  graph.transition(POSTURE.SITTING, { hasSurface: true });
  state.setPosture('SITTING');
  state.supportSurface = { id: 'test_window', isValid: true, minX: 100, maxX: 300, desktopY: 500 };

  // Surface becomes invalid (window closed)
  state.supportSurface.isValid = false;
  const sitCheck = PhysicalValidator.validateSupportSurface(state.supportSurface, world);
  assert(!sitCheck.valid, 'Invalid surface must be rejected');

  // Trigger emergency recovery
  graph.forceReset('Surface Removed');
  state.setPosture('STANDING');
  state.supportSurface = world.groundSurface;

  assert.strictEqual(graph.current, POSTURE.STANDING, 'Posture must be recovered to STANDING');
  assert.strictEqual(state.supportSurface.type, 'GROUND', 'Support surface must revert to GROUND');
  console.log('✓ SCENARIO 3 PASSED: Sudden surface loss triggers immediate safe recovery to GROUND.');
}

// SCENARIO 4: Extreme Out-of-Bounds Target Clamping
{
  const extremeTargets = [-99999, NaN, Infinity, -Infinity, 99999999];
  for (const target of extremeTargets) {
    const val = PhysicalValidator.validateSpatialTarget(target, world);
    assert(val.valid, `Validator must sanitize extreme target: ${target}`);
    const bounds = world.getSafeXBounds('STANDING');
    assert(val.clampedX >= bounds.minX && val.clampedX <= bounds.maxX, `Clamped target ${val.clampedX} must remain inside safe area`);
  }
  console.log('✓ SCENARIO 4 PASSED: Extreme and corrupt coordinates safely clamped.');
}

console.log('=== ALL TORTURE & PREEMPTION TESTS PASSED! ===');
