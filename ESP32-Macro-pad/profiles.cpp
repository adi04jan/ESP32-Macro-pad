#include "profiles.h"
#include "config.h"
#include "storage.h"
#include <LittleFS.h>

JsonDocument profileDoc;
bool profileLoaded = false;
int  currentProfile = 1;
int  idleAnimation = 0;

static String profilePath(int id) {
  return String("/profile") + String(id) + ".json";
}

bool ensureDefaultProfile(int id) {
  if (id < 1 || id > NUM_PROFILES) return false;
  String fname = profilePath(id);
  if (LittleFS.exists(fname.c_str())) return true;

  JsonDocument tmp;
  tmp["schema_version"] = SCHEMA_VERSION;
  tmp["profile_name"] = String("Profile") + String(id);
  tmp["idle_animation"] = "none";
  tmp["default_delay"] = 30;
  tmp["keys"].to<JsonArray>();
  String out;
  serializeJson(tmp, out);
  return writeFileStr(fname.c_str(), out);
}

void ensureAllDefaultProfiles() {
  for (int i = 1; i <= NUM_PROFILES; i++) ensureDefaultProfile(i);
}

void updateProfileLEDs() {
  digitalWrite(LED_PIN_1, currentProfile == 1 ? HIGH : LOW);
  digitalWrite(LED_PIN_2, currentProfile == 2 ? HIGH : LOW);
  digitalWrite(LED_PIN_3, currentProfile == 3 ? HIGH : LOW);
}

bool loadProfile(int id) {
  if (id < 1 || id > NUM_PROFILES) return false;
  ensureDefaultProfile(id);
  String s = readFileStr(profilePath(id).c_str());
  if (s.length() == 0) return false;

  profileDoc.clear();
  DeserializationError err = deserializeJson(profileDoc, s);
  if (err) {
    Serial.printf("Profile %d parse error: %s\n", id, err.c_str());
    profileLoaded = false;
    return false;
  }
  profileLoaded = true;
  currentProfile = id;

  const char *anim = profileDoc["idle_animation"] | "none";
  if (strcmp(anim, "breathe") == 0) idleAnimation = 1;
  else if (strcmp(anim, "rainbow") == 0) idleAnimation = 2;
  else idleAnimation = 0;

  Serial.printf("Loaded profile %d (%s)\n", id,
                profileDoc["profile_name"] | "unnamed");
  updateProfileLEDs();
  return true;
}
