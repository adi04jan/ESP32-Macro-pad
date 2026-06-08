"""
Canonical macro action schema — the single source of truth.

Everything that produces or consumes macros (the GUI editor, the AI pipeline,
the on-disk profile format) validates against the definitions here. The firmware
mirrors the same enums in `config.h` / `hid_maps.*`, so a macro that validates
here is guaranteed to be executable on the device.

The schema is derived directly from the firmware's `executeAction` and its
key/modifier/media tables.

Public API:
    SCHEMA_VERSION, ACTION_TYPES, and the enum lists.
    action_schema()           -> JSON Schema for a single action
    actions_schema()          -> JSON Schema for an array of actions
    shortcut_schema()         -> JSON Schema for an AI "shortcut" object
    shortcuts_schema()        -> JSON Schema for an array of shortcuts
    validate_actions(actions) -> (ok: bool, errors: list[str])
    validate_shortcuts(items) -> (ok: bool, errors: list[str])
    repair_actions(actions)   -> list  (best-effort, drops the unfixable)
    repair_shortcuts(items)   -> list
"""

from __future__ import annotations

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - surfaced at runtime
    raise ImportError(
        "The 'jsonschema' package is required. Install it with: pip install jsonschema"
    ) from exc


SCHEMA_VERSION = 1

# Firmware limits (mirror config.h).
MAX_TEXT_LEN = 4096
MAX_REPEAT_COUNT = 50
NUM_PROFILES = 3
MOUSE_AXIS_MIN = -127
MOUSE_AXIS_MAX = 127

# ----------------------------------------------------------------------------
# Enums — must stay in lockstep with the firmware tables.
# ----------------------------------------------------------------------------
_LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
_DIGITS = [str(d) for d in range(10)]
_FUNCTION_KEYS = [f"F{n}" for n in range(1, 13)]
_NAMED_KEYS = [
    "ENTER", "ESC", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUAL",
    "LEFT_BRACE", "RIGHT_BRACE", "BACKSLASH", "SEMICOLON", "QUOTE", "TILDE",
    "COMMA", "DOT", "SLASH", "CAPS_LOCK", "INSERT", "HOME", "PAGEUP",
    "DELETE", "END", "PAGEDOWN",
    "RIGHT_ARROW", "LEFT_ARROW", "DOWN_ARROW", "UP_ARROW",
]

# Plain keys understood by the firmware `key` action (keyNameToHid table).
KEY_NAMES = _LETTERS + _DIGITS + _FUNCTION_KEYS + _NAMED_KEYS

MODIFIER_NAMES = [
    "LEFT_CTRL", "LEFT_SHIFT", "LEFT_ALT", "LEFT_GUI",
    "RIGHT_CTRL", "RIGHT_SHIFT", "RIGHT_ALT", "RIGHT_GUI",
]

# keycombo / hold accept both plain keys and modifiers.
KEY_AND_MODIFIER = MODIFIER_NAMES + KEY_NAMES

MEDIA_NAMES = [
    "PLAY_PAUSE", "STOP", "NEXT", "PREVIOUS", "MUTE",
    "VOLUME_UP", "VOLUME_DOWN",
]

TELEPHONY_NAMES = ["MIC_MUTE", "ANSWER", "DECLINE"]
MOUSE_BUTTONS = ["LEFT", "RIGHT", "MIDDLE"]
LED_ANIM_VALUES = ["flash", "breathe"]
IDLE_ANIMATIONS = ["none", "breathe", "rainbow", "flash"]

ACTION_TYPES = [
    "comment", "delay", "key", "keycombo", "text", "multiline",
    "hold", "release", "repeat", "media", "mouse_move", "mouse_click",
    "led", "led_anim", "profile", "telephony",
]

# Lookup sets (fast membership tests for repair).
_KEY_AND_MOD_SET = set(KEY_AND_MODIFIER)
_KEY_SET = set(KEY_NAMES)

# Common aliases the AI (or a human) might emit -> canonical name.
ALIASES = {
    "CTRL": "LEFT_CTRL", "CONTROL": "LEFT_CTRL",
    "SHIFT": "LEFT_SHIFT", "ALT": "LEFT_ALT", "OPTION": "LEFT_ALT",
    "GUI": "LEFT_GUI", "WIN": "LEFT_GUI", "WINDOWS": "LEFT_GUI",
    "CMD": "LEFT_GUI", "COMMAND": "LEFT_GUI", "SUPER": "LEFT_GUI", "META": "LEFT_GUI",
    "RETURN": "ENTER", "ESCAPE": "ESC", "DEL": "DELETE",
    "PGUP": "PAGEUP", "PGDN": "PAGEDOWN", "PAGE_UP": "PAGEUP", "PAGE_DOWN": "PAGEDOWN",
    "SPACEBAR": "SPACE", "BKSP": "BACKSPACE", "PERIOD": "DOT", "FULLSTOP": "DOT",
    "UP": "UP_ARROW", "DOWN": "DOWN_ARROW", "LEFT": "LEFT_ARROW", "RIGHT": "RIGHT_ARROW",
    "ARROWUP": "UP_ARROW", "ARROWDOWN": "DOWN_ARROW",
    "ARROWLEFT": "LEFT_ARROW", "ARROWRIGHT": "RIGHT_ARROW",
}

# Action-type aliases.
_TYPE_ALIASES = {
    "keypress": "key", "press": "key", "string": "text", "type": "text",
    "combo": "keycombo", "key_combo": "keycombo", "shortcut": "keycombo",
    "wait": "delay", "sleep": "delay", "pause": "delay",
    "mousemove": "mouse_move", "mouseclick": "mouse_click", "click": "mouse_click",
    "ledanim": "led_anim", "animation": "led_anim",
}


# ----------------------------------------------------------------------------
# JSON Schema construction
# ----------------------------------------------------------------------------
def _keyish(enum):
    """A key reference: a known name, or any single printable character."""
    return {"anyOf": [
        {"enum": list(enum)},
        {"type": "string", "minLength": 1, "maxLength": 1},
    ]}


def _color():
    return {
        "type": "array",
        "items": {"type": "integer", "minimum": 0, "maximum": 255},
        "minItems": 3, "maxItems": 3,
    }


def _action_variants():
    axis = {"type": "integer", "minimum": MOUSE_AXIS_MIN, "maximum": MOUSE_AXIS_MAX}
    return [
        {"properties": {"type": {"const": "comment"},
                        "value": {"type": "string"}},
         "required": ["type"], "additionalProperties": False},

        {"properties": {"type": {"const": "delay"},
                        "ms": {"type": "integer", "minimum": 0}},
         "required": ["type", "ms"], "additionalProperties": False},

        {"properties": {"type": {"const": "key"}, "value": _keyish(KEY_NAMES)},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "keycombo"},
                        "keys": {"type": "array", "minItems": 1,
                                 "items": _keyish(KEY_AND_MODIFIER)}},
         "required": ["type", "keys"], "additionalProperties": False},

        {"properties": {"type": {"const": "text"},
                        "value": {"type": "string", "maxLength": MAX_TEXT_LEN}},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "multiline"},
                        "value": {"type": "string", "maxLength": MAX_TEXT_LEN}},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "hold"}, "key": _keyish(KEY_AND_MODIFIER)},
         "required": ["type", "key"], "additionalProperties": False},

        {"properties": {"type": {"const": "release"}},
         "required": ["type"], "additionalProperties": False},

        {"properties": {"type": {"const": "repeat"},
                        "count": {"type": "integer", "minimum": 1,
                                  "maximum": MAX_REPEAT_COUNT},
                        "actions": {"type": "array",
                                    "items": {"$ref": "#/$defs/action"}}},
         "required": ["type", "count", "actions"], "additionalProperties": False},

        {"properties": {"type": {"const": "media"}, "value": {"enum": MEDIA_NAMES}},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "mouse_move"},
                        "x": axis, "y": axis, "wheel": axis},
         "required": ["type", "x", "y"], "additionalProperties": False},

        {"properties": {"type": {"const": "mouse_click"},
                        "button": {"enum": MOUSE_BUTTONS}},
         "required": ["type", "button"], "additionalProperties": False},

        {"properties": {"type": {"const": "led"}, "color": _color()},
         "required": ["type", "color"], "additionalProperties": False},

        {"properties": {"type": {"const": "led_anim"},
                        "value": {"enum": LED_ANIM_VALUES}, "color": _color()},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "profile"},
                        "value": {"type": "integer", "minimum": 1,
                                  "maximum": NUM_PROFILES}},
         "required": ["type", "value"], "additionalProperties": False},

        {"properties": {"type": {"const": "telephony"},
                        "value": {"enum": TELEPHONY_NAMES}},
         "required": ["type", "value"], "additionalProperties": False},
    ]


def action_schema():
    """JSON Schema for a single action object (self-contained, with $defs)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"action": {"type": "object", "oneOf": _action_variants()}},
        "$ref": "#/$defs/action",
    }


def actions_schema():
    """JSON Schema for an array of actions."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"action": {"type": "object", "oneOf": _action_variants()}},
        "type": "array",
        "items": {"$ref": "#/$defs/action"},
    }


def shortcut_schema():
    """JSON Schema for an AI-generated shortcut: {key_num, description, actions}."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"action": {"type": "object", "oneOf": _action_variants()}},
        "type": "object",
        "properties": {
            "key_num": {"type": "integer", "minimum": 1, "maximum": 12},
            "description": {"type": "string", "minLength": 1},
            "actions": {"type": "array", "minItems": 1,
                        "items": {"$ref": "#/$defs/action"}},
        },
        "required": ["description", "actions"],
        "additionalProperties": False,
    }


def shortcuts_schema():
    """JSON Schema for an array of AI shortcuts."""
    s = shortcut_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": s["$defs"],
        "type": "array",
        "items": {k: v for k, v in s.items() if not k.startswith("$schema")
                  and k != "$defs"},
    }


# Pre-built validators (compiled once).
_ACTIONS_VALIDATOR = jsonschema.Draft202012Validator(actions_schema())
_SHORTCUTS_VALIDATOR = jsonschema.Draft202012Validator(shortcuts_schema())


def _format_errors(validator, instance):
    errors = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors


def validate_actions(actions):
    """Return (ok, errors) for an array of actions."""
    errors = _format_errors(_ACTIONS_VALIDATOR, actions)
    return (not errors, errors)


def validate_shortcuts(items):
    """Return (ok, errors) for an array of AI shortcut objects."""
    errors = _format_errors(_SHORTCUTS_VALIDATOR, items)
    return (not errors, errors)


def is_valid_actions(actions):
    return _ACTIONS_VALIDATOR.is_valid(actions)


# ----------------------------------------------------------------------------
# Best-effort repair — programmatic only (no LLM). Drops the unfixable.
# ----------------------------------------------------------------------------
def _coerce_int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _norm_key(token):
    """Normalize a single key/modifier token, or None if unrecoverable."""
    if not isinstance(token, str):
        return None
    s = token.strip()
    if not s:
        return None
    up = s.upper()
    up = ALIASES.get(up, up)
    if up in _KEY_AND_MOD_SET:
        return up
    if len(s) == 1:  # arbitrary printable char — preserve case
        return s
    return None


def _repair_action(action):
    if not isinstance(action, dict):
        return None
    raw_type = str(action.get("type", "")).strip().lower()
    t = _TYPE_ALIASES.get(raw_type, raw_type)
    if t not in ACTION_TYPES:
        return None

    if t == "comment":
        out = {"type": t}
        if "value" in action:
            out["value"] = str(action.get("value", ""))
        return out

    if t == "delay":
        return {"type": t, "ms": max(0, _coerce_int(action.get("ms"), 0))}

    if t == "key":
        k = _norm_key(action.get("value"))
        # `key` accepts plain keys or single chars, but not bare modifiers.
        if k and (k in _KEY_SET or len(k) == 1):
            return {"type": t, "value": k}
        return None

    if t == "keycombo":
        keys = action.get("keys")
        if not isinstance(keys, list):
            return None
        normed = [k for k in (_norm_key(x) for x in keys) if k]
        return {"type": t, "keys": normed} if normed else None

    if t in ("text", "multiline"):
        val = action.get("value", "")
        return {"type": t, "value": str(val)[:MAX_TEXT_LEN]}

    if t == "hold":
        k = _norm_key(action.get("key", action.get("value")))
        return {"type": t, "key": k} if k else None

    if t == "release":
        return {"type": t}

    if t == "repeat":
        inner = repair_actions(action.get("actions", []))
        if not inner:
            return None
        count = _clamp(_coerce_int(action.get("count"), 1), 1, MAX_REPEAT_COUNT)
        return {"type": t, "count": count, "actions": inner}

    if t == "media":
        v = str(action.get("value", "")).strip().upper()
        return {"type": t, "value": v} if v in MEDIA_NAMES else None

    if t == "mouse_move":
        out = {
            "type": t,
            "x": _clamp(_coerce_int(action.get("x"), 0), MOUSE_AXIS_MIN, MOUSE_AXIS_MAX),
            "y": _clamp(_coerce_int(action.get("y"), 0), MOUSE_AXIS_MIN, MOUSE_AXIS_MAX),
        }
        if "wheel" in action:
            out["wheel"] = _clamp(_coerce_int(action.get("wheel"), 0),
                                  MOUSE_AXIS_MIN, MOUSE_AXIS_MAX)
        return out

    if t == "mouse_click":
        b = str(action.get("button", "")).strip().upper()
        return {"type": t, "button": b} if b in MOUSE_BUTTONS else None

    if t == "led":
        color = action.get("color")
        if not isinstance(color, list) or len(color) != 3:
            return None
        return {"type": t,
                "color": [_clamp(_coerce_int(c, 0), 0, 255) for c in color]}

    if t == "led_anim":
        v = str(action.get("value", "")).strip().lower()
        if v not in LED_ANIM_VALUES:
            return None
        out = {"type": t, "value": v}
        color = action.get("color")
        if isinstance(color, list) and len(color) == 3:
            out["color"] = [_clamp(_coerce_int(c, 0), 0, 255) for c in color]
        return out

    if t == "profile":
        return {"type": t,
                "value": _clamp(_coerce_int(action.get("value"), 1), 1, NUM_PROFILES)}

    if t == "telephony":
        v = str(action.get("value", "")).strip().upper()
        return {"type": t, "value": v} if v in TELEPHONY_NAMES else None

    return None


def repair_actions(actions):
    """Best-effort normalization of an action list. Drops unrecoverable items."""
    if not isinstance(actions, list):
        return []
    out = []
    for a in actions:
        r = _repair_action(a)
        if r is not None:
            out.append(r)
    return out


def repair_shortcuts(items):
    """Repair a list of AI shortcuts, dropping any with no valid actions."""
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        actions = repair_actions(item.get("actions", []))
        if not actions:
            continue
        fixed = {"description": str(item.get("description", "")).strip() or "Macro",
                 "actions": actions}
        if "key_num" in item:
            kn = _coerce_int(item.get("key_num"), 0)
            if 1 <= kn <= 12:
                fixed["key_num"] = kn
        out.append(fixed)
    return out
