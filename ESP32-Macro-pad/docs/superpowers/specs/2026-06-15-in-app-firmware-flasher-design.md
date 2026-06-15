# In-app Firmware Flasher — Design

**Date:** 2026-06-15 · **Target release:** v2.1 (folded in) · **Branch:** `feature/v2.1`

## Context

Macropad Studio can configure a macropad over serial, but getting firmware onto a
board still requires the Arduino IDE. New or bricked boards, and users who don't
want a toolchain, have no in-app path. This feature lets Studio flash the bundled
macropad firmware directly to an ESP32-S2 over the selected COM port.

There are two entry points, both backed by the same flash engine and the same
explicit warning that flashing **erases the whole chip**, including saved profiles:

1. **Recover / flash** — a selected port is **not** an enumerated macropad
   (`VID/PID 303A:80C5`): offer to flash a blank/unrecognized board.
2. **Update** — a macropad **is** detected, but its reported firmware version is
   **older than the bundled version**: offer to update it.

This is the backlogged high-risk "one-click firmware updater"; the design front-loads
safety (hard confirm, chip-type guard, honest download-mode handling).

## Goals / non-goals

- **Goal:** flash the bundled firmware image to an ESP32-S2 on a chosen port (blank
  board *or* an outdated macropad), with progress, safety confirmation, and clear
  recovery instructions.
- **Goal:** read a connected macropad's firmware version and surface an update when
  it's behind the bundled version.
- **Non-goal:** OTA/serial-protocol updates that preserve profiles (a flash always
  erases), and flashing non-ESP32-S2 targets.

## Architecture

```
Dashboard (renderer)                main process
  selected port not a macropad
      │  flashStart(port)           services/flasher.js
      ▼                             ├─ esptool-js (new dep)
  preload.flashStart ── IPC ──────▶ ├─ NodeSerialTransport (adapter over serialport)
      ▲                             │     Readable.toWeb / Writable.toWeb + port.set({dtr,rts})
      │  {type:"flash",phase,%}     └─ reads firmware/macropad.merged.bin (extraResources)
  serial event channel ◀───────────
```

### Bundled binary

- `firmware/macropad.merged.bin` — full 4 MB image, exported from the **verified**
  firmware via Arduino IDE/CLI, committed to the repo.
- `firmware/manifest.json` — `{ "version": "2.1.0" }` (drives the button label /
  surfaced version; single source of truth for what's bundled).
- `studio/package.json` → `build.extraResources` adds the `firmware/` directory.
- main resolves `process.resourcesPath/firmware` when packaged, else the project
  `firmware/` in dev.

### Flash engine — `studio/services/flasher.js` (main)

- Depends on **`esptool-js`** (new runtime dependency; pure JS, no asarUnpack).
- **`NodeSerialTransport`** adapter presents the `esptool-js` Transport surface over
  the existing `serialport`:
  - streams via `stream.Readable.toWeb(port)` / `stream.Writable.toWeb(port)`
  - reset signals via `port.set({ dtr, rts })`
  - `open()` / `close()` / `getInfo()` → `{ usbVendorId, usbProductId }`
- `flash(portPath, onProgress)`:
  1. Ensure the app's `SerialLink` is disconnected from `portPath`.
  2. Open the port; attempt esptool-js auto reset-to-bootloader.
  3. `esploader.main()` → read chip description.
  4. **Guard:** if the detected chip is not ESP32-S2, abort before any write.
  5. `writeFlash({ fileArray:[{data: merged, address: 0x0}], ... })`, forwarding
     write progress as a percentage to `onProgress`.
  6. `hardReset()`, then close the port.
- A connect/sync failure throws a typed error (`code: "NEEDS_DOWNLOAD_MODE"`) so the
  UI can show manual instructions rather than a raw stack.

### IPC + preload

- `flash:info` → `{ version, size }`.
- `flash:start` (portPath) → runs `flasher.flash`, streaming progress on the existing
  serial event channel as `{ type: "flash", phase, percent, error }`
  (`phase` ∈ `connecting | erasing | writing | done | error`).
- `flash:cancel` → best-effort abort of an in-flight flash.
- `preload.js` exposes `flashInfo()`, `flashStart(port)`, `flashCancel()`.

### Device firmware-version detection

- On connect, Studio issues the existing `status` CLI command and parses the
  `ver:<x.y.z>` field (firmware already prints `FW_VERSION` there). The parsed
  version is held in app state and emitted to the renderer.
- Compared against `firmware/manifest.json`'s `version` with a small semver compare:
  `device < bundled` ⇒ update available; `==`/`>` ⇒ up to date.

### Renderer / UX (Dashboard)

Both cards reuse the same flash engine, the **`Confirm`** modal (from the P1 work),
and the same progress view (phase label + % bar). Flashing always shows the erase
warning.

- **Recover / flash** — when a port is selected and `!isMacropad(selectedPort)`:
  - "No macropad detected on `<port>`." + ⚠️ "Flashing **erases everything** on the
    board, including all saved profiles." + **"Flash firmware v2.1.0"** button.
- **Update** — when a macropad is detected and `deviceVersion < bundledVersion`:
  - "Firmware update available — `v<device>` → `v2.1.0`." + the same ⚠️ erase warning
    (updating re-flashes the chip) + **"Update firmware"** button.
  - When `deviceVersion >= bundledVersion`: a quiet "Firmware up to date (`v…`)" line,
    no action.
- Shared outcomes: download-mode error → inline "Hold **BOOT**, tap **RESET**, then
  **Retry**"; success → "Done — the board will reboot; reconnect on the Device tab,"
  then re-scan ports.

## Safety

Layered because a wrong flash bricks hardware:
1. Hard `Confirm` gate with the erase warning.
2. **Chip-type guard** — only flash when an ESP32-S2 is detected; never a wrong board.
3. Honest, non-magical download-mode fallback (manual BOOT/RESET + Retry).
4. Offered **only** when no macropad is detected.

## Error handling

- Port busy / disconnect mid-flash → surfaced; `SerialLink` left disconnected; ports
  re-scanned.
- Wrong chip → abort pre-write with a clear message.
- Connect/sync failure → `NEEDS_DOWNLOAD_MODE` → manual instructions + Retry.
- Missing bundled binary → flasher card shows "firmware image not bundled" and the
  button is disabled (defensive; should not happen in a real build).

## Testing

- **On-device (user):** the actual flash — no hardware in the dev environment.
- **In dev:** `firmware/` resolves at runtime; `services/flasher.js` loads
  (`require("esptool-js")` succeeds); the ESP32-S2 chip-guard branch; the semver
  compare (device-version parsing from `status` + outdated detection); the UI flow —
  the recover card appears only when the port isn't a macropad, the update card only
  when `deviceVersion < bundledVersion`, the `Confirm` gate fires, and the
  `{type:"flash"}` progress events drive the bar — via `node build.js`, syntax checks,
  and a packaged smoke test.

## Build / version

- Folded into **v2.1.0** (no further version bump). Adds the `esptool-js` dependency
  and the bundled `firmware/` resources.

## Prerequisite (blocking)

Export `macropad.merged.bin` from the **verified** v2.1.0 firmware and place it in
`firmware/`. A trustworthy binary cannot be produced in the dev environment, and it
must be the firmware you've confirmed boots correctly.
