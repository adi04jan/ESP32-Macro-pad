/* -------------------------------------------------------------------------
   ESP32-S2 Mini Macropad Firmware (Arduino-ESP32 core 3.2.1) - updated
   Changes:
    - Fix pressKey() to use Keyboard.press/release for HID codes
    - Add prototype for atomicWriteToLittleFS()
    - Fix Serial CLI / JSON upload handling
    - Improve debug prints and some robustness
   ------------------------------------------------------------------------- */

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDMouse.h"
#include "USBHIDConsumerControl.h"

#include <ctype.h>

#define version "0.0.1"

// ----------------------------- User Pin Definitions ----------------------
// Lolin S2 Pico (confirmed by you)
#define TOUCH_PIN_1 2   // GPIO2 (touch-capable)
#define TOUCH_PIN_2 3   // GPIO3 (touch-capable)

#define WS_LED_PIN 36
#define WS_LED_COUNT 12

#define LED_PIN_1 38
#define LED_PIN_2 39
#define LED_PIN_3 40

// NOTE: GPIO1 is UART TX on many ESP32 boards. Using GPIO1 for a button (BUTTON_PIN_2)
// can conflict with Serial output. Consider moving to a different GPIO if possible.
#define BUTTON_PIN_1 5
#define BUTTON_PIN_2 1   // <--- WARNING: GPIO1 = UART TX; consider changing
#define BUTTON_PIN_3 4
#define BUTTON_PIN_4 7
#define BUTTON_PIN_5 6
#define BUTTON_PIN_6 9
#define BUTTON_PIN_7 12
#define BUTTON_PIN_8 10
#define BUTTON_PIN_9 11
#define BUTTON_PIN_10 8
#define BUTTON_PIN_11 13
#define BUTTON_PIN_12 14

// ----------------------------- Constants & Safety -------------------------
#define NUM_KEYS 12
#define NUM_PROFILES 3
#define DEFAULT_DEBOUNCE_MS 50
#define SERIAL_BAUD 115200

#define MAX_TEXT_LEN 4096
#define MAX_REPEAT_COUNT 50

#define HID_USAGE_TELEPHONY_MIC_MUTE   0x2F

const char *profileFiles[NUM_PROFILES] = { "/profile1.json", "/profile2.json", "/profile3.json" };

// ----------------------------- Globals -----------------------------------
Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

const uint8_t buttonPins[NUM_KEYS] = {
  BUTTON_PIN_1, BUTTON_PIN_2, BUTTON_PIN_3, BUTTON_PIN_4,
  BUTTON_PIN_5, BUTTON_PIN_6, BUTTON_PIN_7, BUTTON_PIN_8,
  BUTTON_PIN_9, BUTTON_PIN_10, BUTTON_PIN_11, BUTTON_PIN_12
};

uint16_t rainbowPos = 0;
unsigned long rainbowLastUpdate = 0;
const uint16_t rainbowSpeed = 30;  
uint8_t breatheValue = 0;
int breatheDirection = 1;           // +1 = fade in, -1 = fade out
unsigned long breatheLastUpdate = 0;
uint16_t breatheSpeed = 8;          // lower = faster, higher = slower
uint16_t breatheDelay = 10;         // frame interval in ms (controls smoothness)

// Color for breathe animation
uint8_t breatheR = 64;
uint8_t breatheG = 64;
uint8_t breatheB = 64;

uint8_t keyState[NUM_KEYS];
unsigned long keyLastChange[NUM_KEYS];
unsigned long keyLastPressMillis[NUM_KEYS];

int currentProfile = 1;  // 1..NUM_PROFILES
StaticJsonDocument<8192> profileDoc;
bool profileLoaded = false;
int idleAnimation = 0;
bool macroRunning = false;

// USB objects
USBHIDKeyboard Keyboard;
USBHIDMouse Mouse;
USBHIDConsumerControl Consumer;

// CLI / serial JSON upload
String serialBuffer = "";
bool serialRecording = false;
String serialTargetFile = "";
String cliLine = "";

// Touch calibration
static int baselineA = 0, baselineB = 0;
int touchThreshold = 200;     // default threshold; tune if needed

// ----------------------------- Helper tables ------------------------------
struct KeyMapEntry { const char *name; uint8_t hid; };
static const KeyMapEntry keyMap[] = {
  { "A", 0x04 }, { "B", 0x05 }, { "C", 0x06 }, { "D", 0x07 }, { "E", 0x08 }, { "F", 0x09 }, { "G", 0x0A }, { "H", 0x0B },
  { "I", 0x0C }, { "J", 0x0D }, { "K", 0x0E }, { "L", 0x0F }, { "M", 0x10 }, { "N", 0x11 }, { "O", 0x12 }, { "P", 0x13 },
  { "Q", 0x14 }, { "R", 0x15 }, { "S", 0x16 }, { "T", 0x17 }, { "U", 0x18 }, { "V", 0x19 }, { "W", 0x1A }, { "X", 0x1B },
  { "Y", 0x1C }, { "Z", 0x1D }, { "1", 0x1E }, { "2", 0x1F }, { "3", 0x20 }, { "4", 0x21 }, { "5", 0x22 }, { "6", 0x23 },
  { "7", 0x24 }, { "8", 0x25 }, { "9", 0x26 }, { "0", 0x27 }, { "ENTER", 0x28 }, { "ESC", 0x29 }, { "BACKSPACE", 0x2A },
  { "TAB", 0x2B }, { "SPACE", 0x2C }, { "MINUS", 0x2D }, { "EQUAL", 0x2E }, { "LEFT_BRACE", 0x2F }, { "RIGHT_BRACE", 0x30 },
  { "BACKSLASH", 0x31 }, { "SEMICOLON", 0x33 }, { "QUOTE", 0x34 }, { "TILDE", 0x35 }, { "COMMA", 0x36 }, { "DOT", 0x37 },
  { "SLASH", 0x38 }, { "CAPS_LOCK", 0x39 }, { "F1", 0x3A }, { "F2", 0x3B }, { "F3", 0x3C }, { "F4", 0x3D }, { "F5", 0x3E },
  { "F6", 0x3F }, { "F7", 0x40 }, { "F8", 0x41 }, { "F9", 0x42 }, { "F10", 0x43 }, { "F11", 0x44 }, { "F12", 0x45 },
  { "INSERT", 0x49 }, { "HOME", 0x4A }, { "PAGEUP", 0x4B }, { "DELETE", 0x4C }, { "END", 0x4D }, { "PAGEDOWN", 0x4E },
  { "RIGHT_ARROW", 0x4F }, { "LEFT_ARROW", 0x50 }, { "DOWN_ARROW", 0x51 }, { "UP_ARROW", 0x52 }, { nullptr, 0 }
};

struct ModMapEntry { const char *name; uint8_t code; };
static const ModMapEntry modMap[] = {
  { "LEFT_CTRL", KEY_LEFT_CTRL }, { "LEFT_SHIFT", KEY_LEFT_SHIFT }, { "LEFT_ALT", KEY_LEFT_ALT }, { "LEFT_GUI", KEY_LEFT_GUI },
  { "RIGHT_CTRL", KEY_RIGHT_CTRL }, { "RIGHT_SHIFT", KEY_RIGHT_SHIFT }, { "RIGHT_ALT", KEY_RIGHT_ALT }, { "RIGHT_GUI", KEY_RIGHT_GUI }, { nullptr, 0 }
};

struct MediaMapEntry { const char *name; uint16_t code; };
static const MediaMapEntry mediaMap[] = {
  { "PLAY_PAUSE", HID_USAGE_CONSUMER_PLAY_PAUSE }, { "STOP", HID_USAGE_CONSUMER_STOP }, { "NEXT", HID_USAGE_CONSUMER_SCAN_NEXT },
  { "PREVIOUS", HID_USAGE_CONSUMER_SCAN_PREVIOUS }, { "MUTE", HID_USAGE_CONSUMER_MUTE }, { "VOLUME_UP", HID_USAGE_CONSUMER_VOLUME_INCREMENT },
  { "VOLUME_DOWN", HID_USAGE_CONSUMER_VOLUME_DECREMENT }, { nullptr, 0 }
};

// ----------------------------- Utility helpers ----------------------------
static inline void write_le16(uint8_t *buf, uint32_t off, uint16_t v) {
  buf[off] = v & 0xFF; buf[off + 1] = (v >> 8) & 0xFF;
}
static inline void write_le32(uint8_t *buf, uint32_t off, uint32_t v) {
  buf[off] = v & 0xFF; buf[off + 1] = (v >> 8) & 0xFF; buf[off + 2] = (v >> 16) & 0xFF; buf[off + 3] = (v >> 24) & 0xFF;
}

uint8_t keyNameToHid(const String &s) {
  for (int i = 0; keyMap[i].name; ++i)
    if (s.equalsIgnoreCase(keyMap[i].name)) return keyMap[i].hid;
  return 0;
}
uint8_t modifierNameToCode(const String &s) {
  for (int i = 0; modMap[i].name; ++i)
    if (s.equalsIgnoreCase(modMap[i].name)) return modMap[i].code;
  return 0;
}
uint16_t mediaNameToCode(const String &s) {
  for (int i = 0; mediaMap[i].name; ++i)
    if (s.equalsIgnoreCase(mediaMap[i].name)) return mediaMap[i].code;
  return 0;
}

String readFileStr(const char *path) {
  File f = LittleFS.open(path, "r");
  if (!f) return String();
  String s;
  s.reserve(f.size() + 1);
  while (f.available()) s += (char)f.read();
  f.close();
  return s;
}
bool writeFileStr(const char *path, const String &content) {
  File f = LittleFS.open(path, "w");
  if (!f) return false;
  f.print(content);
  f.close();
  return true;
}

// Prototype for atomicWriteToLittleFS (defined later). needed because handleSerialInput uses it.
bool atomicWriteToLittleFS(const char *targetPath, const uint8_t *data, size_t len);

// ----------------------------- LED helpers --------------------------------
void setKeyLedColor(int keyIndex, uint8_t r, uint8_t g, uint8_t b) {
  if (keyIndex < 0 || keyIndex >= WS_LED_COUNT) return;
  strip.setPixelColor(keyIndex, strip.Color(r, g, b));
  strip.show(); // OK for per-key feedback; quick but fine for 12 LEDs
}
void flashAll(uint8_t r, uint8_t g, uint8_t b, int times = 2, int msOn = 120, int msOff = 80) {
  for (int t = 0; t < times; ++t) {
    for (int i = 0; i < WS_LED_COUNT; i++) strip.setPixelColor(i, strip.Color(r, g, b));
    strip.show();
    delay(msOn);
    strip.clear();
    strip.show();
    delay(msOff);
  }
}
void breatheAll(uint8_t r, uint8_t g, uint8_t b, int cycles = 2) {
  unsigned long now = millis();
  if (now - breatheLastUpdate < breatheDelay) return;
  breatheLastUpdate = now;

  // Update brightness
  if (breatheDirection > 0) {
    if (breatheValue >= 255) breatheDirection = -1;
    else breatheValue++;
  } else {
    if (breatheValue == 0) breatheDirection = 1;
    else breatheValue--;
  }

  // Apply brightness to all LEDs
  for (int i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(
      i,
      strip.Color((r * breatheValue) / 255,
                  (g * breatheValue) / 255,
                  (b * breatheValue) / 255)
    );
  }
  strip.show();
}
void rainbowCycle() {
  unsigned long now = millis();
  if (now - rainbowLastUpdate < rainbowSpeed) return;
  rainbowLastUpdate = now;

  for (uint16_t i = 0; i < strip.numPixels(); i++) {
    uint8_t hue = (i * 256 / strip.numPixels() + rainbowPos) & 255;

    uint8_t r = (hue < 85) ? (hue * 3)
              : (hue < 170) ? (255 - (hue - 85) * 3)
              : 0;

    uint8_t g = (hue < 85) ? 0
              : (hue < 170) ? ((hue - 85) * 3)
              : (255 - (hue - 170) * 3);

    uint8_t b = (hue < 85) ? (255 - hue * 3)
              : (hue < 170) ? 0
              : ((hue - 170) * 3);

    strip.setPixelColor(i, strip.Color(r, g, b));
  }

  strip.show();

  rainbowPos++;
  if (rainbowPos >= 256) rainbowPos = 0;
}

// ----------------------------- Profiles / JSON -----------------------------
bool ensureDefaultProfile(int id) {
  if (id < 1 || id > NUM_PROFILES) return false;
  String fname = String("/profile") + String(id) + ".json";
  if (!LittleFS.exists(fname.c_str())) {
    StaticJsonDocument<512> tmp;
    tmp["profile_name"] = String("Profile") + String(id);
    tmp["idle_animation"] = "none";
    tmp["default_delay"] = 30;
    tmp.createNestedArray("keys");
    String out;
    serializeJson(tmp, out);
    writeFileStr(fname.c_str(), out);
  }
  return true;
}

void updateProfileLEDs() {
  digitalWrite(LED_PIN_1, currentProfile == 1 ? HIGH : LOW);
  digitalWrite(LED_PIN_2, currentProfile == 2 ? HIGH : LOW);
  digitalWrite(LED_PIN_3, currentProfile == 3 ? HIGH : LOW);
}

bool loadProfile(int id) {
  if (id < 1 || id > NUM_PROFILES) return false;
  String path = String("/profile") + String(id) + ".json";
  ensureDefaultProfile(id);
  String s = readFileStr(path.c_str());
  if (s.length() == 0) return false;
  DeserializationError err = deserializeJson(profileDoc, s);
  if (err) {
    Serial.print("Failed parse profile JSON: ");
    Serial.println(err.c_str());
    return false;
  }
  profileLoaded = true;
  currentProfile = id;
  const char *anim = profileDoc["idle_animation"] | "none";
  if (strcmp(anim, "breathe") == 0) idleAnimation = 1;
  else if (strcmp(anim, "rainbow") == 0) idleAnimation = 2;
  else idleAnimation = 0;
  Serial.printf("Loaded profile %d (%s)\n", id, profileDoc["profile_name"] | "unnamed");
  updateProfileLEDs();
  return true;
}

// ----------------------------- Macro engine (keyboard/mouse/media) -------
// void sendText(const String &text) {
//   if (text.length() == 0) return;
//   Keyboard.print(text);
//   delay(100);
// }
void sendText(const String &text) {
  for (int i = 0; i < text.length(); i++) {
    char c = text[i];

    // For ASCII normal characters
    Keyboard.write(c);

    // CRITICAL: allow USB HID buffer to flush
    delay(30);   // 4–8 ms works perfectly
  }

  delay(20);
}

// Improved pressKey: printable single characters -> print; otherwise send HID usage
void pressKey(const String &keyname) {
    if (keyname.length() == 0) return;

    uint8_t hid = keyNameToHid(keyname);

    // Printable single chars → normal print
    if (!hid) {
        if (keyname.length() == 1) {
            Keyboard.print(keyname);
            delay(25);
            return;
        }
        Serial.printf("Unknown key '%s'\n", keyname.c_str());
        return;
    }

    Serial.printf("pressKey: HID=%02X name=%s\n", hid, keyname.c_str());

    // ESP32-S2 MUST use raw HID usage for non-printable
    Keyboard.pressRaw(hid);
    delay(25);
    Keyboard.releaseRaw(hid);
}


void sendKeyCombo(JsonArray keysArr) {
  // press modifiers first
  for (JsonVariant v : keysArr) {
    String ks = v.as<String>();
    uint8_t m = modifierNameToCode(ks);
    if (m) Keyboard.press(m);
  }
  // then press non-modifiers
  for (JsonVariant v : keysArr) {
    String ks = v.as<String>();
    if (modifierNameToCode(ks)) continue;
    pressKey(ks);
  }
  delay(20);
  Keyboard.releaseAll();
}
void sendMedia(uint16_t usage) {
  if (!usage) return;
  Consumer.press(usage);
  delay(20);
  Consumer.release();
}
void mouseMove(int8_t x, int8_t y, int8_t wheel = 0) { Mouse.move(x, y); }
void mouseClick(uint8_t buttons) {
  if (buttons & 1) Mouse.click(MOUSE_LEFT);
  if (buttons & 2) Mouse.click(MOUSE_RIGHT);
  if (buttons & 4) Mouse.click(MOUSE_MIDDLE);
}

void sendTelephony(uint8_t usage) {
    uint8_t report[2] = { usage, 0x00 }; // usage + padding

    // Telephony Page uses Report ID 3
    USBHID().SendReport(3, report, sizeof(report));
    delay(10);

    report[0] = 0x00; // release
    USBHID().SendReport(3, report, sizeof(report));
}

void runActions(JsonArray actions);
void executeAction(JsonObject act) {
  if (!act.containsKey("type")) return;
  String type = act["type"].as<String>(); type.toLowerCase();
  if (type == "comment") return;
  if (type == "delay") { int ms = act["ms"] | 0; if (ms > 0) delay(ms); return; }
  if (type == "key") { pressKey(act["value"].as<String>()); delay(profileDoc["default_delay"] | 30); return; }
  if (type == "keycombo" && act["keys"].is<JsonArray>()) { sendKeyCombo(act["keys"].as<JsonArray>()); delay(profileDoc["default_delay"] | 30); return; }
  if (type == "text" || type == "multiline") { String txt = act["value"].as<String>(); if (txt.length() > MAX_TEXT_LEN) txt = txt.substring(0, MAX_TEXT_LEN); sendText(txt); delay(profileDoc["default_delay"] | 30); return; }
  if (type == "hold") { String k = act["key"].as<String>(); uint8_t code = modifierNameToCode(k); if (code) Keyboard.press(code); else { uint8_t hid = keyNameToHid(k); if (hid) Keyboard.press(hid); } return; }
  if (type == "release") { Keyboard.releaseAll(); return; }
  if (type == "repeat") { int count = act["count"] | 1; if (count < 1) count = 1; if (count > MAX_REPEAT_COUNT) count = MAX_REPEAT_COUNT; if (act["actions"].is<JsonArray>()) for (int i = 0; i < count; i++) runActions(act["actions"].as<JsonArray>()); return; }
  if (type == "media") { uint16_t code = mediaNameToCode(act["value"].as<String>()); if (code) sendMedia(code); return; }
  if (type == "mouse_move") { int x = act["x"] | 0; int y = act["y"] | 0; mouseMove(x, y); return; }
  if (type == "mouse_click") { String b = act["button"].as<String>(); uint8_t btn = 1; if (b.equalsIgnoreCase("RIGHT")) btn = 2; else if (b.equalsIgnoreCase("MIDDLE")) btn = 4; mouseClick(btn); return; }
  if (type == "led") { if (act["color"].is<JsonArray>()) { JsonArray c = act["color"].as<JsonArray>(); for (int i = 0; i < WS_LED_COUNT; i++) strip.setPixelColor(i, strip.Color(c[0] | 0, c[1] | 0, c[2] | 0)); strip.show(); } return; }
  if (type == "led_anim") { String a = act["value"].as<String>(); if (a.equalsIgnoreCase("flash")) { if (act["color"].is<JsonArray>()) { JsonArray c = act["color"].as<JsonArray>(); flashAll(c[0] | 0, c[1] | 0, c[2] | 0, 2, 120, 80); } else flashAll(255, 255, 255, 2, 120, 80); } else if (a.equalsIgnoreCase("breathe")) { if (act["color"].is<JsonArray>()) { JsonArray c = act["color"].as<JsonArray>(); breatheAll(c[0] | 0, c[1] | 0, c[2] | 0, 1); } else breatheAll(255, 255, 255, 1); } return; }
  if (type == "profile") { int p = act["value"] | 1; if (p < 1) p = 1; if (p > NUM_PROFILES) p = NUM_PROFILES; loadProfile(p); return; }
  if (type == "telephony") {
    String val = act["value"].as<String>();
    if (val.equalsIgnoreCase("MIC_MUTE"))
        sendTelephony(HID_USAGE_TELEPHONY_MIC_MUTE);
    return;
}
}

void runActions(JsonArray actions) {
  for (JsonVariant v : actions) {
    if (!v.is<JsonObject>()) continue;
    JsonObject act = v.as<JsonObject>();
    executeAction(act);
    delay(profileDoc["default_delay"] | 30);
  }
}

void runMacroForKey(int keyId) {
  if (!profileLoaded) return;
  if (!profileDoc.containsKey("keys")) return;
  JsonArray keysArr = profileDoc["keys"].as<JsonArray>();
  for (JsonVariant kv : keysArr) {
    JsonObject ko = kv.as<JsonObject>();
    int id = ko["id"] | 0;
    if (id == keyId) {
      if (ko.containsKey("actions") && ko["actions"].is<JsonArray>()) {
        macroRunning = true;
        runActions(ko["actions"].as<JsonArray>());
        macroRunning = false;
      }
      return;
    }
  }
}

// ----------------------------- Input & touch --------------------------------
void initButtons() {
  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    keyState[i] = digitalRead(buttonPins[i]) ? 0 : 1;
    keyLastChange[i] = millis();
    keyLastPressMillis[i] = 0;
  }
  pinMode(LED_PIN_1, OUTPUT);
  pinMode(LED_PIN_2, OUTPUT);
  pinMode(LED_PIN_3, OUTPUT);
  updateProfileLEDs();

  // sample multiple times to create a stable baseline for touch
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

bool touchPressed(int pin) {
  long sum = 0;
  for (int i = 0; i < 4; i++) {
    sum += touchRead(pin);
    delayMicroseconds(500);
  }
  int v = sum / 4;

  int base = (pin == TOUCH_PIN_1) ? baselineA : baselineB;

  return (v - base) > 300;
}

unsigned long touchLastDebounceA = 0, touchLastDebounceB = 0;

void scanTouchProfileSwitch() {
  static bool lastA = false, lastB = false;

  bool a = touchPressed(TOUCH_PIN_1);
  bool b = touchPressed(TOUCH_PIN_2);

  if (a && !lastA && millis() - touchLastDebounceA > 300) {
    int np = currentProfile + 1;
    if (np > NUM_PROFILES) np = 1;
    loadProfile(np);
    flashAll(0, 0, 200, 1, 120, 60);
    touchLastDebounceA = millis();
  }

  if (b && !lastB && millis() - touchLastDebounceB > 300) {
    int np = currentProfile - 1;
    if (np < 1) np = NUM_PROFILES;
    loadProfile(np);
    flashAll(0, 200, 0, 1, 120, 60);
    touchLastDebounceB = millis();
  }

  // both-pressed reset
  static unsigned long bothStart = 0;

  if (a && b) {
    if (bothStart == 0)
      bothStart = millis();

    if (millis() - bothStart > 3000) {
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

void scanKeys() {
  for (int i = 0; i < NUM_KEYS; i++) {
    bool raw = digitalRead(buttonPins[i]) == LOW;
    if (raw != keyState[i]) {
      if (millis() - keyLastChange[i] > DEFAULT_DEBOUNCE_MS) {
        keyState[i] = raw;
        keyLastChange[i] = millis();
        if (raw) {
          keyLastPressMillis[i] = millis();
          setKeyLedColor(i, 255, 255, 255);
          if (!macroRunning && profileLoaded) runMacroForKey(i + 1);
          delay(40);
          setKeyLedColor(i, 0, 0, 0);
        } else {
          setKeyLedColor(i, 0, 0, 0);
        }
      }
    }
  }
}

// ----------------------------- Serial CLI & upload -------------------------
void printPrompt() { Serial.print("macropad:$ "); }

// NOTE: This function now reads lines (until '\n') and supports both the CLI
// and a multi-line JSON upload protocol using ###BEGIN### <name> / ###END###
void cliHandleLine(const String &line) {
  String s = line; s.trim();
  if (s.length() == 0) { printPrompt(); return; }
  int sp = s.indexOf(' ');
  String cmd = (sp == -1) ? s : s.substring(0, sp);
  cmd.toLowerCase();
  String arg = (sp == -1) ? "" : s.substring(sp + 1);
  arg.trim();
  if (cmd == "help") Serial.println("help ls cat setprofile <n> rebuild_msc status unmount reboot");
  else if (cmd == "ls") {
    File root = LittleFS.open("/");
    File f = root.openNextFile();
    while (f) {
      Serial.printf("%s\t%u\n", f.name(), (unsigned)f.size());
      f = root.openNextFile();
    }
  } else if (cmd == "cat") {
    if (arg.length() == 0) Serial.println("cat <file>");
    else Serial.println(readFileStr(arg.c_str()));
  } else if (cmd == "setprofile") {
    int id = arg.toInt();
    if (id < 1 || id > NUM_PROFILES) Serial.println("invalid");
    else { loadProfile(id); Serial.printf("profile %d\n", id); }
  } else if (cmd == "status") Serial.printf("Profile:%d loaded:%d idle:%d\n", currentProfile, profileLoaded, idleAnimation);
  else if (cmd == "reboot") { Serial.println("rebooting"); delay(200); ESP.restart(); }
  else Serial.println("unknown");
  printPrompt();
}

void handleSerialInput() {
  // Read lines as they arrive and handle CLI or JSON upload sequences
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n'); // returns line (without '\n')
    line.trim();

    // If we're not currently recording a JSON file:
    if (!serialRecording) {
      if (line.startsWith("###BEGIN###")) {
        String target = line.substring(strlen("###BEGIN###"));
        target.trim();
        if (target.length() > 0) {
          serialRecording = true;
          serialBuffer = "";
          serialTargetFile = "/" + target;
          Serial.printf("Recording JSON to %s\n", serialTargetFile.c_str());
        } else {
          Serial.println("Usage: ###BEGIN### filename.json");
        }
      } else {
        // treat as CLI input
        if (line.length() > 0) {
          cliHandleLine(line);
        } else {
          printPrompt();
        }
      }
    } else {
      // we are recording JSON lines until ###END###
      if (line == "###END###") {
        if (serialTargetFile.length() > 0) {
          bool ok = atomicWriteToLittleFS(serialTargetFile.c_str(), (const uint8_t *)serialBuffer.c_str(), serialBuffer.length());
          Serial.printf("Wrote %s -> %s\n", serialTargetFile.c_str(), ok ? "OK" : "FAILED");
        }
        serialRecording = false;
        serialTargetFile = "";
        serialBuffer = "";
        printPrompt();
      } else {
        // append line (we already trimmed it)
        serialBuffer += line;
        serialBuffer += "\n";
      }
    }
  }
}

// ----------------------------- Setup & Loop --------------------------------
void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 2000) delay(10);
  Serial.println("Macropad (NO MSC) starting...");

  if (!LittleFS.begin(true)) Serial.println("LittleFS mount failed/format");
  else Serial.println("LittleFS mounted");

  // ensure default profiles exist
  for (int i = 0; i < NUM_PROFILES; i++) {
    String p = String(profileFiles[i]);
    if (!LittleFS.exists(p.c_str())) {
      StaticJsonDocument<512> tmp;
      tmp["profile_name"] = String("Profile") + String(i + 1);
      tmp["idle_animation"] = "none";
      tmp["default_delay"] = 30;
      tmp.createNestedArray("keys");
      String out; serializeJson(tmp, out);
      writeFileStr(p.c_str(), out);
    }
  }
  if (!LittleFS.exists("/backups")) LittleFS.mkdir("/backups");

  strip.begin(); strip.setBrightness(64); strip.clear(); strip.show();
  initButtons();

  // USB init
  USB.begin();
  delay(10);
  Keyboard.begin();
  Mouse.begin();
  Consumer.begin();
  delay(10);

  // load profile1
  loadProfile(1);

  Serial.println("Ready");
  Serial.print("macropad:$ ");
}

void loop() {
  handleSerialInput();
  scanTouchProfileSwitch();
  scanKeys();

  if (!macroRunning) {
    if (idleAnimation == 1) { breatheAll(64, 64, 64, 1); delay(10); }
    else if (idleAnimation == 2) rainbowCycle();
  }

  delay(8);
}

// atomicWriteToLittleFS (kept here)
bool atomicWriteToLittleFS(const char *targetPath, const uint8_t *data, size_t len) {
  String tmp = String(targetPath) + ".tmp";
  File f = LittleFS.open(tmp.c_str(), "w");
  if (!f) return false;
  size_t w = f.write(data, len);
  f.close();
  if (w != len) {
    LittleFS.remove(tmp.c_str());
    return false;
  }
  // backup existing
  if (LittleFS.exists(targetPath)) {
    if (!LittleFS.exists("/backups")) LittleFS.mkdir("/backups");
    String bk = String("/backups/") + String(targetPath + 1) + "-" + String(millis()) + ".bak";
    File old = LittleFS.open(targetPath, "r");
    if (old) {
      File ob = LittleFS.open(bk.c_str(), "w");
      while (old.available()) ob.write(old.read());
      ob.close();
      old.close();
    }
  }
  LittleFS.remove(targetPath);
  return LittleFS.rename(tmp.c_str(), targetPath);
}
