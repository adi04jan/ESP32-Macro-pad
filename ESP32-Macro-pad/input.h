/* Buttons (non-blocking debounce) + capacitive touch profile switching. */
#pragma once
#include <Arduino.h>

void inputBegin();
void scanKeys();
void scanTouch();
void inputApplyProfile();   // load optional per-key debounce from the active profile
