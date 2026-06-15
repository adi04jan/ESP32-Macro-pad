#include "macro_engine.h"
#include "hid_layer.h"
#include "hid_maps.h"
#include "leds.h"
#include "profiles.h"

MacroEngine macroEngine;

void MacroEngine::startKey(int keyId) {
  if (!profileLoaded) return;
  JsonArray keys = profileDoc["keys"].as<JsonArray>();
  if (keys.isNull()) return;

  for (JsonObject ko : keys) {
    if ((ko["id"] | 0) != keyId) continue;
    JsonArrayConst acts = ko["actions"].as<JsonArrayConst>();
    if (acts.isNull()) return;

    // Copy actions into our private doc so concurrent setkey/upload can't
    // invalidate the references we iterate over.
    macroDoc.clear();
    macroDoc.set(acts);

    depth = 0;
    stack[depth++] = { macroDoc.as<JsonArrayConst>(), 0, 0 };
    waitUntil = 0;
    inText = false;
    textPos = 0;
    defaultDelay = profileDoc["default_delay"] | 30;
    running = true;
    return;
  }
}

void MacroEngine::tick() {
  if (!running) return;
  unsigned long now = millis();
  if ((long)(now - waitUntil) < 0) return;   // still waiting

  // Stream text one char per tick.
  if (inText) {
    if (textPos < curText.length()) {
      Keyboard.write(curText[textPos++]);
      waitUntil = now + TEXT_CHAR_DELAY_MS;
    } else {
      inText = false;
      waitUntil = now + defaultDelay;
    }
    return;
  }

  if (depth == 0) { finish(); return; }

  Frame &f = stack[depth - 1];
  if (f.idx >= f.arr.size()) {
    if (f.repeatLeft > 0) { f.repeatLeft--; f.idx = 0; }  // loop the repeat body
    else depth--;                                         // pop frame
    return;
  }

  JsonObjectConst act = f.arr[f.idx].as<JsonObjectConst>();
  f.idx++;
  execAction(act, now);
}

void MacroEngine::execAction(JsonObjectConst act, unsigned long now) {
  const char *type = act["type"] | "";
  waitUntil = now + defaultDelay;   // default inter-action spacing (applied once)

  if (type[0] == '\0' || strcmp(type, "comment") == 0) return;

  if (strcmp(type, "delay") == 0) {
    int ms = act["ms"] | 0;
    if (ms < 0) ms = 0;
    waitUntil = now + ms;
    return;
  }
  if (strcmp(type, "key") == 0) {
    hidPressKey(act["value"] | "");
    return;
  }
  if (strcmp(type, "keycombo") == 0) {
    JsonArrayConst keys = act["keys"].as<JsonArrayConst>();
    if (!keys.isNull()) hidSendKeyCombo(keys);
    return;
  }
  if (strcmp(type, "text") == 0 || strcmp(type, "multiline") == 0) {
    curText = String((const char *)(act["value"] | ""));
    if (curText.length() > MAX_TEXT_LEN) curText = curText.substring(0, MAX_TEXT_LEN);
    textPos = 0;
    inText = true;
    waitUntil = now;   // begin typing on the next tick
    return;
  }
  if (strcmp(type, "hold") == 0) {
    String k = act["key"] | (act["value"] | "");
    hidHold(k);
    return;
  }
  if (strcmp(type, "release") == 0) {
    hidReleaseAll();
    return;
  }
  if (strcmp(type, "repeat") == 0) {
    int count = act["count"] | 1;
    if (count < 1) count = 1;
    if (count > MAX_REPEAT_COUNT) count = MAX_REPEAT_COUNT;
    JsonArrayConst inner = act["actions"].as<JsonArrayConst>();
    if (!inner.isNull() && depth < MACRO_MAX_DEPTH)
      stack[depth++] = { inner, 0, count - 1 };
    return;
  }
  if (strcmp(type, "media") == 0) {
    hidSendMedia(mediaNameToCode(act["value"] | ""));
    return;
  }
  if (strcmp(type, "mouse_move") == 0) {
    hidMouseMove(act["x"] | 0, act["y"] | 0, act["wheel"] | 0);
    return;
  }
  if (strcmp(type, "mouse_click") == 0) {
    String b = act["button"] | "LEFT";
    uint8_t btn = 1;
    if (b.equalsIgnoreCase("RIGHT")) btn = 2;
    else if (b.equalsIgnoreCase("MIDDLE")) btn = 4;
    hidMouseClick(btn);
    return;
  }
  if (strcmp(type, "led") == 0) {
    JsonArrayConst c = act["color"].as<JsonArrayConst>();
    if (!c.isNull()) ledsSetAllBase(c[0] | 0, c[1] | 0, c[2] | 0);  // smoothly eases in
    return;
  }
  if (strcmp(type, "led_anim") == 0) {
    String a = act["value"] | "";
    JsonArrayConst c = act["color"].as<JsonArrayConst>();
    uint8_t r = c.isNull() ? 255 : (uint8_t)(c[0] | 0);
    uint8_t g = c.isNull() ? 255 : (uint8_t)(c[1] | 0);
    uint8_t b = c.isNull() ? 255 : (uint8_t)(c[2] | 0);
    if (a.equalsIgnoreCase("flash")) ledsFlash(r, g, b);            // non-blocking pulse
    else if (a.equalsIgnoreCase("breathe")) { ledsSetAllBase(r, g, b); ledsSetIdleMode(LED_IDLE_BREATHE); }
    return;
  }
  if (strcmp(type, "profile") == 0) {
    int p = act["value"] | 1;
    if (p < 1) p = 1;
    if (p > NUM_PROFILES) p = NUM_PROFILES;
    finish();          // stop this macro before switching context
    loadProfile(p);
    return;
  }
  if (strcmp(type, "telephony") == 0) {
    hidSendTelephony(act["value"] | "");
    return;
  }

  Serial.printf("Unknown action type '%s'\n", type);
}

void MacroEngine::finish() {
  running = false;
  inText = false;
  depth = 0;
  hidReleaseAll();
}

void MacroEngine::abort() {
  if (running) finish();
}
