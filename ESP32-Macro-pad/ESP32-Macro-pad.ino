/* ---------------------------------------------------------------------------
   ESP32-S2 Macropad firmware v2 (Arduino-ESP32 core 3.2.x, ArduinoJson 7).

   Modular rewrite — see the individual translation units:
     config.h        board pins + limits
     hid_maps.*      key/modifier/media name tables
     hid_layer.*     USB HID (keyboard/mouse/consumer + telephony device)
     leds.*          NeoPixel + non-blocking animations
     storage.*       LittleFS read / atomic write + backups
     profiles.*      profile load/store + active state
     input.*         non-blocking buttons + capacitive touch
     macro_engine.*  cooperative, non-blocking macro runner
     cli.*           serial CLI + JSON upload protocol

   loop() never blocks on a running macro: actions are scheduled, so LEDs,
   touch, and serial stay live and any new keypress aborts.
   --------------------------------------------------------------------------- */
#include <Arduino.h>
#include "USB.h"

#include "config.h"
#include "leds.h"
#include "storage.h"
#include "profiles.h"
#include "hid_layer.h"
#include "input.h"
#include "macro_engine.h"
#include "cli.h"

#if ENABLE_WATCHDOG
#include "esp_task_wdt.h"
#endif

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 2000) delay(10);
  Serial.printf("Macropad v%s starting...\n", FW_VERSION);

  if (fsBegin()) Serial.println("LittleFS mounted");
  ensureAllDefaultProfiles();

  ledsBegin();
  inputBegin();

  // Advertise a stable, recognisable USB identity so the Studio app can
  // auto-detect this device by VID/PID regardless of its COM-port number.
  USB.VID(USB_VID);
  USB.PID(USB_PID);
  USB.manufacturerName(USB_MANUFACTURER);
  USB.productName(USB_PRODUCT);
  USB.begin();
  delay(10);
  hidBegin();
  delay(10);

#if ENABLE_WATCHDOG
  // The core initialises the task WDT; widen it to our loop budget and subscribe
  // the loop task. A stall past WDT_TIMEOUT_MS panics + reboots the device.
  esp_task_wdt_config_t wdtCfg = { .timeout_ms = WDT_TIMEOUT_MS, .idle_core_mask = 0, .trigger_panic = true };
  esp_task_wdt_reconfigure(&wdtCfg);
  esp_task_wdt_add(NULL);
#endif

  loadProfileSafe(1);   // safe-boot: if profile 1 is corrupt, rewrite default + retry

  Serial.println("Ready");
  cliBegin();
}

void loop() {
#if ENABLE_WATCHDOG
  esp_task_wdt_reset();
#endif
  handleSerialInput();
  scanTouch();
  scanKeys();
  macroEngine.tick();
  ledsTick();          // render one LED frame (frame-rate limited internally)

  delay(1);
}
