/* Macropad Studio — Electron main process.
 * Owns serial, AI, persistence; the renderer talks to it over IPC. */

"use strict";

const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage, shell, screen } = require("electron");
const path = require("path");
const fs = require("fs");

const ICON = path.join(__dirname, "assets", "icon.ico");
const TRAY_ICON = path.join(__dirname, "assets", "tray.png");

const schema = require("./services/schema");
const store = require("./services/store");
const ai = require("./services/ai");
const backup = require("./services/backup");
const activewin = require("./services/activewin");
const { contextForProcess } = require("./services/contexts");
const { SerialLink, stripCatEcho } = require("./services/serial");
const { autoUpdater } = require("electron-updater");
const flasher = require("./services/flasher");
const { parseStatusVersion } = require("./services/fwversion");

const link = new SerialLink();
let win = null;
let tray = null;                 // system-tray icon (close minimizes here)
let trayHintShown = false;       // one-time "still running" balloon
let widgetWin = null;            // always-on-top key overlay
let widgetProfile = null;        // last profile pushed from the main window
let widgetIdleTimer = null;      // auto-hide-when-idle timer for the overlay
let currentContext = "global";   // focused-app context (from window detection)
let updateState = { status: "idle" };   // auto-update: idle|checking|downloading|downloaded|none|error

const WIDGET_IDLE_MS = 8000;     // hide the overlay after this long without a keypress
const WIDGET_SNAP_PX = 24;       // snap the overlay to a screen edge within this margin

function send(type, data) { if (win && !win.isDestroyed()) win.webContents.send("serial:event", { type, data }); }
function sendWidget(channel, data) { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.webContents.send(channel, data); }

// Forward serial events to the renderer.
link.on("log", (text) => send("log", text));
link.on("fs-info", (info) => send("fs-info", info));
link.on("ready", () => send("ready"));
link.on("open", () => {
  send("open");
  link.command("status").then((out) => {
    const v = parseStatusVersion(out);
    if (v) send("fw-version", { version: v });
  }).catch(() => {});
});
link.on("disconnect", () => send("disconnect"));
link.on("keyevent", (d) => {
  send("key", d); sendWidget("widget:key", d); widgetActivity();   // overlay press-flash + un-idle
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
    backgroundColor: "#0b0b0f", title: "Macropad Studio", icon: ICON,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  win.removeMenu();

  // External links (About, etc.) open in the system browser, never in-app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });

  // Closing the window hides it to the tray instead of quitting; the app keeps
  // running (serial + overlay) until "Quit" is chosen from the tray.
  win.on("close", (e) => {
    if (app.isQuitting) return;
    e.preventDefault();
    win.hide();
    if (!trayHintShown && tray) {
      trayHintShown = true;
      try { tray.displayBalloon({ title: "Macropad Studio", content: "Still running in the tray. Right-click the icon to quit." }); } catch (_) {}
    }
  });
  win.webContents.on("console-message", (_e, level, message, line, src) => {
    if (level >= 2) console.error(`[renderer] ${message} (${src}:${line})`);
  });
  win.webContents.on("render-process-gone", (_e, d) => console.error("[renderer gone]", d.reason));
  win.webContents.on("did-fail-load", (_e, code, desc) => console.error("[load failed]", code, desc));
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
  win.on("closed", () => { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.close(); win = null; });
}

// Snap the overlay to the nearest screen edge once a drag finishes.
function snapWidget() {
  if (!store.loadSettings().widget_snap || !widgetWin || widgetWin.isDestroyed()) return;
  const b = widgetWin.getBounds();
  const area = screen.getDisplayNearestPoint({ x: b.x + b.width / 2, y: b.y + b.height / 2 }).workArea;
  let x = b.x, y = b.y;
  if (Math.abs(b.x - area.x) < WIDGET_SNAP_PX) x = area.x;
  if (Math.abs((b.x + b.width) - (area.x + area.width)) < WIDGET_SNAP_PX) x = area.x + area.width - b.width;
  if (Math.abs(b.y - area.y) < WIDGET_SNAP_PX) y = area.y;
  if (Math.abs((b.y + b.height) - (area.y + area.height)) < WIDGET_SNAP_PX) y = area.y + area.height - b.height;
  if (x !== b.x || y !== b.y) widgetWin.setBounds({ x, y, width: b.width, height: b.height });
}

// Auto-hide-when-idle: a keypress re-shows the overlay and restarts the timer.
function widgetActivity() {
  if (!store.loadSettings().widget_auto_hide || !widgetWin || widgetWin.isDestroyed()) return;
  if (!widgetWin.isVisible()) widgetWin.show();
  clearTimeout(widgetIdleTimer);
  widgetIdleTimer = setTimeout(() => { if (widgetWin && !widgetWin.isDestroyed()) widgetWin.hide(); }, WIDGET_IDLE_MS);
}

function applyLoginItem(open) { try { app.setLoginItemSettings({ openAtLogin: !!open }); } catch (_) {} }

function firmwareDir() {
  return app.isPackaged ? path.join(process.resourcesPath, "firmware")
                        : path.resolve(__dirname, "..", "firmware");
}
function firmwareInfo() {
  try {
    const m = JSON.parse(fs.readFileSync(path.join(firmwareDir(), "manifest.json"), "utf8"));
    const bin = path.join(firmwareDir(), "macropad.merged.bin");
    return { version: m.version || null, bin, available: fs.existsSync(bin),
             size: fs.existsSync(bin) ? fs.statSync(bin).size : 0 };
  } catch (_) { return { version: null, bin: null, available: false, size: 0 }; }
}

// Auto-update from GitHub Releases. Status is mirrored to the renderer over the
// existing event stream as { status, version?, percent?, error? }.
function sendUpdate(patch) { updateState = { ...updateState, ...patch }; send("update", updateState); }
function initAutoUpdate() {
  if (!app.isPackaged) return;   // dev has no app-update.yml
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.on("checking-for-update", () => sendUpdate({ status: "checking" }));
  autoUpdater.on("update-available", (info) => sendUpdate({ status: "downloading", version: info && info.version, percent: 0 }));
  autoUpdater.on("update-not-available", () => sendUpdate({ status: "none" }));
  autoUpdater.on("download-progress", (p) => sendUpdate({ status: "downloading", percent: Math.round(p.percent || 0) }));
  autoUpdater.on("update-downloaded", (info) => sendUpdate({ status: "downloaded", version: info && info.version }));
  autoUpdater.on("error", (err) => sendUpdate({ status: "error", error: String((err && err.message) || err) }));
  autoUpdater.checkForUpdates().catch((e) => sendUpdate({ status: "error", error: e.message }));
}

// Frameless, transparent, always-on-top overlay showing the live key map.
function createWidgetWindow() {
  const s = store.loadSettings();
  widgetWin = new BrowserWindow({
    width: 236, height: 300, minWidth: 190, minHeight: 220,
    frame: false, transparent: true, resizable: true, skipTaskbar: true,
    alwaysOnTop: true, fullscreenable: false, maximizable: false,
    backgroundColor: "#00000000", title: "Macropad Overlay",
    webPreferences: { preload: path.join(__dirname, "widget-preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  widgetWin.setAlwaysOnTop(s.widget_stay_on_top !== false, "screen-saver");   // float above full-screen apps
  widgetWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  widgetWin.removeMenu();
  widgetWin.setOpacity(typeof s.widget_alpha === "number" ? Math.max(0.4, Math.min(1, s.widget_alpha)) : 0.98);
  widgetWin.on("moved", snapWidget);                       // edge-snap after a drag
  widgetWin.loadFile(path.join(__dirname, "renderer", "widget.html"));
  widgetWin.on("closed", () => { clearTimeout(widgetIdleTimer); widgetWin = null; });
}

function toggleWidget() {
  if (widgetWin && !widgetWin.isDestroyed()) {
    if (widgetWin.isVisible()) { widgetWin.hide(); return false; }
    widgetWin.show(); if (widgetProfile) sendWidget("widget:data", widgetProfile); return true;
  }
  createWidgetWindow();
  return true;
}

// Bring the main window back from the tray (or recreate it if it was destroyed).
function showMain() {
  if (!win || win.isDestroyed()) { createWindow(); return; }
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

// System-tray icon: keeps the app alive after the window is closed.
function createTray() {
  if (tray) return;
  const img = nativeImage.createFromPath(TRAY_ICON);
  tray = new Tray(img.isEmpty() ? ICON : TRAY_ICON);
  tray.setToolTip("Macropad Studio");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Show Macropad Studio", click: showMain },
    { label: "Toggle Overlay", click: () => toggleWidget() },
    { type: "separator" },
    { label: "Quit", click: () => { app.isQuitting = true; app.quit(); } },
  ]));
  tray.on("click", showMain);
  tray.on("double-click", showMain);
}

// Single instance — a second launch focuses the existing window instead of
// opening another that would fight over the serial port.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => showMain());

  app.whenReady().then(() => {
    // Writable data (settings, templates, backups) must live outside the
    // read-only app bundle once packaged.
    const dataDir = app.isPackaged ? app.getPath("userData") : path.resolve(__dirname, "..");
    const resourceDir = app.isPackaged ? process.resourcesPath : path.resolve(__dirname, "..");
    store.configure({ dataDir, resourceDir });
    backup.configure({ dataDir });
    const boot = store.loadSettings();
    if (boot.auto_switch_enabled) startDetection();
    applyLoginItem(boot.open_at_login);
    createWindow();
    createTray();
    initAutoUpdate();
  });
}

// Closing the window leaves the app alive in the tray; only a real quit tears down.
app.on("before-quit", () => { app.isQuitting = true; if (tray) { tray.destroy(); tray = null; } });
app.on("window-all-closed", () => {
  if (!app.isQuitting) return;            // keep running in the tray
  stopDetection(); link.disconnect(); app.quit();
});

// -- repair a whole profile's actions before upload -------------------------
function sanitizeProfile(p) {
  const out = {
    schema_version: schema.SCHEMA_VERSION,
    profile_name: String(p.profile_name || "Profile"),
    idle_animation: schema.IDLE_ANIMATIONS.includes(p.idle_animation) ? p.idle_animation : "none",
    default_delay: Number.isInteger(p.default_delay) ? p.default_delay : 30,
    keys: [],
  };
  if (Number.isInteger(p.brightness)) out.brightness = Math.max(0, Math.min(255, p.brightness));
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
ipcMain.handle("serial:setBrightness", (_e, b) => link.setBrightness(b));

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
  const liveWidget = widgetWin && !widgetWin.isDestroyed();
  if (s && typeof s.widget_alpha === "number" && liveWidget) {
    widgetWin.setOpacity(Math.max(0.4, Math.min(1, s.widget_alpha)));
  }
  if (s && "widget_stay_on_top" in s && liveWidget) widgetWin.setAlwaysOnTop(!!s.widget_stay_on_top, "screen-saver");
  if (s && "widget_auto_hide" in s && !s.widget_auto_hide) {   // turning it off: cancel the timer + re-show
    clearTimeout(widgetIdleTimer);
    if (liveWidget && !widgetWin.isVisible()) widgetWin.show();
  }
  if (s && "auto_switch_enabled" in s) { s.auto_switch_enabled ? startDetection() : stopDetection(); }
  if (s && "open_at_login" in s) applyLoginItem(s.open_at_login);
  return r;
});

ipcMain.handle("settings:reset", () => {
  const ok = store.factoryReset();
  applyLoginItem(false);
  return { ok };
});

ipcMain.handle("update:get", () => updateState);
ipcMain.handle("update:check", () => {
  if (!app.isPackaged) { sendUpdate({ status: "none" }); return updateState; }
  autoUpdater.checkForUpdates().catch((e) => sendUpdate({ status: "error", error: e.message }));
  return updateState;
});
ipcMain.handle("update:install", () => {
  if (updateState.status === "downloaded") { app.isQuitting = true; autoUpdater.quitAndInstall(); }
  return true;
});

ipcMain.handle("flash:info", () => { const i = firmwareInfo(); return { version: i.version, available: i.available, size: i.size }; });

let flashing = false;
ipcMain.handle("flash:start", async (_e, portPath) => {
  if (flashing) return { ok: false, error: "already flashing" };
  const info = firmwareInfo();
  if (!info.available) return { ok: false, error: "no firmware image bundled" };
  if (!portPath) return { ok: false, error: "no port selected" };
  flashing = true;
  if (link.isOpen()) link.disconnect();              // free the port for esptool-js
  try {
    await flasher.flashFirmware(portPath, info.bin, (p) => send("flash", p));
    return { ok: true };
  } catch (err) {
    send("flash", { phase: "error", code: err.code || null, error: err.message });
    return { ok: false, code: err.code || null, error: err.message };
  } finally { flashing = false; }
});

ipcMain.handle("templates:get", (_e, ctx) => store.getContextShortcuts(ctx));
ipcMain.handle("templates:ranked", (_e, ctx, limit) => store.rankShortcuts(ctx, limit));
ipcMain.handle("templates:add", (_e, ctx, items) => store.addShortcuts(ctx, items));

// Swallow user-cancelled/superseded aborts; surface real failures (incl. timeouts).
const aiErr = (err) => { const m = String((err && err.message) || err); if (!/abort|cancel|supersed/i.test(m)) send("log", `AI error: ${m}\n`); return []; };
ipcMain.handle("ai:generateShortcuts", (_e, opts) => ai.generateShortcuts(store.loadSettings(), opts).catch(aiErr));
ipcMain.handle("ai:generateActions", (_e, desc) => ai.generateActions(store.loadSettings(), desc).catch(aiErr));
ipcMain.handle("ai:test", () => ai.testConnection(store.loadSettings()).then(() => ({ ok: true })).catch((e) => ({ ok: false, error: e.message })));
ipcMain.handle("ai:cancel", () => ai.cancel());

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

// Export all 3 device profiles into a single JSON file.
ipcMain.handle("dialog:exportAll", async () => {
  if (!link.isOpen()) return { ok: false, error: "not connected" };
  const profiles = {};
  for (const slot of [1, 2, 3]) {
    const raw = await link.readFile(`profile${slot}.json`);
    try { profiles[slot] = JSON.parse(stripCatEcho(raw)); } catch (_) {}
  }
  const r = await dialog.showSaveDialog(win, { defaultPath: "macropad-profiles.json", filters: [{ name: "JSON", extensions: ["json"] }] });
  if (r.canceled || !r.filePath) return null;
  try {
    fs.writeFileSync(r.filePath, JSON.stringify({ exported: new Date().toISOString(), profiles }, null, 2));
    return { ok: true, path: r.filePath, count: Object.keys(profiles).length };
  } catch (e) { return { ok: false, error: e.message }; }
});
