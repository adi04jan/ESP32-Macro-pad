/* Serial link to the macropad (Node port of configurator/serial_link.py).
 *
 * Emits: 'log'(text), 'fs-info'({total,used}), 'file'(lines[]),
 *        'ready', 'disconnect', 'open'. */

"use strict";

const { EventEmitter } = require("events");
const { SerialPort } = require("serialport");

const PROMPT = "macropad:$";
const CAPTURE_TIMEOUT_MS = 4000;

function parseFsInfo(line) {
  const s = line.trim();
  if (!s.startsWith("FS_INFO:")) return null;
  const parts = s.slice("FS_INFO:".length).split(",");
  if (parts.length < 2) return null;
  const total = parseInt(parts[0], 10), used = parseInt(parts[1], 10);
  if (!Number.isFinite(total) || !Number.isFinite(used)) return null;
  return { total, used };
}

function buildUploadLines(filename, obj) {
  const name = String(filename).replace(/^\/+/, "");
  const body = JSON.stringify(obj, null, 2);
  return [`###BEGIN### ${name}`, ...body.split("\n"), "###END###"];
}

function stripCatEcho(text) {
  const lines = text.trim().split("\n");
  if (lines.length && lines[0].trimStart().startsWith("cat ")) lines.shift();
  return lines.join("\n").trim();
}

class SerialLink extends EventEmitter {
  constructor() {
    super();
    this.port = null;
    this._partial = "";
    this._reading = false;       // a command()/upload is awaiting its prompt
    this._readLines = [];
    this._readResolve = null;
    this._readTimer = null;
    this._chain = null;          // serialized command queue
  }

  async listPorts() {
    try {
      const ports = await SerialPort.list();
      return ports.map((p) => ({
        path: p.path,
        label: `${p.path}${p.friendlyName ? " · " + p.friendlyName : ""}`,
        vendorId: p.vendorId, productId: p.productId,
      }));
    } catch (e) {
      this.emit("log", `Port list error: ${e.message}\n`);
      return [];
    }
  }

  isOpen() { return !!(this.port && this.port.isOpen); }

  connect(path, baud = 115200) {
    return new Promise((resolve) => {
      if (this.isOpen()) return resolve(true);
      this.port = new SerialPort({ path, baudRate: baud }, (err) => {
        if (err) {
          this.emit("log", `Connection error: ${err.message}\n`);
          this.port = null;
          return resolve(false);
        }
        this._partial = "";
        this.emit("log", `Connected to ${path} at ${baud} baud.\n`);
        this.emit("open");
        resolve(true);
      });
      this.port.on("data", (buf) => this._feed(buf.toString("utf8")));
      this.port.on("error", (e) => { this.emit("log", `Serial error: ${e.message}\n`); this._down(); });
      this.port.on("close", () => this._down());
    });
  }

  _down() {
    this.port = null;
    // Release any in-flight read so awaiters don't hang on a dropped connection.
    if (this._reading) { this.emit("log", "Connection lost during a device operation.\n"); this._finishRead(); }
    this.emit("disconnect");
  }

  disconnect() {
    if (this.port) { try { this.port.close(); } catch (_) {} }
    this.port = null;
  }

  send(cmd) {
    if (!this.isOpen()) return;
    this.port.write(cmd + "\n", (e) => { if (e) this.emit("log", `Write error: ${e.message}\n`); });
  }

  // ---- serialized device I/O ----------------------------------------
  // The device is a single line interface terminated by a prompt. Running every
  // interaction exclusively (one at a time) stops prompts from being attributed
  // to the wrong command when several are issued close together.
  _runExclusive(fn) {
    const run = () => fn();
    this._chain = (this._chain || Promise.resolve()).then(run, run);
    return this._chain;
  }

  // Send a command, resolve with its output once the prompt returns.
  command(cmd) {
    return this._runExclusive(() => new Promise((resolve) => {
      if (!this.isOpen()) return resolve("");
      this._reading = true;
      this._readLines = [];
      this._readResolve = resolve;
      clearTimeout(this._readTimer);
      this._readTimer = setTimeout(() => this._finishRead(true), CAPTURE_TIMEOUT_MS);
      this.send(cmd);
    }));
  }
  _finishRead(timedOut = false) {
    clearTimeout(this._readTimer);
    const lines = this._readLines;
    const resolve = this._readResolve;
    this._reading = false; this._readLines = []; this._readResolve = null;
    if (timedOut) this.emit("log", "Device did not respond in time — request timed out.\n");
    if (resolve) resolve(lines.join("\n"));
  }

  requestFsInfo() { return this.command("fsinfo"); }   // FS_INFO line emits 'fs-info' during the read
  setActiveProfile(n) { return this.command(`setprofile ${parseInt(n, 10)}`); }

  // Raw file contents (no 'file'/'profile' emit) — used by the editor + backups.
  readFile(filename) {
    if (!filename.startsWith("/")) filename = "/" + filename;
    return this.command(`cat ${filename}`);
  }

  // Explicit "Reload" path: read then emit 'file' for the 'profile' flow.
  requestProfile(path) {
    if (!path.startsWith("/")) path = "/" + path;
    this.command(`cat ${path}`).then((raw) => this.emit("file", raw.split("\n")));
  }

  setKey(keyNum, actions) { return this.command(`setkey ${keyNum} ${JSON.stringify(actions)}`); }
  setLed(keyNum, r, g, b) { return this.command(`setled ${parseInt(keyNum, 10)} ${r | 0} ${g | 0} ${b | 0}`); }
  setIdle(name) { return this.command(`setidle ${String(name)}`); }
  setBrightness(b) { return this.command(`setbrightness ${Math.max(0, Math.min(255, b | 0))}`); }

  uploadProfile(filename, obj) {
    return this._runExclusive(() => new Promise((resolve) => {
      if (!this.isOpen()) return resolve(false);
      let lines;
      try { lines = buildUploadLines(filename, obj); }
      catch (e) { this.emit("log", `Serialization error: ${e.message}\n`); return resolve(false); }
      this._reading = true;
      this._readLines = [];
      this._readResolve = () => resolve(true);   // resolves on the post-upload prompt
      clearTimeout(this._readTimer);
      this._readTimer = setTimeout(() => { this.emit("log", "Upload timed out — device did not acknowledge.\n"); this._finishRead(); }, 8000);
      let i = 0;
      const next = () => {
        if (i >= lines.length) return;
        if (!this.isOpen()) { this._finishRead(); return; }   // bail cleanly if the port dropped mid-upload
        this.send(lines[i++]); setTimeout(next, 8);
      };
      next();
    }));
  }

  // Device -> app live events: "KEY <n> <1|0>" or "IDLE <name>".
  _handleEvent(body) {
    const t = body.split(/\s+/);
    if (t[0] === "KEY") this.emit("keyevent", { key: parseInt(t[1], 10), down: t[2] === "1" });
    else if (t[0] === "IDLE") this.emit("idleevent", { mode: t[1] || "none" });
    else if (t[0] === "PROFILE") this.emit("profileevent", { profile: parseInt(t[1], 10) });
    else if (t[0] === "LEDS") {
      const hex = t[1] || "";
      if (hex.length >= 48) {   // 12 LEDs x RGB565 (4 hex each), hardware order
        const f = new Array(12);
        for (let i = 0; i < 12; i++) {
          const v = parseInt(hex.substr(i * 4, 4), 16);
          let r = (v >> 11) & 0x1F, g = (v >> 5) & 0x3F, b = v & 0x1F;
          r = (r << 3) | (r >> 2); g = (g << 2) | (g >> 4); b = (b << 3) | (b >> 2);   // expand to 8-bit
          f[i] = [r, g, b];
        }
        this.emit("ledsframe", f);
      }
    }
  }

  // -- line assembly --------------------------------------------------
  _feed(text) {
    if (!text) return;
    if (!text.endsWith("\n") && !text.includes(PROMPT)) { this._partial += text; return; }
    const combined = this._partial + text;
    this._partial = "";
    // The prompt may share a chunk with following data; split on newlines but
    // also treat a trailing prompt as a line boundary.
    const parts = combined.split("\n");
    parts.forEach((line, idx) => {
      if (idx === parts.length - 1 && line !== "" && !line.includes(PROMPT)) {
        this._partial = line; // incomplete trailing fragment
      } else if (line !== "" || idx < parts.length - 1) {
        this._handleLine(line);
      }
    });
  }

  _handleLine(line) {
    const clean = line.replace(/\r/g, "");
    // Device->app live events. Divert before capture so they never land in a
    // profile JSON being read via `cat`.
    if (clean.startsWith("EVT:")) { this._handleEvent(clean.slice(4).trim()); return; }
    const fs = parseFsInfo(clean);
    if (fs) { this.emit("fs-info", fs); return; }
    if (clean.includes(PROMPT)) {
      if (this._reading) this._finishRead();
      this.emit("ready");
      return;
    }
    if (this._reading) { this._readLines.push(clean); return; }
    if (clean.trim() !== "") this.emit("log", clean + "\n");
  }
}

module.exports = { SerialLink, parseFsInfo, buildUploadLines, stripCatEcho };
