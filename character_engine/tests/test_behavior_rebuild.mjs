import assert from 'node:assert';
import { WorldModel } from '../src/world/WorldModel.js';
import { CharacterWorldState } from '../src/character/CharacterWorldState.js';
import { PhysicalValidator } from '../src/character/PhysicalValidator.js';
import { PostureGraph, POSTURE } from '../src/character/PostureGraph.js';
import { AnimationResolver } from '../src/character/AnimationResolver.js';
import { ANIMATION_CATALOG } from '../src/character/AnimationCatalog.js';

console.log('--- STARTING AO BEHAVIOR REBUILD UNIT TESTS ---');

// TEST 1: World Model & Safe Margins
{
  const world = new WorldModel();
  assert.strictEqual(world.groundY, 0, 'Ground Y must be 0');
  assert(world.SAFE_MARGIN_X >= 50, 'Safe margin X must be at least 50px');
  assert(world.SAFE_MARGIN_Y >= 30, 'Safe margin Y must be at least 30px');

  // Test offscreen clamping
  const farLeft = -500;
  const farRight = 5000;
  const clampedLeft = world.clampSafeX(farLeft);
  const clampedRight = world.clampSafeX(farRight);

  assert(clampedLeft >= world.SAFE_MARGIN_X, `Clamped left ${clampedLeft} must be >= SAFE_MARGIN_X`);
  assert(clampedRight <= world.screenW - world.SAFE_MARGIN_X, `Clamped right ${clampedRight} must be <= screenW - SAFE_MARGIN_X`);
  console.log('✓ TEST 1 PASSED: WorldModel boundaries and safe margins verified.');
}

// TEST 2: Authoritative Character World State
{
  const world = new WorldModel();
  const state = new CharacterWorldState(world);
  assert.strictEqual(state.posture, 'STANDING', 'Default posture must be STANDING');
  assert(state.isGrounded, 'Character must be grounded by default');

  state.setPosition(world.screenW + 9999);
  assert(state.desktopX <= world.screenW - world.SAFE_MARGIN_X, 'Position must be strictly clamped inside safe margins');
  console.log('✓ TEST 2 PASSED: Authoritative CharacterWorldState position & clamping verified.');
}

// TEST 3: Physical Validator — Anatomical Joint Limits
{
  // Test Knee Limits: Knee must ONLY bend backwards (X in [0.0, 2.6]). Negative X is impossible dislocation.
  const badKneeRotation = { x: -1.2, y: 0.5, z: -0.3 };
  PhysicalValidator.clampBoneRotation('leftLowerLeg', badKneeRotation);
  assert(badKneeRotation.x >= 0.0, `Knee rotation X (${badKneeRotation.x}) must not be negative!`);
  assert(badKneeRotation.y <= 0.08 && badKneeRotation.y >= -0.08, 'Knee twist Y must be bounded');

  // Test Elbow Limits: 1-DOF flex
  const badElbowRotation = { x: 2.5, y: -0.1, z: 4.5 };
  PhysicalValidator.clampBoneRotation('leftLowerArm', badElbowRotation);
  assert(badElbowRotation.z <= 2.4, `Elbow flexion Z (${badElbowRotation.z}) must be clamped <= 2.4`);

  // Test Spine Limits
  const badSpine = { x: 1.5, y: 1.2, z: -1.0 };
  PhysicalValidator.clampBoneRotation('spine', badSpine);
  assert(badSpine.x <= 0.45 && badSpine.x >= -0.35, 'Spine pitch must be bounded');
  console.log('✓ TEST 3 PASSED: PhysicalValidator humanoid joint limits strictly enforced.');
}

// TEST 4: Physical Validator — Spatial & Surface Validation
{
  const world = new WorldModel();
  const state = new CharacterWorldState(world);

  // Walk Intent validation
  const walkCheck = PhysicalValidator.validateIntent({ type: 'WALK', targetX: -100 }, state, world);
  assert(walkCheck.valid, 'Walk intent should be valid after clamping');
  assert(walkCheck.sanitizedIntent.targetX >= world.SAFE_MARGIN_X, 'Walk target must be clamped to safe margin');

  // Sit Intent without valid surface
  const badSitCheck = PhysicalValidator.validateIntent({ type: 'SIT', surface: { isValid: false } }, state, world);
  assert(!badSitCheck.valid, 'Sit intent without valid surface must be rejected');

  // Sit Intent with valid surface
  const goodSitCheck = PhysicalValidator.validateIntent({
    type: 'SIT',
    surface: { isValid: true, minX: 100, maxX: 300, desktopY: world.screenH }
  }, state, world);
  assert(goodSitCheck.valid, 'Sit intent with valid surface must be accepted');
  console.log('✓ TEST 4 PASSED: PhysicalValidator spatial and surface constraints verified.');
}

// TEST 5: Posture Graph — Legal Transitions & Illegal Jump Rejection
{
  const graph = new PostureGraph(POSTURE.STANDING);

  // Legal walk sequence
  assert(graph.transition(POSTURE.WALK_START), 'STANDING -> WALK_START must be legal');
  assert(graph.transition(POSTURE.WALKING), 'WALK_START -> WALKING must be legal');
  assert(graph.transition(POSTURE.WALK_STOP), 'WALKING -> WALK_STOP must be legal');
  assert(graph.transition(POSTURE.STANDING), 'WALK_STOP -> STANDING must be legal');

  // Illegal direct jump: STANDING -> SLEEPING (must be rejected)
  assert(!graph.transition(POSTURE.SLEEPING), 'Direct STANDING -> SLEEPING jump must be rejected');
  assert.strictEqual(graph.current, POSTURE.STANDING, 'Posture must remain STANDING');

  // Legal prepare-to-sit sequence
  assert(graph.transition(POSTURE.SIT_PREPARE, { hasSurface: true }), 'STANDING -> SIT_PREPARE with surface must be legal');
  assert(graph.transition(POSTURE.SITTING, { hasSurface: true }), 'SIT_PREPARE -> SITTING must be legal');
  assert(graph.transition(POSTURE.STAND_PREPARE), 'SITTING -> STAND_PREPARE must be legal');
  assert(graph.transition(POSTURE.STANDING), 'STAND_PREPARE -> STANDING must be legal');
  console.log('✓ TEST 5 PASSED: PostureGraph legal transitions and illegal rejection verified.');
}

// TEST 6: Animation Resolver & Catalog Compatibility
{
  const resolver = new AnimationResolver();
  const mockEmotion = { happiness: 0.8, curiosity: 0.5 };

  // Resolve GREET while STANDING
  const greetStanding = resolver.resolve({ type: 'GREET' }, POSTURE.STANDING, mockEmotion, 0.9);
  assert(greetStanding.animId === 'wave' || greetStanding.animId === 'wave_small', 'GREET standing must resolve to wave variant');

  // Resolve GREET while SLEEPING (incompatible posture fallback)
  const greetSleeping = resolver.resolve({ type: 'GREET' }, POSTURE.SLEEPING, mockEmotion, 0.2);
  assert.strictEqual(greetSleeping.animId, 'idle', 'Incompatible posture must safely fallback to idle');

  // Verify all animations in catalog have required metadata
  for (const [id, meta] of Object.entries(ANIMATION_CATALOG)) {
    assert(meta.id, `Catalog item ${id} must have id`);
    assert(meta.category, `Catalog item ${id} must have category`);
    assert(Array.isArray(meta.compatiblePostures), `Catalog item ${id} must have compatiblePostures array`);
    assert(meta.blendDuration > 0, `Catalog item ${id} must have positive blendDuration`);
  }
  console.log('✓ TEST 6 PASSED: AnimationResolver and ANIMATION_CATALOG verified.');
}

console.log('=== ALL 6 UNIT TESTS PASSED SUCCESSFULLY! ===');
