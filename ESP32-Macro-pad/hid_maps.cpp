#include "hid_maps.h"
#include "USBHIDKeyboard.h"
#include "USBHIDConsumerControl.h"

struct KeyMapEntry { const char *name; uint8_t hid; };
static const KeyMapEntry keyMap[] = {
  { "A", 0x04 }, { "B", 0x05 }, { "C", 0x06 }, { "D", 0x07 }, { "E", 0x08 }, { "F", 0x09 }, { "G", 0x0A }, { "H", 0x0B },
  { "I", 0x0C }, { "J", 0x0D }, { "K", 0x0E }, { "L", 0x0F }, { "M", 0x10 }, { "N", 0x11 }, { "O", 0x12 }, { "P", 0x13 },
  { "Q", 0x14 }, { "R", 0x15 }, { "S", 0x16 }, { "T", 0x17 }, { "U", 0x18 }, { "V", 0x19 }, { "W", 0x1A }, { "X", 0x1B },
  { "Y", 0x1C }, { "Z", 0x1D }, { "1", 0x1E }, { "2", 0x1F }, { "3", 0x20 }, { "4", 0x21 }, { "5", 0x22 }, { "6", 0x23 },
  { "7", 0x24 }, { "8", 0x25 }, { "9", 0x26 }, { "0", 0x27 }, { "ENTER", 0x28 }, { "ESC", 0x29 }, { "BACKSPACE", 0x2A },
  { "TAB", 0x2B }, { "SPACE", 0x2C }, { "MINUS", 0x2D }, { "EQUAL", 0x2E }, { "LEFT_BRACE", 0x2F }, { "RIGHT_BRACE", 0x30 },
  { "BACKSLASH", 0x31 }, { "SEMICOLON", 0x33 }, { "QUOTE", 0x34 }, { "TILDE", 0x35 }, { "COMMA", 0x36 }, { "DOT", 0x37 },
  { "SLASH", 0x38 }, { "CAPS_LOCK", 0x39 }, { "F1", 0x3A }, { "F2", 0x3B }, { "F3", 0x3C }, { "F4", 0x3D }, { "F5", 0x3E },
  { "F6", 0x3F }, { "F7", 0x40 }, { "F8", 0x41 }, { "F9", 0x42 }, { "F10", 0x43 }, { "F11", 0x44 }, { "F12", 0x45 },
  { "INSERT", 0x49 }, { "HOME", 0x4A }, { "PAGEUP", 0x4B }, { "DELETE", 0x4C }, { "END", 0x4D }, { "PAGEDOWN", 0x4E },
  { "RIGHT_ARROW", 0x4F }, { "LEFT_ARROW", 0x50 }, { "DOWN_ARROW", 0x51 }, { "UP_ARROW", 0x52 }, { nullptr, 0 }
};

struct ModMapEntry { const char *name; uint8_t code; };
static const ModMapEntry modMap[] = {
  { "LEFT_CTRL", KEY_LEFT_CTRL }, { "LEFT_SHIFT", KEY_LEFT_SHIFT }, { "LEFT_ALT", KEY_LEFT_ALT }, { "LEFT_GUI", KEY_LEFT_GUI },
  { "RIGHT_CTRL", KEY_RIGHT_CTRL }, { "RIGHT_SHIFT", KEY_RIGHT_SHIFT }, { "RIGHT_ALT", KEY_RIGHT_ALT }, { "RIGHT_GUI", KEY_RIGHT_GUI },
  { nullptr, 0 }
};

struct MediaMapEntry { const char *name; uint16_t code; };
static const MediaMapEntry mediaMap[] = {
  { "PLAY_PAUSE", HID_USAGE_CONSUMER_PLAY_PAUSE }, { "STOP", HID_USAGE_CONSUMER_STOP }, { "NEXT", HID_USAGE_CONSUMER_SCAN_NEXT },
  { "PREVIOUS", HID_USAGE_CONSUMER_SCAN_PREVIOUS }, { "MUTE", HID_USAGE_CONSUMER_MUTE }, { "VOLUME_UP", HID_USAGE_CONSUMER_VOLUME_INCREMENT },
  { "VOLUME_DOWN", HID_USAGE_CONSUMER_VOLUME_DECREMENT }, { nullptr, 0 }
};

uint8_t keyNameToHid(const String &s) {
  for (int i = 0; keyMap[i].name; ++i)
    if (s.equalsIgnoreCase(keyMap[i].name)) return keyMap[i].hid;
  return 0;
}

uint8_t modifierNameToCode(const String &s) {
  for (int i = 0; modMap[i].name; ++i)
    if (s.equalsIgnoreCase(modMap[i].name)) return modMap[i].code;
  return 0;
}

uint16_t mediaNameToCode(const String &s) {
  for (int i = 0; mediaMap[i].name; ++i)
    if (s.equalsIgnoreCase(mediaMap[i].name)) return mediaMap[i].code;
  return 0;
}
