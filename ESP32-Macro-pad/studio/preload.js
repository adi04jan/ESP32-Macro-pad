/* Secure bridge between the renderer and main process. */
"use strict";

const { contextBridge, ipcRenderer } = require("electron");

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
  autoSave: (slot, profile) => ipcRenderer.invoke("device:autosave", slot, profile),
  switchProfile: (n) => ipcRenderer.invoke("device:switchProfile", n),
  backupAll: () => ipcRenderer.invoke("backup:all"),

  // settings / templates
  getSettings: () => ipcRenderer.invoke("settings:get"),
  setSettings: (s) => ipcRenderer.invoke("settings:set", s),
  getTemplates: (ctx) => ipcRenderer.invoke("templates:get", ctx),
  getRankedTemplates: (ctx, limit) => ipcRenderer.invoke("templates:ranked", ctx, limit),
  addTemplates: (ctx, items) => ipcRenderer.invoke("templates:add", ctx, items),

  // AI
  aiShortcuts: (opts) => ipcRenderer.invoke("ai:generateShortcuts", opts),
  aiActions: (desc) => ipcRenderer.invoke("ai:generateActions", desc),
  aiTest: () => ipcRenderer.invoke("ai:test"),

  // always-on-top key overlay
  toggleWidget: () => ipcRenderer.invoke("widget:toggle"),
  widgetSetProfile: (profile) => ipcRenderer.invoke("widget:setProfile", profile),

  // disk
  importProfile: () => ipcRenderer.invoke("dialog:import"),
  exportProfile: (profile) => ipcRenderer.invoke("dialog:export", profile),

  // serial events (log / fs-info / ready / open / disconnect / profile / key / idle)
  onEvent: (cb) => {
    const handler = (_e, payload) => cb(payload);
    ipcRenderer.on("serial:event", handler);
    return () => ipcRenderer.removeListener("serial:event", handler);
  },
});
