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

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 2000) delay(10);
  Serial.printf("Macropad v%s starting...\n", FW_VERSION);

  if (fsBegin()) Serial.println("LittleFS mounted");
  ensureAllDefaultProfiles();

  ledsBegin();
  inputBegin();

  USB.begin();
  delay(10);
  hidBegin();
  delay(10);

  loadProfile(1);

  Serial.println("Ready");
  cliBegin();
}

void loop() {
  handleSerialInput();
  scanTouch();
  scanKeys();
  macroEngine.tick();

  if (!macroEngine.isRunning()) {
    if (idleAnimation == 1) breatheTick(64, 64, 64);
    else if (idleAnimation == 2) rainbowTick();
  }

  delay(1);
}
