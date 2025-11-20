/* -------------------------------------------------------------------------
   ESP32-S2 Mini Macropad Firmware (Arduino-ESP32 core 3.x USB API)
   - 12 keys
   - 12 WS2812 LEDs (per-key)
   - 3 extra digital LEDs (LED_PIN_1..3)
   - 2 Touch pins for profile switching (TOUCH_PIN_1, TOUCH_PIN_2)
   - Composite USB: Keyboard + Mouse + Consumer (Media) + Serial (CDC)
   - LittleFS stored JSON profiles: /profile1.json /profile2.json /profile3.json
   - Serial JSON upload format: ###BEGIN###profile1.json\n{...}\n###END###
   - Macro engine supports many action types
   ------------------------------------------------------------------------- */

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

// Arduino-ESP32 USB HID library (core 3.x)
#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDMouse.h"
#include "USBHIDConsumerControl.h"

// ----------------------------- User Pin Definitions ----------------------
#define TOUCH_PIN_1 1
#define TOUCH_PIN_2 3

#define WS_LED_PIN 36
#define WS_LED_COUNT 12

#define LED_PIN_1 38
#define LED_PIN_2 39
#define LED_PIN_3 40

#define BUTTON_PIN_1 2
#define BUTTON_PIN_2 4
#define BUTTON_PIN_3 5
#define BUTTON_PIN_4 6
#define BUTTON_PIN_5 7
#define BUTTON_PIN_6 8
#define BUTTON_PIN_7 9
#define BUTTON_PIN_8 10
#define BUTTON_PIN_9 11
#define BUTTON_PIN_10 12
#define BUTTON_PIN_11 13
#define BUTTON_PIN_12 14

// ----------------------------- Constants & Safety -------------------------
#define NUM_KEYS 12
#define NUM_PROFILES 3
#define DEFAULT_DEBOUNCE_MS 20
#define SERIAL_BAUD 115200

// Safety caps
#define MAX_REPEAT_COUNT 50
#define MAX_TEXT_LEN 4096

// files
const char *profileFiles[NUM_PROFILES] = {"/profile1.json","/profile2.json","/profile3.json"};

// ----------------------------- Globals -----------------------------------
Adafruit_NeoPixel strip(WS_LED_COUNT, WS_LED_PIN, NEO_GRB + NEO_KHZ800);

// Map button pins in array order 1..12 -> index 0..11
const uint8_t buttonPins[NUM_KEYS] = {
  BUTTON_PIN_1, BUTTON_PIN_2, BUTTON_PIN_3, BUTTON_PIN_4,
  BUTTON_PIN_5, BUTTON_PIN_6, BUTTON_PIN_7, BUTTON_PIN_8,
  BUTTON_PIN_9, BUTTON_PIN_10,BUTTON_PIN_11,BUTTON_PIN_12
};

uint8_t keyState[NUM_KEYS];           // 0 = released, 1 = pressed (after debounce)
unsigned long keyLastChange[NUM_KEYS];
unsigned long keyLastPressMillis[NUM_KEYS];

// touch baseline and thresholds (you may tune these)
const int TOUCH_THRESHOLD = 40; // relative units; tune if needed

// Profile management
int currentProfile = 1; // 1..NUM_PROFILES
StaticJsonDocument<8192> profileDoc; // will be re-used for JSON parsing
bool profileLoaded = false;

// Serial JSON upload buffering
String serialBuffer = "";
bool serialRecording = false;
String serialTargetFile = "";

// USB HID objects (Arduino-ESP32 core 3.x)
USBHIDKeyboard Keyboard;
USBHIDMouse Mouse;
USBHIDConsumerControl Consumer;

// LED pattern state
unsigned long lastAnimMillis = 0;
int idleAnimation = 0; // 0 = none, 1 = breathing, 2 = rainbow, others

// Macro execution queue (simple single-thread, run one macro at a time)
bool macroRunning = false;

// ---------- Helper: basic mapping of keynames to HID keycodes ---------------
// This is a simplified mapping for common keys. Extend as needed.
struct KeyMapEntry { const char *name; uint8_t hid; };
static const KeyMapEntry keyMap[] = {
  {"A", 0x04}, {"B",0x05},{"C",0x06},{"D",0x07},{"E",0x08},{"F",0x09},
  {"G",0x0A},{"H",0x0B},{"I",0x0C},{"J",0x0D},{"K",0x0E},{"L",0x0F},
  {"M",0x10},{"N",0x11},{"O",0x12},{"P",0x13},{"Q",0x14},{"R",0x15},
  {"S",0x16},{"T",0x17},{"U",0x18},{"V",0x19},{"W",0x1A},{"X",0x1B},
  {"Y",0x1C},{"Z",0x1D},
  {"1",0x1E},{"2",0x1F},{"3",0x20},{"4",0x21},{"5",0x22},{"6",0x23},
  {"7",0x24},{"8",0x25},{"9",0x26},{"0",0x27},
  {"ENTER", 0x28}, {"ESC",0x29}, {"BACKSPACE",0x2A}, {"TAB",0x2B}, {"SPACE",0x2C},
  {"MINUS",0x2D}, {"EQUAL",0x2E}, {"LEFT_BRACE",0x2F}, {"RIGHT_BRACE",0x30},
  {"BACKSLASH",0x31}, {"SEMICOLON",0x33}, {"QUOTE",0x34}, {"TILDE",0x35},
  {"COMMA",0x36}, {"DOT",0x37}, {"SLASH",0x38},
  {"CAPS_LOCK",0x39},
  {"F1",0x3A}, {"F2",0x3B}, {"F3",0x3C}, {"F4",0x3D}, {"F5",0x3E}, {"F6",0x3F},
  {"F7",0x40}, {"F8",0x41}, {"F9",0x42}, {"F10",0x43}, {"F11",0x44}, {"F12",0x45},
  {"PRINTSCREEN",0x46}, {"SCROLL_LOCK",0x47}, {"PAUSE",0x48},
  {"INSERT",0x49}, {"HOME",0x4A}, {"PAGEUP",0x4B}, {"DELETE",0x4C}, {"END",0x4D},
  {"PAGEDOWN",0x4E}, {"RIGHT_ARROW",0x4F}, {"LEFT_ARROW",0x50}, {"DOWN_ARROW",0x51}, {"UP_ARROW",0x52},
  // Add more as needed
  {nullptr, 0}
};

// Modifiers mapping (names used in JSON). These map to Arduino Keyboard constants if present.
struct ModMapEntry { const char *name; uint8_t code; };
static const ModMapEntry modMap[] = {
  {"LEFT_CTRL",  KEY_LEFT_CTRL},
  {"LEFT_SHIFT", KEY_LEFT_SHIFT},
  {"LEFT_ALT",   KEY_LEFT_ALT},
  {"LEFT_GUI",   KEY_LEFT_GUI},
  {"RIGHT_CTRL", KEY_RIGHT_CTRL},
  {"RIGHT_SHIFT",KEY_RIGHT_SHIFT},
  {"RIGHT_ALT",  KEY_RIGHT_ALT},
  {"RIGHT_GUI",  KEY_RIGHT_GUI},
  {nullptr,0}
};

// Consumer (media) codes mapping (use Consumer.press() with these values)
struct MediaMapEntry { const char *name; uint16_t code; };
static const MediaMapEntry mediaMap[] = {
  {"PLAY_PAUSE",   HID_USAGE_CONSUMER_PLAY_PAUSE},
  {"STOP",         HID_USAGE_CONSUMER_STOP},
  {"NEXT",         HID_USAGE_CONSUMER_SCAN_NEXT},
  {"PREVIOUS",     HID_USAGE_CONSUMER_SCAN_PREVIOUS},
  {"MUTE",         HID_USAGE_CONSUMER_MUTE},
  {"VOLUME_UP",    HID_USAGE_CONSUMER_VOLUME_INCREMENT},
  {"VOLUME_DOWN",  HID_USAGE_CONSUMER_VOLUME_DECREMENT},
  {nullptr, 0}
};

void updateProfileLEDs() {
  digitalWrite(LED_PIN_1, currentProfile == 1 ? HIGH : LOW);
  digitalWrite(LED_PIN_2, currentProfile == 2 ? HIGH : LOW);
  digitalWrite(LED_PIN_3, currentProfile == 3 ? HIGH : LOW);
}

// ----------------------------- Utility Functions --------------------------
uint8_t keyNameToHid(const String &s) {
  for (int i=0; keyMap[i].name; ++i) {
    if (s.equalsIgnoreCase(keyMap[i].name)) return keyMap[i].hid;
  }
  return 0;
}

uint8_t modifierNameToCode(const String &s) {
  for (int i=0; modMap[i].name; ++i) {
    if (s.equalsIgnoreCase(modMap[i].name)) return modMap[i].code;
  }
  return 0;
}

uint16_t mediaNameToCode(const String &s) {
  for (int i=0; mediaMap[i].name; ++i) {
    if (s.equalsIgnoreCase(mediaMap[i].name)) return mediaMap[i].code;
  }
  return 0;
}

// Helper: press single key (no modifiers) using new USBHIDKeyboard API
void pressKey(const String &keyname) {
  uint8_t hid = keyNameToHid(keyname);
  if (!hid) return;
  // Keyboard.press accepts either ascii or HID key constants; try print for letters/numbers
  // For HID usage, use Keyboard.press(hid) if available. We'll try both:
  if (hid >= 0x04 && hid <= 0x1d) {
    // letters A-Z
    char c = (char)('a' + (hid - 0x04));
    Keyboard.print(String(c));
  } else if (hid >= 0x1e && hid <= 0x27) {
    // digits 1-0
    char c;
    if (hid == 0x27) c = '0'; else c = '1' + (hid - 0x1e);
    Keyboard.print(String(c));
  } else {
    // try to use Keyboard.press with HID usage (some cores accept HID usage values)
    Keyboard.press(hid);
    delay(8);
    Keyboard.releaseAll();
  }
}

// Helper: send keycombo (array of keynames including modifiers)
void sendKeyCombo(JsonArray keysArr) {
  // press modifiers first
  for (JsonVariant v : keysArr) {
    String ks = v.as<String>();
    uint8_t mcode = modifierNameToCode(ks);
    if (mcode) Keyboard.press(mcode);
  }
  // then press non-mod keys
  for (JsonVariant v : keysArr) {
    String ks = v.as<String>();
    uint8_t mcode = modifierNameToCode(ks);
    if (mcode) continue;
    uint8_t hid = keyNameToHid(ks);
    if (hid) {
      // use printable if letter/num
      pressKey(ks);
    }
  }
  delay(20);
  Keyboard.releaseAll();
}

// send text using Keyboard.print (native method)
void sendText(const String &text) {
  if (text.length() == 0) return;
  // Keyboard.print handles most ASCII and modifiers internally
  Keyboard.print(text);
  delay(10);
}

// Send media/consumer control
void sendMedia(uint16_t usage) {
  if (usage == 0) return;
  Consumer.press(usage);
  delay(20);
  Consumer.release();
}

// Mouse helpers using new API
void mouseMove(int8_t x, int8_t y, int8_t wheel = 0) {
    Mouse.move(x, y);
    // No scroll API on ESP32-S2 core 3.2.1
}

void mouseClick(uint8_t buttons) {
  // 1=left,2=right,4=middle
  if (buttons & 1) Mouse.click(MOUSE_LEFT);
  if (buttons & 2) Mouse.click(MOUSE_RIGHT);
  if (buttons & 4) Mouse.click(MOUSE_MIDDLE);
}

// ----------------------------- LED Helpers --------------------------------
void setKeyLedColor(int keyIndex, uint8_t r, uint8_t g, uint8_t b) {
  if (keyIndex < 0 || keyIndex >= WS_LED_COUNT) return;
  strip.setPixelColor(keyIndex, strip.Color(r,g,b));
  strip.show();
}

void flashAll(uint8_t r, uint8_t g, uint8_t b, int times=2, int msOn=120, int msOff=80) {
  for (int t=0;t<times;++t) {
    for (int i=0;i<WS_LED_COUNT;++i) strip.setPixelColor(i, strip.Color(r,g,b));
    strip.show();
    delay(msOn);
    strip.clear();
    strip.show();
    delay(msOff);
  }
}

void breatheAll(uint8_t r, uint8_t g, uint8_t b, int cycles=2) {
  for (int c=0;c<cycles;++c) {
    for (int v=0; v<=255; v+=5) {
      for (int i=0;i<WS_LED_COUNT;++i) strip.setPixelColor(i, strip.Color((r*v)/255,(g*v)/255,(b*v)/255));
      strip.show();
      delay(8);
    }
    for (int v=255; v>=0; v-=5) {
      for (int i=0;i<WS_LED_COUNT;++i) strip.setPixelColor(i, strip.Color((r*v)/255,(g*v)/255,(b*v)/255));
      strip.show();
      delay(8);
    }
  }
}

// simple rainbow cycle
void rainbowCycle(int wait) {
  uint16_t i, j;
  for (j = 0; j < 256; j++) {
    for (i = 0; i < strip.numPixels(); i++) {
      // wheel function simplified: create color from j + i index
      uint8_t hue = (i * 256 / strip.numPixels() + j) & 255;
      // convert one-channel hue to RGB roughly
      uint8_t r = (hue < 85) ? (hue * 3) : (hue < 170 ? (255 - (hue - 85) * 3) : 0);
      uint8_t g = (hue < 85) ? 0 : (hue < 170 ? (hue - 85) * 3 : (255 - (hue - 170) * 3));
      uint8_t b = (hue < 85) ? (255 - hue * 3) : (hue < 170 ? 0 : (hue - 170) * 3);
      strip.setPixelColor(i, strip.Color(r,g,b));
    }
    strip.show();
    delay(wait);
  }
}

// ----------------------------- JSON / Profiles -----------------------------
bool fileExists(const char *path) {
  return LittleFS.exists(path);
}

String readFileStr(const char *path) {
  File f = LittleFS.open(path, "r");
  if (!f) return String();
  String s;
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

bool loadProfile(int id) {
  if (id < 1 || id > NUM_PROFILES) return false;
  const char *file = profileFiles[id-1];
  if (!fileExists(file)) {
    Serial.printf("Profile %d file not found. Creating default.\n", id);
    // create default minimal profile
    StaticJsonDocument<512> tmp;
    tmp["profile_name"] = String("Profile") + String(id);
    tmp["idle_animation"] = "none";
    tmp["default_delay"] = 30;
    tmp["keys"] = JsonArray();
    String out;
    serializeJson(tmp, out);
    writeFileStr(file, out);
  }
  String s = readFileStr(file);
  if (s.length() == 0) return false;
  DeserializationError err = deserializeJson(profileDoc, s);
  if (err) {
    Serial.print("Failed to parse profile JSON: ");
    Serial.println(err.c_str());
    return false;
  }
  profileLoaded = true;
  currentProfile = id;
  // apply profile-level LED or animation if any
  const char* anim = profileDoc["idle_animation"] | "none";
  if (strcmp(anim,"breathe")==0) idleAnimation = 1;
  else if (strcmp(anim,"rainbow")==0) idleAnimation = 2;
  else idleAnimation = 0;
  Serial.printf("Loaded profile %d (%s)\n", id, profileDoc["profile_name"] | "unnamed");
  updateProfileLEDs();
  return true;
}

// ----------------------------- Macro Engine -------------------------------

// Forward declaration
void runActions(JsonArray actions);

// Execute a single Json action object
void executeAction(JsonObject act) {
  if (!act.containsKey("type")) return;
  String type = act["type"].as<String>();
  type.toLowerCase();

  if (type == "comment") {
    // no-op
    return;
  }
  else if (type == "delay") {
    int ms = act["ms"] | 0;
    if (ms < 0) ms = 0;
    delay(ms);
    return;
  }
  else if (type == "key") {
    String v = act["value"].as<String>();
    pressKey(v);
    delay(profileDoc["default_delay"] | 30);
    return;
  }
  else if (type == "keycombo") {
    if (act.containsKey("keys") && act["keys"].is<JsonArray>()) {
      sendKeyCombo(act["keys"].as<JsonArray>());
      delay(profileDoc["default_delay"] | 30);
    }
    return;
  }
  else if (type == "text") {
    String txt = act["value"].as<String>();
    if (txt.length() > MAX_TEXT_LEN) txt = txt.substring(0, MAX_TEXT_LEN);
    sendText(txt);
    delay(profileDoc["default_delay"] | 30);
    return;
  }
  else if (type == "multiline") {
    String txt = act["value"].as<String>();
    if (txt.length() > MAX_TEXT_LEN) txt = txt.substring(0, MAX_TEXT_LEN);
    sendText(txt);
    delay(profileDoc["default_delay"] | 30);
    return;
  }
  else if (type == "hold") {
    String k = act["key"].as<String>();
    uint8_t code = modifierNameToCode(k);
    if (code) {
      Keyboard.press(code);
      delay(10);
    } else {
      uint8_t hid = keyNameToHid(k);
      if (hid) Keyboard.press(hid);
    }
    return;
  }
  else if (type == "release") {
    Keyboard.releaseAll();
    return;
  }
  else if (type == "repeat") {
    int count = act["count"] | 1;
    if (count < 1) count = 1;
    if (count > MAX_REPEAT_COUNT) count = MAX_REPEAT_COUNT;
    if (act.containsKey("actions") && act["actions"].is<JsonArray>()) {
      for (int i=0;i<count;i++) {
        runActions(act["actions"].as<JsonArray>());
      }
    }
    return;
  }
  else if (type == "media") {
    String v = act["value"].as<String>();
    uint16_t code = mediaNameToCode(v);
    if (code) sendMedia(code);
    return;
  }
  else if (type == "mouse_move") {
    int x = act["x"] | 0;
    int y = act["y"] | 0;
    mouseMove(x,y);
    return;
  }
  else if (type == "mouse_click") {
    String b = act["button"].as<String>();
    uint8_t btn = 1;
    if (b.equalsIgnoreCase("LEFT")) btn = 1;
    else if (b.equalsIgnoreCase("RIGHT")) btn = 2;
    else if (b.equalsIgnoreCase("MIDDLE")) btn = 4;
    mouseClick(btn);
    return;
  }
  else if (type == "mouse_scroll") {
    int v = act["value"] | 0;
    return;
  }
  else if (type == "led") {
    if (act.containsKey("color") && act["color"].is<JsonArray>()) {
      JsonArray col = act["color"].as<JsonArray>();
      int r = col[0] | 0;
      int g = col[1] | 0;
      int b = col[2] | 0;
      // apply to all for simplicity
      for (int i=0;i<WS_LED_COUNT;i++) strip.setPixelColor(i, strip.Color(r,g,b));
      strip.show();
    }
    return;
  }
  else if (type == "led_anim") {
    String a = act["value"].as<String>();
    if (a.equalsIgnoreCase("flash")) {
      if (act.containsKey("color") && act["color"].is<JsonArray>()) {
        JsonArray col = act["color"].as<JsonArray>();
        flashAll(col[0]|0,col[1]|0,col[2]|0,2,120,80);
      } else {
        flashAll(255,255,255,2,120,80);
      }
    } else if (a.equalsIgnoreCase("breathe")) {
      if (act.containsKey("color") && act["color"].is<JsonArray>()) {
        JsonArray col = act["color"].as<JsonArray>();
        breatheAll(col[0]|0,col[1]|0,col[2]|0,1);
      } else {
        breatheAll(255,255,255,1);
      }
    }
    return;
  }
  else if (type == "profile") {
    int p = act["value"] | 1;
    if (p < 1) p = 1;
    if (p > NUM_PROFILES) p = NUM_PROFILES;
    loadProfile(p);
    return;
  }
  // unknown types ignored
}

// Run actions sequentially
void runActions(JsonArray actions) {
  for (JsonVariant v : actions) {
    if (!v.is<JsonObject>()) continue;
    JsonObject act = v.as<JsonObject>();
    executeAction(act);
    // small safety delay between actions
    delay(profileDoc["default_delay"] | 30);
  }
}

// Execute macro for a key id (1..12)
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
        JsonArray acts = ko["actions"].as<JsonArray>();
        runActions(acts);
        macroRunning = false;
      }
      return;
    }
  }
}

// ----------------------------- Input Scanning -----------------------------
void initButtons() {
  for (int i=0;i<NUM_KEYS;i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    keyState[i] = digitalRead(buttonPins[i]) ? 0 : 1; // active low assumed
    keyLastChange[i] = millis();
    keyLastPressMillis[i] = 0;
  }
  pinMode(LED_PIN_1, OUTPUT);
  pinMode(LED_PIN_2, OUTPUT);
  pinMode(LED_PIN_3, OUTPUT);
  
  updateProfileLEDs();
  touchSetCycles(0x1000);
}

static int baselineA = 0;
static int baselineB = 0;

bool touchPressed(int pin) {
    static bool calibrated = false;
    if (!calibrated) {
        baselineA = touchRead(TOUCH_PIN_1);
        baselineB = touchRead(TOUCH_PIN_2);
        calibrated = true;
    }
    int val = touchRead(pin);

    if (pin == TOUCH_PIN_1)
        return val < (baselineA - 15);

    if (pin == TOUCH_PIN_2)
        return val < (baselineB - 15);

    return false;
}

unsigned long touchLastDebounceA = 0;
unsigned long touchLastDebounceB = 0;

void scanTouchProfileSwitch() {
  static bool lastA = false, lastB = false;
  bool a = touchPressed(TOUCH_PIN_1);
  bool b = touchPressed(TOUCH_PIN_2);

  // simple debounce / edge detect
  if (a && !lastA && millis() - touchLastDebounceA > 300) {
    // tap A -> next profile
    int np = currentProfile + 1;
    if (np > NUM_PROFILES) np = 1;
    loadProfile(np);
    flashAll(0,0,255,1,140,60);
    touchLastDebounceA = millis();
  }
  if (b && !lastB && millis() - touchLastDebounceB > 300) {
    int np = currentProfile - 1;
    if (np < 1) np = NUM_PROFILES;
    loadProfile(np);
    flashAll(0,255,0,1,140,60);
    touchLastDebounceB = millis();
  }

  // both held -> failsafe disable macros
  if (a && b) {
    static unsigned long bothHoldStart = 0;
    if (bothHoldStart == 0) bothHoldStart = millis();
    if (millis() - bothHoldStart > 3000) {
      // disable macros (simple toggle)
      profileLoaded = false;
      flashAll(255,0,0,3,120,80);
      bothHoldStart = 0;
    }
  } else {
    // reset
  }

  lastA = a; lastB = b;
}

// scan keys, detect rising edge and run macros
void scanKeys() {
  for (int i=0;i<NUM_KEYS;i++) {
    bool raw = digitalRead(buttonPins[i]) == LOW; // active low
    if (raw != keyState[i]) {
      // changed, debounce
      if (millis() - keyLastChange[i] > DEFAULT_DEBOUNCE_MS) {
        keyState[i] = raw;
        keyLastChange[i] = millis();
        if (raw) {
          // pressed
          keyLastPressMillis[i] = millis();
          // light key LED highlight
          // read default color from profile if available
          if (profileLoaded && profileDoc.containsKey("keys")) {
            JsonArray keysArr = profileDoc["keys"].as<JsonArray>();
            for (JsonVariant kv : keysArr) {
              JsonObject ko = kv.as<JsonObject>();
              int id = ko["id"] | 0;
              if (id == (i+1)) {
                if (ko.containsKey("led_color") && ko["led_color"].is<JsonArray>()) {
                  JsonArray col = ko["led_color"].as<JsonArray>();
                  setKeyLedColor(i, col[0]|0, col[1]|0, col[2]|0);
                } else {
                  setKeyLedColor(i, 255,255,255);
                }
                break;
              }
            }
          } else {
            setKeyLedColor(i, 255,255,255);
          }

          // run macro in-line (blocking)
          if (!macroRunning && profileLoaded) {
            runMacroForKey(i+1);
          }
        } else {
          // released -> restore idle color or clear
          setKeyLedColor(i, 0,0,0);
        }
      }
    } // changed
  }
}

// ----------------------------- Serial Upload -------------------------------
void handleSerialInput() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (!serialRecording) {
      if (line.startsWith("###BEGIN###")) {
        String target = line.substring(11);
        target.trim();
        if (target.length() > 0) {
          serialRecording = true;
          serialBuffer = "";
          serialTargetFile = "/" + target;
          Serial.printf("Recording JSON for %s\n", serialTargetFile.c_str());
        }
      }
    } else {
      if (line == "###END###") {
        // write to file
        if (serialTargetFile.length() > 0) {
          bool ok = writeFileStr(serialTargetFile.c_str(), serialBuffer);
          Serial.printf("Wrote %s -> %s\n", serialTargetFile.c_str(), ok ? "OK" : "FAIL");
          // if target matches current profile file name, reload
          String cur = String(profileFiles[currentProfile-1]);
          if (serialTargetFile.equalsIgnoreCase(cur)) {
            loadProfile(currentProfile);
          }
        }
        serialRecording = false;
        serialTargetFile = "";
      } else {
        serialBuffer += line;
        serialBuffer += "\n";
      }
    }
  }
}

// ----------------------------- Setup & Loop --------------------------------
void setup() {
  // init serial USB first
  Serial.begin(SERIAL_BAUD);
  unsigned long tstart = millis();
  while (!Serial && millis() - tstart < 2000) delay(10);
  Serial.println("MacroPad starting...");

  // Mount LittleFS (auto-format if needed)
  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS mount failed or formatted!");
  } else {
    Serial.println("LittleFS mounted");
  }

  // init NeoPixel
  strip.begin();
  strip.setBrightness(64);
  strip.clear();
  strip.show();

  initButtons();
  

  // Initialize USB HID stack (Arduino-ESP32 core 3.x)
  USB.begin();
  delay(10);
  Keyboard.begin();
  Mouse.begin();
  Consumer.begin();
  delay(50);

  // default load profile 1
  if (!loadProfile(1)) {
    Serial.println("Failed to load profile1, created default");
    loadProfile(1);
  }
  Serial.println("Ready");
}

void loop() {
  // handle serial JSON upload
  handleSerialInput();

  // scan touch for profile change
  scanTouchProfileSwitch();

  // scan keys
  scanKeys();

  // idle LED animation if no macro running
  if (!macroRunning) {
    if (idleAnimation == 1) { // breathe
      breatheAll(64,64,64,1);
      delay(10);
    } else if (idleAnimation == 2) {
      rainbowCycle(5);
    }
  }

  delay(5);
}
