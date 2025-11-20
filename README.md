# ESP32-Macro-pad
ESP32 S2 lolin mini powered Macro pad, Inspired by Work Louder Creator Micro but for programmer

### 12-Key Programmable Macropad • JSON Profiles • Touch Switching • RGB WS2812 • HID Keyboard/Mouse

A fully-customizable **ESP32-S2 (LOLIN S2 Pico)** macropad featuring:

- **12 mechanical keys**
- **12 WS2812 RGB LEDs**
- **USB HID Keyboard + Mouse + Media Keys**
- **3 user profiles**
- **Touch-pads for profile switching**
- **JSON-based macro configuration**
- **Serial CLI for updating profiles**

Designed for **Git / Linux / development workflows**.

---

## ⭐ Features

### 🔵 Macro Capabilities per Key
Each key can trigger any of the following:

- Single keypress  
- Key combos (CTRL + SHIFT + R)  
- Multi-line scripts / commands  
- Text blocks  
- Mouse actions (move/click)  
- Media keys (volume, play/pause)  
- Delays, loops, hold/release  
- LED effects  
- Profile switching  

### 🌈 Lighting
- Per-key RGB  
- Flash animation  
- Breathe animation  
- Optional idle animation  

### 🟢 Profile Switching
2 capacitive touch pads:

| Touch Pad | Function |
|-----------|----------|
| GPIO2 | Next Profile |
| GPIO3 | Previous Profile |
| Both (3 sec hold) | Reset profile |

### 🔧 Serial CLI
Built-in command-line for diagnostics & file editing:

