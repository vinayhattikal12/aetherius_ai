import { contextBridge, ipcRenderer } from 'electron';

// Expose safe desktop IPC APIs to the renderer
contextBridge.exposeInMainWorld('electronAPI', {
  getVersion: () => ipcRenderer.invoke('app-version'),
  onMessage: (callback: (message: string) => void) => {
    ipcRenderer.on('main-process-message', (_event, value) => callback(value));
  }
});
