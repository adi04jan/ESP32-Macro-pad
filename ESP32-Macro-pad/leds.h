/* NeoPixel control + non-blocking idle animations. */
#pragma once
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

extern Adafruit_NeoPixel strip;

void ledsBegin();
void setKeyLed(int index, uint8_t r, uint8_t g, uint8_t b);
void ledsSetAll(uint8_t r, uint8_t g, uint8_t b);
void flashAll(uint8_t r, uint8_t g, uint8_t b, int times = 2, int msOn = 120, int msOff = 80);
void breatheTick(uint8_t r, uint8_t g, uint8_t b);  // advance one breathe frame
void rainbowTick();                                 // advance one rainbow frame
