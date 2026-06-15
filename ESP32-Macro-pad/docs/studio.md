# Macropad Studio

The desktop configurator — an Electron app with real device sync over serial,
a visual key editor with a live LED simulation, and local-first AI macro
generation. Every generated or edited macro is validated against the canonical
[action schema](configuration.md) before it can reach the device.

## Architecture

```
renderer/ (React UI, JSX)
    │  window.api  (preload.js, contextIsolation)
    ▼
main.js (Electron main)
    ├── services/serial.js    node-serialport: connect, ###BEGIN/###END upload,
    │                         cat/fsinfo/setprofile/setkey, line + capture parsing
    ├── services/ai/          Ollama (local) / OpenAI / Gemini via fetch,
    │                         schema-driven prompts + code validation + repair
    ├── services/schema.js    canonical action schema (JS port of schema.py)
    ├── services/store.js     settings + per-context templates (shared JSON files)
    ├── services/backup.js    timestamped local backups before every device write
    ├── services/contexts.js  focused-window process name → app context id
    └── services/activewin.js focused-window reporter (Windows, single PowerShell)
```

The renderer is plain React (no framework build): [`build.js`](../studio/build.js)
pre-transforms the JSX to JS with a vendored Babel so Electron can load it over
`file://`. React, ReactDOM and Babel are vendored in `renderer/vendor/`; the
Phosphor icon font and the web fonts are vendored into the build output too, so
the packaged app is fully offline.

### Renderer pieces

- **Key Editor** — click a key, build its action sequence (all 16 action types),
  drag to reorder, "Test" pushes the key live when connected.
- **`renderer/ledsim.js`** — a faithful JS port of the firmware LED engine
  (`leds.cpp`): same patterns, key positions and easing, so the on-screen keypad
  mirrors the device animation in real time.
- **Floating widget** (`renderer/widget.{html,js}`, `widget-preload.js`) — an
  always-on-top overlay that mirrors the physical key grid: key number, LED-colour
  dot, and name, flashing on press.
- **Auto-Switcher** — `services/activewin.js` + `services/contexts.js` map the
  focused application to a context so templates/profiles can follow the active app.

### Dev tool

- **`tools/gen-shortcuts.js`** — regenerates `macropad_default_templates.json`, a
  curated, schema-valid library of common shortcuts per app context. Edit the
  compact specs at the top and run `node tools/gen-shortcuts.js`.

## Run (development)

```sh
cd studio
npm install          # electron + serialport (postinstall rebuilds the native module)
node build.js        # transform renderer JSX -> renderer/build/*.js
npm start            # build + launch Electron
```

Re-run `node build.js` after editing anything in `renderer/*.jsx`.

## Using it

- **Device** tab: pick the COM port (the macropad enumerates as `303A:80C5`),
  Connect, then Load / Save profiles and watch the live console + flash gauge.
  A timestamped backup is written under `device_backups/` before every save.
- **Key Editor**: edit a key's action sequence with the live LED preview; "Test"
  pushes it to the device when connected.
- **AI** tab: generate context shortcuts. Output is parsed, repaired and
  schema-validated in `services/ai` + `services/schema`; only valid macros are
  kept. Needs Ollama running locally (default) or a cloud key set in **Settings**
  (stored in the gitignored `macropad_settings.json`).

## Relationship to the Python tooling

Studio is the primary GUI. The [`configurator/`](../configurator) Python package
is kept as the canonical schema source, the test suite (`tests/`), and
firmware-facing tooling. Studio reads/writes the same `macropad_settings.json`
and `macropad_templates.json`, so the two stay interchangeable.

## Packaging

See [build-and-release.md](build-and-release.md) for building the Windows
installer.
