import json
import os

TK_TO_ESP32_MAP = {
    "Control_L": "LEFT_CTRL", "Control_R": "RIGHT_CTRL",
    "Shift_L": "LEFT_SHIFT", "Shift_R": "RIGHT_SHIFT",
    "Alt_L": "LEFT_ALT", "Alt_R": "RIGHT_ALT",
    "Win_L": "LEFT_GUI", "Win_R": "RIGHT_GUI",
    "Return": "ENTER", "Escape": "ESC", "BackSpace": "BACKSPACE",
    "Tab": "TAB", "space": "SPACE", "minus": "MINUS", "equal": "EQUAL",
    "bracketleft": "LEFT_BRACE", "bracketright": "RIGHT_BRACE",
    "backslash": "BACKSLASH", "semicolon": "SEMICOLON",
    "apostrophe": "QUOTE", "grave": "TILDE", "comma": "COMMA",
    "period": "DOT", "slash": "SLASH", "Caps_Lock": "CAPS_LOCK",
    "Insert": "INSERT", "Home": "HOME", "Prior": "PAGEUP", "Delete": "DELETE", "End": "END",
    "Next": "PAGEDOWN", "Right": "RIGHT_ARROW", "Left": "LEFT_ARROW", "Down": "DOWN_ARROW", "Up": "UP_ARROW"
}

class AppSettings:
    def __init__(self, filename="macropad_settings.json"):
        self.filename = filename
        self.settings = {
            "ai_provider": "Ollama (Local)",
            "ai_key": "http://localhost:11434",
            "ai_model": "llama3:70b",
            "widget_alpha": 0.98,
            "auto_switch_enabled": False,
            "ai_debug_enabled": False
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.settings.update(json.load(f))
            except Exception as e:
                print("Error loading settings:", e)

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print("Error saving settings:", e)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
