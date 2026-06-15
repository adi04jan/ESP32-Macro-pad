/* USB HID layer: keyboard / mouse / consumer + a real Telephony HID device. */
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "USBHIDKeyboard.h"
#include "USBHIDMouse.h"
#include "USBHIDConsumerControl.h"

extern USBHIDKeyboard Keyboard;
extern USBHIDMouse Mouse;
extern USBHIDConsumerControl Consumer;

void hidBegin();                                   // call after USB.begin()
void hidPressKey(const String &name);              // single key tap
void hidSendKeyCombo(JsonArrayConst keys);         // modifiers + keys, then release
void hidHold(const String &name);                  // press & hold (no release)
void hidReleaseAll();
void hidSendMedia(uint16_t usage);
void hidMouseMove(int x, int y, int wheel);
void hidMouseClick(uint8_t buttons);               // bitmask 1=L 2=R 4=M
bool hidSendTelephony(const String &which);        // MIC_MUTE/ANSWER/DECLINE
