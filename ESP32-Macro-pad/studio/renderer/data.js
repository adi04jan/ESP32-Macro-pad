/* ============================================================
   MACROPAD STUDIO — data + metadata
   ============================================================ */
(function () {
  // Action type metadata. color = oklch-ish swatch for the action's icon tile.
  const ACTION_META = {
    text:        { label: "Type Text",      cat: "Keyboard", icon: "ph-text-aa",            color: "#5b8cff", desc: "Type a string of characters" },
    keycombo:    { label: "Key Combo",      cat: "Keyboard", icon: "ph-command",            color: "#ff8a4c", desc: "Press several keys at once" },
    key:         { label: "Tap Key",        cat: "Keyboard", icon: "ph-keyboard",           color: "#7c9cff", desc: "Press and release one key" },
    hold:        { label: "Hold Key",       cat: "Keyboard", icon: "ph-arrow-fat-line-down",color: "#9b8cff", desc: "Press and keep holding" },
    release:     { label: "Release Key",    cat: "Keyboard", icon: "ph-arrow-fat-line-up",  color: "#9b8cff", desc: "Release a held key" },
    delay:       { label: "Delay",          cat: "Timing",   icon: "ph-timer",              color: "#c0c0c8", desc: "Wait a number of milliseconds" },
    mouse_click: { label: "Mouse Click",    cat: "Mouse",    icon: "ph-cursor-click",       color: "#2fe6a8", desc: "Click a mouse button" },
    mouse_move:  { label: "Mouse Move",     cat: "Mouse",    icon: "ph-arrows-out-cardinal",color: "#2fe6a8", desc: "Move the cursor by x / y" },
    media:       { label: "Media",          cat: "System",   icon: "ph-speaker-high",       color: "#36c6ff", desc: "Media & volume controls" },
    telephony:   { label: "Telephony",      cat: "System",   icon: "ph-phone-call",         color: "#36c6ff", desc: "Mute mic, answer, decline" },
    profile:     { label: "Switch Profile", cat: "System",   icon: "ph-stack",              color: "#ffb648", desc: "Jump to another profile" },
    led:         { label: "LED Color",      cat: "Lighting", icon: "ph-lightbulb-filament", color: "#ff6ec7", desc: "Set a static RGB color" },
    led_anim:    { label: "LED Animation",  cat: "Lighting", icon: "ph-sparkle",            color: "#c06bff", desc: "Animate the key lighting" },
  };

  const CATS = ["Keyboard", "Mouse", "Timing", "System", "Lighting"];

  const KEYS = [
    "A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z",
    "1","2","3","4","5","6","7","8","9","0",
    "ENTER","ESC","BACKSPACE","TAB","SPACE","MINUS","EQUAL","DELETE","INSERT","HOME","END","PAGEUP","PAGEDOWN",
    "LEFT_CTRL","LEFT_SHIFT","LEFT_ALT","LEFT_GUI","RIGHT_CTRL","RIGHT_SHIFT","RIGHT_ALT","RIGHT_GUI",
    "UP_ARROW","DOWN_ARROW","LEFT_ARROW","RIGHT_ARROW",
    "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"
  ];

  const ENUMS = {
    media:       ["PLAY_PAUSE","STOP","NEXT","PREVIOUS","MUTE","VOLUME_UP","VOLUME_DOWN"],
    mouse_click: ["LEFT","RIGHT","MIDDLE"],
    profile:     ["1","2","3"],
    telephony:   ["MIC_MUTE","ANSWER","DECLINE"],
    led_anim:    ["flash","breathe","rainbow","none"],
  };

  // Pretty key glyph
  const KEY_GLYPH = {
    LEFT_CTRL: "Ctrl", RIGHT_CTRL: "Ctrl", LEFT_SHIFT: "Shift", RIGHT_SHIFT: "Shift",
    LEFT_ALT: "Alt", RIGHT_ALT: "Alt", LEFT_GUI: "Cmd", RIGHT_GUI: "Cmd",
    ENTER: "Enter", ESC: "Esc", BACKSPACE: "Bksp", SPACE: "Space", TAB: "Tab",
    UP_ARROW: "Up", DOWN_ARROW: "Down", LEFT_ARROW: "Left", RIGHT_ARROW: "Right",
    MINUS: "-", EQUAL: "=", TILDE: "~", PAGEUP: "PgUp", PAGEDOWN: "PgDn",
  };
  function glyph(k) { return KEY_GLYPH[k] || k; }

  // Seed profile
  const SEED = {
    profile_name: "Dev Workflow",
    idle_animation: "breathe",
    default_delay: 30,
    active: 1,
    keys: [
      { id: 1,  name: "Save File",   glow: [80,230,160], actions: [ {type:"keycombo",keys:["LEFT_CTRL","S"]}, {type:"led",color:[80,230,160]} ] },
      { id: 2,  name: "Git Status",  glow: [255,138,76], actions: [ {type:"text",value:"git status"}, {type:"delay",ms:40}, {type:"key",value:"ENTER"} ] },
      { id: 3,  name: "Copy",        glow: [91,140,255], actions: [ {type:"keycombo",keys:["LEFT_CTRL","C"]} ] },
      { id: 4,  name: "Paste",       glow: [91,140,255], actions: [ {type:"keycombo",keys:["LEFT_CTRL","V"]} ] },
      { id: 5,  name: "Build",       glow: [255,138,76], actions: [ {type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","B"]}, {type:"led_anim",value:"flash"} ] },
      { id: 6,  name: "Terminal",    glow: [192,107,255],actions: [ {type:"keycombo",keys:["LEFT_CTRL","TILDE"]} ] },
      { id: 7,  name: "Mute Mic",    glow: [255,93,108], actions: [ {type:"telephony",value:"MIC_MUTE"}, {type:"led",color:[255,93,108]} ] },
      { id: 8,  name: "Volume Up",   glow: [54,230,200], actions: [ {type:"media",value:"VOLUME_UP"} ] },
      { id: 9,  name: "Play / Pause",glow: [54,230,200], actions: [ {type:"media",value:"PLAY_PAUSE"} ] },
      { id: 10, name: "Snip",        glow: [255,138,76], actions: [ {type:"keycombo",keys:["LEFT_GUI","LEFT_SHIFT","S"]} ] },
      { id: 11, name: "Profile 2",   glow: [220,220,230],actions: [ {type:"profile",value:2} ] },
      { id: 12, name: "Ambient",     glow: [255,110,199],actions: [ {type:"led_anim",value:"breathe"}, {type:"led",color:[255,110,199]} ] },
    ],
  };

  const LAYOUT = [
    [null, 1, 2, null],
    [3, 4, 5, 6],
    [7, 8, 9, 10],
    [null, 11, 12, null],
  ];

  // AI context recommendations
  const CONTEXTS = [
    { id: "vscode", label: "Visual Studio Code", icon: "ph-code", sub: "code · editor",
      recs: [
        { key_num: 1, description: "Command Palette", actions:[{type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","P"]}] },
        { key_num: 2, description: "Toggle Sidebar",  actions:[{type:"keycombo",keys:["LEFT_CTRL","B"]}] },
        { key_num: 3, description: "Format Document",  actions:[{type:"keycombo",keys:["LEFT_SHIFT","LEFT_ALT","F"]}] },
        { key_num: 4, description: "Go to Definition", actions:[{type:"key",value:"F12"}] },
      ] },
    { id: "vscode_terminal", label: "VS Code · Terminal", icon: "ph-terminal-window", sub: "shell · bash",
      recs: [
        { key_num: 1, description: "Git Push",   actions:[{type:"text",value:"git push"},{type:"key",value:"ENTER"}] },
        { key_num: 2, description: "Clear",      actions:[{type:"text",value:"clear"},{type:"key",value:"ENTER"}] },
        { key_num: 3, description: "Run Dev",    actions:[{type:"text",value:"npm run dev"},{type:"key",value:"ENTER"}] },
        { key_num: 4, description: "Kill (C-c)", actions:[{type:"keycombo",keys:["LEFT_CTRL","C"]}] },
      ] },
    { id: "chrome", label: "Google Chrome", icon: "ph-globe", sub: "browser",
      recs: [
        { key_num: 1, description: "New Tab",     actions:[{type:"keycombo",keys:["LEFT_CTRL","T"]}] },
        { key_num: 2, description: "Reopen Tab",  actions:[{type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","T"]}] },
        { key_num: 3, description: "Hard Reload", actions:[{type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","R"]}] },
        { key_num: 4, description: "DevTools",    actions:[{type:"key",value:"F12"}] },
      ] },
    { id: "figma", label: "Figma", icon: "ph-pen-nib", sub: "design",
      recs: [
        { key_num: 1, description: "Frame Tool",   actions:[{type:"key",value:"F"}] },
        { key_num: 2, description: "Components",   actions:[{type:"keycombo",keys:["LEFT_ALT","2"]}] },
        { key_num: 3, description: "Group",        actions:[{type:"keycombo",keys:["LEFT_CTRL","G"]}] },
        { key_num: 4, description: "Export",       actions:[{type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","E"]}] },
      ] },
    { id: "excel", label: "Microsoft Excel", icon: "ph-table", sub: "spreadsheet",
      recs: [
        { key_num: 1, description: "Sum Cells",  actions:[{type:"keycombo",keys:["LEFT_ALT","EQUAL"]}] },
        { key_num: 2, description: "New Row",    actions:[{type:"keycombo",keys:["LEFT_CTRL","LEFT_SHIFT","EQUAL"]}] },
        { key_num: 3, description: "Fill Down",  actions:[{type:"keycombo",keys:["LEFT_CTRL","D"]}] },
        { key_num: 4, description: "Format",     actions:[{type:"keycombo",keys:["LEFT_CTRL","1"]}] },
      ] },
  ];

  const PORTS = ["COM3 · USB Serial", "COM4 · ESP32-S3", "/dev/ttyACM0"];

  // Summarize an action into a short label
  function summarize(a) {
    switch (a.type) {
      case "keycombo": return (a.keys || []).map(glyph).join(" + ");
      case "text": return '"' + (a.value || "") + '"';
      case "key": return glyph(a.value || a.key || "");
      case "hold": return "Hold " + glyph(a.key || a.value || "");
      case "release": return "Release " + glyph(a.value || a.key || "");
      case "delay": return (a.ms != null ? a.ms : 0) + " ms";
      case "media": return (a.value || "").replace(/_/g, " ");
      case "telephony": return (a.value || "").replace(/_/g, " ");
      case "mouse_click": return (a.button || "LEFT") + " click";
      case "mouse_move": return "Δ " + (a.x||0) + ", " + (a.y||0);
      case "profile": return "Profile " + (a.value || 1);
      case "led": { const c = a.color || [255,255,255]; return "rgb(" + c.join(",") + ")"; }
      case "led_anim": return (a.value || "none");
      default: return a.type;
    }
  }

  function ledColorOf(key) {
    // prefer an explicit led action color, else the glow
    const led = (key.actions || []).find(a => a.type === "led" && a.color);
    if (led) return led.color;
    return key.glow || null;
  }

  window.MACRO = { ACTION_META, CATS, KEYS, ENUMS, glyph, SEED, LAYOUT, CONTEXTS, PORTS, summarize, ledColorOf };
})();
