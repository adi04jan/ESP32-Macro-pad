/* AI macro generation (Node port of configurator/ai/*).
 * Local-first: Ollama with native JSON output; OpenAI/Gemini optional.
 * All output is validated + repaired against the canonical schema in code. */

"use strict";

const schema = require("../schema");

const TIMEOUT_MS = 120000;

// ---- prompts (built from the schema so they never drift) ------------------
const FEW_SHOT = [
  { key_num: 1, description: "Save file", actions: [{ type: "keycombo", keys: ["LEFT_CTRL", "S"] }] },
  { key_num: 2, description: "Run git status", actions: [{ type: "text", value: "git status" }, { type: "key", value: "ENTER" }] },
  { key_num: 3, description: "Open Run dialog and launch notepad",
    actions: [{ type: "keycombo", keys: ["LEFT_GUI", "R"] }, { type: "delay", ms: 300 }, { type: "text", value: "notepad" }, { type: "key", value: "ENTER" }] },
  { key_num: 4, description: "Mute microphone", actions: [{ type: "telephony", value: "MIC_MUTE" }] },
];

function actionCatalog() {
  return [
    'delay         -> {"type":"delay","ms":<int>=0>}',
    'key           -> {"type":"key","value":"<KEY>"}',
    'keycombo      -> {"type":"keycombo","keys":["<MOD/KEY>",...]}',
    'text          -> {"type":"text","value":"types literally"}',
    'hold/release  -> {"type":"hold","key":"<MOD/KEY>"} / {"type":"release"}',
    `repeat        -> {"type":"repeat","count":<1-${schema.MAX_REPEAT_COUNT}>,"actions":[...]}`,
    'media         -> {"type":"media","value":"<MEDIA>"}',
    'mouse_move    -> {"type":"mouse_move","x":-127..127,"y":-127..127}',
    'mouse_click   -> {"type":"mouse_click","button":"LEFT|RIGHT|MIDDLE"}',
    'led/led_anim  -> {"type":"led","color":[r,g,b]} / {"type":"led_anim","value":"flash|breathe"}',
    `profile       -> {"type":"profile","value":<1-${schema.NUM_PROFILES}>}`,
    'telephony     -> {"type":"telephony","value":"<TELEPHONY>"}',
  ].join("\n");
}
function enumRef() {
  return [
    `MODIFIERS: ${schema.MODIFIER_NAMES.join(", ")}`,
    `KEYS: ${schema.KEY_NAMES.join(", ")}`,
    `MEDIA: ${schema.MEDIA_NAMES.join(", ")}`,
    `TELEPHONY: ${schema.TELEPHONY_NAMES.join(", ")}`,
    `MOUSE: ${schema.MOUSE_BUTTONS.join(", ")}`,
  ].join("\n");
}
const RULES =
  "You generate macros for an ESP32 macropad.\n" +
  "- Respond with ONLY a raw JSON array. No prose, no markdown fences.\n" +
  "- Use ONLY the action types and key names listed; anything else is rejected.\n" +
  "- Key names are case-sensitive and exact (LEFT_CTRL, not Ctrl).\n";

function systemShortcuts() {
  return RULES + "\nACTION TYPES:\n" + actionCatalog() + "\n\nALLOWED NAMES:\n" + enumRef() +
    '\n\nEach item MUST be: {"key_num":<1-12>,"description":"<short>","actions":[<action>,...]}' +
    "\n\nEXAMPLES:\n" + JSON.stringify(FEW_SHOT, null, 2);
}
function userShortcuts(context, existing, count, keyNums) {
  let p = `Context: ${context}.\nGenerate ${count} new, unique, genuinely useful keyboard shortcuts for this context.`;
  if (existing && existing.length) p += "\nYou already have these (do NOT duplicate; build on this style):\n" + JSON.stringify(existing, null, 2);
  if (keyNums) p += `\nAssign them to these key_num values: ${keyNums}.`;
  return p;
}
function systemActions() {
  return RULES + "\nACTION TYPES:\n" + actionCatalog() + "\n\nALLOWED NAMES:\n" + enumRef() +
    "\n\nRespond with ONLY a JSON array of action objects.\n\nEXAMPLE:\n" + JSON.stringify(FEW_SHOT[2].actions, null, 2);
}

// ---- lenient parse --------------------------------------------------------
function parseLenient(text) {
  if (text == null) return null;
  if (typeof text !== "string") return text;
  let s = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  try { return JSON.parse(s); } catch (_) {}
  const span = firstJsonSpan(s);
  if (span) { try { return JSON.parse(span); } catch (_) {} }
  return null;
}
function firstJsonSpan(text) {
  let start = -1, opener;
  for (let i = 0; i < text.length; i++) { if (text[i] === "[" || text[i] === "{") { start = i; opener = text[i]; break; } }
  if (start < 0) return null;
  const closer = opener === "[" ? "]" : "}";
  let depth = 0, inStr = false, esc = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (inStr) { if (esc) esc = false; else if (c === "\\") esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true;
    else if (c === opener) depth++;
    else if (c === closer) { depth--; if (depth === 0) return text.slice(start, i + 1); }
  }
  return null;
}

function partitionShortcuts(items) {
  const list = Array.isArray(items) ? items : (items ? [items] : []);
  const valid = [], invalid = [];
  for (const item of list) {
    const repaired = schema.repairShortcuts([item]);
    if (!repaired.length) { invalid.push({ item, errors: ["no recoverable actions"] }); continue; }
    const cand = repaired[0];
    const { ok, errors } = validateShortcut(cand);
    if (ok) valid.push(cand); else invalid.push({ item: cand, errors });
  }
  return { valid, invalid };
}
function validateShortcut(s) {
  if (!s || typeof s !== "object") return { ok: false, errors: ["not an object"] };
  if (!s.description) return { ok: false, errors: ["missing description"] };
  return schema.validateActions(s.actions || []);
}

// ---- providers ------------------------------------------------------------
async function callProvider(settings, system, user, jsonSchema) {
  const provider = settings.provider || "Ollama (Local)";
  const ctrl = AbortSignal.timeout ? AbortSignal.timeout(TIMEOUT_MS) : undefined;
  if (provider.includes("OpenAI")) {
    const r = await fetch(`${(settings.endpoint || "https://api.openai.com/v1").replace(/\/$/, "")}/chat/completions`, {
      method: "POST", signal: ctrl,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${settings.key}` },
      body: JSON.stringify({ model: settings.model || "gpt-4o-mini",
        messages: [{ role: "system", content: system }, { role: "user", content: user }],
        response_format: { type: "json_object" } }),
    });
    if (!r.ok) throw new Error(`OpenAI HTTP ${r.status}`);
    return (await r.json()).choices[0].message.content;
  }
  if (provider.includes("Gemini")) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${settings.model || "gemini-1.5-flash"}:generateContent?key=${settings.key}`;
    const r = await fetch(url, { method: "POST", signal: ctrl, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_instruction: { parts: [{ text: system }] }, contents: [{ parts: [{ text: user }] }],
        generationConfig: { responseMimeType: "application/json" } }) });
    if (!r.ok) throw new Error(`Gemini HTTP ${r.status}`);
    return (await r.json()).candidates[0].content.parts[0].text;
  }
  // Ollama (default)
  const base = (settings.endpoint || settings.key || "http://localhost:11434").replace(/\/$/, "");
  const body = { model: settings.model || "llama3", prompt: `${system}\n\n${user}`, stream: false };
  if (jsonSchema) body.format = jsonSchema;
  let r = await fetch(`${base}/api/generate`, { method: "POST", signal: ctrl, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok && jsonSchema) { body.format = "json"; r = await fetch(`${base}/api/generate`, { method: "POST", signal: ctrl, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  if (!r.ok) throw new Error(`Ollama HTTP ${r.status}`);
  return (await r.json()).response || "";
}

// ---- public generators ----------------------------------------------------
async function generateShortcuts(settings, { context, existing = [], count = 4, keyNums = null } = {}) {
  const raw = await callProvider(settings, systemShortcuts(), userShortcuts(context, existing, count, keyNums), null);
  let { valid, invalid } = partitionShortcuts(parseLenient(raw));
  if (invalid.length) {
    const errs = [...new Set(invalid.flatMap((x) => x.errors))];
    const repairUser = "Fix these validation errors and return ONLY the corrected JSON array.\nERRORS:\n" +
      errs.map((e) => "- " + e).join("\n") + "\n\nJSON:\n" + JSON.stringify(invalid.map((x) => x.item), null, 2);
    try {
      const raw2 = await callProvider(settings, systemShortcuts(), repairUser, null);
      valid = valid.concat(partitionShortcuts(parseLenient(raw2)).valid);
    } catch (_) {}
  }
  // dedupe by description
  const seen = new Set(); const out = [];
  for (const s of valid) { const k = (s.description || "").toLowerCase(); if (k && !seen.has(k)) { seen.add(k); out.push(s); } }
  return out;
}

async function generateActions(settings, description) {
  const raw = await callProvider(settings, systemActions(), `Build a macro that does the following:\n${description}`, null);
  const parsed = parseLenient(raw);
  const actions = schema.repairActions(Array.isArray(parsed) ? parsed : (parsed && parsed.actions) || []);
  return actions.length && schema.isValidActions(actions) ? actions : [];
}

async function testConnection(settings) {
  await callProvider(settings, "Reply with the single word OK.", "ping", null);
  return true;
}

module.exports = { generateShortcuts, generateActions, testConnection, parseLenient, partitionShortcuts };
