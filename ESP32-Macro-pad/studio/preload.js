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
  saveProfile: (filename, profile) => ipcRenderer.invoke("serial:saveProfile", filename, profile),
  setKey: (knum, actions) => ipcRenderer.invoke("serial:setKey", knum, actions),

  // settings / templates
  getSettings: () => ipcRenderer.invoke("settings:get"),
  setSettings: (s) => ipcRenderer.invoke("settings:set", s),
  getTemplates: (ctx) => ipcRenderer.invoke("templates:get", ctx),
  addTemplates: (ctx, items) => ipcRenderer.invoke("templates:add", ctx, items),

  // AI
  aiShortcuts: (opts) => ipcRenderer.invoke("ai:generateShortcuts", opts),
  aiActions: (desc) => ipcRenderer.invoke("ai:generateActions", desc),
  aiTest: () => ipcRenderer.invoke("ai:test"),

  // disk
  importProfile: () => ipcRenderer.invoke("dialog:import"),
  exportProfile: (profile) => ipcRenderer.invoke("dialog:export", profile),

  // serial events (log / fs-info / ready / open / disconnect / profile)
  onEvent: (cb) => {
    const handler = (_e, payload) => cb(payload);
    ipcRenderer.on("serial:event", handler);
    return () => ipcRenderer.removeListener("serial:event", handler);
  },
});
