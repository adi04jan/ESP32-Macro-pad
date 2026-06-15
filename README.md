# ESP32 Macro-pad

ESP32-S2 (LOLIN S2 Pico) powered macropad — inspired by the Work Louder Creator
Micro, but built for programmers. **12 programmable keys, 12 WS2812 RGB LEDs,
USB HID, 3 JSON profiles, capacitive-touch profile switching**, and a desktop
configurator with local-first AI macro generation.

> **v2** — modular non-blocking firmware (ArduinoJson 7) + **Macropad Studio**,
> an Electron desktop app that replaces the old CustomTkinter configurator.

<img width="712" height="560" alt="ESP32 Macropad" src="https://github.com/user-attachments/assets/45e009f4-ea78-450a-b862-cfce8e7b1cef" />
<img width="709" height="698" alt="Macropad Studio" src="https://github.com/user-attachments/assets/0003f9b6-e20b-4d1a-904a-aaf0c55a2186" />

## Features

- **12 mechanical keys**, each able to run a sequence of any of 16 action types:
  keypress, combo, text, multiline script, mouse move/click, media & telephony
  keys, delays, repeat loops, hold/release, per-key LED colour, and profile
  switching.
- **12 WS2812 RGB LEDs** driven by a frame-based (~60 FPS) non-blocking engine:
  per-key colours, press highlights, and idle animations (breathe, rainbow,
  wave, comet, twinkle, ripple).
- **USB HID** keyboard + mouse + media + telephony composite device.
- **3 user profiles** stored on LittleFS, switchable from **2 capacitive touch
  pads** (next / previous / hold-to-reset).
- **Serial CLI** for diagnostics and live edits, plus a JSON upload protocol.
- **Macropad Studio** desktop app: device sync, a visual key editor with a live
  LED simulation, an always-on-top key overlay, and AI macro generation
  (Ollama / OpenAI / Gemini) where every macro is schema-validated before it
  reaches the device.

## Repository layout

```
ESP32-Macro-pad/
├── ESP32-Macro-pad.ino, *.cpp/*.h   firmware (modular, non-blocking)
├── config.h                          board/build configuration
├── data/profile{1,2,3}.json          example profiles
├── configurator/                     Python package: canonical action schema + tooling
├── tests/                            Python test suite for the schema/tooling
├── studio/                           Macropad Studio (Electron desktop app)
├── tools/key_led_mapper/             firmware diagnostic sketch
└── docs/                             full documentation (start here)
```

## Quick start

**Flash the firmware** — open `ESP32-Macro-pad/ESP32-Macro-pad.ino` in the
Arduino IDE for a LOLIN S2 Pico (Arduino-ESP32 3.2.x, ArduinoJson 7, USB-OTG /
TinyUSB mode). See [docs/firmware.md](ESP32-Macro-pad/docs/firmware.md).

**Configure it** — install Macropad Studio (grab the
`Macropad Studio-<version>-setup.exe` from the
[Releases](../../releases) page) or run it from source:

```sh
cd ESP32-Macro-pad/studio
npm install
npm start
```

## Documentation

Full docs live in [`ESP32-Macro-pad/docs/`](ESP32-Macro-pad/docs/):

- [Firmware](ESP32-Macro-pad/docs/firmware.md) — architecture, pin map, serial CLI, build & flash
- [Configuration](ESP32-Macro-pad/docs/configuration.md) — profile/settings formats and the action schema
- [Macropad Studio](ESP32-Macro-pad/docs/studio.md) — the desktop app
- [Build & Release](ESP32-Macro-pad/docs/build-and-release.md) — installer + GitHub release

## Hardware

LOLIN S2 Pico (ESP32-S2) · 12 mechanical switches · 12 WS2812 RGB LEDs · 2
capacitive touch pads. USB identity `303A:80C5`. Full pin map in
[`config.h`](ESP32-Macro-pad/config.h).

## Developer

**Aditya Biswas**

- GitHub: [@adi04jan](https://github.com/adi04jan)
- LinkedIn: [aditya-biswas](https://www.linkedin.com/in/aditya-biswas-6409b78b/)

## License

MIT © Aditya Biswas.
