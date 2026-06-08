/* Pre-transform the renderer JSX to plain JS so Electron can load it over
 * file:// without runtime Babel (which can't fetch local files under CORS).
 * Run with: node build.js  (also wired as npm prebuild via package scripts). */

"use strict";

const fs = require("fs");
const path = require("path");

let Babel = require("./renderer/vendor/babel.min.js");
if (!Babel || !Babel.transform) Babel = global.Babel;
if (!Babel || !Babel.transform) { console.error("Babel not available"); process.exit(1); }

const RENDERER = path.join(__dirname, "renderer");
const OUT = path.join(RENDERER, "build");
fs.mkdirSync(OUT, { recursive: true });

// Order matters: globals must be registered before App uses them.
const JSX = ["ui", "ActionBuilder", "KeyEditor", "Dashboard", "AutoSwitcher", "Settings", "Widget", "CommandPalette", "App"];

// Plain JS, copied verbatim.
fs.copyFileSync(path.join(RENDERER, "data.js"), path.join(OUT, "data.js"));

for (const name of JSX) {
  const src = fs.readFileSync(path.join(RENDERER, name + ".jsx"), "utf8");
  const { code } = Babel.transform(src, { presets: [["react"]], filename: name + ".jsx" });
  fs.writeFileSync(path.join(OUT, name + ".js"), code);
  console.log("built", name + ".js");
}
console.log("renderer build complete ->", path.relative(__dirname, OUT));
