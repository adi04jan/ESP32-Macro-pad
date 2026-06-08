"""
ActionEditorRow: one editable row per macro action.

Covers ALL 16 firmware action types (the old release/ui_components only had 6).
The row mutates its backing action dict in place; values are best-effort and are
schema-repaired on save, so partial/in-progress edits never corrupt the profile.
"""

from __future__ import annotations

import copy

import customtkinter as ctk

from .. import schema
from .popups import RecordKeycomboPopup, TextEditPopup, JsonEditPopup

# A minimal valid template per type, used when the user switches type.
DEFAULT_ACTION = {
    "comment": {"type": "comment", "value": ""},
    "delay": {"type": "delay", "ms": 100},
    "key": {"type": "key", "value": "ENTER"},
    "keycombo": {"type": "keycombo", "keys": ["LEFT_CTRL", "S"]},
    "text": {"type": "text", "value": ""},
    "multiline": {"type": "multiline", "value": ""},
    "hold": {"type": "hold", "key": "LEFT_SHIFT"},
    "release": {"type": "release"},
    "repeat": {"type": "repeat", "count": 2, "actions": []},
    "media": {"type": "media", "value": "PLAY_PAUSE"},
    "mouse_move": {"type": "mouse_move", "x": 0, "y": 0},
    "mouse_click": {"type": "mouse_click", "button": "LEFT"},
    "led": {"type": "led", "color": [255, 255, 255]},
    "led_anim": {"type": "led_anim", "value": "flash"},
    "profile": {"type": "profile", "value": 1},
    "telephony": {"type": "telephony", "value": "MIC_MUTE"},
}


def _to_int(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


class ActionEditorRow(ctk.CTkFrame):
    def __init__(self, master, action, on_delete, on_change):
        super().__init__(master)
        self.action = action
        self.on_delete = on_delete
        self.on_change = on_change

        self.grid_columnconfigure(1, weight=1)

        self.type_var = ctk.StringVar(value=action.get("type", "text"))
        ctk.CTkComboBox(self, values=schema.ACTION_TYPES, variable=self.type_var,
                        command=self._on_type_change, width=130, state="readonly"
                        ).grid(row=0, column=0, padx=5, pady=5)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.body.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="✕", width=30, fg_color="#a33", hover_color="#c44",
                      command=lambda: self.on_delete(self)
                      ).grid(row=0, column=2, padx=5, pady=5)

        self._build_body()

    # ------------------------------------------------------------------
    def _on_type_change(self, new_type):
        self.action.clear()
        self.action.update(copy.deepcopy(DEFAULT_ACTION[new_type]))
        self._build_body()
        self.on_change()

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _build_body(self):
        self._clear_body()
        builder = getattr(self, f"_build_{self.type_var.get()}", None)
        if builder:
            builder()

    # -- per-type builders ---------------------------------------------
    def _entry(self, var, **kw):
        e = ctk.CTkEntry(self.body, textvariable=var, **kw)
        e.grid(row=0, column=kw.pop("_col", 0), sticky="ew", padx=2)
        return e

    def _combo(self, var, values, **kw):
        c = ctk.CTkComboBox(self.body, values=values, variable=var,
                            command=lambda *_: self.on_change(), **kw)
        c.grid(row=0, column=0, sticky="ew", padx=2)
        return c

    def _build_comment(self):
        var = ctk.StringVar(value=self.action.get("value", ""))
        var.trace_add("write", lambda *_: self._set("value", var.get()))
        self._entry(var)

    def _build_text(self):
        self._text_like("value")

    def _build_multiline(self):
        self._text_like("value")

    def _text_like(self, field):
        var = ctk.StringVar(value=self.action.get(field, ""))
        var.trace_add("write", lambda *_: self._set(field, var.get()))
        self._entry(var)
        ctk.CTkButton(self.body, text="Edit…", width=60,
                      command=lambda: self._open_text_popup(field, var)
                      ).grid(row=0, column=1, padx=(4, 0))

    def _open_text_popup(self, field, var):
        TextEditPopup(self, self.action.get(field, ""),
                      lambda val: (var.set(val), self._set(field, val)))

    def _build_delay(self):
        var = ctk.StringVar(value=str(self.action.get("ms", 100)))
        var.trace_add("write", lambda *_: self._set("ms", _to_int(var.get(), 0)))
        self._entry(var)

    def _build_key(self):
        var = ctk.StringVar(value=self.action.get("value", "ENTER"))
        var.trace_add("write", lambda *_: self._set("value", var.get()))
        self._combo(var, schema.KEY_NAMES, state="normal")

    def _build_hold(self):
        var = ctk.StringVar(value=self.action.get("key", "LEFT_SHIFT"))
        var.trace_add("write", lambda *_: self._set("key", var.get()))
        self._combo(var, schema.KEY_AND_MODIFIER, state="normal")

    def _build_release(self):
        ctk.CTkLabel(self.body, text="(releases all held keys)",
                     text_color="#888").grid(row=0, column=0, sticky="w")

    def _build_keycombo(self):
        keys = self.action.get("keys", [])
        var = ctk.StringVar(value=", ".join(keys) if isinstance(keys, list) else "")
        entry = ctk.CTkEntry(self.body, textvariable=var, state="readonly")
        entry.grid(row=0, column=0, sticky="ew", padx=2)

        def save(val):
            var.set(val)
            self._set("keys", [k.strip() for k in val.split(",") if k.strip()])

        ctk.CTkButton(self.body, text="Record", width=70, fg_color="orange",
                      hover_color="darkorange",
                      command=lambda: RecordKeycomboPopup(self, var.get(), save)
                      ).grid(row=0, column=1, padx=(4, 0))

    def _build_media(self):
        var = ctk.StringVar(value=self.action.get("value", "PLAY_PAUSE"))
        var.trace_add("write", lambda *_: self._set("value", var.get()))
        self._combo(var, schema.MEDIA_NAMES, state="readonly")

    def _build_mouse_click(self):
        var = ctk.StringVar(value=self.action.get("button", "LEFT"))
        var.trace_add("write", lambda *_: self._set("button", var.get()))
        self._combo(var, schema.MOUSE_BUTTONS, state="readonly")

    def _build_telephony(self):
        var = ctk.StringVar(value=self.action.get("value", "MIC_MUTE"))
        var.trace_add("write", lambda *_: self._set("value", var.get()))
        self._combo(var, schema.TELEPHONY_NAMES, state="readonly")

    def _build_profile(self):
        var = ctk.StringVar(value=str(self.action.get("value", 1)))
        var.trace_add("write", lambda *_: self._set("value", _to_int(var.get(), 1)))
        self._combo(var, [str(i) for i in range(1, schema.NUM_PROFILES + 1)],
                    state="readonly")

    def _build_mouse_move(self):
        self.body.grid_columnconfigure((0, 1, 2), weight=1)
        for col, field in enumerate(("x", "y", "wheel")):
            var = ctk.StringVar(value=str(self.action.get(field, 0)))
            var.trace_add("write",
                          lambda *_, f=field, v=var: self._set_axis(f, v.get()))
            box = ctk.CTkFrame(self.body, fg_color="transparent")
            box.grid(row=0, column=col, padx=2, sticky="ew")
            ctk.CTkLabel(box, text=field, width=20).pack(side="left")
            ctk.CTkEntry(box, textvariable=var, width=60).pack(side="left", fill="x")

    def _set_axis(self, field, text):
        val = max(-127, min(127, _to_int(text, 0)))
        if field == "wheel" and val == 0:
            self.action.pop("wheel", None)
        else:
            self.action[field] = val
        self.on_change()

    def _build_led(self):
        color = self.action.get("color", [255, 255, 255])
        var = ctk.StringVar(value=", ".join(str(c) for c in color))
        var.trace_add("write", lambda *_: self._set_color(var.get()))
        ctk.CTkLabel(self.body, text="R,G,B:").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(self.body, textvariable=var).grid(row=0, column=1, sticky="ew")
        self.body.grid_columnconfigure(1, weight=1)

    def _build_led_anim(self):
        var = ctk.StringVar(value=self.action.get("value", "flash"))
        var.trace_add("write", lambda *_: self._set("value", var.get()))
        self._combo(var, schema.LED_ANIM_VALUES, state="readonly")
        color = self.action.get("color", [255, 255, 255])
        cvar = ctk.StringVar(value=", ".join(str(c) for c in color))
        cvar.trace_add("write", lambda *_: self._set_color(cvar.get()))
        ctk.CTkEntry(self.body, textvariable=cvar, width=110,
                     placeholder_text="R,G,B").grid(row=0, column=1, padx=(4, 0))

    def _set_color(self, text):
        parts = [_to_int(p, 0) for p in text.split(",") if p.strip()]
        if len(parts) == 3:
            self.action["color"] = [max(0, min(255, c)) for c in parts]
            self.on_change()

    def _build_repeat(self):
        var = ctk.StringVar(value=str(self.action.get("count", 2)))
        var.trace_add("write", lambda *_: self._set("count", _to_int(var.get(), 1)))
        ctk.CTkLabel(self.body, text="count:").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(self.body, textvariable=var, width=60).grid(row=0, column=1)
        self.count_summary = ctk.CTkLabel(
            self.body, text=self._repeat_summary(), text_color="#888")
        self.count_summary.grid(row=0, column=2, padx=8)
        ctk.CTkButton(self.body, text="Edit actions…", width=110,
                      command=self._edit_repeat).grid(row=0, column=3, padx=4)

    def _repeat_summary(self):
        return f"{len(self.action.get('actions', []))} action(s)"

    def _edit_repeat(self):
        def save(actions):
            self.action["actions"] = actions
            if hasattr(self, "count_summary") and self.count_summary.winfo_exists():
                self.count_summary.configure(text=self._repeat_summary())
            self.on_change()
        JsonEditPopup(self, self.action.get("actions", []), save)

    # ------------------------------------------------------------------
    def _set(self, field, value):
        self.action[field] = value
        self.on_change()
