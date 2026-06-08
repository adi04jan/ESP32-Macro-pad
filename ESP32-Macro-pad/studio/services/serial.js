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
    this._capturing = false;
    this._captureLines = [];
    this._captureTimer = null;
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
    this._clearCapture();
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

  requestFsInfo() { this.send("fsinfo"); }
  setActiveProfile(n) { this.send(`setprofile ${parseInt(n, 10)}`); }

  requestProfile(path) {
    if (!path.startsWith("/")) path = "/" + path;
    this._beginCapture();
    this.send(`cat ${path}`);
  }

  uploadProfile(filename, obj) {
    return new Promise((resolve) => {
      let lines;
      try { lines = buildUploadLines(filename, obj); }
      catch (e) { this.emit("log", `Serialization error: ${e.message}\n`); return resolve(false); }
      let i = 0;
      const next = () => {
        if (i >= lines.length) { this.emit("log", "Upload sequence sent.\n"); return resolve(true); }
        this.send(lines[i++]);
        setTimeout(next, 10);
      };
      next();
    });
  }

  setKey(keyNum, actions) {
    this.send(`setkey ${keyNum} ${JSON.stringify(actions)}`);
  }

  // -- capture --------------------------------------------------------
  _beginCapture() {
    this._capturing = true;
    this._captureLines = [];
    clearTimeout(this._captureTimer);
    this._captureTimer = setTimeout(() => {
      this.emit("log", "Warning: file capture timed out.\n");
      this._finishCapture();
    }, CAPTURE_TIMEOUT_MS);
  }

  _clearCapture() { this._capturing = false; this._captureLines = []; clearTimeout(this._captureTimer); }

  _finishCapture() {
    const lines = this._captureLines;
    this._clearCapture();
    this.emit("file", lines);
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
    const fs = parseFsInfo(clean);
    if (fs) { this.emit("fs-info", fs); return; }
    if (clean.includes(PROMPT)) {
      if (this._capturing) this._finishCapture();
      this.emit("ready");
      return;
    }
    if (this._capturing) this._captureLines.push(clean);
    else if (clean.trim() !== "") this.emit("log", clean + "\n");
  }
}

module.exports = { SerialLink, parseFsInfo, buildUploadLines, stripCatEcho };
