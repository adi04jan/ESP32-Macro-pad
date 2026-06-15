/* Generates macropad_default_templates.json — a curated, schema-valid library
 * of common shortcuts per app context. Edit the COMPACT specs below and run:
 *   node tools/gen-shortcuts.js
 * Combo syntax: "Ctrl+Shift+P" (one combo), "Ctrl+K Ctrl+S" (sequence),
 *   "F12" (single key), "run:git status" (type + Enter), "text:foo" (type),
 *   "media:VOLUME_UP" (media key). */
"use strict";
const fs = require("fs");
const path = require("path");
const schema = require("../services/schema");

const OUT = path.resolve(__dirname, "..", "..", "macropad_default_templates.json");

const TOK = {
  ctrl: "LEFT_CTRL", control: "LEFT_CTRL", shift: "LEFT_SHIFT", alt: "LEFT_ALT",
  win: "LEFT_GUI", cmd: "LEFT_GUI", super: "LEFT_GUI", meta: "LEFT_GUI",
  enter: "ENTER", return: "ENTER", esc: "ESC", escape: "ESC", tab: "TAB", space: "SPACE",
  backspace: "BACKSPACE", del: "DELETE", delete: "DELETE", ins: "INSERT", insert: "INSERT",
  home: "HOME", end: "END", pgup: "PAGEUP", pageup: "PAGEUP", pgdn: "PAGEDOWN", pagedown: "PAGEDOWN",
  caps: "CAPS_LOCK", up: "UP_ARROW", down: "DOWN_ARROW", left: "LEFT_ARROW", right: "RIGHT_ARROW",
  "`": "TILDE", "~": "TILDE", "-": "MINUS", "_": "MINUS", "=": "EQUAL", "+": "EQUAL",
  "[": "LEFT_BRACE", "]": "RIGHT_BRACE", "\\": "BACKSLASH", ";": "SEMICOLON", "'": "QUOTE",
  ",": "COMMA", ".": "DOT", "/": "SLASH",
};
function mapTok(t) {
  const low = t.toLowerCase();
  if (TOK[low]) return TOK[low];
  if (TOK[t]) return TOK[t];
  if (/^f([1-9]|1[0-2])$/i.test(t)) return t.toUpperCase();
  if (/^[a-z]$/i.test(t)) return t.toUpperCase();
  if (/^[0-9]$/.test(t)) return t;
  throw new Error("unknown token: " + t);
}
function combo(step) {
  const parts = step.split("+").map(mapTok);
  return parts.length === 1 ? { type: "key", value: parts[0] } : { type: "keycombo", keys: parts };
}
function expand(spec) {
  if (spec.startsWith("run:")) return [{ type: "text", value: spec.slice(4) }, { type: "key", value: "ENTER" }];
  if (spec.startsWith("text:")) return [{ type: "text", value: spec.slice(5) }];
  if (spec.startsWith("media:")) return [{ type: "media", value: spec.slice(6) }];
  if (spec.startsWith("tel:")) return [{ type: "telephony", value: spec.slice(4) }];
  return spec.split(/\s+/).map(combo);
}

// [description, spec]
const LIB = {
  global: [
    ["Copy", "Ctrl+C"], ["Paste", "Ctrl+V"], ["Cut", "Ctrl+X"], ["Undo", "Ctrl+Z"], ["Redo", "Ctrl+Y"],
    ["Select all", "Ctrl+A"], ["Save", "Ctrl+S"], ["Find", "Ctrl+F"], ["Print", "Ctrl+P"],
    ["Switch app", "Alt+Tab"], ["Show desktop", "Win+D"], ["Lock PC", "Win+L"], ["Snip screenshot", "Win+Shift+S"],
    ["File Explorer", "Win+E"], ["Run dialog", "Win+R"], ["Settings", "Win+I"], ["Emoji picker", "Win+."],
    ["Clipboard history", "Win+V"], ["Task view", "Win+Tab"], ["Close window", "Alt+F4"],
    ["Rename", "F2"], ["Refresh", "F5"], ["New folder", "Ctrl+Shift+N"], ["Minimize all", "Win+M"],
    ["Maximize window", "Win+Up"], ["Snap left", "Win+Left"], ["Snap right", "Win+Right"],
    ["Virtual desktop right", "Win+Ctrl+Right"], ["Virtual desktop left", "Win+Ctrl+Left"],
  ],
  media: [
    ["Play / pause", "media:PLAY_PAUSE"], ["Next track", "media:NEXT"], ["Previous track", "media:PREVIOUS"],
    ["Volume up", "media:VOLUME_UP"], ["Volume down", "media:VOLUME_DOWN"], ["Mute", "media:MUTE"],
    ["Stop", "media:STOP"], ["Mute mic", "tel:MIC_MUTE"],
  ],
  chrome: [
    ["New tab", "Ctrl+T"], ["Close tab", "Ctrl+W"], ["Reopen tab", "Ctrl+Shift+T"], ["Next tab", "Ctrl+Tab"],
    ["Previous tab", "Ctrl+Shift+Tab"], ["Address bar", "Ctrl+L"], ["Reload", "Ctrl+R"], ["Hard reload", "Ctrl+Shift+R"],
    ["Find in page", "Ctrl+F"], ["History", "Ctrl+H"], ["Downloads", "Ctrl+J"], ["Bookmark page", "Ctrl+D"],
    ["DevTools", "F12"], ["Incognito window", "Ctrl+Shift+N"], ["Zoom in", "Ctrl+="], ["Zoom out", "Ctrl+-"],
    ["Reset zoom", "Ctrl+0"], ["Fullscreen", "F11"], ["New window", "Ctrl+N"], ["Focus next pane", "F6"],
    ["Save page", "Ctrl+S"], ["Switch to tab 1", "Ctrl+1"], ["Last tab", "Ctrl+9"],
  ],
  vscode: [
    ["Command palette", "Ctrl+Shift+P"], ["Quick open file", "Ctrl+P"], ["Toggle sidebar", "Ctrl+B"],
    ["Toggle terminal", "Ctrl+`"], ["Format document", "Shift+Alt+F"], ["Go to definition", "F12"],
    ["Peek definition", "Alt+F12"], ["Rename symbol", "F2"], ["Toggle comment", "Ctrl+/"], ["Find", "Ctrl+F"],
    ["Replace", "Ctrl+H"], ["Find in files", "Ctrl+Shift+F"], ["Save all", "Ctrl+K Ctrl+S"],
    ["Split editor", "Ctrl+\\"], ["Next editor", "Ctrl+Tab"], ["Go to line", "Ctrl+G"],
    ["Add cursor below", "Ctrl+Alt+Down"], ["Select next match", "Ctrl+D"], ["Move line up", "Alt+Up"],
    ["Move line down", "Alt+Down"], ["Copy line down", "Shift+Alt+Down"], ["Delete line", "Ctrl+Shift+K"],
    ["Toggle word wrap", "Alt+Z"], ["Problems panel", "Ctrl+Shift+M"], ["Source control", "Ctrl+Shift+G"],
    ["Trigger suggest", "Ctrl+Space"], ["Quick fix", "Ctrl+."], ["Fold region", "Ctrl+Shift+["],
  ],
  terminal: [
    ["Git status", "run:git status"], ["Git pull", "run:git pull"], ["Git push", "run:git push"],
    ["Git add all", "run:git add ."], ["Git log oneline", "run:git log --oneline -10"],
    ["npm install", "run:npm install"], ["npm run dev", "run:npm run dev"], ["npm run build", "run:npm run build"],
    ["Clear screen", "run:clear"], ["List files", "run:ls"], ["Up a directory", "run:cd .."],
    ["Kill (Ctrl+C)", "Ctrl+C"], ["New tab", "Ctrl+Shift+T"], ["Split pane", "Alt+Shift+D"],
    ["docker ps", "run:docker ps"], ["Python venv", "run:source .venv/bin/activate"],
  ],
  slack: [
    ["Quick switcher", "Ctrl+K"], ["Jump to channel", "Ctrl+G"], ["Search", "Ctrl+F"], ["Next unread", "Alt+Shift+Down"],
    ["Previous unread", "Alt+Shift+Up"], ["Mark all read", "Shift+Esc"], ["Threads", "Ctrl+Shift+T"],
    ["Direct messages", "Ctrl+Shift+K"], ["Activity", "Ctrl+Shift+A"], ["Edit last message", "Up"],
    ["Toggle sidebar", "Ctrl+Shift+D"], ["Set status", "Ctrl+Shift+Y"], ["Create snippet", "Ctrl+Shift+Enter"],
    ["Upload file", "Ctrl+U"], ["Bold text", "Ctrl+B"], ["Italic text", "Ctrl+I"],
  ],
  discord: [
    ["Quick switcher", "Ctrl+K"], ["Mark read", "Esc"], ["Toggle mute", "Ctrl+Shift+M"], ["Toggle deafen", "Ctrl+Shift+D"],
    ["Next channel", "Alt+Down"], ["Previous channel", "Alt+Up"], ["Search", "Ctrl+F"], ["Pin messages", "Ctrl+P"],
    ["Toggle members", "Ctrl+U"], ["Emoji picker", "Ctrl+E"], ["Upload file", "Ctrl+Shift+U"],
  ],
  figma: [
    ["Move tool", "V"], ["Frame tool", "F"], ["Rectangle", "R"], ["Text", "T"], ["Pen", "P"], ["Comment", "C"],
    ["Components", "Alt+2"], ["Group", "Ctrl+G"], ["Ungroup", "Ctrl+Shift+G"], ["Export", "Ctrl+Shift+E"],
    ["Zoom to fit", "Shift+1"], ["Zoom to selection", "Shift+2"], ["Duplicate", "Ctrl+D"],
    ["Toggle UI", "Ctrl+\\"], ["Outline view", "Ctrl+Shift+O"], ["Mask", "Ctrl+Alt+M"],
  ],
  excel: [
    ["Sum cells", "Alt+="], ["Insert row", "Ctrl+Shift+="], ["Delete row", "Ctrl+-"], ["Fill down", "Ctrl+D"],
    ["Fill right", "Ctrl+R"], ["Format cells", "Ctrl+1"], ["Bold", "Ctrl+B"], ["Filter", "Ctrl+Shift+L"],
    ["Insert chart", "Alt+F1"], ["New sheet", "Shift+F11"], ["Find", "Ctrl+F"], ["Go to", "Ctrl+G"],
    ["Edit cell", "F2"], ["Save", "Ctrl+S"], ["Paste special", "Ctrl+Alt+V"], ["Select column", "Ctrl+Space"],
  ],
  word: [
    ["Bold", "Ctrl+B"], ["Italic", "Ctrl+I"], ["Underline", "Ctrl+U"], ["Save", "Ctrl+S"], ["Find", "Ctrl+F"],
    ["Replace", "Ctrl+H"], ["Heading 1", "Ctrl+Alt+1"], ["Heading 2", "Ctrl+Alt+2"], ["Bullet list", "Ctrl+Shift+L"],
    ["Center", "Ctrl+E"], ["Left align", "Ctrl+L"], ["Print", "Ctrl+P"], ["Word count", "Ctrl+Shift+G"],
    ["Insert hyperlink", "Ctrl+K"], ["Select all", "Ctrl+A"],
  ],
  outlook: [
    ["New mail", "Ctrl+N"], ["Send", "Ctrl+Enter"], ["Reply", "Ctrl+R"], ["Reply all", "Ctrl+Shift+R"],
    ["Forward", "Ctrl+F"], ["Search", "Ctrl+E"], ["Mark read", "Ctrl+Q"], ["Delete", "Del"],
    ["New meeting", "Ctrl+Shift+Q"], ["Flag", "Ctrl+Shift+G"], ["Go to inbox", "Ctrl+Shift+I"], ["Next item", "Ctrl+."],
  ],
  explorer: [
    ["New folder", "Ctrl+Shift+N"], ["Rename", "F2"], ["Copy", "Ctrl+C"], ["Paste", "Ctrl+V"], ["Cut", "Ctrl+X"],
    ["Delete", "Del"], ["Address bar", "Ctrl+L"], ["Search", "Ctrl+F"], ["Up one level", "Alt+Up"],
    ["Back", "Alt+Left"], ["Properties", "Alt+Enter"], ["Select all", "Ctrl+A"], ["New window", "Ctrl+N"],
  ],
  photoshop: [
    ["Move tool", "V"], ["Brush", "B"], ["Marquee", "M"], ["Lasso", "L"], ["Eyedropper", "I"], ["Undo", "Ctrl+Z"],
    ["New layer", "Ctrl+Shift+N"], ["Group layers", "Ctrl+G"], ["Flatten", "Ctrl+Shift+E"], ["Deselect", "Ctrl+D"],
    ["Save", "Ctrl+S"], ["Save as", "Ctrl+Shift+S"], ["Export", "Ctrl+Alt+Shift+S"], ["Fit on screen", "Ctrl+0"],
    ["Free transform", "Ctrl+T"], ["Fill", "Shift+F5"],
  ],
  spotify: [
    ["Play / pause", "media:PLAY_PAUSE"], ["Next track", "media:NEXT"], ["Previous track", "media:PREVIOUS"],
    ["Volume up", "media:VOLUME_UP"], ["Volume down", "media:VOLUME_DOWN"], ["Mute", "media:MUTE"],
    ["Search", "Ctrl+L"], ["Like song", "Alt+Shift+B"], ["Repeat", "Ctrl+R"], ["Shuffle", "Ctrl+S"],
  ],
  notion: [
    ["New page", "Ctrl+N"], ["Search", "Ctrl+P"], ["Bold", "Ctrl+B"], ["Italic", "Ctrl+I"], ["Checkbox", "Ctrl+Shift+1"],
    ["Toggle list", "Ctrl+Shift+7"], ["Heading 1", "Ctrl+Shift+1"], ["Code block", "Ctrl+Shift+9"],
    ["Indent", "Tab"], ["Outdent", "Shift+Tab"], ["Toggle sidebar", "Ctrl+\\"],
  ],
  teams: [
    ["Mute mic", "Ctrl+Shift+M"], ["Toggle video", "Ctrl+Shift+O"], ["Share screen", "Ctrl+Shift+E"],
    ["Raise hand", "Ctrl+Shift+K"], ["New chat", "Ctrl+N"], ["Search", "Ctrl+E"], ["Calls", "Ctrl+5"],
    ["Files", "Ctrl+6"], ["Go to", "Ctrl+G"], ["Leave call", "Ctrl+Shift+H"],
  ],
  zoom: [
    ["Mute / unmute", "Alt+A"], ["Start / stop video", "Alt+V"], ["Share screen", "Alt+S"],
    ["Chat", "Alt+H"], ["Raise hand", "Alt+Y"], ["Record", "Alt+R"], ["Gallery view", "Alt+F2"],
    ["Leave meeting", "Alt+Q"], ["Invite", "Alt+I"], ["Full screen", "Alt+F"],
  ],
};

const out = {};
let total = 0, dropped = 0;
for (const [ctx, items] of Object.entries(LIB)) {
  const list = [];
  for (const [description, spec] of items) {
    let actions;
    try { actions = schema.repairActions(expand(spec)); }
    catch (e) { console.warn(`DROP [${ctx}] "${description}" (${spec}): ${e.message}`); dropped++; continue; }
    if (!actions.length || !schema.isValidActions(actions)) { console.warn(`INVALID [${ctx}] "${description}" (${spec})`); dropped++; continue; }
    list.push({ description, actions });
    total++;
  }
  out[ctx] = list;
}
fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
console.log(`Wrote ${total} shortcuts across ${Object.keys(out).length} contexts (${dropped} dropped) -> ${OUT}`);
