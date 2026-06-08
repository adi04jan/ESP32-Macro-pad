/* ---------------------------------------------------------------------------
   Macropad firmware v2 — board/build configuration.
   Lolin S2 PICO (ESP32-S2), Arduino-ESP32 core 3.2.x, ArduinoJson 7.
   --------------------------------------------------------------------------- */
#pragma once

#define FW_VERSION       "2.0.0"
#define SCHEMA_VERSION   1

// ----- Pins (Lolin S2 Pico) -----
#define TOUCH_PIN_1   2
#define TOUCH_PIN_2   3

#define WS_LED_PIN    36
#define WS_LED_COUNT  12

#define LED_PIN_1     38
#define LED_PIN_2     39
#define LED_PIN_3     40

// NOTE: GPIO1 is UART TX on many ESP32 boards. Using it for BUTTON_PIN_2 can
// conflict with Serial output; move it if a free GPIO is available.
#define BUTTON_PIN_1   5
#define BUTTON_PIN_2   1   // <-- WARNING: GPIO1 = UART TX
#define BUTTON_PIN_3   4
#define BUTTON_PIN_4   7
#define BUTTON_PIN_5   6
#define BUTTON_PIN_6   9
#define BUTTON_PIN_7   12
#define BUTTON_PIN_8   10
#define BUTTON_PIN_9   11
#define BUTTON_PIN_10  8
#define BUTTON_PIN_11  13
#define BUTTON_PIN_12  14

// ----- Counts / limits (mirror configurator/schema.py) -----
#define NUM_KEYS              12
#define NUM_PROFILES          3
#define DEFAULT_DEBOUNCE_MS   50
#define SERIAL_BAUD           115200
#define MAX_TEXT_LEN          4096
#define MAX_REPEAT_COUNT      50

// ----- Macro engine -----
#define TEXT_CHAR_DELAY_MS    12     // pacing for streamed text typing
#define MACRO_MAX_DEPTH       4      // nested-repeat recursion limit

// ----- Serial upload safety -----
#define SERIAL_UPLOAD_MAX        16384   // cap recorded JSON upload size (bytes)
#define SERIAL_UPLOAD_TIMEOUT_MS 5000    // abort an upload stalled this long

// ----- LED engine (frame-based, non-blocking) -----
#define LED_BRIGHTNESS        80     // global NeoPixel brightness (0-255)
#define LED_FRAME_MS          16     // ~60 FPS render cadence
#define LED_EASE              0.22f  // per-frame easing of colour toward target
#define LED_PRESS_RISE        1.0f   // press highlight rises instantly to full
#define LED_PRESS_FADE        0.12f  // per-frame fade of a released key's highlight
#define LED_FLASH_FADE        0.07f  // per-frame fade of a global flash pulse
#define LED_BREATHE_SPEED     0.05f  // radians/frame for the sine breathe envelope
#define LED_BREATHE_FLOOR     0.12f  // breathe never dims fully to black
#define LED_RAINBOW_SPEED     2      // hue units/frame for the rainbow sweep

// ----- Touch -----
#define TOUCH_THRESHOLD       300    // delta over baseline that counts as a press
#define TOUCH_DEBOUNCE_MS     300

// ----- LittleFS backups -----
#define MAX_BACKUPS_PER_FILE  3

// ----- Telephony HID -----
// Custom Telephony-page HID device with a real report ID (fixes the old code's
// guessed report id 3). If it fails to enumerate on your host, set to 0.
#define ENABLE_TELEPHONY_HID  1
#define TELEPHONY_REPORT_ID   8
