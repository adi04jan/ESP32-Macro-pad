/* Profile storage + active-profile state. */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

extern JsonDocument profileDoc;   // ArduinoJson 7 elastic document
extern bool profileLoaded;
extern int  currentProfile;       // 1..NUM_PROFILES
extern int  idleAnimation;        // mirrors LedIdleMode: 0 none,1 breathe,2 rainbow,3 wave,4 comet,5 twinkle,6 ripple

bool ensureDefaultProfile(int id);
bool loadProfile(int id);
bool loadProfileSafe(int id);     // load; on failure rewrite the default and retry
void updateProfileLEDs();
void ensureAllDefaultProfiles();
