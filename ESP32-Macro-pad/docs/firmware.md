# Firmware

Modular, non-blocking firmware for the LOLIN S2 Pico (ESP32-S2), built with the
Arduino-ESP32 core 3.2.x and ArduinoJson 7. Firmware version `2.0.0`,
schema version `1` (see [`config.h`](../config.h)).

## Modules

The sketch is split into focused translation units, each with a small header
interface:

| File | Responsibility |
|------|----------------|
| [`ESP32-Macro-pad.ino`](../ESP32-Macro-pad.ino) | Entry point: `setup()` wires the modules, `loop()` polls input, runs the LED frame engine, and services the serial CLI — all non-blocking. |
| [`config.h`](../config.h) | Board/build configuration: pins, counts, limits, LED tuning, key-position grid. |
| [`input.cpp` / `.h`](../input.cpp) | Debounced button scan and capacitive-touch handling (profile switching, LED-pattern cycling, reset). |
| [`profiles.cpp` / `.h`](../profiles.cpp) | Load/save/switch the 3 user profiles; maps logical key numbers ⇄ hardware index. |
| [`macro_engine.cpp` / `.h`](../macro_engine.cpp) | `executeAction` — the runtime that interprets each action type. The schema is derived from this. |
| [`leds.cpp` / `.h`](../leds.cpp) | Frame-based (~60 FPS) non-blocking LED engine: per-key framebuffer, easing, press highlights, idle animations, and framebuffer streaming to Studio. |
| [`hid_layer.cpp` / `.h`](../hid_layer.cpp) | USB HID composite device (keyboard, mouse, media, telephony). |
| [`hid_maps.cpp` / `.h`](../hid_maps.cpp) | Name → HID-usage lookup tables for keys, modifiers, and media — kept in lockstep with the schema enums. |
| [`storage.cpp` / `.h`](../storage.cpp) | LittleFS filesystem: profile JSON, backups (`MAX_BACKUPS_PER_FILE`). |
| [`cli.cpp` / `.h`](../cli.cpp) | Serial CLI and the JSON upload protocol. |

## Hardware / pin map

Defined in [`config.h`](../config.h). Key values:

- **USB identity:** VID `0x303A` (Espressif), PID `0x80C5`. Studio auto-detects
  the device by this `303A:80C5` pair.
- **Keys:** 12 buttons on GPIO 5, 1, 4, 7, 6, 9, 12, 10, 11, 8, 13, 14.
  > ⚠️ `BUTTON_PIN_2` uses GPIO1, which is UART TX on many ESP32 boards and can
  > conflict with serial output. Move it if a free GPIO is available.
- **LEDs:** 12 WS2812 on GPIO 36 (`WS_LED_PIN`).
- **Touch:** GPIO 2 (next profile) and GPIO 3 (previous profile).
- **Serial:** 115200 baud.

### Key numbering

Hardware index (button + LED chain order) is remapped to a natural,
left-to-right / top-to-bottom logical numbering used by the app, profiles, and
`EVT:KEY` events (see `KEY_POS_INIT` / `HW_TO_LOGICAL_INIT` in `config.h`):

```
 .  K1  K2  .
K3 K4  K5  K6
K7 K8  K9  K10
 .  K11 K12 .
```

## Touch controls

| Gesture | Action |
|---------|--------|
| Tap GPIO2 | Next profile |
| Tap GPIO3 | Previous profile |
| Hold one pad (≥800 ms) | Cycle the idle LED pattern |
| Hold both pads (≥3 s) | Unload / reset profile |

## Serial CLI

Connect at 115200 baud (Studio's Device tab, or any serial monitor). Commands:

| Command | Description |
|---------|-------------|
| `help` | List commands |
| `ls` | List files on LittleFS |
| `cat <file>` | Print a file |
| `status` | Firmware/profile status |
| `fsinfo` | Filesystem usage (used/total bytes) |
| `setprofile <n>` | Switch to profile `n` (1–3) |
| `setkey <id> <json-actions>` | Replace one key's action list |
| `setled <k> <r> <g> <b>` | Set key `k`'s LED colour live |
| `setidle <name>` | Set the idle animation (`none`, `breathe`, `rainbow`, `flash`, `wave`, `comet`, `twinkle`, `ripple`) |
| `reboot` | Restart the device |

### Profile upload protocol

A whole profile file is uploaded between sentinel lines:

```
###BEGIN### profile1.json
{ ...profile JSON... }
###END###
```

Uploads are capped (`SERIAL_UPLOAD_MAX`, 16 KB) and time out
(`SERIAL_UPLOAD_TIMEOUT_MS`) if stalled. Studio uses this protocol for Save.

## Build & flash

Open [`ESP32-Macro-pad.ino`](../ESP32-Macro-pad.ino) in the Arduino IDE (or
`arduino-cli`) with:

- **Board:** LOLIN S2 Pico / ESP32-S2 Dev Module
- **Core:** Arduino-ESP32 3.2.x
- **Libraries:** ArduinoJson 7, Adafruit NeoPixel
- **USB mode:** USB-OTG (TinyUSB) so the HID + CDC composite enumerates
- **Partition scheme:** use [`partitions.csv`](../partitions.csv)

Compiled artifacts are local-only and git-ignored (`build_out/`,
`build_mapper/`).

## Diagnostics tool

[`tools/key_led_mapper/key_led_mapper.ino`](../tools/key_led_mapper) is a
standalone sketch used to discover the physical (col,row) of each hardware
index, which produced the `KEY_POS_INIT` grid in `config.h`.
