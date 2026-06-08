"""
SQLite storage for AI-generated / user shortcuts, with voting metadata.

Migrates the existing `macropad_db.sqlite` in place: the original schema
(id, app_name, key_num, description, action_json, likes, dislikes) gains
created_at, schema_version, and is_valid columns. Actions are repaired and
validated against the canonical schema before they are stored, so the DB never
holds a macro the firmware can't run.
"""

from __future__ import annotations

import json
import sqlite3
import time

from . import schema

DB_PATH = "macropad_db.sqlite"

_BASE_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "app_name": "TEXT",
    "key_num": "INTEGER",
    "description": "TEXT",
    "action_json": "TEXT",
    "likes": "INTEGER DEFAULT 0",
    "dislikes": "INTEGER DEFAULT 0",
}
# Columns added by v2; applied via ALTER TABLE on existing databases.
_ADDED_COLUMNS = {
    "created_at": "INTEGER DEFAULT 0",
    "schema_version": "INTEGER DEFAULT 0",
    "is_valid": "INTEGER DEFAULT 1",
}


class ShortcutDB:
    def __init__(self, path=DB_PATH):
        self.path = path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)

    def _init(self):
        conn = self._connect()
        try:
            c = conn.cursor()
            cols = ", ".join(f"{n} {t}" for n, t in _BASE_COLUMNS.items())
            c.execute(f"CREATE TABLE IF NOT EXISTS shortcuts ({cols})")
            existing = {row[1] for row in c.execute("PRAGMA table_info(shortcuts)")}
            for name, decl in _ADDED_COLUMNS.items():
                if name not in existing:
                    c.execute(f"ALTER TABLE shortcuts ADD COLUMN {name} {decl}")
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    def get_app_shortcuts(self, app_name):
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT id, key_num, description, action_json, likes, dislikes "
                "FROM shortcuts WHERE app_name=? AND is_valid=1 ORDER BY key_num ASC",
                (app_name.lower(),),
            )
            rows = c.fetchall()
        finally:
            conn.close()

        results = []
        for r in rows:
            try:
                actions = json.loads(r[3])
            except (TypeError, json.JSONDecodeError):
                continue
            results.append({
                "id": r[0], "key_num": r[1], "description": r[2],
                "actions": actions, "likes": r[4], "dislikes": r[5],
            })
        return results

    def save_app_shortcuts(self, app_name, shortcuts_list):
        """Replace all shortcuts for an app. Each is repaired + validated first.

        Returns the number of shortcuts actually stored (invalid ones dropped).
        """
        app = app_name.lower()
        now = int(time.time())
        stored = 0
        conn = self._connect()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM shortcuts WHERE app_name=?", (app,))
            for s in shortcuts_list:
                actions = schema.repair_actions(s.get("actions", []))
                ok = bool(actions) and schema.is_valid_actions(actions)
                if not ok:
                    continue
                c.execute(
                    "INSERT INTO shortcuts (app_name, key_num, description, "
                    "action_json, created_at, schema_version, is_valid) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (app, s.get("key_num"), s.get("description", ""),
                     json.dumps(actions), now, schema.SCHEMA_VERSION),
                )
                stored += 1
            conn.commit()
        finally:
            conn.close()
        return stored

    def vote(self, shortcut_id, is_like):
        conn = self._connect()
        try:
            c = conn.cursor()
            col = "likes" if is_like else "dislikes"
            c.execute(f"UPDATE shortcuts SET {col} = {col} + 1 WHERE id=?",
                      (shortcut_id,))
            conn.commit()
        finally:
            conn.close()
