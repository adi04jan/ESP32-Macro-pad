#include "input.h"
#include "config.h"
#include "leds.h"
#include "profiles.h"
#include "macro_engine.h"

static const uint8_t buttonPins[NUM_KEYS] = {
  BUTTON_PIN_1, BUTTON_PIN_2, BUTTON_PIN_3, BUTTON_PIN_4,
  BUTTON_PIN_5, BUTTON_PIN_6, BUTTON_PIN_7, BUTTON_PIN_8,
  BUTTON_PIN_9, BUTTON_PIN_10, BUTTON_PIN_11, BUTTON_PIN_12
};

static uint8_t keyState[NUM_KEYS];
static unsigned long keyLastChange[NUM_KEYS];

static int baselineA = 0, baselineB = 0;
static unsigned long touchDebounceA = 0, touchDebounceB = 0;

void inputBegin() {
  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    keyState[i] = digitalRead(buttonPins[i]) ? 0 : 1;
    keyLastChange[i] = millis();
  }
  pinMode(LED_PIN_1, OUTPUT);
  pinMode(LED_PIN_2, OUTPUT);
  pinMode(LED_PIN_3, OUTPUT);
  updateProfileLEDs();

  // Stable touch baseline.
  delay(10);
  long sumA = 0, sumB = 0;
  const int samples = 8;
  for (int i = 0; i < samples; ++i) {
    sumA += touchRead(TOUCH_PIN_1);
    sumB += touchRead(TOUCH_PIN_2);
    delay(20);
  }
  baselineA = (int)(sumA / samples);
  baselineB = (int)(sumB / samples);
  Serial.printf("Touch baseline A=%d B=%d\n", baselineA, baselineB);
}

// Non-blocking debounce: register a press the instant the level is stable past
// the debounce window — no blocking delay() inside the scan.
void scanKeys() {
  for (int i = 0; i < NUM_KEYS; i++) {
    uint8_t raw = (digitalRead(buttonPins[i]) == LOW) ? 1 : 0;
    if (raw == keyState[i]) continue;
    if (millis() - keyLastChange[i] <= DEFAULT_DEBOUNCE_MS) continue;
    keyState[i] = raw;
    keyLastChange[i] = millis();
    if (raw) {  // pressed
      if (macroEngine.isRunning()) {
        macroEngine.abort();           // a new press cancels a running macro
      } else {
        macroEngine.startKey(i + 1, i);
      }
    }
  }
}

static bool touchPressed(int pin) {
  long sum = 0;
  for (int i = 0; i < 4; i++) {
    sum += touchRead(pin);
    delayMicroseconds(500);
  }
  int v = sum / 4;
  int base = (pin == TOUCH_PIN_1) ? baselineA : baselineB;
  return (v - base) > TOUCH_THRESHOLD;   // S2 touch value rises when touched
}

void scanTouch() {
  static bool lastA = false, lastB = false;
  static unsigned long bothStart = 0;

  bool a = touchPressed(TOUCH_PIN_1);
  bool b = touchPressed(TOUCH_PIN_2);

  if (a && !lastA && millis() - touchDebounceA > TOUCH_DEBOUNCE_MS) {
    macroEngine.abort();
    int np = currentProfile + 1;
    if (np > NUM_PROFILES) np = 1;
    loadProfile(np);
    flashAll(0, 0, 200, 1, 120, 60);
    touchDebounceA = millis();
  }
  if (b && !lastB && millis() - touchDebounceB > TOUCH_DEBOUNCE_MS) {
    macroEngine.abort();
    int np = currentProfile - 1;
    if (np < 1) np = NUM_PROFILES;
    loadProfile(np);
    flashAll(0, 200, 0, 1, 120, 60);
    touchDebounceB = millis();
  }

  // Both held for 3s -> reset (unload profile).
  if (a && b) {
    if (bothStart == 0) bothStart = millis();
    if (millis() - bothStart > 3000) {
      macroEngine.abort();
      profileLoaded = false;
      flashAll(255, 0, 0, 3, 120, 80);
      bothStart = 0;
    }
  } else {
    bothStart = 0;
  }

  lastA = a;
  lastB = b;
}
