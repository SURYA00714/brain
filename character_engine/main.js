const { app, BrowserWindow, screen, globalShortcut, ipcMain } = require('electron');
const path = require('path');

// GPU & Linux X11 stability flags - MUST be before app is ready
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('enable-transparent-visuals');
app.commandLine.appendSwitch('disable-gpu-process-crash-limit');
app.commandLine.appendSwitch('disable-dev-shm-usage');
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=256');

let mainWindow = null;
let isHidden = false;
let watchdogInterval = null;

function createWindow() {
  try {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;

    mainWindow = new BrowserWindow({
      width: width,
      height: height,
      x: 0,
      y: 0,
      show: false,                   // Don't show until ready, prevents unmapped X11 shape corruption
      transparent: true,
      frame: false,
      hasShadow: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      resizable: false,
      focusable: false,
      type: 'utility',               // X11 utility overlay: stops window manager from grabbing mouse clicks
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: true,
        contextIsolation: false,
        backgroundThrottling: false
      }
    });

    // Set click-through and workspace visibility ONLY after the window is realized & ready
    mainWindow.once('ready-to-show', () => {
      try {
        mainWindow.show();
        mainWindow.setIgnoreMouseEvents(true);
        mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: false });
        console.log('[MAIN] Window ready and click-through enabled safely.');
      } catch (e) {
        console.error('[MAIN] ready-to-show setup error:', e);
      }
    });

    mainWindow.loadFile('index.html');

    mainWindow.on('closed', () => { mainWindow = null; });

    mainWindow.webContents.on('crashed', (event, killed) => {
      console.error(`[MAIN] Renderer crashed (killed=${killed}). Use Ctrl+Shift+Q to quit.`);
    });

    mainWindow.webContents.on('render-process-gone', (event, details) => {
      console.error(`[MAIN] Render process gone: ${details.reason} (exitCode=${details.exitCode})`);
    });

  } catch (err) {
    console.error('[MAIN] createWindow error:', err);
  }
}

function hideOverlay() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
    isHidden = true;
  }
}

function showOverlay() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    isHidden = false;
  }
}

function toggleOverlay() {
  if (isHidden) showOverlay(); else hideOverlay();
}

function startWatchdog() {
  // Pure in-memory check every 10 seconds — zero OS/X11 calls
  watchdogInterval = setInterval(() => {
    try {
      const mem = process.memoryUsage();
      const heapUsedMb = Math.round(mem.heapUsed / 1024 / 1024);
      if (heapUsedMb > 250) {
        console.warn(`[WATCHDOG] Memory: ${heapUsedMb}MB. Running GC check.`);
        if (global.gc) {
          global.gc();
        }
      }
    } catch (e) { /* safe */ }
  }, 10000);
}

app.whenReady().then(() => {
  try {
    // Emergency quit
    globalShortcut.register('CommandOrControl+Shift+Q', () => {
      console.log('[MAIN] Emergency quit triggered.');
      app.quit();
    });

    // Toggle hide/show
    globalShortcut.register('Escape', () => {
      toggleOverlay();
    });

    // Character control keys — Ctrl+Arrow/Key
    const debugKeys = {
      'CommandOrControl+Right': 'walk-right',
      'CommandOrControl+Left': 'walk-left',
      'CommandOrControl+Up': 'jump',
      'CommandOrControl+Down': 'sit',
      'CommandOrControl+H': 'go-home',
      'CommandOrControl+P': 'pet',
    };

    for (const [key, cmd] of Object.entries(debugKeys)) {
      globalShortcut.register(key, () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('character-command', cmd);
        }
      });
    }
  } catch (e) {
    console.error('[MAIN] Shortcut registration failed:', e);
  }

  startWatchdog();

  // Delay window creation slightly for XFCE compositor stabilization
  setTimeout(createWindow, 300);
});

// IPC
ipcMain.on('hide-overlay', () => hideOverlay());
ipcMain.on('show-overlay', () => showOverlay());
ipcMain.on('quit-app', () => app.quit());

app.on('will-quit', () => {
  if (watchdogInterval) clearInterval(watchdogInterval);
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
  app.quit();
});

process.on('uncaughtException', (err) => {
  console.error('[MAIN] Uncaught:', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[MAIN] Unhandled rejection:', reason);
});
