"""Tests for the shortcut DB: migration and validate-on-save."""

import sqlite3

from configurator.db import ShortcutDB, _ADDED_COLUMNS


def _columns(path):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(shortcuts)")}
    finally:
        conn.close()


def test_migrates_legacy_table(tmp_path):
    path = str(tmp_path / "legacy.sqlite")
    # Build the OLD schema (no created_at/schema_version/is_valid) + a row.
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE shortcuts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "app_name TEXT, key_num INTEGER, description TEXT, action_json TEXT, "
        "likes INTEGER DEFAULT 0, dislikes INTEGER DEFAULT 0)")
    conn.execute(
        "INSERT INTO shortcuts (app_name, key_num, description, action_json) "
        "VALUES ('vscode', 1, 'Save', '[{\"type\":\"keycombo\",\"keys\":[\"LEFT_CTRL\",\"S\"]}]')")
    conn.commit()
    conn.close()

    db = ShortcutDB(path)  # triggers migration
    cols = _columns(path)
    assert set(_ADDED_COLUMNS).issubset(cols)
    # Legacy row survives and is readable.
    rows = db.get_app_shortcuts("vscode")
    assert len(rows) == 1
    assert rows[0]["description"] == "Save"


def test_save_validates_and_drops_invalid(tmp_path):
    db = ShortcutDB(str(tmp_path / "new.sqlite"))
    stored = db.save_app_shortcuts("excel", [
        {"key_num": 1, "description": "good",
         "actions": [{"type": "keycombo", "keys": ["LEFT_CTRL", "C"]}]},
        {"key_num": 2, "description": "bad",
         "actions": [{"type": "totally_bogus"}]},
        {"key_num": 3, "description": "repairable",
         "actions": [{"type": "keycombo", "keys": ["ctrl", "v"]}]},  # aliases
    ])
    assert stored == 2  # bad one dropped, repairable one kept
    rows = db.get_app_shortcuts("excel")
    descs = {r["description"] for r in rows}
    assert descs == {"good", "repairable"}
    # The repaired entry was normalized before storage.
    repaired = next(r for r in rows if r["description"] == "repairable")
    assert repaired["actions"] == [{"type": "keycombo", "keys": ["LEFT_CTRL", "V"]}]


def test_vote_increments(tmp_path):
    db = ShortcutDB(str(tmp_path / "v.sqlite"))
    db.save_app_shortcuts("slack", [
        {"key_num": 1, "description": "x",
         "actions": [{"type": "key", "value": "ENTER"}]}])
    sid = db.get_app_shortcuts("slack")[0]["id"]
    db.vote(sid, True)
    db.vote(sid, True)
    db.vote(sid, False)
    row = db.get_app_shortcuts("slack")[0]
    assert row["likes"] == 2
    assert row["dislikes"] == 1
