/* Frame-based, non-blocking LED engine.
 *
 * Holds a per-key colour framebuffer that eases smoothly toward a target each
 * frame, with a single strip.show() per frame. Per-key resting colours come
 * from the profile's led_color; presses add a smooth white highlight; idle
 * breathe/rainbow modes and a global flash pulse layer on top. Nothing blocks. */
#pragma once
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

extern Adafruit_NeoPixel strip;

enum LedIdleMode { LED_IDLE_NONE = 0, LED_IDLE_BREATHE = 1, LED_IDLE_RAINBOW = 2 };

void ledsBegin();
void ledsTick();                       // call every loop(); frame-rate limited

// Resting (base) colours.
void ledsSetKeyBase(int index, uint8_t r, uint8_t g, uint8_t b);
void ledsSetAllBase(uint8_t r, uint8_t g, uint8_t b);
void ledsApplyProfile();               // read led_color + idle_animation from profileDoc
void ledsSetIdleMode(LedIdleMode mode);
void ledsSetBrightness(uint8_t b);

// Transient feedback.
void ledsKeyDown(int index);           // sustained press highlight on a key
void ledsKeyUp(int index);             // release -> highlight fades out
void ledsFlash(uint8_t r, uint8_t g, uint8_t b);   // non-blocking whole-pad pulse
