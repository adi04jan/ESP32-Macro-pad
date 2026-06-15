# In-app Firmware Flasher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Macropad Studio flash the bundled ESP32-S2 firmware over a selected COM port — to recover/flash an unrecognized board, and to update a connected macropad whose firmware is older than the bundled version.

**Architecture:** A main-process flasher (`services/flasher.js`) runs `esptool-js` over an adapter that presents the existing `serialport` as a Web-Serial-style device (Node `Readable.toWeb`/`Writable.toWeb` + `port.set({dtr,rts})`). The bundled `firmware/macropad.merged.bin` is flashed at `0x0` with a chip-type guard and a hard confirm. The renderer (Dashboard) shows a recover card when no macropad is detected and an update card when the connected device's version (read via the `status` CLI) is behind the bundled `manifest.json` version. Progress streams over the existing serial event channel as `{type:"flash"}`.

**Tech Stack:** Electron (main + no-bundler renderer), `serialport` (existing), `esptool-js` (new), Node `node:test` for pure-logic tests, React (vendored).

**Branch:** `feature/v2.1` (folded into v2.1).

---

## File structure

- `firmware/macropad.merged.bin` — bundled full-flash image (provided by the user; not produced in dev).
- `firmware/manifest.json` — `{ "version": "2.1.0" }`, the source of truth for the bundled version.
- `firmware/README.md` — how to export the image.
- `studio/services/fwversion.js` — **pure** helpers: parse device version from `status`, semver compare, outdated check. No deps → unit-tested.
- `studio/services/flasher.js` — `esptool-js` engine + Web-Serial-over-serialport device shim + `flashFirmware()`.
- `studio/main.js` — flash IPC (`flash:info/start/cancel`), read device version on connect, resolve firmware path.
- `studio/preload.js` — `flashInfo/flashStart/flashCancel`.
- `studio/renderer/App.jsx` — device-version state, bundled-version load, flash-progress event, pass props to Dashboard.
- `studio/renderer/Dashboard.jsx` — recover card (not-detected) + update card (outdated) + `Confirm` + progress UI.
- `studio/tests/fwversion.test.js` — `node:test` unit tests for `fwversion.js`.
- `studio/package.json` — add `esptool-js` dep, `firmware/` extraResources, `test` script.

---

## Task 1: Bundle scaffolding + dependency

**Files:**
- Create: `firmware/manifest.json`, `firmware/README.md`
- Modify: `studio/package.json`

- [ ] **Step 1: Create the firmware manifest**

`firmware/manifest.json`:
```json
{ "version": "2.1.0" }
```

- [ ] **Step 2: Create the firmware README**

`firmware/README.md`:
```markdown
# Bundled firmware

`macropad.merged.bin` is the full-flash image the Studio app flashes to a board.

## Export it (per firmware version)

Arduino IDE: **Sketch → Export Compiled Binary**, then take the
`*.ino.merged.bin` from the build output. Or with arduino-cli:

```sh
arduino-cli compile --fqbn esp32:esp32:lolin_s2_pico \
  --output-dir build_out ESP32-Macro-pad
cp build_out/ESP32-Macro-pad.ino.merged.bin firmware/macropad.merged.bin
```

Then update `manifest.json`'s `version` to match `config.h`'s `FW_VERSION`,
and commit both. Only commit an image you have flashed and verified.
```

- [ ] **Step 3: Add esptool-js, firmware resources, and a test script**

In `studio/package.json`: add `"esptool-js": "^0.5.7"` to `dependencies`; add a `firmware` entry to `build.extraResources`; add `"test": "node --test"` to `scripts`.

```jsonc
// dependencies
"esptool-js": "^0.5.7",
// build.extraResources (append)
{ "from": "../firmware", "to": "firmware" }
// scripts
"test": "node --test"
```

- [ ] **Step 4: Install**

Run: `cd studio && npm install`
Expected: `esptool-js` added, exit 0.

- [ ] **Step 5: Commit**

```bash
git add firmware/manifest.json firmware/README.md studio/package.json studio/package-lock.json
git commit -m "feat(flasher): bundle scaffolding + esptool-js dependency"
```

> The real `firmware/macropad.merged.bin` is dropped in by the user (the verified v2.1.0 image). The code must treat a missing image gracefully (Task 4/7).

---

## Task 2: Pure version helpers (TDD)

**Files:**
- Create: `studio/services/fwversion.js`
- Test: `studio/tests/fwversion.test.js`

- [ ] **Step 1: Write the failing tests**

`studio/tests/fwversion.test.js`:
```js
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const { parseStatusVersion, cmpSemver, isOutdated } = require("../services/fwversion");

test("parseStatusVersion pulls ver: from a status line", () => {
  assert.equal(parseStatusVersion("Profile:1 loaded:1 idle:2 mode:rainbow ver:2.0.0"), "2.0.0");
});
test("parseStatusVersion handles multiline + CRLF", () => {
  assert.equal(parseStatusVersion("noise\r\nProfile:1 loaded:1 idle:0 mode:none ver:2.1.0\r\n"), "2.1.0");
});
test("parseStatusVersion returns null when absent", () => {
  assert.equal(parseStatusVersion("no version here"), null);
});
test("cmpSemver orders versions", () => {
  assert.equal(cmpSemver("2.0.0", "2.1.0"), -1);
  assert.equal(cmpSemver("2.1.0", "2.1.0"), 0);
  assert.equal(cmpSemver("2.2.0", "2.1.0"), 1);
  assert.equal(cmpSemver("2.1.0", "2.1"), 1);
});
test("isOutdated true only when device < bundled", () => {
  assert.equal(isOutdated("2.0.0", "2.1.0"), true);
  assert.equal(isOutdated("2.1.0", "2.1.0"), false);
  assert.equal(isOutdated("2.2.0", "2.1.0"), false);
  assert.equal(isOutdated(null, "2.1.0"), false);   // unknown -> don't nag
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd studio && node --test tests/fwversion.test.js`
Expected: FAIL — `Cannot find module '../services/fwversion'`.

- [ ] **Step 3: Implement the helpers**

`studio/services/fwversion.js`:
```js
/* Pure firmware-version helpers: parse the device's `status` line and compare
 * semver strings. No I/O — unit-tested in tests/fwversion.test.js. */
"use strict";

function parseStatusVersion(text) {
  if (!text) return null;
  const m = String(text).match(/ver:\s*([0-9]+(?:\.[0-9]+){1,2})/i);
  return m ? m[1] : null;
}

function _parts(v) { return String(v).split(".").map((n) => parseInt(n, 10) || 0); }

// -1 if a<b, 0 if equal, 1 if a>b (missing minor/patch treated as 0).
function cmpSemver(a, b) {
  const pa = _parts(a), pb = _parts(b);
  for (let i = 0; i < 3; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d > 0 ? 1 : -1;
  }
  return 0;
}

function isOutdated(deviceVer, bundledVer) {
  if (!deviceVer || !bundledVer) return false;
  return cmpSemver(deviceVer, bundledVer) < 0;
}

module.exports = { parseStatusVersion, cmpSemver, isOutdated };
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd studio && node --test tests/fwversion.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/services/fwversion.js studio/tests/fwversion.test.js
git commit -m "feat(flasher): pure firmware-version helpers + tests"
```

---

## Task 3: Flasher engine (`services/flasher.js`)

**Files:**
- Create: `studio/services/flasher.js`

> No hardware in dev — this task is verified by `node --check` and a `require()` smoke test; the real flash is verified on-device (Task 8). The `esptool-js` Transport targets the Web Serial `SerialPort` interface, so the adapter presents exactly that surface over `serialport`.

- [ ] **Step 1: Implement the Web-Serial-over-serialport device + flash**

`studio/services/flasher.js`:
```js
/* Firmware flasher: esptool-js over a Web-Serial-style adapter around the
 * existing node serialport. Flashes firmware/macropad.merged.bin at 0x0 to an
 * ESP32-S2. Main-process only. */
"use strict";

const fs = require("fs");
const { Readable, Writable } = require("stream");
const { SerialPort } = require("serialport");
const { ESPLoader, Transport } = require("esptool-js");

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
      flashSize: "keep", eraseAll: true, compress: true,
      reportProgress: (_i, written, total) => {
        onProgress({ phase: "writing", percent: total ? Math.round((written / total) * 100) : 0 });
      },
    });
    onProgress({ phase: "done", percent: 100 });
    try { await esploader.hardReset(); } catch (_) {}
  } finally {
    try { await transport.disconnect(); } catch (_) {}
  }
}

module.exports = { flashFirmware, makeWebSerialDevice };
```

- [ ] **Step 2: Syntax check**

Run: `cd studio && node --check services/flasher.js`
Expected: exit 0.

- [ ] **Step 3: Require smoke test (module + esptool-js load)**

Run: `cd studio && node -e "require('./services/flasher'); console.log('ok')"`
Expected: prints `ok` (confirms `esptool-js` resolves and the module loads).

- [ ] **Step 4: Commit**

```bash
git add studio/services/flasher.js
git commit -m "feat(flasher): esptool-js engine over serialport adapter (ESP32-S2 guard)"
```

---

## Task 4: Main-process IPC + device-version read

**Files:**
- Modify: `studio/main.js`

- [ ] **Step 1: Import the flasher + version helpers and resolve firmware paths**

Near the other `require`s in `studio/main.js`:
```js
const flasher = require("./services/flasher");
const { parseStatusVersion } = require("./services/fwversion");
```

Add path resolver + manifest reader (place beside the dataDir/resourceDir setup):
```js
function firmwareDir() {
  return app.isPackaged ? path.join(process.resourcesPath, "firmware")
                        : path.resolve(__dirname, "..", "firmware");
}
function firmwareInfo() {
  try {
    const m = JSON.parse(fs.readFileSync(path.join(firmwareDir(), "manifest.json"), "utf8"));
    const bin = path.join(firmwareDir(), "macropad.merged.bin");
    return { version: m.version || null, bin, available: fs.existsSync(bin),
             size: fs.existsSync(bin) ? fs.statSync(bin).size : 0 };
  } catch (_) { return { version: null, bin: null, available: false, size: 0 }; }
}
```

- [ ] **Step 2: Read the device firmware version on connect**

In the `link.on("open", ...)` flow (the existing `open` event handler that calls `fsinfo` / `switchProfile`), after `api.fsinfo()`-equivalent, query status:
```js
link.command("status").then((out) => {
  const v = parseStatusVersion(out);
  if (v) send("fw-version", { version: v });
}).catch(() => {});
```
(`send` already posts `{type, data}` on the `serial:event` channel; the renderer handles `type: "fw-version"`.)

- [ ] **Step 3: Add the flash IPC handlers**

Beside the other `ipcMain.handle` calls:
```js
ipcMain.handle("flash:info", () => { const i = firmwareInfo(); return { version: i.version, available: i.available, size: i.size }; });

let flashing = false;
ipcMain.handle("flash:start", async (_e, portPath) => {
  if (flashing) return { ok: false, error: "already flashing" };
  const info = firmwareInfo();
  if (!info.available) return { ok: false, error: "no firmware image bundled" };
  if (!portPath) return { ok: false, error: "no port selected" };
  flashing = true;
  if (link.isOpen()) link.disconnect();              // free the port for esptool-js
  try {
    await flasher.flashFirmware(portPath, info.bin, (p) => send("flash", p));
    return { ok: true };
  } catch (err) {
    send("flash", { phase: "error", code: err.code || null, error: err.message });
    return { ok: false, code: err.code || null, error: err.message };
  } finally { flashing = false; }
});
```

- [ ] **Step 4: Syntax check**

Run: `cd studio && node --check main.js`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add studio/main.js
git commit -m "feat(flasher): flash IPC + device firmware-version read on connect"
```

---

## Task 5: Preload bridge

**Files:**
- Modify: `studio/preload.js`

- [ ] **Step 1: Expose the flash API**

In the `contextBridge.exposeInMainWorld("api", { ... })` object:
```js
  // firmware flashing
  flashInfo: () => ipcRenderer.invoke("flash:info"),
  flashStart: (port) => ipcRenderer.invoke("flash:start", port),
```

- [ ] **Step 2: Syntax check**

Run: `cd studio && node --check preload.js`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add studio/preload.js
git commit -m "feat(flasher): preload bridge for flash info/start"
```

---

## Task 6: Renderer state + events (`App.jsx`)

**Files:**
- Modify: `studio/renderer/App.jsx`

- [ ] **Step 1: Add state for bundled + device versions and flash progress**

Near the other `useState` declarations:
```jsx
    const [fwBundled, setFwBundled] = useState({ version: null, available: false });
    const [fwDevice, setFwDevice] = useState(null);     // device FW version string
    const [flash, setFlash] = useState(null);           // {phase,percent,code,error} | null
```

- [ ] **Step 2: Load bundled info on boot; reset device version on disconnect**

In the boot `useEffect` (where settings are loaded), add:
```jsx
      api.flashInfo().then((i) => setFwBundled(i || { version: null, available: false }));
```
In the `onEvent` switch, add cases (place beside the existing `else if (type === ...)` chain):
```jsx
        else if (type === "fw-version") { setFwDevice(data && data.version); }
        else if (type === "flash") { setFlash(data); }
```
In the `disconnect` handling (`else if (type === "disconnect")`), also clear the device version: add `setFwDevice(null);`.

- [ ] **Step 3: Add the flash handler**

Beside the other handlers (e.g., near `onExportAll`):
```jsx
    const startFlash = (portPath) => {
      setFlash({ phase: "connecting", percent: 0 });
      api.flashStart(portPath).then((r) => {
        if (r && r.ok) { setFlash({ phase: "done", percent: 100 }); setTimeout(refreshPorts, 1500); }
        else if (!(r && r.code)) setFlash({ phase: "error", error: (r && r.error) || "flash failed" });
      }).catch((e) => setFlash({ phase: "error", error: e.message }));
    };
```

- [ ] **Step 4: Pass flash props to Dashboard**

In the `view === "dashboard"` `React.createElement(window.Dashboard, { ... })` props, append:
```jsx
                fwBundled, fwDevice, flash, onFlash: startFlash, onFlashDismiss: () => setFlash(null),
```

- [ ] **Step 5: Build + verify renderer compiles**

Run: `cd studio && node build.js`
Expected: `renderer build complete`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add studio/renderer/App.jsx
git commit -m "feat(flasher): renderer state, fw-version/flash events, Dashboard props"
```

---

## Task 7: Dashboard cards + progress UI

**Files:**
- Modify: `studio/renderer/Dashboard.jsx`

- [ ] **Step 1: Accept the new props and import helpers**

Update the `Dashboard({ ... })` destructure to add:
```jsx
fwBundled = {}, fwDevice, flash, onFlash, onFlashDismiss,
```
At the top of `Dashboard.jsx`'s IIFE, alongside the existing `window.UI` destructure, add `Confirm`:
```jsx
  const { /* existing… */ Confirm } = window.UI;
```
And the outdated check (inline, mirrors `fwversion.isOutdated`):
```jsx
  const cmpSemver = (a, b) => { const pa=String(a).split(".").map(Number), pb=String(b).split(".").map(Number);
    for (let i=0;i<3;i++){ const d=(pa[i]||0)-(pb[i]||0); if(d) return d>0?1:-1; } return 0; };
```

- [ ] **Step 2: Add the flash card + Confirm + progress (recover & update)**

Add a `useState` for the confirm dialog at the top of the `Dashboard` function:
```jsx
    const [askFlash, setAskFlash] = React.useState(false);
```
Render this block inside the Device-tab layout (e.g., directly after the port/connect panel). `detected` (already computed as the macropad port) and `port` (selected path) exist in the component:
```jsx
            {(() => {
              const selectedIsMacropad = detected && port && detected.path === port;
              const outdated = selectedIsMacropad && fwDevice && fwBundled.version && cmpSemver(fwDevice, fwBundled.version) < 0;
              const showRecover = port && !selectedIsMacropad && !connected;
              if (!fwBundled.available || (!showRecover && !outdated)) return null;
              const flashing = flash && flash.phase && flash.phase !== "error" && flash.phase !== "done";
              return (
                <Panel title={outdated ? "Firmware update" : "Flash / recover firmware"} icon="lightning"
                       sub={outdated ? `v${fwDevice} → v${fwBundled.version}` : `No macropad detected on ${port}`}>
                  <div className="fs13" style={{ color: "var(--danger, #ff5d6c)", marginBottom: 10 }}>
                    ⚠ Flashing erases everything on the board, including all saved profiles.
                  </div>
                  {flash && flash.phase === "error" && flash.code === "NEEDS_DOWNLOAD_MODE" &&
                    <div className="fs12 faint" style={{ marginBottom: 10 }}>
                      Couldn’t reach the bootloader. Hold <b>BOOT</b>, tap <b>RESET</b>, then Retry.</div>}
                  {flash && flash.phase === "error" && flash.code !== "NEEDS_DOWNLOAD_MODE" &&
                    <div className="fs12" style={{ color: "var(--danger,#ff5d6c)", marginBottom: 10 }}>{flash.error}</div>}
                  {flash && flash.phase === "done" &&
                    <div className="fs12" style={{ color: "var(--ok,#2fe6a8)", marginBottom: 10 }}>Done — the board will reboot. Reconnect above.</div>}
                  {flashing
                    ? <div>
                        <div className="row between"><span className="fs12 faint">{flash.phase}…</span>
                          <span className="mono fs12 faint">{flash.percent != null ? flash.percent + "%" : ""}</span></div>
                        <div style={{ height: 6, borderRadius: 99, background: "var(--line)", marginTop: 6 }}>
                          <div style={{ height: "100%", width: (flash.percent || 0) + "%", background: "var(--accent)", borderRadius: 99 }} /></div>
                      </div>
                    : <Btn icon="lightning" variant="danger" onClick={() => setAskFlash(true)}>
                        {outdated ? "Update firmware" : `Flash firmware v${fwBundled.version}`}</Btn>}
                  <Confirm open={askFlash}
                    title={outdated ? "Update firmware?" : "Flash firmware?"}
                    message={`This erases the entire board — all profiles are lost — and writes firmware v${fwBundled.version}. The board may need BOOT+RESET to enter flashing mode. Continue?`}
                    confirmLabel={outdated ? "Erase & update" : "Erase & flash"}
                    onCancel={() => setAskFlash(false)}
                    onConfirm={() => { setAskFlash(false); onFlash && onFlash(port); }} />
                </Panel>
              );
            })()}
```

- [ ] **Step 3: Build + verify renderer compiles**

Run: `cd studio && node build.js`
Expected: `built Dashboard.js`, `renderer build complete`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add studio/renderer/Dashboard.jsx
git commit -m "feat(flasher): Dashboard recover/update cards with confirm + progress"
```

---

## Task 8: Integration verification

**Files:** none (verification only)

- [ ] **Step 1: Full unit + build pass**

Run: `cd studio && node --test && node build.js`
Expected: fwversion tests PASS; renderer build completes.

- [ ] **Step 2: Packaged smoke test (no device)**

Drop a placeholder/real `firmware/macropad.merged.bin` in place, then:
Run: `cd studio && npm run dist`
Expected: build succeeds; `dist-build/win-unpacked/resources/firmware/macropad.merged.bin` + `manifest.json` are present (extraResources bundled).

- [ ] **Step 3: On-device verification (user, with hardware)**

- Recover: select a blank/unrecognized S2 port → the recover card appears → Confirm → (BOOT+RESET if prompted) → progress to 100% → board reboots and enumerates as `303A:80C5`.
- Update: connect a macropad running older firmware → the update card shows `v<old> → v2.1.0` → Confirm → flashes → reboots updated.
- Guard: confirm a non-S2 serial device is refused with the WRONG_CHIP message.

- [ ] **Step 4: Commit any fixes from on-device iteration**

```bash
git add -A
git commit -m "fix(flasher): on-device adjustments"
```

---

## Notes / risks

- **esptool-js Transport surface:** the adapter targets the Web Serial `SerialPort` API esptool-js expects. If the pinned `esptool-js` version calls methods the shim doesn't cover, extend `makeWebSerialDevice` (it's the single integration point). Verify the exact API against `node_modules/esptool-js` at execution time.
- **Download mode on native-USB S2:** auto reset-to-bootloader is unreliable; the BOOT+RESET fallback is expected and surfaced.
- **Bundled image is a prerequisite:** the user supplies the verified `firmware/macropad.merged.bin`; without it the cards stay hidden (`fwBundled.available === false`) and `flash:start` returns an error.
- **4 MB write** is slowish; acceptable for v1. A later optimization could flash bootloader/partition/app component files instead of the merged image.
- **Cancel is intentionally omitted.** The spec listed a best-effort `flash:cancel`, but aborting mid-`writeFlash` can leave a half-written board (worse than finishing). The UI shows progress but no cancel during the write; the operation runs to completion or errors out. Revisit only if a safe abort point is identified.
