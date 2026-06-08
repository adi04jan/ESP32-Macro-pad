"""
Macropad Configurator v2 — main application.

Wires together the canonical schema, the robust serial link, the validated
AI pipeline, templates, and the window tracker behind a CustomTkinter UI.

Run with:  python -m configurator.app
"""

from __future__ import annotations

import json
import re

import customtkinter as ctk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from .config import AppSettings, PROFILE_FILES, NUM_KEYS, SERIAL_BAUD
from .profile_model import Profile
from .serial_link import SerialLink, list_ports, parse_profile_payload
from .templates import TemplatesManager
from .db import ShortcutDB
from .window_tracker import WindowTracker
from .ai.ai_worker import MacroGenerator, AIQueueManager, make_client
from .ui.action_editor import ActionEditorRow, DEFAULT_ACTION
from .ui.recommendation_widget import RecommendationWidget
from .ui.popups import AISettingsPopup, WidgetSettingsPopup

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

KEY_LAYOUT = [[None, 1, 2, None], [3, 4, 5, 6], [7, 8, 9, 10], [None, 11, 12, None]]


class MacropadApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Macropad Configurator v2")
        self.geometry("1200x800")

        # State / services.
        self.settings = AppSettings()
        self.profile = self._blank_profile()
        self.selected_key = 1
        self.action_rows = []
        self.templates = TemplatesManager()
        self.db = ShortcutDB()
        self.current_context = None
        self.auto_switch_var = ctk.BooleanVar(
            value=self.settings.get("auto_switch_enabled", False))

        self.link = SerialLink(
            on_log=lambda m: self.after(0, self._console, m),
            on_fs_info=lambda t, u: self.after(0, self._update_storage, t, u),
            on_file=lambda lines: self.after(0, self._on_file_captured, lines),
            on_ready=lambda: self.after(0, self._console, "Ready.\n"),
            on_disconnect=lambda: self.after(0, self._on_disconnect),
        )

        self._build_ai()

        # UI.
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_dash = self.tabs.add("Dashboard")
        self.tab_editor = self.tabs.add("Key Editor")
        self.tab_auto = self.tabs.add("Auto-Switcher")
        self.tab_settings = self.tabs.add("Settings")
        self._build_dashboard()
        self._build_editor()
        self._build_autoswitch()
        self._build_settings()

        self.rec_widget = RecommendationWidget(
            self, on_regen=self._regen_key, on_push=self.push_shortcut_to_device,
            on_settings=lambda: WidgetSettingsPopup(self, self.settings, self.rec_widget))
        self.rec_widget.withdraw()

        self.tracker = WindowTracker(
            on_context=lambda c: self.after(0, self._on_context_change, c),
            is_enabled=self.auto_switch_var.get, log=lambda m: self.after(0, self._tlog, m))
        self.tracker.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _blank_profile(self):
        p = Profile(profile_name="New Profile")
        for i in range(1, NUM_KEYS + 1):
            p.key(i)
        return p

    def _build_ai(self):
        generator = MacroGenerator(make_client(self.settings),
                                   log=lambda m: self.after(0, self._tlog, m))
        self.ai = AIQueueManager(generator, marshal=lambda fn, *a: self.after(0, fn, *a))

    def _rebuild_ai_client(self):
        self.ai.generator.client = make_client(self.settings)

    # -- Dashboard -----------------------------------------------------
    def _build_dashboard(self):
        self.tab_dash.grid_columnconfigure(1, weight=1)
        self.tab_dash.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(self.tab_dash, width=320)
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        conn = ctk.CTkFrame(left)
        conn.pack(fill="x", pady=8)
        ctk.CTkLabel(conn, text="Device Connection",
                     font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.port_var = ctk.StringVar(value=self.settings.get("last_port") or "Select Port")
        self.port_combo = ctk.CTkComboBox(conn, variable=self.port_var,
                                          values=self._ports())
        self.port_combo.pack(padx=10, pady=5)
        ctk.CTkButton(conn, text="Refresh Ports", command=self._refresh_ports).pack(pady=4)
        self.connect_btn = ctk.CTkButton(conn, text="Connect", fg_color="green",
                                         hover_color="darkgreen",
                                         command=self._toggle_connection)
        self.connect_btn.pack(pady=8)

        sync = ctk.CTkFrame(left)
        sync.pack(fill="x", pady=8)
        ctk.CTkLabel(sync, text="Sync Profiles",
                     font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.profile_file_var = ctk.StringVar(value="profile1.json")
        ctk.CTkComboBox(sync, variable=self.profile_file_var,
                        values=[p.lstrip("/") for p in PROFILE_FILES]).pack(pady=4)
        self.load_btn = ctk.CTkButton(sync, text="Load from Device",
                                      command=self._load_from_device, state="disabled")
        self.load_btn.pack(pady=4)
        self.save_btn = ctk.CTkButton(sync, text="Save to Device",
                                      command=self._save_to_device, state="disabled")
        self.save_btn.pack(pady=4)
        self.active_btn = ctk.CTkButton(sync, text="Set Active",
                                        command=self._set_active, state="disabled")
        self.active_btn.pack(pady=4)
        self.storage_lbl = ctk.CTkLabel(sync, text="Storage: unknown",
                                        font=ctk.CTkFont(size=11))
        self.storage_lbl.pack(pady=(8, 0))
        self.storage_bar = ctk.CTkProgressBar(sync, height=10)
        self.storage_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.storage_bar.set(0)

        glob = ctk.CTkFrame(left)
        glob.pack(fill="x", pady=8)
        ctk.CTkLabel(glob, text="Profile Settings",
                     font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.name_var = ctk.StringVar(value=self.profile.profile_name)
        self.name_var.trace_add("write",
                                lambda *_: setattr(self.profile, "profile_name",
                                                   self.name_var.get()))
        self._labeled(glob, "Name:", ctk.CTkEntry(glob, textvariable=self.name_var))
        self.anim_var = ctk.StringVar(value=self.profile.idle_animation)
        self.anim_var.trace_add("write",
                                lambda *_: setattr(self.profile, "idle_animation",
                                                   self.anim_var.get()))
        self._labeled(glob, "Idle Anim:",
                      ctk.CTkComboBox(glob, values=["none", "breathe", "rainbow", "flash"],
                                      variable=self.anim_var))
        self.delay_var = ctk.StringVar(value=str(self.profile.default_delay))
        self.delay_var.trace_add("write", lambda *_: self._set_delay())
        self._labeled(glob, "Delay(ms):", ctk.CTkEntry(glob, textvariable=self.delay_var))
        disk = ctk.CTkFrame(glob, fg_color="transparent")
        disk.pack(fill="x", pady=8)
        ctk.CTkButton(disk, text="Import", width=100, command=self._import_disk).pack(side="left", padx=5)
        ctk.CTkButton(disk, text="Export", width=100, command=self._export_disk).pack(side="right", padx=5)

        logf = ctk.CTkFrame(self.tab_dash)
        logf.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        logf.grid_columnconfigure(0, weight=1)
        logf.grid_rowconfigure(0, weight=1)
        self.console = ctk.CTkTextbox(logf, font=ctk.CTkFont(family="Consolas", size=12),
                                      text_color="lightgreen", state="disabled")
        self.console.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _labeled(self, parent, label, widget):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row, text=label, width=85).pack(side="left")
        widget.master = row
        widget.pack(in_=row, side="left", fill="x", expand=True)

    def _set_delay(self):
        try:
            self.profile.default_delay = int(self.delay_var.get())
        except ValueError:
            pass

    # -- Key Editor ----------------------------------------------------
    def _build_editor(self):
        self.tab_editor.grid_columnconfigure(1, weight=1)
        self.tab_editor.grid_rowconfigure(0, weight=1)
        kb = ctk.CTkFrame(self.tab_editor, width=260)
        kb.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(kb, text="Keys", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=10)
        grid = ctk.CTkFrame(kb, fg_color="transparent")
        grid.pack(pady=20)
        self.key_buttons = {}
        for r, row in enumerate(KEY_LAYOUT):
            for c, kid in enumerate(row):
                if kid is None:
                    continue
                btn = ctk.CTkButton(grid, text=f"Key {kid}", width=80, height=80,
                                    command=lambda k=kid: self._select_key(k))
                btn.grid(row=r, column=c, padx=5, pady=5)
                self.key_buttons[kid] = btn

        area = ctk.CTkFrame(self.tab_editor)
        area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(area, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        head.grid_columnconfigure(0, weight=1)
        self.editor_title = ctk.CTkLabel(head, text="Actions for Key 1",
                                         font=ctk.CTkFont(size=18, weight="bold"))
        self.editor_title.grid(row=0, column=0, sticky="w")
        btns = ctk.CTkFrame(head, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btns, text="+ Add", width=80, command=self._add_action).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="✨ AI", width=70, fg_color="#7a3cba",
                      hover_color="#612f95", command=self._ai_fill_key).pack(side="left", padx=4)
        self.action_scroll = ctk.CTkScrollableFrame(area)
        self.action_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self._select_key(1)

    def _select_key(self, kid):
        self.selected_key = kid
        self.editor_title.configure(text=f"Actions for Key {kid}")
        for k, btn in self.key_buttons.items():
            btn.configure(fg_color=["#2fa572", "#106A43"] if k == kid
                          else ["#3B8ED0", "#1F6AA5"])
        self._refresh_actions()

    def _refresh_actions(self):
        for row in self.action_rows:
            row.destroy()
        self.action_rows.clear()
        for act in self.profile.key(self.selected_key).actions:
            self._add_action_row(act)

    def _add_action_row(self, action):
        row = ActionEditorRow(self.action_scroll, action,
                              on_delete=self._remove_action, on_change=lambda: None)
        row.pack(fill="x", pady=2, padx=5)
        self.action_rows.append(row)

    def _add_action(self):
        act = dict(DEFAULT_ACTION["text"])
        self.profile.key(self.selected_key).actions.append(act)
        self._add_action_row(act)

    def _remove_action(self, row):
        actions = self.profile.key(self.selected_key).actions
        if row.action in actions:
            actions.remove(row.action)
        row.destroy()
        self.action_rows.remove(row)

    def _ai_fill_key(self):
        dialog = ctk.CTkInputDialog(text="Describe the macro for this key:",
                                    title="AI Macro")
        desc = dialog.get_input()
        if not desc:
            return
        self._console(f"AI: generating macro for key {self.selected_key}...\n")
        kid = self.selected_key

        def done(actions):
            if not actions:
                self._console("AI: no valid macro produced.\n")
                return
            self.profile.key(kid).actions[:] = actions
            if self.selected_key == kid:
                self._refresh_actions()
            self._console(f"AI: filled key {kid} with {len(actions)} action(s).\n")

        self.ai.submit("generate_actions", desc, on_done=done)

    # -- Auto-Switcher -------------------------------------------------
    def _build_autoswitch(self):
        self.tab_auto.grid_columnconfigure(0, weight=1)
        self.tab_auto.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self.tab_auto, text="Auto Switcher",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=10)
        ctrls = ctk.CTkFrame(self.tab_auto, fg_color="transparent")
        ctrls.grid(row=1, column=0, pady=5)
        ctk.CTkCheckBox(ctrls, text="Enable background auto-switching",
                        variable=self.auto_switch_var,
                        command=self._toggle_autoswitch).pack(side="left", padx=10)
        self.tracking_console = ctk.CTkTextbox(
            self.tab_auto, font=ctk.CTkFont(family="Consolas", size=12),
            text_color="cyan", state="disabled")
        self.tracking_console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

    def _toggle_autoswitch(self):
        self.settings.set("auto_switch_enabled", self.auto_switch_var.get())

    # -- Settings ------------------------------------------------------
    def _build_settings(self):
        ctk.CTkLabel(self.tab_settings, text="Settings",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        ctk.CTkButton(self.tab_settings, text="AI Configuration",
                      command=lambda: AISettingsPopup(self, self.settings,
                                                      on_save=self._rebuild_ai_client)
                      ).pack(pady=8)
        ctk.CTkButton(self.tab_settings, text="Widget Appearance",
                      command=lambda: WidgetSettingsPopup(self, self.settings,
                                                          self.rec_widget)).pack(pady=8)

    # -- Serial --------------------------------------------------------
    def _ports(self):
        ports = list_ports()
        return ports or ["No Ports Found"]

    def _refresh_ports(self):
        self.port_combo.configure(values=self._ports())

    def _toggle_connection(self):
        if self.link.is_open():
            self.link.disconnect()
            self._on_disconnect()
            return
        port = self.port_var.get()
        if "Select" in port or "No Ports" in port:
            messagebox.showerror("Error", "Select a valid COM port.")
            return
        if self.link.connect(port, SERIAL_BAUD):
            self.settings.set("last_port", port)
            self.connect_btn.configure(text="Disconnect", fg_color="red",
                                       hover_color="darkred")
            for b in (self.load_btn, self.save_btn, self.active_btn):
                b.configure(state="normal")
            self.after(400, self.link.request_fs_info)

    def _on_disconnect(self):
        self.connect_btn.configure(text="Connect", fg_color="green",
                                   hover_color="darkgreen")
        for b in (self.load_btn, self.save_btn, self.active_btn):
            b.configure(state="disabled")

    def _load_from_device(self):
        self._console(f"Fetching {self.profile_file_var.get()}...\n")
        self.link.request_profile(self.profile_file_var.get())

    def _on_file_captured(self, lines):
        try:
            data = parse_profile_payload(lines)
        except (json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Parse Error", f"Invalid profile JSON:\n{e}")
            return
        try:
            self.profile = Profile.from_dict(data)
        except ValueError as e:
            messagebox.showerror("Profile Error", str(e))
            return
        for i in range(1, NUM_KEYS + 1):
            self.profile.key(i)
        self._sync_global_fields()
        self._select_key(self.selected_key)
        self._console("Profile loaded into editor.\n")

    def _save_to_device(self):
        ok, errors = self.profile.validate()
        if not ok:
            if not messagebox.askyesno(
                    "Validation warnings",
                    "Some actions failed validation and will be repaired/dropped:\n\n"
                    + "\n".join(errors[:8]) + "\n\nContinue?"):
                return
        target = self.profile_file_var.get()
        self._console(f"Uploading {target}...\n")
        self.link.upload_profile(
            target, self.profile.to_dict(),
            on_complete=lambda: self.after(500, self._post_upload))

    def _post_upload(self):
        self._set_active()
        self.after(600, self.link.request_fs_info)

    def _set_active(self):
        m = re.search(r"profile(\d+)", self.profile_file_var.get())
        if m:
            self.link.set_active_profile(int(m.group(1)))
            self._console(f"Set active profile {m.group(1)}.\n")

    def _update_storage(self, total, used):
        free = max(0, total - used)
        self.storage_lbl.configure(
            text=f"Storage: {used/1024:.1f} KB used / {free/1024:.1f} KB free")
        self.storage_bar.set(used / total if total > 0 else 0)

    def push_shortcut_to_device(self, shortcut):
        if not self.link.is_open():
            return
        knum = shortcut.get("key_num")
        if knum and 1 <= knum <= NUM_KEYS:
            self.link.send_cmd(f"setkey {knum} {json.dumps(shortcut.get('actions', []))}")

    # -- Disk I/O ------------------------------------------------------
    def _import_disk(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.profile = Profile.from_dict(json.load(f))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            messagebox.showerror("Import Error", str(e))
            return
        for i in range(1, NUM_KEYS + 1):
            self.profile.key(i)
        self._sync_global_fields()
        self._select_key(self.selected_key)
        self._console(f"Imported {path}\n")

    def _export_disk(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.profile.to_dict(), f, indent=2)
            self._console(f"Exported {path}\n")
        except OSError as e:
            messagebox.showerror("Export Error", str(e))

    def _sync_global_fields(self):
        self.name_var.set(self.profile.profile_name)
        self.anim_var.set(self.profile.idle_animation)
        self.delay_var.set(str(self.profile.default_delay))

    # -- Context / AI --------------------------------------------------
    def _on_context_change(self, context):
        self.current_context = context
        self._tlog(f"Context -> [{context}]\n")
        shortcuts = self.templates.get_context_shortcuts(context)
        try:
            if self.rec_widget.winfo_exists() and self.auto_switch_var.get():
                self.rec_widget.deiconify()
                self.rec_widget.update_context(context, shortcuts or None,
                                               is_generating=not shortcuts)
        except Exception:  # noqa: BLE001
            pass
        existing = self.templates.custom_templates.get(context.lower(), [])
        self.ai.submit("generate_shortcuts", context, existing=existing,
                       on_done=lambda items, c=context: self._on_ai_shortcuts(c, items))

    def _on_ai_shortcuts(self, context, items):
        if not items:
            return
        added = self.templates.add_shortcuts(context, items)
        self.db.save_app_shortcuts(context, self.templates.get_context_shortcuts(context))
        self._tlog(f"AI: added {added} new shortcut(s) for [{context}].\n")
        if self.current_context == context and self.rec_widget.winfo_exists():
            self.rec_widget.update_context(
                context, self.templates.get_context_shortcuts(context))

    def _regen_key(self, knum):
        if not self.current_context:
            return
        ctx = self.current_context
        self._tlog(f"Regenerating key {knum} for [{ctx}]...\n")
        self.ai.submit("generate_shortcuts", ctx,
                       existing=self.templates.custom_templates.get(ctx.lower(), []),
                       key_nums=[knum],
                       on_done=lambda items, c=ctx: self._on_ai_shortcuts(c, items))

    # -- logging / lifecycle ------------------------------------------
    def _console(self, text):
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _tlog(self, text):
        self.tracking_console.configure(state="normal")
        self.tracking_console.insert("end", text)
        self.tracking_console.see("end")
        self.tracking_console.configure(state="disabled")

    def _on_close(self):
        try:
            self.tracker.stop()
            self.ai.stop()
            self.link.disconnect()
        finally:
            self.destroy()


def main():
    MacropadApp().mainloop()


if __name__ == "__main__":
    main()
