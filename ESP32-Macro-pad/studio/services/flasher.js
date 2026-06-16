/* Firmware flasher: drives the bundled `esptool` to write the merged firmware
 * image to an ESP32-S2. On native USB the chip re-enumerates to a *different*
 * COM port when it enters the ROM bootloader, so we (1) reboot it via a 1200-baud
 * touch, (2) detect the new bootloader port, then (3) run esptool there. */
"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { SerialPort } = require("serialport");

let app = null;
try { app = require("electron").app; } catch (_) {}

const FW_PID = "80C5";          // running-firmware USB PID
const ESP_VID = "303A";         // Espressif VID (firmware and ROM bootloader)

function esptoolPath() {
  const name = process.platform === "win32" ? "esptool.exe" : "esptool";
  const candidates = [
    app && app.isPackaged ? path.join(process.resourcesPath, "tools", name) : null,
    path.join(__dirname, "..", "tools", name),
  ].filter(Boolean);
  return candidates.find((p) => fs.existsSync(p)) || null;
}

const delay = (ms) => new Promise((r) => setTimeout(r, ms));
async function espPorts() {
  try { return (await SerialPort.list()).filter((p) => (p.vendorId || "").toUpperCase() === ESP_VID); }
  catch (_) { return []; }
}

// 1200-baud touch: the Arduino-ESP32 USB-CDC stack reboots into the ROM
// bootloader when the host opens the port at 1200 baud with DTR de-asserted.
function touch1200(portPath) {
  return new Promise((resolve) => {
    let sp;
    try { sp = new SerialPort({ path: portPath, baudRate: 1200, autoOpen: false }); }
    catch (_) { return resolve(false); }
    sp.open((err) => {
      if (err) return resolve(false);
      sp.set({ dtr: false, rts: false }, () => setTimeout(() => { try { sp.close(() => resolve(true)); } catch (_) { resolve(true); } }, 200));
    });
  });
}

// After a reboot, find the bootloader port: prefer one that wasn't there before
// the touch; else any Espressif port that isn't the running firmware.
async function findBootloaderPort(beforePaths, originalPort) {
  for (let i = 0; i < 24; i++) {        // ~7s
    await delay(300);
    const ports = await espPorts();
    const fresh = ports.find((p) => !beforePaths.includes(p.path));
    if (fresh) return fresh.path;
    const boot = ports.find((p) => (p.productId || "").toUpperCase() !== FW_PID);
    if (boot) return boot.path;
  }
  return originalPort;                   // fall back: device may have kept its port
}

function classify(output, code) {
  const s = String(output || "");
  const last = s.split("\n").map((l) => l.trim()).filter(Boolean).pop() || `esptool exited with code ${code}`;
  const e = new Error(last.slice(0, 300));
  if (/wrong chip|chip.*mismatch|does not match|expected esp32-s2/i.test(s)) e.code = "WRONG_CHIP";
  else if (/failed to connect|no serial data received|invalid head of packet|wrong boot mode/i.test(s)) e.code = "NEEDS_DOWNLOAD_MODE";
  else if (/could not open|does not exist|permission denied|access is denied/i.test(s)) e.code = "PORT_BUSY";
  return e;
}

function runEsptool(flashPort, binPath, onProgress) {
  return new Promise((resolve, reject) => {
    const tool = esptoolPath();
    if (!tool) return reject(new Error("esptool is not bundled with the app."));
    // Device is already in the bootloader (from the touch), so --before no-reset.
    const args = ["--chip", "esp32s2", "--port", flashPort, "--baud", "921600",
      "--before", "no-reset", "--after", "hard-reset",
      "write-flash", "-z", "0x0", binPath];
    let proc;
    try { proc = spawn(tool, args, { windowsHide: true }); }
    catch (e) { return reject(e); }
    let out = "";
    const onChunk = (buf) => {
      const s = buf.toString();
      out += s; if (out.length > 20000) out = out.slice(-20000);
      const m = s.match(/(\d+(?:\.\d+)?)\s*%/);
      if (m) onProgress({ phase: "writing", percent: Math.round(parseFloat(m[1])) });
      if (/Hash of data verified|Wrote \d+ bytes/i.test(s)) onProgress({ phase: "writing", percent: 100 });
    };
    proc.stdout.on("data", onChunk);
    proc.stderr.on("data", onChunk);
    proc.on("error", (e) => reject(e));
    proc.on("close", (code) => { code === 0 ? (onProgress({ phase: "done", percent: 100 }), resolve()) : reject(classify(out, code)); });
  });
}

/**
 * Flash `binPath` (merged image) at 0x0 to the ESP32-S2 reachable via `portPath`
 * (the running-firmware port, or a board already in the bootloader).
 * onProgress({ phase, percent }) — phase ∈ connecting|rebooting|writing|done.
 */
async function flashFirmware(portPath, binPath, onProgress = () => {}) {
  if (!portPath) throw Object.assign(new Error("No port selected."), { code: "NO_PORT" });
  if (!fs.existsSync(binPath)) throw new Error("Firmware image is missing.");
  if (!esptoolPath()) throw new Error("esptool is not bundled with the app.");

  onProgress({ phase: "connecting", percent: 0 });
  const before = (await espPorts()).map((p) => p.path);
  onProgress({ phase: "rebooting", percent: 0 });
  await touch1200(portPath);                                  // reboot into the ROM bootloader
  const flashPort = await findBootloaderPort(before.filter((p) => p !== portPath), portPath);
  return runEsptool(flashPort, binPath, onProgress);
}

module.exports = { flashFirmware, esptoolPath };
