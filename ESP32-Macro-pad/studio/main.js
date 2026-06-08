/* Macropad Studio — Electron main process.
 * Owns serial, AI, persistence; the renderer talks to it over IPC. */

"use strict";

const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const fs = require("fs");

const schema = require("./services/schema");
const store = require("./services/store");
const ai = require("./services/ai");
const { SerialLink, stripCatEcho } = require("./services/serial");

const link = new SerialLink();
let win = null;

function send(type, data) { if (win && !win.isDestroyed()) win.webContents.send("serial:event", { type, data }); }

// Forward serial events to the renderer.
link.on("log", (text) => send("log", text));
link.on("fs-info", (info) => send("fs-info", info));
link.on("ready", () => send("ready"));
link.on("open", () => send("open"));
link.on("disconnect", () => send("disconnect"));
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
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { link.disconnect(); app.quit(); });

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
ipcMain.handle("serial:saveProfile", (_e, filename, profile) => link.uploadProfile(filename, sanitizeProfile(profile)));
ipcMain.handle("serial:setKey", (_e, knum, actions) => link.setKey(knum, schema.repairActions(actions)));

ipcMain.handle("settings:get", () => store.loadSettings());
ipcMain.handle("settings:set", (_e, s) => store.saveSettings(s));

ipcMain.handle("templates:get", (_e, ctx) => store.getContextShortcuts(ctx));
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
