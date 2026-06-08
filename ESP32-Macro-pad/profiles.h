/* Profile storage + active-profile state. */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

extern JsonDocument profileDoc;   // ArduinoJson 7 elastic document
extern bool profileLoaded;
extern int  currentProfile;       // 1..NUM_PROFILES
extern int  idleAnimation;        // 0 none, 1 breathe, 2 rainbow

bool ensureDefaultProfile(int id);
bool loadProfile(int id);
void updateProfileLEDs();
void ensureAllDefaultProfiles();
