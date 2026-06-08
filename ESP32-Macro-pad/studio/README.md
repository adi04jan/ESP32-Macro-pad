# Macropad Studio

The desktop configurator for the ESP32-S2 macropad — an Electron app built from
the `APP_assets` "Macropad Studio" design. Real device sync over serial and
local-first AI macro generation, with every generated/edited macro validated
against the canonical action schema before it can reach the device.

## Architecture

```
renderer/ (React UI, from APP_assets)
    │  window.api  (preload.js, contextIsolation)
    ▼
main.js (Electron main)
    ├── services/serial.js   node-serialport: connect, ###BEGIN/###END upload,
    │                        cat/fsinfo/setprofile/setkey, line+capture parsing
    ├── services/ai/         Ollama (local) / OpenAI / Gemini via fetch,
    │                        schema-driven prompts + code validation + repair
    ├── services/schema.js   canonical action schema (JS port of configurator/schema.py)
    └── services/store.js    settings + per-context templates (shared JSON files)
```

The renderer is plain React (no framework build): `build.js` pre-transforms the
JSX to JS with the vendored Babel so Electron can load it over `file://`. React,
ReactDOM and Babel are vendored in `renderer/vendor/` (offline); the Phosphor
icon font and Google Fonts load from CDN.

## Run (development)

```sh
cd studio
npm install            # electron + serialport (already done if node_modules exists)
node build.js          # transform renderer JSX -> renderer/build/*.js
npm start              # launch Electron
```

Re-run `node build.js` after editing anything in `renderer/*.jsx`.

## Build a Windows installer

```sh
npm run dist           # electron-builder -> studio/dist-build/
```

## Using it

- **Device** tab: pick the COM port (the macropad enumerates as `303A:80C2`),
  Connect, then Load / Save profiles and watch the live console + flash gauge.
- **Key Editor**: click a key, build its action sequence (all 16 action types),
  drag to reorder, "Test" pushes the key live when connected.
- **AI** tab / floating widget: generate context shortcuts. Output is parsed,
  repaired, and schema-validated in `services/ai` + `services/schema`; only valid
  macros are kept. Needs Ollama running locally (default) or a cloud key in
  **Settings**.

## Relationship to the Python tooling

Studio is the primary GUI. The `configurator/` Python package is kept as the
canonical schema source, the test suite, and firmware-facing tooling. Studio
reads/writes the same `macropad_settings.json` and `macropad_templates.json`, so
the two stay interchangeable. The old CustomTkinter UI has been retired.
