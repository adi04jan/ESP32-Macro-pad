"""
Prompt construction for AI macro generation.

The whole point of v2's AI overhaul: the prompts are *generated from the
canonical schema*, so the model is always told the complete, correct set of
action types and key names — never a hand-maintained subset that drifts from
the firmware. Few-shot examples cover varied action types so the model has
concrete patterns to imitate.
"""

from __future__ import annotations

import json

from .. import schema

# Few-shot examples — every one is a schema-valid macro spanning varied types.
FEW_SHOT = [
    {"key_num": 1, "description": "Save file",
     "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]},
    {"key_num": 2, "description": "Run git status",
     "actions": [{"type": "text", "value": "git status"},
                 {"type": "key", "value": "ENTER"}]},
    {"key_num": 3, "description": "Open Run dialog and launch notepad",
     "actions": [{"type": "keycombo", "keys": ["LEFT_GUI", "R"]},
                 {"type": "delay", "ms": 300},
                 {"type": "text", "value": "notepad"},
                 {"type": "key", "value": "ENTER"}]},
    {"key_num": 4, "description": "Mute microphone",
     "actions": [{"type": "telephony", "value": "MIC_MUTE"}]},
]


def _action_catalog():
    """Human-readable description of every action type and its fields."""
    lines = [
        "comment       -> {\"type\":\"comment\",\"value\":\"note (ignored)\"}",
        "delay         -> {\"type\":\"delay\",\"ms\":<int>=0>}",
        "key           -> {\"type\":\"key\",\"value\":\"<KEY>\"}  (single key or char)",
        "keycombo      -> {\"type\":\"keycombo\",\"keys\":[\"<MOD/KEY>\",...]}  (pressed together)",
        "text          -> {\"type\":\"text\",\"value\":\"types this literally\"}",
        "multiline     -> {\"type\":\"multiline\",\"value\":\"line1\\nline2\"}",
        "hold          -> {\"type\":\"hold\",\"key\":\"<MOD/KEY>\"}  (press & hold)",
        "release       -> {\"type\":\"release\"}  (release all held keys)",
        "repeat        -> {\"type\":\"repeat\",\"count\":<1-%d>,\"actions\":[...]}" % schema.MAX_REPEAT_COUNT,
        "media         -> {\"type\":\"media\",\"value\":\"<MEDIA>\"}",
        "mouse_move    -> {\"type\":\"mouse_move\",\"x\":<-127..127>,\"y\":<-127..127>,\"wheel\":<opt>}",
        "mouse_click   -> {\"type\":\"mouse_click\",\"button\":\"LEFT|RIGHT|MIDDLE\"}",
        "led           -> {\"type\":\"led\",\"color\":[r,g,b]}  (0-255 each)",
        "led_anim      -> {\"type\":\"led_anim\",\"value\":\"flash|breathe\",\"color\":[r,g,b]}",
        "profile       -> {\"type\":\"profile\",\"value\":<1-%d>}" % schema.NUM_PROFILES,
        "telephony     -> {\"type\":\"telephony\",\"value\":\"<TELEPHONY>\"}",
    ]
    return "\n".join(lines)


def _enum_reference():
    return (
        f"MODIFIERS: {', '.join(schema.MODIFIER_NAMES)}\n"
        f"KEYS: {', '.join(schema.KEY_NAMES)}\n"
        f"MEDIA values: {', '.join(schema.MEDIA_NAMES)}\n"
        f"TELEPHONY values: {', '.join(schema.TELEPHONY_NAMES)}\n"
        f"MOUSE buttons: {', '.join(schema.MOUSE_BUTTONS)}"
    )


_RULES = (
    "You generate macros for an ESP32 macropad.\n"
    "CRITICAL OUTPUT RULES:\n"
    "- Respond with ONLY a raw JSON array. No prose, no markdown, no ```json fences.\n"
    "- Use ONLY the action types and key names listed below — anything else is rejected.\n"
    "- Key names are case-sensitive and must match exactly (e.g. LEFT_CTRL, not Ctrl).\n"
    "- Prefer keycombo for shortcuts; use text+key(ENTER) for typed commands.\n"
)


def system_prompt_shortcuts():
    """System prompt for context-based generation of {key_num,description,actions}."""
    return (
        _RULES
        + "\nACTION TYPES:\n" + _action_catalog()
        + "\n\nALLOWED NAMES:\n" + _enum_reference()
        + "\n\nEach array item MUST be: "
        '{"key_num": <1-12>, "description": "<short>", "actions": [ <action>, ... ]}'
        + "\n\nEXAMPLES:\n" + json.dumps(FEW_SHOT, indent=2)
    )


def user_prompt_shortcuts(context, existing=None, count=4, key_nums=None):
    """User prompt: ask for `count` unique shortcuts for `context`."""
    parts = [
        f"Context: {context}.",
        f"Generate {count} new, unique, genuinely useful keyboard shortcuts "
        f"for this context.",
    ]
    if existing:
        # Pass full action objects (not just descriptions) so the model adapts.
        parts.append(
            "You already have these shortcuts (do NOT duplicate them; build on "
            "this workflow style):\n" + json.dumps(existing, indent=2))
    if key_nums:
        parts.append(f"Assign them to these key_num values: {key_nums}.")
    return "\n".join(parts)


def system_prompt_actions():
    """System prompt for turning a free-text instruction into an action array."""
    return (
        _RULES
        + "\nACTION TYPES:\n" + _action_catalog()
        + "\n\nALLOWED NAMES:\n" + _enum_reference()
        + "\n\nRespond with ONLY a JSON array of action objects (no wrapper)."
        + "\n\nEXAMPLE for 'open run dialog and type notepad then enter':\n"
        + json.dumps(FEW_SHOT[2]["actions"], indent=2)
    )


def user_prompt_actions(description):
    return f"Build a macro that does the following:\n{description}"


def repair_user_prompt(invalid_json, errors):
    """Ask the model to fix specific schema violations in its previous output."""
    return (
        "Your previous JSON had validation errors. Fix them and return ONLY the "
        "corrected raw JSON array.\n\nERRORS:\n"
        + "\n".join(f"- {e}" for e in errors)
        + "\n\nJSON TO FIX:\n" + json.dumps(invalid_json, indent=2)
    )
