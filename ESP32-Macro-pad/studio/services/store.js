/* File-backed persistence: settings + per-context templates.
 * Reads/writes the same JSON files the Python tooling uses, so the two stay
 * interchangeable. Templates are schema-validated + deduped on load/add. */

"use strict";

const fs = require("fs");
const path = require("path");
const schema = require("./schema");

// Writable data dir + read-only resource dir. In dev both default to the
// project root (so the JSON files stay shared with the Python tooling); in a
// packaged app main.js points DATA_DIR at userData and RES_DIR at resources.
let DATA_DIR = path.resolve(__dirname, "..", "..");
let RES_DIR = DATA_DIR;
function configure(opts = {}) {
  if (opts.dataDir) { DATA_DIR = opts.dataDir; try { fs.mkdirSync(DATA_DIR, { recursive: true }); } catch (_) {} }
  if (opts.resourceDir) RES_DIR = opts.resourceDir;
  _custom = null; _default = null; _usage = null;   // paths may have changed; drop caches
}
const settingsFile = () => path.join(DATA_DIR, "macropad_settings.json");
const customFile = () => path.join(DATA_DIR, "macropad_templates.json");
const defaultFile = () => path.join(RES_DIR, "macropad_default_templates.json");
const usageFile = () => path.join(DATA_DIR, "macropad_usage.json");

const DEFAULT_SETTINGS = {
  provider: "Ollama (Local)",
  endpoint: "http://localhost:11434",
  key: "",
  model: "llama3",
  widget_alpha: 0.98,
  widget_stay_on_top: true,
  widget_snap: true,
  widget_auto_hide: false,
  auto_switch_enabled: false,
  auto_connect: true,
  auto_assign: false,
  confirm_destructive: true,
  open_at_login: false,
};

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (_) { return fallback; }
}
function writeJson(file, obj) {
  try { fs.writeFileSync(file, JSON.stringify(obj, null, 2)); return true; }
  catch (e) { console.error("write failed", file, e.message); return false; }
}

// -- settings ---------------------------------------------------------------
function loadSettings() {
  const raw = readJson(settingsFile(), {});
  const out = { ...DEFAULT_SETTINGS };
  // Accept the configurator's keys too (ai_provider/ai_endpoint/...).
  const map = { ai_provider: "provider", ai_endpoint: "endpoint", ai_key: "key", ai_model: "model" };
  for (const [k, v] of Object.entries(raw)) {
    const key = map[k] || k;
    if (key in out && typeof v === typeof out[key]) out[key] = v;
  }
  return out;
}
function saveSettings(settings) {
  const cur = readJson(settingsFile(), {});
  const merged = { ...cur, ...settings };
  // Mirror into the configurator's key names so both UIs share config.
  merged.ai_provider = settings.provider ?? merged.ai_provider;
  merged.ai_endpoint = settings.endpoint ?? merged.ai_endpoint;
  merged.ai_key = settings.key ?? merged.ai_key;
  merged.ai_model = settings.model ?? merged.ai_model;
  return writeJson(settingsFile(), merged);
}

// Wipe user customization: settings -> defaults, drop templates + usage stats.
// The shipped default templates (resource dir) are untouched.
function factoryReset() {
  const ok = writeJson(settingsFile(), { ...DEFAULT_SETTINGS });
  writeJson(customFile(), {});
  try { fs.unlinkSync(usageFile()); } catch (_) {}
  _custom = null; _usage = null;   // drop caches so the next read reflects the wipe
  return ok;
}

// -- templates --------------------------------------------------------------
function _normSig(actions) { return JSON.stringify(schema.repairActions(actions)); }

function _loadTemplateFile(file) {
  const data = readJson(file, {});
  if (!data || typeof data !== "object") return {};
  const out = {};
  for (const [ctx, items] of Object.entries(data)) {
    if (!Array.isArray(items)) continue;
    const good = [];
    for (const s of items) {
      if (!s || typeof s !== "object") continue;
      const actions = schema.repairActions(s.actions || []);
      if (actions.length && schema.isValidActions(actions)) {
        const e = { description: s.description || "Macro", actions };
        if ("key_num" in s) e.key_num = s.key_num;
        good.push(e);
      }
    }
    if (good.length) out[ctx.toLowerCase()] = good;
  }
  return out;
}

let _custom = null, _default = null;
function _ensureLoaded() {
  if (_custom === null) _custom = _loadTemplateFile(customFile());
  if (_default === null) _default = _loadTemplateFile(defaultFile());
}

function getContextShortcuts(context) {
  _ensureLoaded();
  const ctx = String(context).toLowerCase();
  const out = [], seenDesc = new Set(), seenSig = new Set();
  const add = (items) => {
    for (const s of items || []) {
      const d = (s.description || "").toLowerCase(), sig = _normSig(s.actions);
      if (seenDesc.has(d) || seenSig.has(sig)) continue;
      seenDesc.add(d); seenSig.add(sig); out.push(s);
    }
  };
  add(_custom[ctx]); add(_default[ctx]);
  if (!out.length) {
    for (const src of [_custom, _default])
      for (const key of Object.keys(src))
        if (key.includes(ctx) || ctx.includes(key)) { add(src[key]); break; }
  }
  return out;
}

function addShortcuts(context, newShortcuts) {
  _ensureLoaded();
  const ctx = String(context).toLowerCase();
  if (!_custom[ctx]) _custom[ctx] = [];
  const existing = getContextShortcuts(ctx);
  const seenDesc = new Set(existing.map((s) => (s.description || "").toLowerCase()));
  const seenSig = new Set(existing.map((s) => _normSig(s.actions)));
  let added = 0;
  for (const s of newShortcuts) {
    const actions = schema.repairActions(s.actions || []);
    if (!actions.length || !schema.isValidActions(actions)) continue;
    const desc = s.description || "Macro", sig = _normSig(actions);
    if (seenDesc.has(desc.toLowerCase()) || seenSig.has(sig)) continue;
    const e = { description: desc, actions };
    if ("key_num" in s) e.key_num = s.key_num;
    _custom[ctx].push(e); seenDesc.add(desc.toLowerCase()); seenSig.add(sig); added++;
  }
  if (added) writeJson(customFile(), _custom);
  return added;
}

// -- usage tracking + ranking ----------------------------------------------
let _usage = null;
function loadUsage() { if (_usage === null) _usage = readJson(usageFile(), {}); return _usage; }
function signature(actions) { return _normSig(actions); }

// Record one use of a macro (by signature) in a context — driven by key presses.
function recordUsage(context, sig) {
  if (!context || !sig) return;
  const u = loadUsage();
  const ctx = String(context).toLowerCase();
  u[ctx] = u[ctx] || {};
  const e = u[ctx][sig] || { count: 0, last: 0 };
  e.count += 1; e.last = Date.now();
  u[ctx][sig] = e;
  writeJson(usageFile(), u);
}

// The context's library, ranked by usage (most-used first), with key_num + use
// count attached. `bottomN` flags the least-used entries as refresh candidates.
function rankShortcuts(context, limit = 8) {
  const list = getContextShortcuts(context);
  const u = loadUsage()[String(context).toLowerCase()] || {};
  const scored = list.map((s) => {
    const e = u[_normSig(s.actions)] || { count: 0, last: 0 };
    return { s, count: e.count, last: e.last };
  });
  scored.sort((a, b) => (b.count - a.count) || (b.last - a.last));
  return scored.slice(0, limit).map((x, i) => ({ ...x.s, key_num: (i % 4) + 1, uses: x.count }));
}

module.exports = { configure, loadSettings, saveSettings, factoryReset, getContextShortcuts, addShortcuts,
  recordUsage, rankShortcuts, signature, readJson, writeJson };
