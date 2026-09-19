// preload.js - minimal, safe bridge
const { ipcRenderer } = require('electron');

window.brainIPC = {
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),
  quit: () => ipcRenderer.send('quit-app'),
};
