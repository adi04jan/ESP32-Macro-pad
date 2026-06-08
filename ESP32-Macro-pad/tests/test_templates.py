"""Tests for TemplatesManager dedup/validation and window context detection."""

import json

from configurator.templates import TemplatesManager
from configurator.window_tracker import detect_context


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_dedups_by_actions_not_just_description(tmp_path):
    custom = str(tmp_path / "custom.json")
    default = str(tmp_path / "default.json")
    _write(default, {})
    _write(custom, {"vscode": [
        {"description": "Save", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]},
        # same actions, different description -> duplicate, should be dropped
        {"description": "Save File", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "S"]}]},
        {"description": "Copy", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "C"]}]},
    ]})
    mgr = TemplatesManager(custom_file=custom, default_file=default)
    out = mgr.get_context_shortcuts("vscode")
    sigs = {json.dumps(s["actions"], sort_keys=True) for s in out}
    assert len(sigs) == 2  # Save (==Save File) collapsed, plus Copy


def test_invalid_shortcuts_dropped_on_load(tmp_path):
    custom = str(tmp_path / "custom.json")
    default = str(tmp_path / "default.json")
    _write(default, {})
    _write(custom, {"excel": [
        {"description": "good", "actions": [{"type": "key", "value": "ENTER"}]},
        {"description": "bad", "actions": [{"type": "bogus_type"}]},
    ]})
    mgr = TemplatesManager(custom_file=custom, default_file=default)
    out = mgr.get_context_shortcuts("excel")
    assert [s["description"] for s in out] == ["good"]


def test_add_shortcuts_repairs_and_dedupes(tmp_path):
    custom = str(tmp_path / "custom.json")
    default = str(tmp_path / "default.json")
    _write(default, {})
    _write(custom, {})
    mgr = TemplatesManager(custom_file=custom, default_file=default)

    added = mgr.add_shortcuts("slack", [
        {"description": "Bold", "actions": [
            {"type": "keycombo", "keys": ["ctrl", "b"]}]},   # aliases -> repaired
        {"description": "bogus", "actions": [{"type": "nope"}]},  # dropped
    ])
    assert added == 1
    # Re-adding the same effective macro adds nothing.
    again = mgr.add_shortcuts("slack", [
        {"description": "Bold again", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "B"]}]}])
    assert again == 0


def test_custom_overrides_default_ordering(tmp_path):
    custom = str(tmp_path / "custom.json")
    default = str(tmp_path / "default.json")
    _write(default, {"chrome": [
        {"description": "New Tab", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "T"]}]}]})
    _write(custom, {"chrome": [
        {"description": "Reopen Tab", "actions": [
            {"type": "keycombo", "keys": ["LEFT_CTRL", "LEFT_SHIFT", "T"]}]}]})
    mgr = TemplatesManager(custom_file=custom, default_file=default)
    out = mgr.get_context_shortcuts("chrome")
    assert out[0]["description"] == "Reopen Tab"  # custom first
    assert len(out) == 2


def test_detect_context():
    assert detect_context("main.py - Visual Studio Code") == "vscode"
    assert detect_context("VSCode - powershell terminal") == "vscode_terminal"
    assert detect_context("Book1 - Excel") == "excel"
    assert detect_context("general - Slack") == "slack"
    assert detect_context("") == ""
    assert detect_context("Inbox - Gmail - Google Chrome") == "chrome"
