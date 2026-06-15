/* Firmware flasher: esptool-js over a Web-Serial-style adapter around the
 * existing node serialport. Flashes firmware/macropad.merged.bin at 0x0 to an
 * ESP32-S2. Main-process only. */
"use strict";

const fs = require("fs");
const { Readable, Writable } = require("stream");
const { SerialPort } = require("serialport");

// Present a node serialport as the subset of the Web Serial `SerialPort` API
// that esptool-js's Transport uses: open/close, readable/writable Web streams,
// setSignals (DTR/RTS), getInfo.
function makeWebSerialDevice(path) {
  let port = null;
  return {
    readable: null,
    writable: null,
    async open(opts = {}) {
      port = new SerialPort({ path, baudRate: opts.baudRate || 115200, autoOpen: false });
      await new Promise((res, rej) => port.open((e) => (e ? rej(e) : res())));
      this.readable = Readable.toWeb(port);
      this.writable = Writable.toWeb(port);
    },
    async close() {
      try { if (port && port.isOpen) await new Promise((res) => port.close(() => res())); } catch (_) {}
      this.readable = null; this.writable = null; port = null;
    },
    async setSignals(sig = {}) {
      if (!port) return;
      await new Promise((res, rej) => port.set(
        { dtr: !!sig.dataTerminalReady, rts: !!sig.requestToSend },
        (e) => (e ? rej(e) : res())));
    },
    getInfo() { return { usbVendorId: 0x303a }; },
  };
}

function downloadModeError(cause) {
  const e = new Error("Could not reach the chip's bootloader. Hold BOOT, tap RESET, then retry.");
  e.code = "NEEDS_DOWNLOAD_MODE";
  e.cause = cause;
  return e;
}

// Read a binary file as the latin1 "binary string" esptool-js expects.
function readBinaryString(path) {
  return fs.readFileSync(path).toString("latin1");
}

/**
 * Flash `binPath` (a merged image) at 0x0 to an ESP32-S2 on `portPath`.
 * onProgress({ phase, percent }). Throws on wrong chip / connect failure.
 */
async function flashFirmware(portPath, binPath, onProgress = () => {}) {
  // esptool-js is ESM-only; load lazily so this CJS module can be require()'d
  // without ERR_REQUIRE_ESM at startup.
  const { ESPLoader, Transport } = await import("esptool-js");

  if (!fs.existsSync(binPath)) throw new Error("Bundled firmware image is missing.");
  const device = makeWebSerialDevice(portPath);
  const transport = new Transport(device, false);
  const esploader = new ESPLoader({
    transport, baudrate: 460800, romBaudrate: 115200,
    terminal: { clean() {}, writeLine() {}, write() {} },
  });

  onProgress({ phase: "connecting", percent: 0 });
  let chip;
  try { chip = await esploader.main(); }      // syncs + detects chip
  catch (e) { try { await transport.disconnect(); } catch (_) {} throw downloadModeError(e); }

  // Safety: never flash a non-S2 board.
  const name = String(chip || esploader.chip?.CHIP_NAME || "");
  if (!/ESP32-?S2/i.test(name)) {
    try { await transport.disconnect(); } catch (_) {}
    const e = new Error(`Refusing to flash: detected "${name || "unknown chip"}", expected ESP32-S2.`);
    e.code = "WRONG_CHIP";
    throw e;
  }

  try {
    const data = readBinaryString(binPath);
    onProgress({ phase: "writing", percent: 0 });
    await esploader.writeFlash({
      fileArray: [{ data, address: 0x0 }],
      flashSize: "keep", flashMode: "keep", flashFreq: "keep", eraseAll: true, compress: true,
      reportProgress: (_i, written, total) => {
        onProgress({ phase: "writing", percent: total ? Math.round((written / total) * 100) : 0 });
      },
    });
    onProgress({ phase: "done", percent: 100 });
    try { await esploader.after("hard_reset"); } catch (_) {}
  } finally {
    try { await transport.disconnect(); } catch (_) {}
  }
}

module.exports = { flashFirmware, makeWebSerialDevice };
