#include "leds.h"
#include "config.h"
#include "profiles.h"
#include <math.h>

Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

// Per-key state.
static uint8_t baseR[WS_LED_COUNT], baseG[WS_LED_COUNT], baseB[WS_LED_COUNT];
static float   curR[WS_LED_COUNT], curG[WS_LED_COUNT], curB[WS_LED_COUNT];
static float   press[WS_LED_COUNT];   // 0..1 white highlight per key
static bool    held[WS_LED_COUNT];    // key physically/logically down

// Idle + global effects.
static LedIdleMode idleMode = LED_IDLE_NONE;
static float breathePhase = 0.0f;
static uint16_t rainbowPhase = 0;
static float flashLevel = 0.0f;
static uint8_t flashR = 0, flashG = 0, flashB = 0;

static unsigned long lastFrame = 0;

static inline float clampf(float v) { return v < 0 ? 0 : (v > 255 ? 255 : v); }

// hue 0..255 -> rgb (same wheel as before).
static void wheel(uint8_t h, float &r, float &g, float &b) {
  r = (h < 85) ? (h * 3) : (h < 170) ? (255 - (h - 85) * 3) : 0;
  g = (h < 85) ? 0 : (h < 170) ? ((h - 85) * 3) : (255 - (h - 170) * 3);
  b = (h < 85) ? (255 - h * 3) : (h < 170) ? 0 : ((h - 170) * 3);
}

void ledsBegin() {
  strip.begin();
  strip.setBrightness(LED_BRIGHTNESS);
  strip.clear();
  strip.show();
  for (int i = 0; i < WS_LED_COUNT; i++) {
    baseR[i] = baseG[i] = baseB[i] = 0;
    curR[i] = curG[i] = curB[i] = 0;
    press[i] = 0; held[i] = false;
  }
}

void ledsSetBrightness(uint8_t b) { strip.setBrightness(b); }
void ledsSetIdleMode(LedIdleMode mode) { idleMode = mode; }

void ledsSetKeyBase(int i, uint8_t r, uint8_t g, uint8_t b) {
  if (i < 0 || i >= WS_LED_COUNT) return;
  baseR[i] = r; baseG[i] = g; baseB[i] = b;
}

void ledsSetAllBase(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < WS_LED_COUNT; i++) ledsSetKeyBase(i, r, g, b);
}

// Pull per-key resting colours and the idle animation from the loaded profile.
void ledsApplyProfile() {
  ledsSetAllBase(0, 0, 0);
  if (profileLoaded && profileDoc["keys"].is<JsonArray>()) {
    for (JsonObjectConst ko : profileDoc["keys"].as<JsonArrayConst>()) {
      int id = ko["id"] | 0;
      if (id < 1 || id > WS_LED_COUNT) continue;
      JsonArrayConst c = ko["led_color"].as<JsonArrayConst>();
      if (!c.isNull() && c.size() >= 3)
        ledsSetKeyBase(id - 1, c[0] | 0, c[1] | 0, c[2] | 0);
    }
  }
  const char *anim = profileDoc["idle_animation"] | "none";
  if (strcmp(anim, "breathe") == 0) idleMode = LED_IDLE_BREATHE;
  else if (strcmp(anim, "rainbow") == 0) idleMode = LED_IDLE_RAINBOW;
  else idleMode = LED_IDLE_NONE;
}

void ledsKeyDown(int i) { if (i >= 0 && i < WS_LED_COUNT) { held[i] = true; press[i] = LED_PRESS_RISE; } }
void ledsKeyUp(int i)   { if (i >= 0 && i < WS_LED_COUNT) held[i] = false; }

void ledsFlash(uint8_t r, uint8_t g, uint8_t b) { flashR = r; flashG = g; flashB = b; flashLevel = 1.0f; }

void ledsTick() {
  unsigned long now = millis();
  if (now - lastFrame < LED_FRAME_MS) return;
  lastFrame = now;

  // Advance idle phases.
  breathePhase += LED_BREATHE_SPEED;
  if (breathePhase > TWO_PI) breathePhase -= TWO_PI;
  rainbowPhase = (rainbowPhase + LED_RAINBOW_SPEED) & 0xFF;
  float breatheEnv = LED_BREATHE_FLOOR + (1.0f - LED_BREATHE_FLOOR) * 0.5f * (1.0f + sinf(breathePhase));

  for (int i = 0; i < WS_LED_COUNT; i++) {
    // Target colour for this key.
    float tr, tg, tb;
    if (idleMode == LED_IDLE_RAINBOW) {
      wheel((uint8_t)((i * 256 / WS_LED_COUNT + rainbowPhase) & 0xFF), tr, tg, tb);
    } else {
      tr = baseR[i]; tg = baseG[i]; tb = baseB[i];
      if (idleMode == LED_IDLE_BREATHE) { tr *= breatheEnv; tg *= breatheEnv; tb *= breatheEnv; }
    }

    // Ease current colour toward target.
    curR[i] += (tr - curR[i]) * LED_EASE;
    curG[i] += (tg - curG[i]) * LED_EASE;
    curB[i] += (tb - curB[i]) * LED_EASE;

    // Press highlight: sustain while held, fade after release.
    if (held[i]) press[i] = LED_PRESS_RISE;
    else if (press[i] > 0.002f) press[i] *= (1.0f - LED_PRESS_FADE);
    else press[i] = 0;

    // Blend toward white by the press level.
    float p = press[i];
    float orr = curR[i] * (1 - p) + 255 * p;
    float org = curG[i] * (1 - p) + 255 * p;
    float orb = curB[i] * (1 - p) + 255 * p;

    // Global flash pulse on top.
    if (flashLevel > 0.002f) {
      orr = orr * (1 - flashLevel) + flashR * flashLevel;
      org = org * (1 - flashLevel) + flashG * flashLevel;
      orb = orb * (1 - flashLevel) + flashB * flashLevel;
    }

    strip.setPixelColor(i, strip.Color((uint8_t)clampf(orr), (uint8_t)clampf(org), (uint8_t)clampf(orb)));
  }

  if (flashLevel > 0.002f) flashLevel *= (1.0f - LED_FLASH_FADE); else flashLevel = 0;
  strip.show();   // single update per frame
}
