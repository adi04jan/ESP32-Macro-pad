#include "leds.h"
#include "config.h"

Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

// Breathe state.
static uint8_t breatheValue = 0;
static int breatheDir = 1;
static unsigned long breatheLast = 0;
static const uint16_t breatheDelay = 10;

// Rainbow state.
static uint16_t rainbowPos = 0;
static unsigned long rainbowLast = 0;
static const uint16_t rainbowSpeed = 30;

void ledsBegin() {
  strip.begin();
  strip.setBrightness(64);
  strip.clear();
  strip.show();
}

void setKeyLed(int index, uint8_t r, uint8_t g, uint8_t b) {
  if (index < 0 || index >= WS_LED_COUNT) return;
  strip.setPixelColor(index, strip.Color(r, g, b));
  strip.show();
}

void ledsSetAll(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < strip.numPixels(); i++)
    strip.setPixelColor(i, strip.Color(r, g, b));
  strip.show();
}

void flashAll(uint8_t r, uint8_t g, uint8_t b, int times, int msOn, int msOff) {
  for (int t = 0; t < times; ++t) {
    ledsSetAll(r, g, b);
    delay(msOn);
    strip.clear();
    strip.show();
    delay(msOff);
  }
}

void breatheTick(uint8_t r, uint8_t g, uint8_t b) {
  unsigned long now = millis();
  if (now - breatheLast < breatheDelay) return;
  breatheLast = now;
  if (breatheDir > 0) {
    if (breatheValue >= 255) breatheDir = -1; else breatheValue++;
  } else {
    if (breatheValue == 0) breatheDir = 1; else breatheValue--;
  }
  for (int i = 0; i < strip.numPixels(); i++)
    strip.setPixelColor(i, strip.Color((r * breatheValue) / 255,
                                        (g * breatheValue) / 255,
                                        (b * breatheValue) / 255));
  strip.show();
}

void rainbowTick() {
  unsigned long now = millis();
  if (now - rainbowLast < rainbowSpeed) return;
  rainbowLast = now;
  for (uint16_t i = 0; i < strip.numPixels(); i++) {
    uint8_t hue = (i * 256 / strip.numPixels() + rainbowPos) & 255;
    uint8_t r = (hue < 85) ? (hue * 3) : (hue < 170) ? (255 - (hue - 85) * 3) : 0;
    uint8_t g = (hue < 85) ? 0 : (hue < 170) ? ((hue - 85) * 3) : (255 - (hue - 170) * 3);
    uint8_t b = (hue < 85) ? (255 - hue * 3) : (hue < 170) ? 0 : ((hue - 170) * 3);
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
  rainbowPos = (rainbowPos + 1) & 255;
}
