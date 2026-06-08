/* Canonical macro-action schema (JS port of configurator/schema.py).
 *
 * Single source of truth on the Electron side: enums, validation, and
 * best-effort repair. Kept in lockstep with the Python schema and the firmware
 * tables so a macro that validates here is executable on the device. */

"use strict";

const SCHEMA_VERSION = 1;
const MAX_TEXT_LEN = 4096;
const MAX_REPEAT_COUNT = 50;
const NUM_PROFILES = 3;
const AXIS_MIN = -127, AXIS_MAX = 127;

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const DIGITS = "0123456789".split("");
const FN = Array.from({ length: 12 }, (_, i) => `F${i + 1}`);
const NAMED = [
  "ENTER", "ESC", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUAL",
  "LEFT_BRACE", "RIGHT_BRACE", "BACKSLASH", "SEMICOLON", "QUOTE", "TILDE",
  "COMMA", "DOT", "SLASH", "CAPS_LOCK", "INSERT", "HOME", "PAGEUP",
  "DELETE", "END", "PAGEDOWN", "RIGHT_ARROW", "LEFT_ARROW", "DOWN_ARROW", "UP_ARROW",
];
const KEY_NAMES = [...LETTERS, ...DIGITS, ...FN, ...NAMED];
const MODIFIER_NAMES = [
  "LEFT_CTRL", "LEFT_SHIFT", "LEFT_ALT", "LEFT_GUI",
  "RIGHT_CTRL", "RIGHT_SHIFT", "RIGHT_ALT", "RIGHT_GUI",
];
const KEY_AND_MODIFIER = [...MODIFIER_NAMES, ...KEY_NAMES];
const MEDIA_NAMES = ["PLAY_PAUSE", "STOP", "NEXT", "PREVIOUS", "MUTE", "VOLUME_UP", "VOLUME_DOWN"];
const TELEPHONY_NAMES = ["MIC_MUTE", "ANSWER", "DECLINE"];
const MOUSE_BUTTONS = ["LEFT", "RIGHT", "MIDDLE"];
const LED_ANIM_VALUES = ["flash", "breathe"];
const IDLE_ANIMATIONS = ["none", "breathe", "rainbow", "flash"];
const ACTION_TYPES = [
  "comment", "delay", "key", "keycombo", "text", "multiline", "hold", "release",
  "repeat", "media", "mouse_move", "mouse_click", "led", "led_anim", "profile", "telephony",
];

const KEY_SET = new Set(KEY_NAMES);
const KEY_AND_MOD_SET = new Set(KEY_AND_MODIFIER);
const MEDIA_SET = new Set(MEDIA_NAMES);
const TEL_SET = new Set(TELEPHONY_NAMES);
const BTN_SET = new Set(MOUSE_BUTTONS);
const LED_ANIM_SET = new Set(LED_ANIM_VALUES);
const TYPE_SET = new Set(ACTION_TYPES);

const ALIASES = {
  CTRL: "LEFT_CTRL", CONTROL: "LEFT_CTRL",
  SHIFT: "LEFT_SHIFT", ALT: "LEFT_ALT", OPTION: "LEFT_ALT",
  GUI: "LEFT_GUI", WIN: "LEFT_GUI", WINDOWS: "LEFT_GUI",
  LEFT_WIN: "LEFT_GUI", RIGHT_WIN: "RIGHT_GUI",
  LEFT_WINDOWS: "LEFT_GUI", RIGHT_WINDOWS: "RIGHT_GUI",
  CMD: "LEFT_GUI", COMMAND: "LEFT_GUI", LEFT_COMMAND: "LEFT_GUI",
  SUPER: "LEFT_GUI", META: "LEFT_GUI",
  RETURN: "ENTER", ESCAPE: "ESC", DEL: "DELETE",
  PGUP: "PAGEUP", PGDN: "PAGEDOWN", PAGE_UP: "PAGEUP", PAGE_DOWN: "PAGEDOWN",
  SPACEBAR: "SPACE", BKSP: "BACKSPACE", PERIOD: "DOT", FULLSTOP: "DOT",
  UP: "UP_ARROW", DOWN: "DOWN_ARROW", LEFT: "LEFT_ARROW", RIGHT: "RIGHT_ARROW",
  ARROWUP: "UP_ARROW", ARROWDOWN: "DOWN_ARROW", ARROWLEFT: "LEFT_ARROW", ARROWRIGHT: "RIGHT_ARROW",
};
const TYPE_ALIASES = {
  keypress: "key", press: "key", string: "text", combo: "keycombo",
  key_combo: "keycombo", shortcut: "keycombo", wait: "delay", sleep: "delay",
  pause: "delay", mousemove: "mouse_move", mouseclick: "mouse_click",
  click: "mouse_click", ledanim: "led_anim", animation: "led_anim",
};

// ---------------------------------------------------------------------------
const clampInt = (v, lo, hi, dflt = 0) => {
  let n = typeof v === "number" ? v : parseInt(v, 10);
  if (!Number.isFinite(n)) n = dflt;
  return Math.max(lo, Math.min(hi, Math.round(n)));
};
const toInt = (v, dflt = 0) => {
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? Math.round(n) : dflt;
};

function normKey(token) {
  if (typeof token !== "string") return null;
  const s = token.trim();
  if (!s) return null;
  let up = s.toUpperCase();
  if (ALIASES[up]) up = ALIASES[up];
  if (KEY_AND_MOD_SET.has(up)) return up;
  if (s.length === 1) return s; // arbitrary printable char, preserve case
  return null;
}

// ---- validation: returns array of error strings (empty = valid) -----------
function validateAction(a, path = "") {
  const e = [];
  const p = path ? path + ": " : "";
  if (a === null || typeof a !== "object" || Array.isArray(a)) return [`${p}not an object`];
  const t = a.type;
  if (!TYPE_SET.has(t)) return [`${p}unknown type '${t}'`];

  const reqStr = (k, set) => {
    const v = a[k];
    if (typeof v !== "string") { e.push(`${p}${k} must be a string`); return; }
    if (set && !set.has(v)) e.push(`${p}${k} '${v}' not allowed`);
  };
  const keyish = (v, set, k) => {
    if (typeof v !== "string" || (!set.has(v) && v.length !== 1))
      e.push(`${p}${k} '${v}' is not a valid key`);
  };

  switch (t) {
    case "comment": break;
    case "delay":
      if (!Number.isInteger(a.ms) || a.ms < 0) e.push(`${p}ms must be a non-negative integer`);
      break;
    case "key": keyish(a.value, KEY_SET, "value"); break;
    case "keycombo":
      if (!Array.isArray(a.keys) || a.keys.length === 0) e.push(`${p}keys must be a non-empty array`);
      else a.keys.forEach((k) => keyish(k, KEY_AND_MOD_SET, "keys[]"));
      break;
    case "text": case "multiline":
      if (typeof a.value !== "string") e.push(`${p}value must be a string`);
      else if (a.value.length > MAX_TEXT_LEN) e.push(`${p}value too long`);
      break;
    case "hold": keyish(a.key, KEY_AND_MOD_SET, "key"); break;
    case "release": break;
    case "repeat":
      if (!Number.isInteger(a.count) || a.count < 1 || a.count > MAX_REPEAT_COUNT)
        e.push(`${p}count must be 1..${MAX_REPEAT_COUNT}`);
      if (!Array.isArray(a.actions)) e.push(`${p}actions must be an array`);
      else a.actions.forEach((x, i) => e.push(...validateAction(x, `${path}actions[${i}]`)));
      break;
    case "media": reqStr("value", MEDIA_SET); break;
    case "mouse_move":
      for (const k of ["x", "y"]) if (!Number.isInteger(a[k]) || a[k] < AXIS_MIN || a[k] > AXIS_MAX) e.push(`${p}${k} out of range`);
      if (a.wheel !== undefined && (!Number.isInteger(a.wheel) || a.wheel < AXIS_MIN || a.wheel > AXIS_MAX)) e.push(`${p}wheel out of range`);
      break;
    case "mouse_click": reqStr("button", BTN_SET); break;
    case "led":
      if (!Array.isArray(a.color) || a.color.length !== 3 || a.color.some((c) => !Number.isInteger(c) || c < 0 || c > 255))
        e.push(`${p}color must be [r,g,b] 0..255`);
      break;
    case "led_anim":
      reqStr("value", LED_ANIM_SET);
      if (a.color !== undefined && (!Array.isArray(a.color) || a.color.length !== 3)) e.push(`${p}color must be [r,g,b]`);
      break;
    case "profile":
      if (!Number.isInteger(a.value) || a.value < 1 || a.value > NUM_PROFILES) e.push(`${p}value must be 1..${NUM_PROFILES}`);
      break;
    case "telephony": reqStr("value", TEL_SET); break;
  }
  return e;
}

function validateActions(actions) {
  if (!Array.isArray(actions)) return { ok: false, errors: ["actions is not an array"] };
  const errors = [];
  actions.forEach((a, i) => errors.push(...validateAction(a, `[${i}]`)));
  return { ok: errors.length === 0, errors };
}
const isValidActions = (actions) => validateActions(actions).ok;

// ---- repair: best-effort normalization, drops the unfixable ---------------
function repairAction(a) {
  if (a === null || typeof a !== "object" || Array.isArray(a)) return null;
  let t = String(a.type || "").trim().toLowerCase();
  t = TYPE_ALIASES[t] || t;
  if (!TYPE_SET.has(t)) return null;

  switch (t) {
    case "comment": {
      const o = { type: t };
      if ("value" in a) o.value = String(a.value ?? "");
      return o;
    }
    case "delay": return { type: t, ms: Math.max(0, toInt(a.ms, 0)) };
    case "key": {
      const k = normKey(a.value);
      return k && (KEY_SET.has(k) || k.length === 1) ? { type: t, value: k } : null;
    }
    case "keycombo": {
      if (!Array.isArray(a.keys)) return null;
      const keys = a.keys.map(normKey).filter(Boolean);
      return keys.length ? { type: t, keys } : null;
    }
    case "text": case "multiline":
      return { type: t, value: String(a.value ?? "").slice(0, MAX_TEXT_LEN) };
    case "hold": {
      const k = normKey(a.key ?? a.value);
      return k ? { type: t, key: k } : null;
    }
    case "release": return { type: t };
    case "repeat": {
      const inner = repairActions(a.actions || []);
      if (!inner.length) return null;
      return { type: t, count: clampInt(a.count, 1, MAX_REPEAT_COUNT, 1), actions: inner };
    }
    case "media": {
      const v = String(a.value ?? "").trim().toUpperCase();
      return MEDIA_SET.has(v) ? { type: t, value: v } : null;
    }
    case "mouse_move": {
      const o = { type: t, x: clampInt(a.x, AXIS_MIN, AXIS_MAX), y: clampInt(a.y, AXIS_MIN, AXIS_MAX) };
      if ("wheel" in a) o.wheel = clampInt(a.wheel, AXIS_MIN, AXIS_MAX);
      return o;
    }
    case "mouse_click": {
      const b = String(a.button ?? "").trim().toUpperCase();
      return BTN_SET.has(b) ? { type: t, button: b } : null;
    }
    case "led": {
      if (!Array.isArray(a.color) || a.color.length !== 3) return null;
      return { type: t, color: a.color.map((c) => clampInt(c, 0, 255)) };
    }
    case "led_anim": {
      const v = String(a.value ?? "").trim().toLowerCase();
      if (!LED_ANIM_SET.has(v)) return null;
      const o = { type: t, value: v };
      if (Array.isArray(a.color) && a.color.length === 3) o.color = a.color.map((c) => clampInt(c, 0, 255));
      return o;
    }
    case "profile": return { type: t, value: clampInt(a.value, 1, NUM_PROFILES, 1) };
    case "telephony": {
      const v = String(a.value ?? "").trim().toUpperCase();
      return TEL_SET.has(v) ? { type: t, value: v } : null;
    }
    default: return null;
  }
}

function repairActions(actions) {
  if (!Array.isArray(actions)) return [];
  return actions.map(repairAction).filter((x) => x !== null);
}

function repairShortcuts(items) {
  if (!Array.isArray(items)) return [];
  const out = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const actions = repairActions(item.actions || []);
    if (!actions.length) continue;
    const fixed = { description: String(item.description || "").trim() || "Macro", actions };
    const kn = toInt(item.key_num, 0);
    if (kn >= 1 && kn <= 12) fixed.key_num = kn;
    out.push(fixed);
  }
  return out;
}

module.exports = {
  SCHEMA_VERSION, MAX_TEXT_LEN, MAX_REPEAT_COUNT, NUM_PROFILES,
  KEY_NAMES, MODIFIER_NAMES, KEY_AND_MODIFIER, MEDIA_NAMES, TELEPHONY_NAMES,
  MOUSE_BUTTONS, LED_ANIM_VALUES, IDLE_ANIMATIONS, ACTION_TYPES, ALIASES,
  normKey, validateAction, validateActions, isValidActions,
  repairAction, repairActions, repairShortcuts,
};
