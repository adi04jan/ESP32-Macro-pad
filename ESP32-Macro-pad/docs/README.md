# ESP32 Macropad — Documentation

Documentation for the ESP32-S2 macropad: the firmware, the **Macropad Studio**
desktop configurator, the shared configuration format, and how to build a
release.

| Doc | What it covers |
|-----|----------------|
| [firmware.md](firmware.md) | Firmware architecture, modules, pin map, serial CLI, build & flash |
| [configuration.md](configuration.md) | Profile/settings/template file formats and the canonical action schema |
| [studio.md](studio.md) | Macropad Studio desktop app — architecture, services, dev workflow |
| [build-and-release.md](build-and-release.md) | Building the Windows installer and cutting a GitHub release |

## At a glance

- **Hardware:** LOLIN S2 Pico (ESP32-S2), 12 mechanical keys, 12 WS2812 RGB LEDs,
  2 capacitive touch pads.
- **Firmware:** modular, non-blocking Arduino C++ (core 3.2.x, ArduinoJson 7).
  USB HID keyboard + mouse + media/telephony. 3 profiles stored on LittleFS.
- **Studio:** Electron desktop app — serial device sync, visual key editor, live
  LED simulation, and local-first AI macro generation.
- **Single source of truth:** the action schema in
  [`configurator/schema.py`](../configurator/schema.py) (mirrored in
  [`studio/services/schema.js`](../studio/services/schema.js) and the firmware).
  A macro that validates is guaranteed executable on the device.
