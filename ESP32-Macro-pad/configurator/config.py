"""
Application configuration: persisted settings and the Tk<->firmware key map.

This is the single home for these — the old code duplicated TK_TO_ESP32_MAP and
the settings defaults across v3/v4/release.
"""

from __future__ import annotations

import json
import os

# Firmware / connection constants.
SERIAL_BAUD = 115200
NUM_KEYS = 12
PROFILE_FILES = ["/profile1.json", "/profile2.json", "/profile3.json"]

# Tk keysym -> firmware key name (used by the keycombo recorder).
TK_TO_ESP32_MAP = {
    "Control_L": "LEFT_CTRL", "Control_R": "RIGHT_CTRL",
    "Shift_L": "LEFT_SHIFT", "Shift_R": "RIGHT_SHIFT",
    "Alt_L": "LEFT_ALT", "Alt_R": "RIGHT_ALT",
    "Win_L": "LEFT_GUI", "Win_R": "RIGHT_GUI", "Super_L": "LEFT_GUI",
    "Return": "ENTER", "Escape": "ESC", "BackSpace": "BACKSPACE",
    "Tab": "TAB", "space": "SPACE", "minus": "MINUS", "equal": "EQUAL",
    "bracketleft": "LEFT_BRACE", "bracketright": "RIGHT_BRACE",
    "backslash": "BACKSLASH", "semicolon": "SEMICOLON",
    "apostrophe": "QUOTE", "grave": "TILDE", "comma": "COMMA",
    "period": "DOT", "slash": "SLASH", "Caps_Lock": "CAPS_LOCK",
    "Insert": "INSERT", "Home": "HOME", "Prior": "PAGEUP",
    "Delete": "DELETE", "End": "END", "Next": "PAGEDOWN",
    "Right": "RIGHT_ARROW", "Left": "LEFT_ARROW",
    "Down": "DOWN_ARROW", "Up": "UP_ARROW",
}

DEFAULT_SETTINGS = {
    "ai_provider": "Ollama (Local)",   # "Ollama (Local)" | "Gemini" | "OpenAI"
    "ai_endpoint": "http://localhost:11434",
    "ai_key": "",                       # API key for cloud providers
    "ai_model": "llama3",
    "widget_alpha": 0.98,
    "auto_switch_enabled": False,
    "ai_debug_enabled": False,
    "last_port": "",
}


class AppSettings:
    """Settings with enforced defaults and type-checked loading."""

    def __init__(self, filename="macropad_settings.json"):
        self.filename = filename
        self.settings = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[settings] load failed, using defaults: {e}")
            return
        if not isinstance(data, dict):
            return
        # Only accept keys we know, and only if the type matches the default.
        for key, default in DEFAULT_SETTINGS.items():
            if key in data and isinstance(data[key], type(default)):
                self.settings[key] = data[key]

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except OSError as e:
            print(f"[settings] save failed: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key, value):
        self.settings[key] = value
        self.save()
