#include "input.h"
#include "config.h"
#include "leds.h"
#include "profiles.h"
#include "macro_engine.h"
#include <ArduinoJson.h>

static const uint8_t buttonPins[NUM_KEYS] = {
  BUTTON_PIN_1, BUTTON_PIN_2, BUTTON_PIN_3, BUTTON_PIN_4,
  BUTTON_PIN_5, BUTTON_PIN_6, BUTTON_PIN_7, BUTTON_PIN_8,
  BUTTON_PIN_9, BUTTON_PIN_10, BUTTON_PIN_11, BUTTON_PIN_12
};

// Hardware index -> natural (left-to-right) key number.
static const uint8_t HW_TO_LOGICAL[NUM_KEYS] = HW_TO_LOGICAL_INIT;

static uint8_t keyState[NUM_KEYS];
static unsigned long keyLastChange[NUM_KEYS];
static uint16_t keyDebounceMs[NUM_KEYS];   // per-key debounce window (hw-indexed)

static int baselineA = 0, baselineB = 0;
static unsigned long touchDebounceA = 0, touchDebounceB = 0;

void inputBegin() {
  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    keyState[i] = digitalRead(buttonPins[i]) ? 0 : 1;
    keyLastChange[i] = millis();
    keyDebounceMs[i] = DEFAULT_DEBOUNCE_MS;
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
    if (millis() - keyLastChange[i] <= keyDebounceMs[i]) continue;
    keyState[i] = raw;
    keyLastChange[i] = millis();
    int logical = HW_TO_LOGICAL[i];    // natural key number for profiles/app/EVT
    if (raw) {  // pressed
      ledsKeyDown(i);                  // highlight the physical LED (hardware index)
      Serial.printf("EVT:KEY %d 1\n", logical);   // live mirror to the app
      if (macroEngine.isRunning()) {
        macroEngine.abort();           // a new press cancels a running macro
      } else {
        macroEngine.startKey(logical);
      }
    } else {                           // released
      ledsKeyUp(i);                    // highlight fades out
      Serial.printf("EVT:KEY %d 0\n", logical);
    }
  }
}

// Refresh per-key debounce from the active profile (optional "debounce" field on
// a key; falls back to DEFAULT_DEBOUNCE_MS). Indexed by hardware position.
void inputApplyProfile() {
  for (int i = 0; i < NUM_KEYS; i++) keyDebounceMs[i] = DEFAULT_DEBOUNCE_MS;
  if (!profileLoaded || !profileDoc["keys"].is<JsonArray>()) return;
  for (JsonObjectConst ko : profileDoc["keys"].as<JsonArrayConst>()) {
    int id = ko["id"] | 0;
    if (id < 1 || id > NUM_KEYS || !ko["debounce"].is<int>()) continue;
    int db = constrain((int)(ko["debounce"] | DEFAULT_DEBOUNCE_MS), 0, 1000);
    for (int i = 0; i < NUM_KEYS; i++) if (HW_TO_LOGICAL[i] == id) { keyDebounceMs[i] = (uint16_t)db; break; }
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

// Touch gestures:
//   * short tap A / B            -> next / previous profile
//   * hold one pad alone >800ms  -> cycle the live LED pattern (not saved)
//   * both pads held >3s         -> unload profile (reset)
void scanTouch() {
  static bool lastA = false, lastB = false;
  static unsigned long aDown = 0, bDown = 0;
  static bool aHoldFired = false, bHoldFired = false;
  static bool aCompanion = false, bCompanion = false;  // other pad joined this press
  static unsigned long bothStart = 0;
  static bool bothFired = false;

  bool a = touchPressed(TOUCH_PIN_1);
  bool b = touchPressed(TOUCH_PIN_2);

  // Rising edges: start timing; note if the other pad is already down.
  if (a && !lastA) { aDown = millis(); aHoldFired = false; aCompanion = b; }
  if (b && !lastB) { bDown = millis(); bHoldFired = false; bCompanion = a; }
  if (a && b) { aCompanion = bCompanion = true; }   // any overlap cancels solo intent

  // Solo long-hold (pad A) -> cycle the live LED pattern, once per hold.
  if (a && !b && !aCompanion && !aHoldFired && millis() - aDown > TOUCH_HOLD_MS) {
    LedIdleMode m = ledsCycleIdleMode();
    ledsFlash(120, 60, 200);
    Serial.printf("EVT:IDLE %s\n", ledsModeName(m));
    aHoldFired = true;
  }
  // Solo long-hold (pad B) -> cycle backwards-ish (also just advances; one fire).
  if (b && !a && !bCompanion && !bHoldFired && millis() - bDown > TOUCH_HOLD_MS) {
    LedIdleMode m = ledsCycleIdleMode();
    ledsFlash(120, 60, 200);
    Serial.printf("EVT:IDLE %s\n", ledsModeName(m));
    bHoldFired = true;
  }

  // Falling edges: a short solo tap (no companion, no hold fired) switches profile.
  if (!a && lastA && !aCompanion && !aHoldFired &&
      millis() - aDown < TOUCH_HOLD_MS && millis() - touchDebounceA > TOUCH_DEBOUNCE_MS) {
    macroEngine.abort();
    int np = currentProfile + 1; if (np > NUM_PROFILES) np = 1;
    loadProfile(np);
    ledsFlash(0, 0, 200);
    touchDebounceA = millis();
  }
  if (!b && lastB && !bCompanion && !bHoldFired &&
      millis() - bDown < TOUCH_HOLD_MS && millis() - touchDebounceB > TOUCH_DEBOUNCE_MS) {
    macroEngine.abort();
    int np = currentProfile - 1; if (np < 1) np = NUM_PROFILES;
    loadProfile(np);
    ledsFlash(0, 200, 0);
    touchDebounceB = millis();
  }

  // Both held long -> reset (unload profile), fires once.
  if (a && b) {
    if (bothStart == 0) { bothStart = millis(); bothFired = false; }
    if (!bothFired && millis() - bothStart > TOUCH_RESET_MS) {
      macroEngine.abort();
      profileLoaded = false;
      ledsFlash(255, 0, 0);
      bothFired = true;
    }
  } else {
    bothStart = 0;
  }

  lastA = a;
  lastB = b;
}
