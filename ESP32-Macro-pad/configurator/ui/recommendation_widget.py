"""
Floating, frameless AI recommendation overlay.

Shows up to 4 suggested shortcuts (one per device key K1-K4) for the current
context, lets the user cycle alternatives, regenerate, and pushes the chosen
shortcut to the device. Single implementation (the old code had two divergent
render paths in v4 and ui_widget.py).
"""

from __future__ import annotations

import customtkinter as ctk

BG = "#252526"
HEADER_BG = "#333333"
BORDER = "#3c3c3c"
TEXT = "#cccccc"
ACCENT = "#007acc"


def _macro_summary(actions):
    parts = []
    for act in actions:
        t = act.get("type", "")
        if t == "keycombo":
            parts.append("+".join(act.get("keys", [])))
        elif t in ("text", "multiline"):
            parts.append(f"'{act.get('value', '')}'")
        elif t in ("key", "hold"):
            parts.append(str(act.get("value", act.get("key", ""))))
        elif t == "delay":
            parts.append(f"{act.get('ms', 0)}ms")
        elif t in ("media", "telephony"):
            parts.append(str(act.get("value", "")))
        else:
            parts.append(t)
    text = " → ".join(parts) if parts else "empty"
    return text[:27] + "…" if len(text) > 30 else text


class RecommendationWidget(ctk.CTkToplevel):
    def __init__(self, master, on_regen=None, on_push=None, on_settings=None):
        super().__init__(master)
        self.on_regen = on_regen or (lambda knum: None)
        self.on_push = on_push or (lambda shortcut: None)
        self.on_settings = on_settings or (lambda: None)

        self.title("Macropad AI")
        self.geometry("360x300+20+20")
        self.attributes("-topmost", True)
        self.overrideredirect(True)

        self.current_context = ""
        self.options_map = {1: [], 2: [], 3: [], 4: []}
        self.index_map = {1: 0, 2: 0, 3: 0, 4: 0}

        self.main = ctk.CTkFrame(self, corner_radius=0, border_width=1,
                                 border_color=BORDER, fg_color=BG)
        self.main.pack(fill="both", expand=True)

        bar = ctk.CTkFrame(self.main, fg_color=HEADER_BG, corner_radius=0, height=28)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.header = ctk.CTkLabel(bar, text=" AI Context", text_color=TEXT,
                                   font=ctk.CTkFont(family="Consolas", size=12))
        self.header.pack(side="left", padx=8)
        ctk.CTkButton(bar, text="✕", width=28, height=28, corner_radius=0,
                      fg_color="transparent", text_color="#aaa",
                      hover_color="#e81123", command=self.withdraw).pack(side="right")
        ctk.CTkButton(bar, text="⚙", width=28, height=28, corner_radius=0,
                      fg_color="transparent", text_color="#aaa",
                      hover_color="#555", command=lambda: self.on_settings()
                      ).pack(side="right")

        self.status = ctk.CTkLabel(self.main, text="", text_color="#888",
                                   font=ctk.CTkFont(family="Consolas", size=11,
                                                    slant="italic"))
        self.list_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=2, pady=4)

        for w in (bar, self.header):
            w.bind("<ButtonPress-1>", self._start_move)
            w.bind("<B1-Motion>", self._do_move)

    # -- dragging ------------------------------------------------------
    def _start_move(self, event):
        self._mx, self._my = event.x, event.y

    def _do_move(self, event):
        self.geometry(f"+{self.winfo_x() + event.x - self._mx}"
                      f"+{self.winfo_y() + event.y - self._my}")

    # -- content -------------------------------------------------------
    def update_context(self, context_name, shortcuts=None, is_generating=False):
        self.current_context = context_name
        self.header.configure(text=f" {context_name[:25]}")
        for w in self.list_frame.winfo_children():
            w.destroy()

        if is_generating and not shortcuts:
            self.status.configure(text="Generating AI shortcuts…", text_color=ACCENT)
            self.status.pack(pady=40)
            return
        self.status.pack_forget()

        self.options_map = {1: [], 2: [], 3: [], 4: []}
        for i, s in enumerate(shortcuts or []):
            knum = s.get("key_num") or ((i % 4) + 1)
            if 1 <= knum <= 4:
                self.options_map[knum].append(s)
        for knum in range(1, 5):
            self._render_row(knum)

    def _render_row(self, knum):
        opts = self.options_map[knum]
        idx = self.index_map.setdefault(knum, 0)

        row = ctk.CTkFrame(self.list_frame, fg_color="transparent", height=52)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        ctk.CTkFrame(row, width=3, fg_color=ACCENT, corner_radius=0).pack(
            side="left", fill="y")
        ctk.CTkLabel(row, text=f"K{knum}", fg_color="#37373d", corner_radius=2,
                     width=24, text_color="#d4d4d4",
                     font=ctk.CTkFont(family="Consolas", size=10, weight="bold")
                     ).pack(side="left", padx=(6, 8), pady=10)

        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="both", expand=True)

        if not opts:
            ctk.CTkLabel(col, text="No shortcut", anchor="w", text_color="#888",
                         font=ctk.CTkFont(size=12, slant="italic")
                         ).pack(side="top", anchor="w", pady=(15, 0))
        else:
            idx = idx % len(opts)
            self.index_map[knum] = idx
            s = opts[idx]
            desc = s.get("description", "")[:28]
            if len(opts) > 1:
                desc += f" ({idx + 1}/{len(opts)})"
            ctk.CTkLabel(col, text=desc, anchor="w", text_color=TEXT,
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).pack(side="top", anchor="w", pady=(5, 0))
            ctk.CTkLabel(col, text=_macro_summary(s.get("actions", [])), anchor="w",
                         text_color="#858585",
                         font=ctk.CTkFont(family="Consolas", size=10)
                         ).pack(side="top", anchor="w", pady=(0, 4))
            self.on_push(s)

        controls = ctk.CTkFrame(row, fg_color="transparent")
        controls.pack(side="right", fill="y", padx=2)
        ctk.CTkButton(controls, text="⟳", width=22, height=22, corner_radius=2,
                      fg_color="transparent", hover_color="#37373d",
                      text_color="#aaa", command=lambda: self.on_regen(knum)
                      ).pack(side="left", padx=1, pady=15)
        arrows = ctk.CTkFrame(controls, fg_color="transparent")
        arrows.pack(side="left")
        ctk.CTkButton(arrows, text="▲", width=22, height=18, corner_radius=0,
                      fg_color="transparent", hover_color="#37373d",
                      text_color="#888", font=ctk.CTkFont(size=10),
                      command=lambda: self._cycle(knum, -1)).pack(side="top")
        ctk.CTkButton(arrows, text="▼", width=22, height=18, corner_radius=0,
                      fg_color="transparent", hover_color="#37373d",
                      text_color="#888", font=ctk.CTkFont(size=10),
                      command=lambda: self._cycle(knum, 1)).pack(side="bottom")

    def _cycle(self, knum, direction):
        opts = self.options_map[knum]
        if len(opts) <= 1:
            return
        self.index_map[knum] = (self.index_map[knum] + direction) % len(opts)
        self._refresh_row(knum)

    def _refresh_row(self, knum):
        # Re-render just by rebuilding all rows (cheap; max 4 rows).
        for w in self.list_frame.winfo_children():
            w.destroy()
        for k in range(1, 5):
            self._render_row(k)
