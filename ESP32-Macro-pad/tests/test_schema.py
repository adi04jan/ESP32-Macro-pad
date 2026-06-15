"""Tests for the canonical action schema (configurator/schema.py)."""

import pytest

from configurator import schema


# ---------------------------------------------------------------------------
# Valid actions — one representative per action type.
# ---------------------------------------------------------------------------
VALID_ACTIONS = [
    {"type": "comment", "value": "hi"},
    {"type": "comment"},
    {"type": "delay", "ms": 100},
    {"type": "key", "value": "ENTER"},
    {"type": "key", "value": "a"},  # single printable char
    {"type": "keycombo", "keys": ["LEFT_CTRL", "S"]},
    {"type": "keycombo", "keys": ["LEFT_CTRL", "LEFT_SHIFT", "P"]},
    {"type": "text", "value": "git status"},
    {"type": "multiline", "value": "line1\nline2"},
    {"type": "hold", "key": "LEFT_SHIFT"},
    {"type": "hold", "key": "A"},
    {"type": "release"},
    {"type": "repeat", "count": 3,
     "actions": [{"type": "key", "value": "DOWN_ARROW"}]},
    {"type": "media", "value": "PLAY_PAUSE"},
    {"type": "mouse_move", "x": 10, "y": -20},
    {"type": "mouse_move", "x": 0, "y": 0, "wheel": 5},
    {"type": "mouse_click", "button": "LEFT"},
    {"type": "led", "color": [255, 0, 0]},
    {"type": "led_anim", "value": "flash"},
    {"type": "led_anim", "value": "breathe", "color": [0, 64, 128]},
    {"type": "profile", "value": 2},
    {"type": "telephony", "value": "MIC_MUTE"},
]


@pytest.mark.parametrize("action", VALID_ACTIONS)
def test_valid_action_accepted(action):
    ok, errors = schema.validate_actions([action])
    assert ok, f"expected valid, got errors: {errors}"


def test_all_valid_actions_as_one_list():
    ok, errors = schema.validate_actions(VALID_ACTIONS)
    assert ok, errors


# ---------------------------------------------------------------------------
# Invalid actions — each must be rejected.
# ---------------------------------------------------------------------------
INVALID_ACTIONS = [
    {"type": "bogus"},                                  # unknown type
    {"type": "delay"},                                  # missing ms
    {"type": "delay", "ms": -5},                        # negative ms
    {"type": "key", "value": "CTRL"},                   # not a valid key name
    {"type": "key", "value": "LEFT_CTRL"},              # modifier not allowed for `key`
    {"type": "keycombo", "keys": []},                   # empty combo
    {"type": "keycombo", "keys": ["NOPE_KEY"]},         # bad key in combo
    {"type": "media", "value": "REWIND"},               # not a media value
    {"type": "mouse_move", "x": 200, "y": 0},           # x out of int8 range
    {"type": "mouse_click", "button": "SCROLL"},        # bad button
    {"type": "led", "color": [255, 0]},                 # wrong color length
    {"type": "led", "color": [256, 0, 0]},              # channel out of range
    {"type": "profile", "value": 9},                    # profile out of range
    {"type": "repeat", "count": 100,                    # count over max
     "actions": [{"type": "release"}]},
    {"type": "telephony", "value": "HANGUP"},           # bad telephony value
    {"type": "key", "value": "ENTER", "extra": 1},      # additional property
]


@pytest.mark.parametrize("action", INVALID_ACTIONS)
def test_invalid_action_rejected(action):
    ok, _ = schema.validate_actions([action])
    assert not ok, f"expected rejection for {action}"


# ---------------------------------------------------------------------------
# Repair — malformed-but-recoverable input becomes valid.
# ---------------------------------------------------------------------------
def test_repair_maps_modifier_aliases():
    repaired = schema.repair_actions(
        [{"type": "keycombo", "keys": ["ctrl", "shift", "p"]}])
    assert repaired == [{"type": "keycombo",
                         "keys": ["LEFT_CTRL", "LEFT_SHIFT", "P"]}]
    assert schema.is_valid_actions(repaired)


def test_repair_coerces_numeric_strings_and_clamps():
    repaired = schema.repair_actions([
        {"type": "delay", "ms": "250"},
        {"type": "mouse_move", "x": "999", "y": "-999"},
        {"type": "profile", "value": "5"},
    ])
    assert repaired[0] == {"type": "delay", "ms": 250}
    assert repaired[1] == {"type": "mouse_move", "x": 127, "y": -127}
    assert repaired[2] == {"type": "profile", "value": 3}
    assert schema.is_valid_actions(repaired)


def test_repair_strips_unknown_fields():
    repaired = schema.repair_actions(
        [{"type": "key", "value": "ENTER", "junk": "x", "comment": "hi"}])
    assert repaired == [{"type": "key", "value": "ENTER"}]
    assert schema.is_valid_actions(repaired)


def test_repair_handles_type_aliases():
    repaired = schema.repair_actions([
        {"type": "wait", "ms": 50},
        {"type": "combo", "keys": ["LEFT_GUI", "r"]},
    ])
    assert repaired[0]["type"] == "delay"
    assert repaired[1]["type"] == "keycombo"
    assert schema.is_valid_actions(repaired)


def test_repair_drops_unrecoverable():
    repaired = schema.repair_actions([
        {"type": "totally_unknown"},
        {"type": "media", "value": "not_a_real_media_key"},
        {"type": "key", "value": "ENTER"},  # the only good one
    ])
    assert repaired == [{"type": "key", "value": "ENTER"}]


def test_repair_nested_repeat():
    repaired = schema.repair_actions([
        {"type": "repeat", "count": "4",
         "actions": [{"type": "key", "value": "down"},
                     {"type": "bogus"}]},
    ])
    assert repaired == [{"type": "repeat", "count": 4,
                         "actions": [{"type": "key", "value": "DOWN_ARROW"}]}]
    assert schema.is_valid_actions(repaired)


def test_repeat_with_no_valid_inner_actions_is_dropped():
    repaired = schema.repair_actions(
        [{"type": "repeat", "count": 3, "actions": [{"type": "bogus"}]}])
    assert repaired == []


# ---------------------------------------------------------------------------
# Shortcut (AI output) schema + repair.
# ---------------------------------------------------------------------------
def test_valid_shortcuts_accepted():
    items = [
        {"key_num": 1, "description": "Save File",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]},
        {"description": "Git status",
         "actions": [{"type": "text", "value": "git status"},
                     {"type": "key", "value": "ENTER"}]},
    ]
    ok, errors = schema.validate_shortcuts(items)
    assert ok, errors


def test_shortcut_repair_drops_entries_with_no_valid_actions():
    items = [
        {"key_num": 1, "description": "good",
         "actions": [{"type": "key", "value": "ENTER"}]},
        {"key_num": 2, "description": "bad",
         "actions": [{"type": "bogus"}]},
    ]
    repaired = schema.repair_shortcuts(items)
    assert len(repaired) == 1
    assert repaired[0]["description"] == "good"
    ok, errors = schema.validate_shortcuts(repaired)
    assert ok, errors


def test_enums_match_expected_counts():
    # Guards against accidental enum drift.
    assert len(schema.MODIFIER_NAMES) == 8
    assert len(schema.MEDIA_NAMES) == 7
    assert len(schema.ACTION_TYPES) == 16
    assert "LEFT_GUI" in schema.KEY_AND_MODIFIER
    assert "RIGHT_ALT" in schema.KEY_AND_MODIFIER
