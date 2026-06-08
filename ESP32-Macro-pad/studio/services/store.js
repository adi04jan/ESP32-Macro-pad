/* File-backed persistence: settings + per-context templates.
 * Reads/writes the same JSON files the Python tooling uses, so the two stay
 * interchangeable. Templates are schema-validated + deduped on load/add. */

"use strict";

const fs = require("fs");
const path = require("path");
const schema = require("./schema");

// Project root (where the shared JSON files live): studio/services -> ../..
const ROOT = path.resolve(__dirname, "..", "..");
const SETTINGS_FILE = path.join(ROOT, "macropad_settings.json");
const CUSTOM_FILE = path.join(ROOT, "macropad_templates.json");
const DEFAULT_FILE = path.join(ROOT, "macropad_default_templates.json");

const DEFAULT_SETTINGS = {
  provider: "Ollama (Local)",
  endpoint: "http://localhost:11434",
  key: "",
  model: "llama3",
  widget_alpha: 0.98,
  auto_switch_enabled: false,
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
  const raw = readJson(SETTINGS_FILE, {});
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
  const cur = readJson(SETTINGS_FILE, {});
  const merged = { ...cur, ...settings };
  // Mirror into the configurator's key names so both UIs share config.
  merged.ai_provider = settings.provider ?? merged.ai_provider;
  merged.ai_endpoint = settings.endpoint ?? merged.ai_endpoint;
  merged.ai_key = settings.key ?? merged.ai_key;
  merged.ai_model = settings.model ?? merged.ai_model;
  return writeJson(SETTINGS_FILE, merged);
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
  if (_custom === null) _custom = _loadTemplateFile(CUSTOM_FILE);
  if (_default === null) _default = _loadTemplateFile(DEFAULT_FILE);
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
  if (added) writeJson(CUSTOM_FILE, _custom);
  return added;
}

module.exports = { loadSettings, saveSettings, getContextShortcuts, addShortcuts, readJson, writeJson, ROOT };
