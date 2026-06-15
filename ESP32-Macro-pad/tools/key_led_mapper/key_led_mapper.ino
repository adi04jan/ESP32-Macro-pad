/* ---------------------------------------------------------------------------
   Key / LED layout mapper — standalone diagnostic for the ESP32-S2 macropad.

   Flash this temporarily (it has no HID, won't type anything) to discover how
   the WS2812 LED chain is wired relative to the physical keys.

   HOW TO USE (open Serial Monitor @ 115200):
     * Press any key  -> prints the button index (1..12) and lights the LED with
                         the SAME index. If the lit LED is NOT under the key you
                         pressed, the chain order differs -> note the mismatch.
     * Type  c <Enter> -> "chase": lights LED 0,1,2,...,11 one at a time (1s each)
                         and prints each index. Watch which PHYSICAL key lights
                         at each step and write it down — that is the definitive
                         LED-index -> key map.
     * Type  a number (0-11) <Enter> -> light just that LED index.
     * Type  k <Enter> -> "key walk": tells you to press keys 1..12 in order and
                         logs the button index it actually detects for each.

   Send the results back and the real firmware's LED mapping will be corrected.
   --------------------------------------------------------------------------- */

#include <Adafruit_NeoPixel.h>

#define WS_LED_PIN    36
#define WS_LED_COUNT  12
#define NUM_KEYS      12

// Button GPIOs in key order 1..12 (must match the main firmware's config.h).
const uint8_t buttonPins[NUM_KEYS] = { 5, 1, 4, 7, 6, 9, 12, 10, 11, 8, 13, 14 };

Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

uint8_t keyState[NUM_KEYS];
unsigned long keyLastChange[NUM_KEYS];
const unsigned long DEBOUNCE_MS = 40;

void lightOnly(int idx, uint8_t r, uint8_t g, uint8_t b) {
  strip.clear();
  if (idx >= 0 && idx < WS_LED_COUNT) strip.setPixelColor(idx, strip.Color(r, g, b));
  strip.show();
}

void chase() {
  Serial.println("CHASE: each LED lights for 1s in chain order 0..11.");
  for (int i = 0; i < WS_LED_COUNT; i++) {
    Serial.printf("  LED index %d lit  -> which physical key is this?\n", i);
    lightOnly(i, 0, 180, 255);
    delay(1000);
  }
  strip.clear();
  strip.show();
  Serial.println("CHASE done.\n");
}

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 2000) delay(10);

  strip.begin();
  strip.setBrightness(90);
  strip.clear();
  strip.show();

  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    keyState[i] = digitalRead(buttonPins[i]) ? 0 : 1;
    keyLastChange[i] = millis();
  }

  Serial.println("\n=== Key/LED Mapper ===");
  Serial.println("Press keys (lights same-index LED). Commands: 'c' chase, 'k' key-walk, 0-11 light one LED.");
}

void keyWalk() {
  Serial.println("KEY WALK: press your keys in order 1..12 (your correct visual order).");
  for (int expected = 1; expected <= NUM_KEYS; expected++) {
    Serial.printf("  Press your key #%d ... ", expected);
    Serial.flush();
    int got = -1;
    while (got < 0) {
      for (int i = 0; i < NUM_KEYS; i++) {
        bool down = digitalRead(buttonPins[i]) == LOW;
        if (down && keyState[i] == 0 && millis() - keyLastChange[i] > DEBOUNCE_MS) {
          keyState[i] = 1; keyLastChange[i] = millis(); got = i; break;
        }
        if (!down && keyState[i] == 1 && millis() - keyLastChange[i] > DEBOUNCE_MS) {
          keyState[i] = 0; keyLastChange[i] = millis();
        }
      }
      delay(2);
    }
    lightOnly(got, 0, 255, 80);
    Serial.printf("detected button index %d (GPIO %d)%s\n", got + 1, buttonPins[got],
                  (got + 1 == expected) ? "" : "  <-- DIFFERS from expected");
    delay(250);
  }
  strip.clear(); strip.show();
  Serial.println("KEY WALK done.\n");
}

void handleSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;
  if (line.equalsIgnoreCase("c")) { chase(); return; }
  if (line.equalsIgnoreCase("k")) { keyWalk(); return; }
  int n = line.toInt();
  if (n >= 0 && n < WS_LED_COUNT) {
    Serial.printf("Lighting LED index %d\n", n);
    lightOnly(n, 255, 255, 255);
  }
}

void scanKeys() {
  for (int i = 0; i < NUM_KEYS; i++) {
    bool down = digitalRead(buttonPins[i]) == LOW;
    if ((down ? 1 : 0) == keyState[i]) continue;
    if (millis() - keyLastChange[i] <= DEBOUNCE_MS) continue;
    keyState[i] = down ? 1 : 0;
    keyLastChange[i] = millis();
    if (down) {
      Serial.printf("KEY %d pressed (GPIO %d) -> lighting LED index %d\n", i + 1, buttonPins[i], i);
      lightOnly(i, 255, 255, 255);
    }
  }
}

void loop() {
  handleSerial();
  scanKeys();
  delay(2);
}
