const { app, BrowserWindow, screen, globalShortcut, ipcMain } = require('electron');
const path = require('path');

// GPU flags - BEFORE app ready. Only safe ones.
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('enable-transparent-visuals');

let mainWindow = null;
let isHidden = false;

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

    // Log renderer errors but do NOT auto-reload
    mainWindow.webContents.on('crashed', () => {
      console.error('[MAIN] Renderer crashed. Use Ctrl+Shift+Q to quit.');
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

  // Delay window creation for XFCE compositor
  setTimeout(createWindow, 500);
});

// IPC
ipcMain.on('hide-overlay', () => hideOverlay());
ipcMain.on('show-overlay', () => showOverlay());
ipcMain.on('quit-app', () => app.quit());

app.on('will-quit', () => {
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
