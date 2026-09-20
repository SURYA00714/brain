import assert from 'assert';
import { BrainBridge } from '../src/bridge/BrainBridge.js';
import { ACTION_PRIORITY } from '../src/character/ActionIntent.js';

console.log('============================================================');
console.log('AO ARPA AGENT BUS SEMANTIC DISPATCH TESTS');
console.log('============================================================');

// Mock CharacterController for bus unit tests
class MockCharacterController {
  constructor() {
    this.state = { state: 'IDLE' };
    this.postureGraph = { current: 'STANDING', transition: () => true };
    this.movement = { desktopX: 1000, stop: () => {}, walkTo: () => {} };
    this.emotion = { current: 'neutral', setEmotion: (e) => { this.emotion.current = e; }, toJSON: () => ({ current: 'neutral' }) };
    this.lookAt = { attention: null, setAttention: (t, d, i) => { this.lookAt.attention = { t, d, i }; } };
    this.voice = { lastSpoken: null, speak: (text) => { this.voice.lastSpoken = text; } };
    this.worldModel = {
      homeDesktopX: 960,
      desktopToWorldX: (x) => (x - 960) * 0.002,
      desktopToWorldY: (y) => (1080 - y) * 0.002
    };
    this.windowManager = {
      windows: [
        { id: '0x01', title: 'Visual Studio Code', category: 'CODING', x: 200, y: 100, width: 800, height: 600, topEdgeY: 100, platformX: 600 },
        { id: '0x02', title: 'Google Chrome', category: 'BROWSER', x: 100, y: 50, width: 1000, height: 700, topEdgeY: 50, platformX: 600 }
      ]
    };
    this.lastExecutedIntent = null;
  }

  executeActionIntent(intent) {
    this.lastExecutedIntent = intent;
    return true;
  }

  idle() {
    this.state.state = 'IDLE';
    this.postureGraph.current = 'STANDING';
  }

  setEmotion(name) {
    this.emotion.current = name;
  }

  speak(text) {
    this.voice.speak(text);
  }

  jump() {
    this.postureGraph.current = 'FALLING';
  }

  wake() {
    this.postureGraph.current = 'WAKING';
  }

  stopAction() {
    this.movement.stop();
  }

  goHome() {
    this.movement.desktopX = this.worldModel.homeDesktopX;
  }
}

const mockChar = new MockCharacterController();
const bridge = new BrainBridge(mockChar);
const character = bridge.character;

// 1. character.idle()
const resIdle = character.idle();
assert.strictEqual(resIdle.success, true);
assert.strictEqual(mockChar.state.state, 'IDLE');
console.log('✓ character.idle() passed');

// 2. character.walkTo(x)
const resWalk = character.walkTo(1200);
assert.strictEqual(resWalk.success, true);
assert.strictEqual(mockChar.lastExecutedIntent.type, 'WALK');
assert.strictEqual(mockChar.lastExecutedIntent.targetX, 1200);
assert.strictEqual(mockChar.lastExecutedIntent.priority, ACTION_PRIORITY.BRAIN_COMMAND);
console.log('✓ character.walkTo() passed with BRAIN_COMMAND priority');

// 3. character.lookAtMouse()
const resLook = character.lookAtMouse();
assert.strictEqual(resLook.success, true);
assert.strictEqual(mockChar.lookAt.attention.t, 'CURSOR');
console.log('✓ character.lookAtMouse() passed');

// 4. character.emotion('happy')
const resEmo = character.emotion('happy');
assert.strictEqual(resEmo.success, true);
assert.strictEqual(mockChar.emotion.current, 'happy');
console.log('✓ character.emotion() passed');

// 5. character.speak('Hey Macha!')
const resSpeak = character.speak('Hey Macha!');
assert.strictEqual(resSpeak.success, true);
assert.strictEqual(mockChar.voice.lastSpoken, 'Hey Macha!');
console.log('✓ character.speak() passed');

// 6. character.react('annoyed')
const resReact = character.react('annoyed');
assert.strictEqual(resReact.success, true);
assert.strictEqual(mockChar.lastExecutedIntent.type, 'REACTION');
assert.strictEqual(mockChar.lastExecutedIntent.priority, ACTION_PRIORITY.IMPORTANT_REACTION);
assert.strictEqual(mockChar.lastExecutedIntent.emotion, 'annoyed');
console.log('✓ character.react() passed with IMPORTANT_REACTION priority');

// 7. character.jumpToWindow('VS Code')
const resWin = character.jumpToWindow('code');
assert.strictEqual(resWin.success, true);
assert.strictEqual(mockChar.lastExecutedIntent.targetX, 600);
console.log('✓ character.jumpToWindow() passed');

// 8. character.sitOnWindow('Chrome')
const resSitWin = character.sitOnWindow('chrome');
assert.strictEqual(resSitWin.success, true);
assert.strictEqual(mockChar.lastExecutedIntent.type, 'SIT');
assert.ok(mockChar.lastExecutedIntent.surface.id.includes('0x02'));
console.log('✓ character.sitOnWindow() passed');

// 9. Semantic Command Router via _executeSemanticCommand
const resRouter = bridge._executeSemanticCommand({ action: 'speak', text: 'ARPA loopback verified' });
assert.strictEqual(resRouter.success, true);
assert.strictEqual(mockChar.voice.lastSpoken, 'ARPA loopback verified');

const resRouterWalk = bridge._executeSemanticCommand({ action: 'walk_to', x: 500 });
assert.strictEqual(resRouterWalk.success, true);
assert.strictEqual(mockChar.lastExecutedIntent.targetX, 500);
console.log('✓ Bridge semantic router passed');

console.log('=== ALL ARPA AGENT BUS TESTS PASSED! ===');
