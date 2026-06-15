"""Tests for the AI pipeline: lenient parsing, validation, and the generator's
repair loop — all with a fake client (no network)."""

import json

from configurator import schema
from configurator.ai import validator, prompts
from configurator.ai.ai_worker import MacroGenerator


# ---------------------------------------------------------------------------
# Lenient JSON parsing
# ---------------------------------------------------------------------------
def test_parse_plain_array():
    assert validator.parse_json_lenient('[{"a":1}]') == [{"a": 1}]


def test_parse_strips_markdown_fence():
    text = "```json\n[{\"type\":\"release\"}]\n```"
    assert validator.parse_json_lenient(text) == [{"type": "release"}]


def test_parse_extracts_array_amid_prose():
    text = 'Sure! Here you go:\n[{"type":"release"}]\nHope that helps.'
    assert validator.parse_json_lenient(text) == [{"type": "release"}]


def test_parse_returns_none_on_garbage():
    assert validator.parse_json_lenient("not json at all") is None
    assert validator.parse_json_lenient("") is None


# ---------------------------------------------------------------------------
# process_shortcuts / process_actions
# ---------------------------------------------------------------------------
def test_process_shortcuts_partitions_valid_and_invalid():
    raw = json.dumps([
        {"key_num": 1, "description": "good",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]},
        {"key_num": 2, "description": "bad",
         "actions": [{"type": "nonsense_type"}]},
    ])
    valid, invalid = validator.process_shortcuts(raw)
    assert [s["description"] for s in valid] == ["good"]
    assert len(invalid) == 1


def test_process_actions_repairs_then_validates():
    raw = '[{"type":"combo","keys":["ctrl","c"]}]'   # alias type + alias keys
    actions = validator.process_actions(raw)
    assert actions == [{"type": "keycombo", "keys": ["LEFT_CTRL", "C"]}]


def test_process_actions_rejects_unrecoverable():
    assert validator.process_actions('[{"type":"???"}]') is None


# ---------------------------------------------------------------------------
# MacroGenerator with a scripted fake client
# ---------------------------------------------------------------------------
class FakeClient:
    """Returns queued responses; records the prompts it was called with."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, system, user, json_schema=None):
        self.calls.append((system, user, json_schema))
        return self._responses.pop(0) if self._responses else "[]"


def test_generator_returns_only_valid_shortcuts():
    good = json.dumps([
        {"key_num": 1, "description": "Save",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]}])
    gen = MacroGenerator(FakeClient([good]), max_repair=0)
    out = gen.generate_shortcuts("vscode")
    assert len(out) == 1
    assert out[0]["description"] == "Save"


def test_generator_runs_one_repair_pass_for_invalid():
    first = json.dumps([
        {"key_num": 1, "description": "ok",
         "actions": [{"type": "key", "value": "ENTER"}]},
        {"key_num": 2, "description": "broken",
         "actions": [{"type": "media", "value": "REWIND"}]},  # invalid media
    ])
    # The repair pass returns a corrected version of the broken one.
    repaired = json.dumps([
        {"key_num": 2, "description": "fixed",
         "actions": [{"type": "media", "value": "NEXT"}]}])
    client = FakeClient([first, repaired])
    gen = MacroGenerator(client, max_repair=1)
    out = gen.generate_shortcuts("media app")
    descs = {s["description"] for s in out}
    assert descs == {"ok", "fixed"}
    assert len(client.calls) == 2  # initial + one repair


def test_generator_handles_total_garbage_gracefully():
    gen = MacroGenerator(FakeClient(["I cannot help with that."]), max_repair=0)
    assert gen.generate_shortcuts("anything") == []


def test_generator_dedupes_descriptions():
    dupes = json.dumps([
        {"key_num": 1, "description": "Copy",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "C"]}]},
        {"key_num": 2, "description": "copy",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "C"]}]},
    ])
    gen = MacroGenerator(FakeClient([dupes]), max_repair=0)
    out = gen.generate_shortcuts("x")
    assert len(out) == 1


def test_generate_actions_with_repair():
    bad = '[{"type":"media","value":"REWIND"}]'
    good = '[{"type":"media","value":"PREVIOUS"}]'
    gen = MacroGenerator(FakeClient([bad, good]), max_repair=1)
    out = gen.generate_actions("go to previous track")
    assert out == [{"type": "media", "value": "PREVIOUS"}]


# ---------------------------------------------------------------------------
# Prompts are built from the schema (anti-drift guarantee)
# ---------------------------------------------------------------------------
def test_system_prompt_lists_all_keys_and_types():
    sp = prompts.system_prompt_shortcuts()
    for mod in schema.MODIFIER_NAMES:
        assert mod in sp
    for media in schema.MEDIA_NAMES:
        assert media in sp
    for atype in schema.ACTION_TYPES:
        assert atype in sp


def test_few_shot_examples_are_themselves_valid():
    ok, errors = schema.validate_shortcuts(prompts.FEW_SHOT)
    assert ok, errors
