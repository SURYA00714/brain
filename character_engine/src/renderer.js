import * as THREE from 'three';
import { CONFIG } from './config.js';
import { CharacterController } from './character/CharacterController.js';

// ============================================================
// ONE RENDER LOOP. Global error handlers. Keyboard debug controls.
// ============================================================

let renderer, scene, camera, character;
let clock;

function init() {
  try {
    const canvas = document.createElement('canvas');
    document.body.appendChild(canvas);

    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'low-power'
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);

    scene = new THREE.Scene();

    // Camera: positioned so that world y=0 is the bottom of the screen
    camera = new THREE.PerspectiveCamera(
      CONFIG.camera.fov,
      window.innerWidth / window.innerHeight,
      CONFIG.camera.near,
      CONFIG.camera.far
    );
    // We'll set camera.position.y after character loads (uses DesktopCoordinates.camY)

    // Lights
    const dirLight = new THREE.DirectionalLight(0xffffff, Math.PI);
    dirLight.position.set(1, 1, 1).normalize();
    scene.add(dirLight);
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));

    clock = new THREE.Clock();

    character = new CharacterController(scene);
    character.load().then(() => {
      // Set camera Y so ground (y=0) is at the bottom of the screen
      camera.position.set(0, character.desktop.camY, CONFIG.camera.z);
      console.log('[RENDER] Ready. Camera Y =', character.desktop.camY.toFixed(2));
    }).catch((err) => {
      console.error('[RENDER] Load failed:', err);
    });

    // IPC command listener
    setupCommandListener();

    window.addEventListener('resize', onResize);

    // Start ONE loop
    animate();

  } catch (err) {
    console.error('[RENDER] Init failed:', err);
    document.body.innerHTML = `<pre style="color:red;padding:20px">Error: ${err.message}</pre>`;
  }
}

function animate() {
  requestAnimationFrame(animate);
  try {
    const delta = clock.getDelta();
    if (character) character.update(delta);
    renderer.render(scene, camera);
  } catch (err) {
    console.error('[RENDER] Frame error:', err);
    // Don't stop — try next frame
  }
}

function onResize() {
  try {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    if (character && character.desktop) {
      camera.position.set(0, character.desktop.camY, CONFIG.camera.z);
    }
  } catch (e) { /* safe */ }
}

// --- IPC command handler (from main process global shortcuts) ---
function setupCommandListener() {
  const WALK_DISTANCE = 250; // pixels per press
  try {
    const { ipcRenderer } = require('electron');
    ipcRenderer.on('character-command', (event, cmd) => {
      if (!character || !character._loaded) return;
      try {
        switch (cmd) {
          case 'walk-right':
            character.walkTo(character.movement.desktopX + WALK_DISTANCE);
            break;
          case 'walk-left':
            character.walkTo(character.movement.desktopX - WALK_DISTANCE);
            break;
          case 'jump':
            character.jump();
            break;
          case 'go-home':
            character.goHome();
            break;
          case 'sit':
            if (character.state.state === 'SITTING') {
              character.idle();
            } else {
              character.sit();
            }
            break;
        }
      } catch (e) { console.error('[CMD]', e); }
    });
  } catch (e) {
    console.error('[RENDER] IPC setup failed:', e);
  }
}

// Global error safety
window.addEventListener('error', (e) => {
  console.error('[GLOBAL]', e.error || e.message);
  e.preventDefault();
});
window.addEventListener('unhandledrejection', (e) => {
  console.error('[GLOBAL] Promise:', e.reason);
  e.preventDefault();
});

// Expose for console
window.brainCharacter = null;

init();

setTimeout(() => { window.brainCharacter = character; }, 3000);
