/* Cooperative, non-blocking macro runner.

   On a keypress the key's actions are copied into a private document and run
   step-by-step from loop() via tick(). Delays and inter-action spacing become
   scheduled waits instead of blocking delay()s, so LEDs, touch, and serial stay
   responsive while a macro runs. A new keypress (or touch reset) aborts. */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "config.h"

class MacroEngine {
 public:
  void startKey(int keyId);
  void tick();
  void abort();
  bool isRunning() const { return running; }

 private:
  struct Frame { JsonArrayConst arr; size_t idx; int repeatLeft; };

  void execAction(JsonObjectConst act, unsigned long now);
  void finish();

  bool running = false;
  JsonDocument macroDoc;            // private copy of the key's action list
  Frame stack[MACRO_MAX_DEPTH];
  int depth = 0;
  unsigned long waitUntil = 0;
  int defaultDelay = 30;

  // Streamed text typing.
  bool inText = false;
  String curText;
  size_t textPos = 0;
};

extern MacroEngine macroEngine;
