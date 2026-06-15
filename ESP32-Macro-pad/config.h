/* ---------------------------------------------------------------------------
   Macropad firmware v2 — board/build configuration.
   Lolin S2 PICO (ESP32-S2), Arduino-ESP32 core 3.2.x, ArduinoJson 7.
   --------------------------------------------------------------------------- */
#pragma once

#define FW_VERSION       "2.0.0"
#define SCHEMA_VERSION   1

// ----- USB identity (used by the Studio app for auto-detection) -----
#define USB_VID          0x303A           // Espressif
#define USB_PID          0x80C5           // this macropad build
#define USB_MANUFACTURER "DIY Macropad"
#define USB_PRODUCT      "ESP32-S2 Macropad"

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
#define LED_STREAM_DIV        3      // stream the framebuffer to the app every Nth frame (~20fps)

// ----- LED keyboard patterns (spatial; use KEY_POS grid below) -----
#define LED_GRID_COLS         4
#define LED_GRID_ROWS         4
#define LED_WAVE_SPEED        2.2f   // hue units/frame the diagonal wave scrolls
#define LED_WAVE_HUE_STEP     30.0f  // hue spread per grid step (x+y)
#define LED_COMET_SPEED       0.16f  // LEDs/frame the comet head advances
#define LED_COMET_TAIL        4.0f   // tail length in LEDs before it fully fades
#define LED_COMET_HUE_SPEED   1      // hue units/frame the comet colour cycles
#define LED_COMET_FLOOR       0.04f  // dim background level behind the comet
#define LED_TWINKLE_CHANCE    7      // /1000 chance per key per frame to ignite
#define LED_TWINKLE_RISE      0.16f  // per-frame rise of a new twinkle
#define LED_TWINKLE_FADE      0.05f  // per-frame fade of a twinkle
#define LED_TWINKLE_BOOST     1.0f   // how far a full twinkle pushes toward white
#define LED_RIPPLE_MAX        4      // concurrent ripples
#define LED_RIPPLE_SPEED      0.085f // grid-units/frame the ring expands
#define LED_RIPPLE_WIDTH      0.9f   // ring thickness in grid units
#define LED_RIPPLE_LIFE       4.6f   // grid-units of travel before a ripple dies

// Physical (col,row) of each hardware index (button + LED chain) on the 4x4
// grid (corners empty), captured from the device.
#define KEY_POS_INIT { \
  {2,0}, {1,0}, {0,1}, {1,1}, {2,1}, {3,1}, \
  {3,2}, {2,2}, {1,2}, {0,2}, {1,3}, {2,3}  \
}

// Natural, left-to-right / top-to-bottom key numbering (what the app, profiles
// and EVT:KEY use) mapped to/from the hardware index, derived from KEY_POS:
//   .  K1 K2  .
//  K3 K4 K5 K6
//  K7 K8 K9 K10
//   .  K11 K12 .
#define HW_TO_LOGICAL_INIT { 2, 1, 3, 4, 5, 6, 10, 9, 8, 7, 11, 12 }  // hw index -> logical key #
#define LOGICAL_TO_HW_INIT { 1, 0, 2, 3, 4, 5, 9, 8, 7, 6, 10, 11 }   // (logical#-1) -> hw index

// ----- Touch -----
#define TOUCH_THRESHOLD       300    // delta over baseline that counts as a press
#define TOUCH_DEBOUNCE_MS     300
#define TOUCH_HOLD_MS         800    // solo pad held this long = cycle LED pattern
#define TOUCH_RESET_MS        3000   // both pads held this long = unload profile

// ----- LittleFS backups -----
#define MAX_BACKUPS_PER_FILE  3

// ----- Telephony HID -----
// Custom Telephony-page HID device with a real report ID (fixes the old code's
// guessed report id 3). If it fails to enumerate on your host, set to 0.
#define ENABLE_TELEPHONY_HID  1
#define TELEPHONY_REPORT_ID   8
