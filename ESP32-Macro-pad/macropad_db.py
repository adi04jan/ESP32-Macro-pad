import sqlite3
import json
import os

DB_PATH = "macropad_db.sqlite"

def get_db():
    return sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS shortcuts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT,
                    key_num INTEGER,
                    description TEXT,
                    action_json TEXT,
                    likes INTEGER DEFAULT 0,
                    dislikes INTEGER DEFAULT 0
                 )''')
    conn.commit()
    conn.close()

def get_app_shortcuts(app_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, key_num, description, action_json, likes, dislikes FROM shortcuts WHERE app_name=? ORDER BY key_num ASC", (app_name.lower(),))
    rows = c.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "key_num": r[1],
            "description": r[2],
            "actions": json.loads(r[3]),
            "likes": r[4],
            "dislikes": r[5]
        })
    return results

def save_app_shortcuts(app_name, shortcuts_list):
    """
    shortcuts_list is a list of dicts: {"key_num": 1, "description": "copy", "actions": [...]}
    """
    conn = get_db()
    c = conn.cursor()
    
    c.execute("DELETE FROM shortcuts WHERE app_name=?", (app_name.lower(),))
    
    for s in shortcuts_list:
        c.execute("INSERT INTO shortcuts (app_name, key_num, description, action_json) VALUES (?, ?, ?, ?)",
                  (app_name.lower(), s["key_num"], s.get("description", ""), json.dumps(s.get("actions", []))))
                  
    conn.commit()
    conn.close()

def vote_shortcut(shortcut_id, is_like):
    conn = get_db()
    c = conn.cursor()
    if is_like:
        c.execute("UPDATE shortcuts SET likes = likes + 1 WHERE id=?", (shortcut_id,))
    else:
        c.execute("UPDATE shortcuts SET dislikes = dislikes + 1 WHERE id=?", (shortcut_id,))
    conn.commit()
    conn.close()

# Initialize on import
init_db()
