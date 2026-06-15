/* Macropad Studio — Electron main process.
 * Owns serial, AI, persistence; the renderer talks to it over IPC. */

"use strict";

const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const fs = require("fs");

const schema = require("./services/schema");
const store = require("./services/store");
const ai = require("./services/ai");
const backup = require("./services/backup");
const activewin = require("./services/activewin");
const { contextForProcess } = require("./services/contexts");
const { SerialLink, stripCatEcho } = require("./services/serial");

const link = new SerialLink();
let win = null;
let widgetWin = null;            // always-on-top key overlay
let widgetProfile = null;        // last profile pushed from the main window
let currentContext = "global";   // focused-app context (from window detection)

function send(type, data) { if (win && !win.isDestroyed()) win.webContents.send("serial:event", { type, data }); }
function sendWidget(channel, data) { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.webContents.send(channel, data); }

// Forward serial events to the renderer.
link.on("log", (text) => send("log", text));
link.on("fs-info", (info) => send("fs-info", info));
link.on("ready", () => send("ready"));
link.on("open", () => send("open"));
link.on("disconnect", () => send("disconnect"));
link.on("keyevent", (d) => {
  send("key", d); sendWidget("widget:key", d);   // overlay press-flash
  // Usage tracking: a press "uses" the macro bound to that key in the focused context.
  if (d && d.down && widgetProfile) {
    const k = (widgetProfile.keys || []).find((x) => x.id === d.key);
    if (k && k.actions && k.actions.length) store.recordUsage(currentContext, store.signature(k.actions));
  }
});
link.on("idleevent", (d) => send("idle", d));
link.on("profileevent", (d) => send("profile-active", d));   // device-side profile switch
link.on("ledsframe", (d) => send("leds", d));                // live LED framebuffer mirror

// Focused-app detection -> context. Started/stopped with the auto-switch setting.
function startDetection() {
  activewin.start((proc) => {
    const ctx = contextForProcess(proc);
    if (ctx !== currentContext) { currentContext = ctx; send("active-context", { context: ctx, process: proc }); }
  });
}
function stopDetection() { activewin.stop(); }
link.on("file", (lines) => {
  try {
    const profile = JSON.parse(stripCatEcho(lines.join("\n")));
    send("profile", profile);
  } catch (e) {
    send("log", `Failed to parse profile: ${e.message}\n`);
  }
});

function createWindow() {
  win = new BrowserWindow({
    width: 1320, height: 880, minWidth: 1080, minHeight: 720,
    backgroundColor: "#0b0b0f", title: "Macropad Studio",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  win.removeMenu();
  win.webContents.on("console-message", (_e, level, message, line, src) => {
    if (level >= 2) console.error(`[renderer] ${message} (${src}:${line})`);
  });
  win.webContents.on("render-process-gone", (_e, d) => console.error("[renderer gone]", d.reason));
  win.webContents.on("did-fail-load", (_e, code, desc) => console.error("[load failed]", code, desc));
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
  win.on("closed", () => { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.close(); win = null; });
}

// Frameless, transparent, always-on-top overlay showing the live key map.
function createWidgetWindow() {
  widgetWin = new BrowserWindow({
    width: 236, height: 300, minWidth: 190, minHeight: 220,
    frame: false, transparent: true, resizable: true, skipTaskbar: true,
    alwaysOnTop: true, fullscreenable: false, maximizable: false,
    backgroundColor: "#00000000", title: "Macropad Overlay",
    webPreferences: { preload: path.join(__dirname, "widget-preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  widgetWin.setAlwaysOnTop(true, "screen-saver");          // float above full-screen apps
  widgetWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  widgetWin.removeMenu();
  const a = store.loadSettings().widget_alpha;
  widgetWin.setOpacity(typeof a === "number" ? Math.max(0.4, Math.min(1, a)) : 0.98);
  widgetWin.loadFile(path.join(__dirname, "renderer", "widget.html"));
  widgetWin.on("closed", () => { widgetWin = null; });
}

function toggleWidget() {
  if (widgetWin && !widgetWin.isDestroyed()) {
    if (widgetWin.isVisible()) { widgetWin.hide(); return false; }
    widgetWin.show(); if (widgetProfile) sendWidget("widget:data", widgetProfile); return true;
  }
  createWidgetWindow();
  return true;
}

// Single instance — a second launch focuses the existing window instead of
// opening another that would fight over the serial port.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
  });

  app.whenReady().then(() => {
    // Writable data (settings, templates, backups) must live outside the
    // read-only app bundle once packaged.
    const dataDir = app.isPackaged ? app.getPath("userData") : path.resolve(__dirname, "..");
    const resourceDir = app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
    store.configure({ dataDir, resourceDir });
    backup.configure({ dataDir });
    if (store.loadSettings().auto_switch_enabled) startDetection();
    createWindow();
  });
}

app.on("window-all-closed", () => { stopDetection(); link.disconnect(); app.quit(); });

// -- repair a whole profile's actions before upload -------------------------
function sanitizeProfile(p) {
  const out = {
    schema_version: schema.SCHEMA_VERSION,
    profile_name: String(p.profile_name || "Profile"),
    idle_animation: schema.IDLE_ANIMATIONS.includes(p.idle_animation) ? p.idle_animation : "none",
    default_delay: Number.isInteger(p.default_delay) ? p.default_delay : 30,
    keys: [],
  };
  for (const k of p.keys || []) {
    const key = { id: k.id, actions: schema.repairActions(k.actions || []) };
    if (k.name) key.name = k.name;
    if (Array.isArray(k.glow)) key.led_color = k.glow.map((c) => Math.max(0, Math.min(255, c | 0)));
    out.keys.push(key);
  }
  return out;
}

// -- IPC --------------------------------------------------------------------
ipcMain.handle("ports:list", () => link.listPorts());
ipcMain.handle("serial:connect", (_e, p) => link.connect(p));
ipcMain.handle("serial:disconnect", () => { link.disconnect(); return true; });
ipcMain.handle("serial:fsinfo", () => link.requestFsInfo());
ipcMain.handle("serial:setActive", (_e, n) => link.setActiveProfile(n));
ipcMain.handle("serial:loadProfile", (_e, filename) => link.requestProfile(filename));
ipcMain.handle("serial:setKey", (_e, knum, actions) => link.setKey(knum, schema.repairActions(actions)));
ipcMain.handle("serial:setLed", (_e, knum, r, g, b) => link.setLed(knum, r, g, b));
ipcMain.handle("serial:setIdle", (_e, name) => link.setIdle(name));

// Debounced auto-save: PC backup BEFORE the flash write, then upload.
ipcMain.handle("device:autosave", async (_e, slot, profile) => {
  const clean = sanitizeProfile(profile);
  backup.autoBackup(slot, clean);
  if (!link.isOpen()) return { ok: false, error: "not connected" };
  await link.uploadProfile(`profile${slot}.json`, clean);
  return { ok: true };
});

// Make slot n active on the device, then read it back — sequenced so the cat
// capture never swallows setprofile's reply (and the JSON never leaks to logs).
ipcMain.handle("device:switchProfile", async (_e, n) => {
  if (!link.isOpen()) return null;
  await link.setActiveProfile(n);                       // serialized: setprofile (LED preview)
  const raw = await link.readFile(`profile${n}.json`);  // serialized: cat
  try { return JSON.parse(stripCatEcho(raw)); } catch (_) { return null; }
});

// Manual backup of all 3 profiles straight from the device (no editor side effects).
ipcMain.handle("backup:all", async () => {
  if (!link.isOpen()) return { ok: false, error: "not connected" };
  const profiles = {};
  for (const slot of [1, 2, 3]) {
    const raw = await link.readFile(`profile${slot}.json`);
    try { profiles[slot] = JSON.parse(stripCatEcho(raw)); } catch (_) {}
  }
  return backup.manualBackupAll(profiles);
});

// -- always-on-top key overlay ----------------------------------------------
ipcMain.handle("widget:toggle", () => toggleWidget());
ipcMain.handle("widget:setProfile", (_e, profile) => {
  widgetProfile = profile;
  sendWidget("widget:data", profile);
});
ipcMain.on("widget:ready", () => { if (widgetProfile) sendWidget("widget:data", widgetProfile); });
ipcMain.on("widget:close", () => { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.hide(); });

ipcMain.handle("settings:get", () => store.loadSettings());
ipcMain.handle("settings:set", (_e, s) => {
  const r = store.saveSettings(s);
  if (s && typeof s.widget_alpha === "number" && widgetWin && !widgetWin.isDestroyed()) {
    widgetWin.setOpacity(Math.max(0.4, Math.min(1, s.widget_alpha)));
  }
  if (s && "auto_switch_enabled" in s) { s.auto_switch_enabled ? startDetection() : stopDetection(); }
  return r;
});

ipcMain.handle("templates:get", (_e, ctx) => store.getContextShortcuts(ctx));
ipcMain.handle("templates:ranked", (_e, ctx, limit) => store.rankShortcuts(ctx, limit));
ipcMain.handle("templates:add", (_e, ctx, items) => store.addShortcuts(ctx, items));

ipcMain.handle("ai:generateShortcuts", (_e, opts) => ai.generateShortcuts(store.loadSettings(), opts).catch((err) => { send("log", `AI error: ${err.message}\n`); return []; }));
ipcMain.handle("ai:generateActions", (_e, desc) => ai.generateActions(store.loadSettings(), desc).catch((err) => { send("log", `AI error: ${err.message}\n`); return []; }));
ipcMain.handle("ai:test", () => ai.testConnection(store.loadSettings()).then(() => ({ ok: true })).catch((e) => ({ ok: false, error: e.message })));

ipcMain.handle("dialog:import", async () => {
  const r = await dialog.showOpenDialog(win, { filters: [{ name: "JSON", extensions: ["json"] }], properties: ["openFile"] });
  if (r.canceled || !r.filePaths[0]) return null;
  try { return { ok: true, profile: JSON.parse(fs.readFileSync(r.filePaths[0], "utf8")), path: r.filePaths[0] }; }
  catch (e) { return { ok: false, error: e.message }; }
});
ipcMain.handle("dialog:export", async (_e, profile) => {
  const r = await dialog.showSaveDialog(win, { defaultPath: "profile.json", filters: [{ name: "JSON", extensions: ["json"] }] });
  if (r.canceled || !r.filePath) return null;
  try { fs.writeFileSync(r.filePath, JSON.stringify(sanitizeProfile(profile), null, 2)); return { ok: true, path: r.filePath }; }
  catch (e) { return { ok: false, error: e.message }; }
});
