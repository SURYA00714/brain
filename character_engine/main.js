const { app, BrowserWindow, screen, globalShortcut, ipcMain } = require('electron');
const path = require('path');

// GPU & Stability flags - BEFORE app ready.
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
      transparent: true,
      frame: false,
      hasShadow: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      resizable: false,
      focusable: false,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: true,
        contextIsolation: false,
        backgroundThrottling: false
      }
    });

    // Simple click-through. NO {forward: true} — that crashes XFCE.
    mainWindow.setIgnoreMouseEvents(true);
    mainWindow.setVisibleOnAllWorkspaces(true);

    mainWindow.loadFile('index.html');

    mainWindow.on('closed', () => { mainWindow = null; });

    // Log renderer errors but do NOT auto-reload endlessly
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
  // Watchdog checks system memory & process stability every 10 seconds
  watchdogInterval = setInterval(() => {
    try {
      const mem = process.memoryUsage();
      const heapUsedMb = Math.round(mem.heapUsed / 1024 / 1024);
      if (heapUsedMb > 250) {
        console.warn(`[WATCHDOG] High memory usage detected: ${heapUsedMb}MB. Running GC safety check.`);
        if (global.gc) {
          global.gc();
        }
      }
    } catch (e) { /* safe */ }
  }, 10000);
}

app.whenReady().then(() => {
  // Register emergency shortcuts BEFORE window creation
  try {
    globalShortcut.register('CommandOrControl+Shift+Q', () => {
      console.log('[MAIN] Emergency quit triggered.');
      app.quit();
    });
    globalShortcut.register('Escape', () => {
      toggleOverlay();
    });

    // Debug movement keys — Ctrl+Arrow so they don't steal normal keys
    const debugKeys = {
      'CommandOrControl+Right': 'walk-right',
      'CommandOrControl+Left': 'walk-left',
      'CommandOrControl+Up': 'jump',
      'CommandOrControl+Down': 'sit',
      'CommandOrControl+H': 'go-home',
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

  // Delay window creation for XFCE/KDE/GNOME compositor
  setTimeout(createWindow, 500);
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
