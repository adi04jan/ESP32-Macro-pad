/* Preload for the always-on-top key-overlay widget window. */
"use strict";
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("widgetApi", {
  // profile/key-press updates pushed from the main process
  onData: (cb) => { const h = (_e, d) => cb(d); ipcRenderer.on("widget:data", h); return () => ipcRenderer.removeListener("widget:data", h); },
  onKey: (cb) => { const h = (_e, d) => cb(d); ipcRenderer.on("widget:key", h); return () => ipcRenderer.removeListener("widget:key", h); },
  close: () => ipcRenderer.send("widget:close"),
  ready: () => ipcRenderer.send("widget:ready"),
});
