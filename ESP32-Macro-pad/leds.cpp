#include "leds.h"
#include "config.h"
#include "profiles.h"
#include <math.h>

Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

// Physical (col,row) of every LED on the 4x4 grid (corners empty).
static const uint8_t KEY_POS[WS_LED_COUNT][2] = KEY_POS_INIT;
// Natural key number (1..12) -> hardware LED/chain index.
static const uint8_t LOGICAL_TO_HW[WS_LED_COUNT] = LOGICAL_TO_HW_INIT;

// Per-key state.
static uint8_t baseR[WS_LED_COUNT], baseG[WS_LED_COUNT], baseB[WS_LED_COUNT];
static float   curR[WS_LED_COUNT], curG[WS_LED_COUNT], curB[WS_LED_COUNT];
static float   press[WS_LED_COUNT];   // 0..1 white highlight per key
static bool    held[WS_LED_COUNT];    // key physically/logically down
static float   twk[WS_LED_COUNT];     // 0..1 twinkle bloom per key
static bool    twRising[WS_LED_COUNT]; // twinkle currently rising vs. fading

// Idle + global effects.
static LedIdleMode idleMode = LED_IDLE_NONE;
static float breathePhase = 0.0f;
static uint16_t rainbowPhase = 0;
static float wavePhase = 0.0f;
static float cometHead = 0.0f;
static uint8_t cometHue = 0;
static float flashLevel = 0.0f;
static uint8_t flashR = 0, flashG = 0, flashB = 0;

// Reactive ripples (ripple idle mode).
struct Ripple { float cx, cy, age; bool active; };
static Ripple ripples[LED_RIPPLE_MAX];

static unsigned long lastFrame = 0;

// Live frame streaming to the app (exact, in-sync mirror).
static uint8_t ledFrame[WS_LED_COUNT * 3];
static uint8_t streamCount = 0;
static const char HEXC[] = "0123456789abcdef";

static inline float clampf(float v) { return v < 0 ? 0 : (v > 255 ? 255 : v); }
static inline float clamp01(float v) { return v < 0 ? 0 : (v > 1 ? 1 : v); }

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
    press[i] = 0; held[i] = false; twk[i] = 0;
  }
  for (int i = 0; i < LED_RIPPLE_MAX; i++) ripples[i].active = false;
}

void ledsSetBrightness(uint8_t b) { strip.setBrightness(b); }
void ledsSetIdleMode(LedIdleMode mode) { idleMode = mode; }
LedIdleMode ledsGetIdleMode() { return idleMode; }

LedIdleMode ledsModeFromName(const char *name) {
  if (!name) return LED_IDLE_NONE;
  if (!strcmp(name, "breathe")) return LED_IDLE_BREATHE;
  if (!strcmp(name, "rainbow")) return LED_IDLE_RAINBOW;
  if (!strcmp(name, "wave"))    return LED_IDLE_WAVE;
  if (!strcmp(name, "comet"))   return LED_IDLE_COMET;
  if (!strcmp(name, "twinkle")) return LED_IDLE_TWINKLE;
  if (!strcmp(name, "ripple"))  return LED_IDLE_RIPPLE;
  return LED_IDLE_NONE;
}

const char *ledsModeName(LedIdleMode m) {
  switch (m) {
    case LED_IDLE_BREATHE: return "breathe";
    case LED_IDLE_RAINBOW: return "rainbow";
    case LED_IDLE_WAVE:    return "wave";
    case LED_IDLE_COMET:   return "comet";
    case LED_IDLE_TWINKLE: return "twinkle";
    case LED_IDLE_RIPPLE:  return "ripple";
    default:               return "none";
  }
}

LedIdleMode ledsCycleIdleMode() {
  idleMode = (LedIdleMode)(((int)idleMode + 1) % LED_IDLE_COUNT);
  // Reset transient pattern state so the new mode starts clean.
  for (int i = 0; i < WS_LED_COUNT; i++) twk[i] = 0;
  for (int i = 0; i < LED_RIPPLE_MAX; i++) ripples[i].active = false;
  return idleMode;
}

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
        ledsSetKeyBase(LOGICAL_TO_HW[id - 1], c[0] | 0, c[1] | 0, c[2] | 0);   // natural id -> physical LED
    }
  }
  idleMode = ledsModeFromName(profileDoc["idle_animation"] | "none");
}

static void spawnRipple(int i) {
  int slot = -1;
  float oldest = -1;
  for (int r = 0; r < LED_RIPPLE_MAX; r++) {
    if (!ripples[r].active) { slot = r; break; }
    if (ripples[r].age > oldest) { oldest = ripples[r].age; slot = r; }  // recycle the most-faded
  }
  ripples[slot].cx = KEY_POS[i][0];
  ripples[slot].cy = KEY_POS[i][1];
  ripples[slot].age = 0;
  ripples[slot].active = true;
}

void ledsKeyDown(int i) {
  if (i < 0 || i >= WS_LED_COUNT) return;
  held[i] = true; press[i] = LED_PRESS_RISE;
  if (idleMode == LED_IDLE_RIPPLE) spawnRipple(i);
}
void ledsKeyUp(int i)   { if (i >= 0 && i < WS_LED_COUNT) held[i] = false; }

void ledsFlash(uint8_t r, uint8_t g, uint8_t b) { flashR = r; flashG = g; flashB = b; flashLevel = 1.0f; }

void ledsTick() {
  unsigned long now = millis();
  if (now - lastFrame < LED_FRAME_MS) return;
  lastFrame = now;

  // Advance shared phases.
  breathePhase += LED_BREATHE_SPEED;
  if (breathePhase > TWO_PI) breathePhase -= TWO_PI;
  rainbowPhase = (rainbowPhase + LED_RAINBOW_SPEED) & 0xFF;
  wavePhase += LED_WAVE_SPEED;
  if (wavePhase > 256.0f) wavePhase -= 256.0f;
  cometHead += LED_COMET_SPEED;
  if (cometHead >= WS_LED_COUNT) cometHead -= WS_LED_COUNT;
  cometHue = (uint8_t)(cometHue + LED_COMET_HUE_SPEED);
  float breatheEnv = LED_BREATHE_FLOOR + (1.0f - LED_BREATHE_FLOOR) * 0.5f * (1.0f + sinf(breathePhase));

  // Advance ripples.
  if (idleMode == LED_IDLE_RIPPLE) {
    for (int r = 0; r < LED_RIPPLE_MAX; r++) {
      if (!ripples[r].active) continue;
      ripples[r].age += LED_RIPPLE_SPEED;
      if (ripples[r].age > LED_RIPPLE_LIFE) ripples[r].active = false;
    }
  }

  for (int i = 0; i < WS_LED_COUNT; i++) {
    // ---- Target colour for this key (eased) ----
    float tr, tg, tb;
    if (idleMode == LED_IDLE_RAINBOW) {
      wheel((uint8_t)((i * 256 / WS_LED_COUNT + rainbowPhase) & 0xFF), tr, tg, tb);
    } else if (idleMode == LED_IDLE_WAVE) {
      float hue = (KEY_POS[i][0] + KEY_POS[i][1]) * LED_WAVE_HUE_STEP - wavePhase;
      wheel((uint8_t)((int)hue & 0xFF), tr, tg, tb);
    } else if (idleMode == LED_IDLE_COMET) {
      float dist = cometHead - i;          // LEDs behind the head, in chain order
      if (dist < 0) dist += WS_LED_COUNT;
      float bright = 1.0f - dist / LED_COMET_TAIL;
      if (bright < LED_COMET_FLOOR) bright = LED_COMET_FLOOR;
      wheel((uint8_t)(cometHue - (uint8_t)(dist * 12)), tr, tg, tb);
      tr *= bright; tg *= bright; tb *= bright;
    } else {
      // NONE / BREATHE / TWINKLE / RIPPLE all rest on the per-key base colour.
      tr = baseR[i]; tg = baseG[i]; tb = baseB[i];
      if (idleMode == LED_IDLE_BREATHE) { tr *= breatheEnv; tg *= breatheEnv; tb *= breatheEnv; }
    }

    curR[i] += (tr - curR[i]) * LED_EASE;
    curG[i] += (tg - curG[i]) * LED_EASE;
    curB[i] += (tb - curB[i]) * LED_EASE;

    float orr = curR[i], org = curG[i], orb = curB[i];

    // ---- Twinkle bloom (rise to full, then fade, over the resting colour) ----
    if (idleMode == LED_IDLE_TWINKLE) {
      if (twk[i] <= 0.001f) {
        if ((int)random(1000) < LED_TWINKLE_CHANCE) { twk[i] = 0.02f; twRising[i] = true; }  // ignite
        else twk[i] = 0;
      } else if (twRising[i]) {
        twk[i] += LED_TWINKLE_RISE;
        if (twk[i] >= 1.0f) { twk[i] = 1.0f; twRising[i] = false; }
      } else {
        twk[i] -= LED_TWINKLE_FADE;
        if (twk[i] < 0) twk[i] = 0;
      }
      float t = twk[i] * LED_TWINKLE_BOOST;
      if (t > 0) { orr = orr * (1 - t) + 255 * t; org = org * (1 - t) + 255 * t; orb = orb * (1 - t) + 255 * t; }
    } else if (twk[i] != 0) {
      twk[i] = 0;  // clear stale twinkle when leaving the mode
    }

    // Press highlight: sustain while held, fade after release.
    if (held[i]) press[i] = LED_PRESS_RISE;
    else if (press[i] > 0.002f) press[i] *= (1.0f - LED_PRESS_FADE);
    else press[i] = 0;

    float p = press[i];
    if (p > 0) { orr = orr * (1 - p) + 255 * p; org = org * (1 - p) + 255 * p; orb = orb * (1 - p) + 255 * p; }

    // ---- Ripple rings ----
    if (idleMode == LED_IDLE_RIPPLE) {
      float add = 0;
      for (int r = 0; r < LED_RIPPLE_MAX; r++) {
        if (!ripples[r].active) continue;
        float dx = KEY_POS[i][0] - ripples[r].cx;
        float dy = KEY_POS[i][1] - ripples[r].cy;
        float d = sqrtf(dx * dx + dy * dy);
        float ringDist = fabsf(d - ripples[r].age);
        float inten = 1.0f - ringDist / LED_RIPPLE_WIDTH;
        if (inten <= 0) continue;
        float life = 1.0f - ripples[r].age / LED_RIPPLE_LIFE;       // fade with travel
        float v = inten * (life < 0 ? 0 : life);
        if (v > add) add = v;
      }
      add = clamp01(add);
      if (add > 0) { orr = orr * (1 - add) + 255 * add; org = org * (1 - add) + 255 * add; orb = orb * (1 - add) + 255 * add; }
    }

    // ---- Global flash pulse on top ----
    if (flashLevel > 0.002f) {
      orr = orr * (1 - flashLevel) + flashR * flashLevel;
      org = org * (1 - flashLevel) + flashG * flashLevel;
      orb = orb * (1 - flashLevel) + flashB * flashLevel;
    }

    uint8_t cr = (uint8_t)clampf(orr), cg = (uint8_t)clampf(org), cb = (uint8_t)clampf(orb);
    ledFrame[i * 3] = cr; ledFrame[i * 3 + 1] = cg; ledFrame[i * 3 + 2] = cb;   // for streaming
    strip.setPixelColor(i, strip.Color(cr, cg, cb));
  }

  if (flashLevel > 0.002f) flashLevel *= (1.0f - LED_FLASH_FADE); else flashLevel = 0;
  strip.show();   // single update per frame

  // Stream the framebuffer to the app every Nth frame so its on-screen mirror
  // stays exactly in sync. Packed as RGB565 (4 hex/LED = 48 chars) so the whole
  // line fits the small USB-CDC TX buffer; only sent when there's room, so it
  // never blocks the loop when no host is reading.
  if (++streamCount >= LED_STREAM_DIV) {
    streamCount = 0;
    if (Serial.availableForWrite() >= 60) {
      char buf[WS_LED_COUNT * 4 + 1];
      char *p = buf;
      for (int i = 0; i < WS_LED_COUNT; i++) {
        uint16_t v = ((ledFrame[i * 3] & 0xF8) << 8) | ((ledFrame[i * 3 + 1] & 0xFC) << 3) | (ledFrame[i * 3 + 2] >> 3);
        *p++ = HEXC[(v >> 12) & 0xF]; *p++ = HEXC[(v >> 8) & 0xF]; *p++ = HEXC[(v >> 4) & 0xF]; *p++ = HEXC[v & 0xF];
      }
      *p = 0;
      Serial.print("EVT:LEDS ");
      Serial.println(buf);
    }
  }
}
