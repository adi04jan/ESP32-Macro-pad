/* Secure bridge between the renderer and main process. */
"use strict";

const { contextBridge, ipcRenderer } = require("electron");

// Inlined version helper — a sandboxed preload cannot require local app modules
// (that previously broke window.api entirely). Mirrors services/fwversion.js.
function isOutdated(deviceVer, bundledVer) {
  if (!deviceVer || !bundledVer) return false;
  const pa = String(deviceVer).split(".").map((n) => parseInt(n, 10) || 0);
  const pb = String(bundledVer).split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i++) { const d = (pa[i] || 0) - (pb[i] || 0); if (d) return d < 0; }
  return false;
}

contextBridge.exposeInMainWorld("api", {
  // device
  listPorts: () => ipcRenderer.invoke("ports:list"),
  connect: (path) => ipcRenderer.invoke("serial:connect", path),
  disconnect: () => ipcRenderer.invoke("serial:disconnect"),
  fsinfo: () => ipcRenderer.invoke("serial:fsinfo"),
  setActive: (n) => ipcRenderer.invoke("serial:setActive", n),
  loadProfile: (filename) => ipcRenderer.invoke("serial:loadProfile", filename),
  setKey: (knum, actions) => ipcRenderer.invoke("serial:setKey", knum, actions),
  setLed: (knum, r, g, b) => ipcRenderer.invoke("serial:setLed", knum, r, g, b),
  setIdle: (name) => ipcRenderer.invoke("serial:setIdle", name),
  setBrightness: (b) => ipcRenderer.invoke("serial:setBrightness", b),
  autoSave: (slot, profile) => ipcRenderer.invoke("device:autosave", slot, profile),
  switchProfile: (n) => ipcRenderer.invoke("device:switchProfile", n),
  backupAll: () => ipcRenderer.invoke("backup:all"),
  listBackups: () => ipcRenderer.invoke("backup:list"),
  restoreBackup: (id) => ipcRenderer.invoke("backup:restore", id),
  restoreAllBackups: (activeSlot) => ipcRenderer.invoke("backup:restoreAll", activeSlot),

  // settings / templates
  getSettings: () => ipcRenderer.invoke("settings:get"),
  setSettings: (s) => ipcRenderer.invoke("settings:set", s),
  factoryReset: () => ipcRenderer.invoke("settings:reset"),
  getTemplates: (ctx) => ipcRenderer.invoke("templates:get", ctx),
  getRankedTemplates: (ctx, limit) => ipcRenderer.invoke("templates:ranked", ctx, limit),
  addTemplates: (ctx, items) => ipcRenderer.invoke("templates:add", ctx, items),

  // AI
  aiShortcuts: (opts) => ipcRenderer.invoke("ai:generateShortcuts", opts),
  aiActions: (desc) => ipcRenderer.invoke("ai:generateActions", desc),
  aiTest: () => ipcRenderer.invoke("ai:test"),
  aiCancel: () => ipcRenderer.invoke("ai:cancel"),

  // auto-update
  getUpdate: () => ipcRenderer.invoke("update:get"),
  checkForUpdates: () => ipcRenderer.invoke("update:check"),
  installUpdate: () => ipcRenderer.invoke("update:install"),

  // firmware flashing
  flashInfo: () => ipcRenderer.invoke("flash:info"),
  flashStart: (port) => ipcRenderer.invoke("flash:start", port),
  fwIsOutdated: (deviceVer, bundledVer) => isOutdated(deviceVer, bundledVer),

  // always-on-top key overlay
  toggleWidget: () => ipcRenderer.invoke("widget:toggle"),
  widgetSetProfile: (profile) => ipcRenderer.invoke("widget:setProfile", profile),

  // disk
  importProfile: () => ipcRenderer.invoke("dialog:import"),
  exportProfile: (profile) => ipcRenderer.invoke("dialog:export", profile),
  exportAll: () => ipcRenderer.invoke("dialog:exportAll"),

  // serial events (log / fs-info / ready / open / disconnect / profile / key / idle)
  onEvent: (cb) => {
    const handler = (_e, payload) => cb(payload);
    ipcRenderer.on("serial:event", handler);
    return () => ipcRenderer.removeListener("serial:event", handler);
  },
});
