// Brain Companion Desktop Avatar Controller
// High-performance SSE-driven avatar with mouse tracking and expressive states

const root = document.getElementById('companionRoot');
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');
const leftEye = document.getElementById('leftEye');
const rightEye = document.getElementById('rightEye');
const leftPupil = document.getElementById('leftPupil');
const rightPupil = document.getElementById('rightPupil');
const mouthLine = document.getElementById('mouthLine');
const commandForm = document.getElementById('commandForm');
const commandInput = document.getElementById('commandInput');
const voiceToggleBtn = document.getElementById('voiceToggleBtn');
const avatarSvg = document.getElementById('avatarSvg');

let currentState = 'IDLE';
let isSpeaking = false;
let mouthAnimationInterval = null;
let voiceEnabled = true;
let eventSource = null;

// Mouth curves for speech animation
const speechMouthShapes = [
  'M 70 98 Q 80 106 90 98',
  'M 68 97 Q 80 110 92 97',
  'M 72 99 Q 80 102 88 99',
  'M 69 98 Q 80 107 91 98',
  'M 71 100 Q 80 100 89 100'
];
let speechFrameIndex = 0;

// Voice toggle
if (voiceToggleBtn) {
  voiceToggleBtn.addEventListener('click', () => {
    voiceEnabled = !voiceEnabled;
    voiceToggleBtn.classList.toggle('muted', !voiceEnabled);
    voiceToggleBtn.textContent = voiceEnabled ? '🔊' : '🔇';
  });
}

// Eye blink animation loop
function blink() {
  if (currentState === 'SLEEPING') {
    leftEye.setAttribute('ry', '1');
    rightEye.setAttribute('ry', '1');
    setTimeout(blink, 2000);
    return;
  }
  
  leftEye.setAttribute('ry', '1');
  rightEye.setAttribute('ry', '1');
  setTimeout(() => {
    leftEye.setAttribute('ry', '12');
    rightEye.setAttribute('ry', '12');
  }, 140);

  const nextBlink = Math.random() * 4000 + 2500;
  setTimeout(blink, nextBlink);
}
setTimeout(blink, 2000);

// Mouse pupil tracking
window.addEventListener('mousemove', (e) => {
  if (currentState === 'SLEEPING') return;

  const rect = avatarSvg.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;

  const dx = e.clientX - centerX;
  const dy = e.clientY - centerY;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Clamp translation
  const maxOffset = 3.5;
  const factor = dist > 0 ? Math.min(dist / 200, 1) * maxOffset / dist : 0;
  const offsetX = dx * factor;
  const offsetY = dy * factor;

  leftPupil.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  rightPupil.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
});

// Start / stop mouth speech animation
function setMouthSpeaking(speaking) {
  if (speaking && !mouthAnimationInterval) {
    mouthAnimationInterval = setInterval(() => {
      speechFrameIndex = (speechFrameIndex + 1) % speechMouthShapes.length;
      mouthLine.setAttribute('d', speechMouthShapes[speechFrameIndex]);
    }, 110);
  } else if (!speaking && mouthAnimationInterval) {
    clearInterval(mouthAnimationInterval);
    mouthAnimationInterval = null;
    applyMouthShape(currentState);
  }
}

// Apply static mouth shape per state
function applyMouthShape(state) {
  switch (state) {
    case 'SUCCESS':
      mouthLine.setAttribute('d', 'M 65 96 Q 80 108 95 96');
      break;
    case 'ERROR':
      mouthLine.setAttribute('d', 'M 68 103 Q 80 96 92 103');
      break;
    case 'CONFUSED':
      mouthLine.setAttribute('d', 'M 68 97 Q 78 104 92 98');
      break;
    case 'WARNING':
      mouthLine.setAttribute('d', 'M 72 98 Q 80 102 88 98');
      break;
    case 'THINKING':
      mouthLine.setAttribute('d', 'M 72 100 Q 80 100 88 100');
      break;
    case 'SLEEPING':
      mouthLine.setAttribute('d', 'M 74 100 Q 80 101 86 100');
      break;
    default:
      mouthLine.setAttribute('d', 'M 70 98 Q 80 103 90 98');
      break;
  }
}

// Apply incoming state data
function applyState(data) {
  if (!data) return;

  const state = (data.state || data.activity || 'IDLE').toUpperCase();
  const speaking = Boolean(data.speaking);

  if (state !== currentState) {
    currentState = state;
    statusBadge.textContent = state;
    root.className = 'companion-container state-' + state.toLowerCase();
    
    if (!speaking) {
      applyMouthShape(state);
    }
  }

  if (speaking !== isSpeaking) {
    isSpeaking = speaking;
    setMouthSpeaking(speaking);
  }

  if (data.status_text) {
    statusText.textContent = data.status_text;
  }

  // Update status panel fields
  updateStatusPanel(data);

  // Voice synthesis through Web Speech API if requested and enabled
  if (data.speak_text && voiceEnabled && window.speechSynthesis) {
    try {
      const utter = new SpeechSynthesisUtterance(data.speak_text);
      utter.rate = 1.05;
      utter.pitch = 1.0;
      utter.onstart = () => setMouthSpeaking(true);
      utter.onend = () => setMouthSpeaking(false);
      utter.onerror = () => setMouthSpeaking(false);
      window.speechSynthesis.speak(utter);
    } catch (err) {
      console.warn('Speech synthesis error:', err);
    }
  }
}

// Update companion status panel
function updateStatusPanel(data) {
  const set = (id, value, cls) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value || '—';
    el.className = 'status-value' + (cls ? ' ' + cls : '');
  };

  // Desktop Mate status
  const dmStatus = data.desktop_mate_status;
  if (dmStatus) {
    const dmCls = dmStatus === 'AVAILABLE' ? 'ok' : (dmStatus === 'DISCONNECTED' ? 'warn' : 'err');
    set('dmStatus', dmStatus, dmCls);
  }

  // Bridge: infer from desktop_mate_status or bridge field
  const bridgeConnected = data.bridge_connected;
  if (bridgeConnected !== undefined) {
    set('bridgeStatus', bridgeConnected ? 'CONNECTED' : 'DISCONNECTED', bridgeConnected ? 'ok' : 'warn');
  } else if (dmStatus) {
    set('bridgeStatus', dmStatus === 'AVAILABLE' ? 'CONNECTED' : 'DISCONNECTED',
        dmStatus === 'AVAILABLE' ? 'ok' : 'warn');
  }

  // Companion mode
  if (data.companion_mode) set('modeStatus', data.companion_mode, null);

  // Voice status
  const voiceStatus = data.voice_status;
  if (voiceStatus) {
    const vCls = voiceStatus === 'AVAILABLE' ? 'ok' : (data.speaking ? 'ok' : null);
    set('voiceStatus', data.speaking ? 'SPEAKING' : voiceStatus, vCls);
  }

  // Active application
  const app = data.current_application || data.active_application || data.focused_app;
  if (app) set('appStatus', app, null);

  // Current task
  const task = data.current_task || data.active_task;
  if (task) set('taskStatus', task.length > 24 ? task.substring(0, 24) + '…' : task, null);
}

// Real-time EventSource connection (SSE)
function connectSSE() {
  try {
    eventSource = new EventSource('/api/events');

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const data = payload.data ? payload.data : payload; // Support nested or flat payload
        applyState(data);
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      // Reconnect after delay
      setTimeout(connectSSE, 3000);
    };
  } catch (e) {
    console.warn('SSE not supported or failed, falling back to polling');
    startPolling();
  }
}

// Polling fallback
let pollingTimer = null;
async function pollState() {
  if (eventSource && eventSource.readyState === EventSource.OPEN) {
    return; // SSE is active
  }
  try {
    const res = await fetch('/api/state');
    if (res.ok) {
      const data = await res.json();
      applyState(data);
    }
  } catch (e) {
    // Network reconnecting
  }
  pollingTimer = setTimeout(pollState, 800);
}

function startPolling() {
  if (!pollingTimer) {
    pollState();
  }
}

// Initialize live connections
connectSSE();
startPolling(); // Runs as backup if SSE disconnects

// Interactive Command submission
commandForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const cmd = commandInput.value.trim();
  if (!cmd) return;

  commandInput.value = '';
  applyState({ state: 'THINKING', status_text: 'Processing: ' + cmd, speaking: false });

  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd })
    });
    const data = await res.json();
    if (data.success) {
      applyState({ state: 'SUCCESS', status_text: data.result || 'Task completed' });
    } else {
      applyState({ state: 'ERROR', status_text: data.error || 'Failed' });
    }
  } catch (err) {
    applyState({ state: 'ERROR', status_text: 'Connection error' });
  }
});
