/* Name <-> HID usage lookup tables (keys, modifiers, media). */
#pragma once
#include <Arduino.h>

uint8_t  keyNameToHid(const String &s);       // 0 if not a named key
uint8_t  modifierNameToCode(const String &s);  // 0 if not a modifier
uint16_t mediaNameToCode(const String &s);     // 0 if not a media key
