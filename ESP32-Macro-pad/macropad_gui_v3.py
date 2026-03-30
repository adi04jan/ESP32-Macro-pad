import os
import sys
import json
import time
import threading
import serial
import serial.tools.list_ports
import customtkinter as ctk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ACTION_TYPES = [
    "text", "keycombo", "delay", "key", "hold", "release", "repeat",
    "media", "mouse_click", "mouse_move", "led", "led_anim", "profile", "telephony"
]

TK_TO_ESP32_MAP = {
    "Control_L": "LEFT_CTRL", "Shift_L": "LEFT_SHIFT", "Alt_L": "LEFT_ALT", "Win_L": "LEFT_GUI",
    "Control_R": "RIGHT_CTRL", "Shift_R": "RIGHT_SHIFT", "Alt_R": "RIGHT_ALT", "Win_R": "RIGHT_GUI",
    "Return": "ENTER", "Escape": "ESC", "BackSpace": "BACKSPACE", "Tab": "TAB", "space": "SPACE",
    "minus": "MINUS", "equal": "EQUAL", "bracketleft": "LEFT_BRACE", "bracketright": "RIGHT_BRACE",
    "backslash": "BACKSLASH", "semicolon": "SEMICOLON", "apostrophe": "QUOTE", "grave": "TILDE",
    "asciitilde": "TILDE", "comma": "COMMA", "period": "DOT", "slash": "SLASH", "Caps_Lock": "CAPS_LOCK",
    "Insert": "INSERT", "Home": "HOME", "Prior": "PAGEUP", "Delete": "DELETE", "End": "END",
    "Next": "PAGEDOWN", "Right": "RIGHT_ARROW", "Left": "LEFT_ARROW", "Down": "DOWN_ARROW", "Up": "UP_ARROW"
}

class RecordKeycomboPopup(ctk.CTkToplevel):
    def __init__(self, master, current_value, on_save):
        super().__init__(master)
        self.title("Record Keycombo")
        self.geometry("450x200")
        self.attributes('-topmost', 'true')
        self.on_save = on_save
        
        self.recorded_keys = set()
        self.ordered_keys = []
        
        self.label = ctk.CTkLabel(self, text="Press keys to record...", font=ctk.CTkFont(size=16))
        self.label.pack(pady=20)
        
        self.result_var = ctk.StringVar(value=current_value)
        self.result_label = ctk.CTkLabel(self, textvariable=self.result_var, font=ctk.CTkFont(size=18, weight="bold"))
        self.result_label.pack(pady=10)
        
        self.stop_btn = ctk.CTkButton(self, text="Stop Recording & Save", fg_color="red", hover_color="darkred", command=self.save_and_close)
        self.stop_btn.pack(pady=10)
        
        self.bind("<KeyPress>", self.on_key_press)
        self.focus_force()

    def map_keysym(self, keysym):
        if keysym in TK_TO_ESP32_MAP: return TK_TO_ESP32_MAP[keysym]
        if len(keysym) == 1: return keysym.upper()
        if keysym.startswith("F") and keysym[1:].isdigit(): return keysym
        return keysym.upper()

    def on_key_press(self, event):
        esp_key = self.map_keysym(event.keysym)
        if esp_key not in self.recorded_keys:
            self.recorded_keys.add(esp_key)
            self.ordered_keys.append(esp_key)
            self.result_var.set(", ".join(self.ordered_keys))

    def save_and_close(self):
        self.on_save(self.result_var.get())
        self.destroy()

class ActionEditorRow(ctk.CTkFrame):
    def __init__(self, master, action_dict, on_delete, on_change, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.action_dict = action_dict
        self.on_delete = on_delete
        self.on_change = on_change
        
        self.grid_columnconfigure(1, weight=1)
        
        self.type_var = ctk.StringVar(value=action_dict.get("type", "text"))
        self.type_dropdown = ctk.CTkComboBox(self, values=ACTION_TYPES, variable=self.type_var, command=self.type_changed_cb, width=120)
        self.type_dropdown.grid(row=0, column=0, padx=5, pady=5)
        
        self.value_var = ctk.StringVar()
        
        self.value_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.value_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.value_frame.grid_columnconfigure(0, weight=1)

        self.value_entry = ctk.CTkEntry(self.value_frame, textvariable=self.value_var)
        self.value_entry.grid(row=0, column=0, sticky="ew")
        self.value_entry.bind("<KeyRelease>", self.value_changed)
        
        self.record_btn = ctk.CTkButton(self.value_frame, text="Record", width=60, fg_color="orange", hover_color="darkorange", command=self.open_record_popup)
        
        self.del_btn = ctk.CTkButton(self, text="X", width=30, fg_color="red", hover_color="darkred", command=self.delete_me)
        self.del_btn.grid(row=0, column=3, padx=5, pady=5)
        
        self.populate_value_from_dict()
        self.update_ui_for_type()

    def update_ui_for_type(self):
        t = self.type_var.get()
        if t == "keycombo":
            self.record_btn.grid(row=0, column=1, padx=(5,0))
            self.value_entry.configure(state="readonly")
        else:
            self.record_btn.grid_forget()
            self.value_entry.configure(state="normal")
            if t == "release":
                self.value_entry.configure(state="disabled")

    def open_record_popup(self):
        RecordKeycomboPopup(self, self.value_var.get(), self.on_record_save)

    def on_record_save(self, val):
        self.value_var.set(val)
        self.value_changed()

    def populate_value_from_dict(self):
        t = self.type_var.get()
        d = self.action_dict
        if t in ["text", "key", "led_anim", "hold"]:
            self.value_var.set(d.get("value", d.get("key", "")))
        elif t == "delay": self.value_var.set(str(d.get("ms", 30)))
        elif t == "repeat": self.value_var.set(str(d.get("count", 1)))
        elif t == "keycombo":
            keys = d.get("keys", [])
            self.value_var.set(", ".join(keys) if isinstance(keys, list) else str(keys))
        elif t == "media": self.value_var.set(d.get("value", "PLAY_PAUSE"))
        elif t == "mouse_click": self.value_var.set(d.get("button", "LEFT"))
        elif t == "mouse_move": self.value_var.set(f"{d.get('x',0)}, {d.get('y',0)}")
        elif t == "led":
            c = d.get("color", [255,255,255])
            self.value_var.set(", ".join(map(str, c)))
        elif t == "profile": self.value_var.set(str(d.get("value", 1)))
        elif t == "telephony": self.value_var.set(d.get("value", "MIC_MUTE"))
        else: self.value_var.set("")
            
    def type_changed_cb(self, new_type):
        self.action_dict["type"] = new_type
        keys_to_remove = [k for k in self.action_dict.keys() if k != "type"]
        for k in keys_to_remove: del self.action_dict[k]
        self.update_ui_for_type()
        self.populate_value_from_dict()
        self.on_change()
        
    def value_changed(self, event=None):
        t = self.type_var.get()
        v = self.value_var.get()
        d = self.action_dict
        
        if t in ["text", "key", "led_anim", "media", "telephony"]: d["value"] = v
        elif t == "hold": d["key"] = v
        elif t == "delay":
            try: d["ms"] = int(v)
            except: pass
        elif t == "repeat":
            try: d["count"] = int(v)
            except: pass
        elif t == "keycombo": d["keys"] = [x.strip() for x in v.split(",") if x.strip()]
        elif t == "mouse_click": d["button"] = v
        elif t == "mouse_move":
            try:
                parts = [x.strip() for x in v.split(",")]
                d["x"] = int(parts[0])
                if len(parts) > 1: d["y"] = int(parts[1])
            except: pass
        elif t == "led":
            try: d["color"] = [int(x.strip()) for x in v.split(",") if x.strip()]
            except: pass
        elif t == "profile":
            try: d["value"] = int(v)
            except: pass
        self.on_change()
        
    def delete_me(self):
        self.on_delete(self)


class MacropadV3App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Macropad Configurator V3")
        self.geometry("1200x800")

        self.serial_port = None
        self.serial_thread = None
        self.stop_event = threading.Event()
        self.capturing_file = False
        self.file_buffer = []
        
        self.selected_key_id = 1
        self.action_rows = []

        self.profile_data = self.create_empty_profile()
        self.auto_switch_rules = {"code": 2, "photoshop": 3}
        self.auto_switch_enabled = ctk.BooleanVar(value=False)

        # Tab Layout
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_editor = self.tabview.add("Key Editor")
        self.tab_autoswitch = self.tabview.add("Auto-Switcher")

        self.setup_dashboard()
        self.setup_editor()
        self.setup_autoswitch()

        self.auto_switch_thread = threading.Thread(target=self.auto_switch_loop, daemon=True)
        self.auto_switch_thread.start()

    def create_empty_profile(self):
        return {
            "profile_name": "New Profile",
            "idle_animation": "none",
            "default_delay": 30,
            "keys": [{"id": i, "actions": []} for i in range(1, 13)]
        }

    def setup_dashboard(self):
        # Dashboard layout: Left config/sync panel, Right logging panel
        self.tab_dashboard.grid_columnconfigure(1, weight=1)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)

        left_side = ctk.CTkFrame(self.tab_dashboard, width=300)
        left_side.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        log_frame = ctk.CTkFrame(self.tab_dashboard)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # --- Connection Box ---
        conn_box = ctk.CTkFrame(left_side)
        conn_box.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(conn_box, text="Device Connection", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.port_var = ctk.StringVar(value="Select Port")
        self.port_dropdown = ctk.CTkComboBox(conn_box, variable=self.port_var, values=self.get_ports())
        self.port_dropdown.pack(padx=10, pady=5)
        
        ctk.CTkButton(conn_box, text="Refresh Ports", command=self.refresh_ports).pack(padx=10, pady=5)
        self.connect_btn = ctk.CTkButton(conn_box, text="Connect", command=self.toggle_connection, fg_color="green", hover_color="darkgreen")
        self.connect_btn.pack(padx=10, pady=10)
        
        # --- File Management Box ---
        file_box = ctk.CTkFrame(left_side)
        file_box.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(file_box, text="Sync Profiles", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.profile_var = ctk.StringVar(value="profile1.json")
        ctk.CTkComboBox(file_box, variable=self.profile_var, values=["profile1.json", "profile2.json", "profile3.json"]).pack(padx=10, pady=5)
        
        self.load_btn = ctk.CTkButton(file_box, text="Load from Device", command=self.load_profile_from_device, state="disabled")
        self.load_btn.pack(padx=10, pady=5)
        self.save_btn = ctk.CTkButton(file_box, text="Save to Device", command=self.save_profile_to_device, state="disabled")
        self.save_btn.pack(padx=10, pady=5)
        self.set_active_btn = ctk.CTkButton(file_box, text="Set Active", command=self.set_active_profile, state="disabled")
        self.set_active_btn.pack(padx=10, pady=5)

        # --- Global Settings ---
        set_box = ctk.CTkFrame(left_side)
        set_box.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(set_box, text="Profile Global Settings", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        f1 = ctk.CTkFrame(set_box, fg_color="transparent")
        f1.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f1, text="Name:", width=80).pack(side="left")
        self.prof_name_var = ctk.StringVar(value=self.profile_data["profile_name"])
        self.prof_name_var.trace_add("write", lambda *args: self.update_global_setting("profile_name", self.prof_name_var.get()))
        ctk.CTkEntry(f1, textvariable=self.prof_name_var).pack(side="left", fill="x", expand=True)

        f2 = ctk.CTkFrame(set_box, fg_color="transparent")
        f2.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f2, text="Idle Anim:", width=80).pack(side="left")
        self.idle_anim_var = ctk.StringVar(value=self.profile_data["idle_animation"])
        self.idle_anim_var.trace_add("write", lambda *args: self.update_global_setting("idle_animation", self.idle_anim_var.get()))
        ctk.CTkComboBox(f2, values=["none", "breathe", "flash", "rainbow"], variable=self.idle_anim_var).pack(side="left", fill="x", expand=True)
        
        f3 = ctk.CTkFrame(set_box, fg_color="transparent")
        f3.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(f3, text="Delay (ms):", width=80).pack(side="left")
        self.def_delay_var = ctk.StringVar(value=str(self.profile_data["default_delay"]))
        self.def_delay_var.trace_add("write", lambda *args: self.update_global_int("default_delay", self.def_delay_var.get()))
        ctk.CTkEntry(f3, textvariable=self.def_delay_var).pack(side="left", fill="x", expand=True)
        
        local_btn_frame = ctk.CTkFrame(set_box, fg_color="transparent")
        local_btn_frame.pack(fill="x", padx=5, pady=10)
        ctk.CTkButton(local_btn_frame, text="Import Disk", width=100, command=self.import_disk).pack(side="left", padx=5)
        ctk.CTkButton(local_btn_frame, text="Export Disk", width=100, command=self.export_disk).pack(side="right", padx=5)

        # Logging View
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        self.console = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=12), text_color="lightgreen", state="disabled")
        self.console.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def setup_editor(self):
        self.tab_editor.grid_columnconfigure(1, weight=1)
        self.tab_editor.grid_rowconfigure(0, weight=1)

        # Keyboard Mapping
        self.kb_frame = ctk.CTkFrame(self.tab_editor, width=250)
        self.kb_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.kb_frame, text="Keyboard Layout", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=10)
        
        grid_frame = ctk.CTkFrame(self.kb_frame, fg_color="transparent")
        grid_frame.pack(pady=20)
        
        self.key_buttons = {}
        layout = [
            [None, 1, 2, None],
            [3, 4, 5, 6],
            [7, 8, 9, 10],
            [None, 11, 12, None]
        ]
        for r, row in enumerate(layout):
            grid_frame.grid_rowconfigure(r, weight=1)
            for c, key_id in enumerate(row):
                grid_frame.grid_columnconfigure(c, weight=1)
                if key_id is not None:
                    btn = ctk.CTkButton(grid_frame, text=f"Key {key_id}", width=80, height=80, 
                                        command=lambda kid=key_id: self.select_key(kid))
                    btn.grid(row=r, column=c, padx=5, pady=5)
                    self.key_buttons[key_id] = btn

        # Actions Editor
        self.action_area = ctk.CTkFrame(self.tab_editor)
        self.action_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.action_area.grid_columnconfigure(0, weight=1)
        self.action_area.grid_rowconfigure(1, weight=1)
        
        header = ctk.CTkFrame(self.action_area, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(0, weight=1)
        
        self.action_title = ctk.CTkLabel(header, text="Actions for Key 1", font=ctk.CTkFont(size=18, weight="bold"))
        self.action_title.grid(row=0, column=0, sticky="w")
        
        ctk.CTkButton(header, text="+ Add Action", width=120, command=self.add_action).grid(row=0, column=1, sticky="e")
        
        self.action_scroll = ctk.CTkScrollableFrame(self.action_area)
        self.action_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.select_key(1)

    def setup_autoswitch(self):
        self.tab_autoswitch.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.tab_autoswitch, text="Auto Switcher assigns specific window titles to switch to specific profiles automatically.", font=ctk.CTkFont(size=14)).grid(row=0, column=0, pady=10)
        ctk.CTkCheckBox(self.tab_autoswitch, text="Enable Background Auto-Switching", variable=self.auto_switch_enabled).grid(row=1, column=0, pady=10)
        # We can implement full UI editing for rules if needed later.
        ctk.CTkLabel(self.tab_autoswitch, text="Note: Add more advanced tracking features in future versions.", font=ctk.CTkFont(size=12, slant="italic")).grid(row=2, column=0, pady=30)

    # --- Utility Methods ---
    def update_global_setting(self, key, val):
        self.profile_data[key] = val
        
    def update_global_int(self, key, val):
        try: self.profile_data[key] = int(val)
        except: pass

    # --- Key Selection & Actions ---
    def select_key(self, key_id):
        self.selected_key_id = key_id
        self.action_title.configure(text=f"Actions for Key {key_id}")
        
        for kid, btn in self.key_buttons.items():
            btn.configure(fg_color=["#3B8ED0", "#1F6AA5"] if kid != key_id else ["#2fa572", "#106A43"])
            
        self.refresh_action_editor()

    def get_key_data(self, key_id):
        keys = self.profile_data.setdefault("keys", [])
        for k in keys:
            if k.get("id") == key_id:
                return k
        new_k = {"id": key_id, "actions": []}
        keys.append(new_k)
        return new_k

    def refresh_action_editor(self):
        for row in self.action_rows: row.destroy()
        self.action_rows.clear()
        
        kdata = self.get_key_data(self.selected_key_id)
        for act in kdata.setdefault("actions", []):
            self.create_action_row(act)

    def create_action_row(self, action_dict):
        row = ActionEditorRow(self.action_scroll, action_dict, self.remove_action, self.on_action_change)
        row.pack(fill="x", pady=2, padx=5)
        self.action_rows.append(row)

    def add_action(self):
        kdata = self.get_key_data(self.selected_key_id)
        new_act = {"type": "text", "value": ""}
        kdata.setdefault("actions", []).append(new_act)
        self.create_action_row(new_act)
        
    def remove_action(self, row_obj):
        kdata = self.get_key_data(self.selected_key_id)
        if row_obj.action_dict in kdata.get("actions", []):
            kdata["actions"].remove(row_obj.action_dict)
        row_obj.destroy()
        self.action_rows.remove(row_obj)
        
    def on_action_change(self):
        pass # The object references change directly so no rebuild needed

    def sync_ui_to_data(self):
        self.prof_name_var.set(self.profile_data.get("profile_name", "Unknown"))
        self.idle_anim_var.set(self.profile_data.get("idle_animation", "none"))
        self.def_delay_var.set(str(self.profile_data.get("default_delay", 30)))
        
        existing_ids = [k.get("id") for k in self.profile_data.setdefault("keys", [])]
        for i in range(1, 13):
            if i not in existing_ids:
                self.profile_data["keys"].append({"id": i, "actions": []})
        self.refresh_action_editor()

    # --- Disk I/O ---
    def import_disk(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if f:
            try:
                with open(f, "r") as file:
                    self.profile_data = json.load(file)
                    self.sync_ui_to_data()
                    self.append_console(f"Successfully loaded {f}\n")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def export_disk(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if f:
            try:
                with open(f, "w") as file:
                    json.dump(self.profile_data, file, indent=2)
                self.append_console(f"Successfully saved to {f}\n")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    # --- Auto-Switch Engine ---
    def auto_switch_loop(self):
        last_active = ""
        while not self.stop_event.is_set():
            if self.auto_switch_enabled.get():
                try:
                    import pygetwindow as gw
                    win = gw.getActiveWindow()
                    if win and win.title:
                        title = win.title.lower()
                        if title != last_active:
                            last_active = title
                            for keyword, profile_num in self.auto_switch_rules.items():
                                if keyword in title:
                                    if self.serial_port and self.serial_port.is_open:
                                        self.send_cmd(f"setprofile {profile_num}")
                                        self.after(0, self.append_console, f"Auto-Switched to Profile {profile_num} ({keyword})\n")
                                    break
                except Exception:
                    pass
            time.sleep(1.0)

    # --- Serial Control ---
    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports] if ports else ["No Ports Found"]

    def refresh_ports(self):
        self.port_dropdown.configure(values=self.get_ports())
        self.port_dropdown.set("Select Port")

    def append_console(self, text):
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def send_cmd(self, cmd):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.write((cmd + "\n").encode('utf-8'))

    def toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.stop_event.set()
            if self.serial_thread:
                self.serial_thread.join(timeout=1.0)
            self.serial_port.close()
            self.serial_port = None
            self.connect_btn.configure(text="Connect", fg_color="green", hover_color="darkgreen")
            self.append_console("Disconnected from serial port.\n")
            self.set_buttons_state("disabled")
        else:
            port = self.port_var.get()
            if "Select" in port or "No Ports" in port:
                messagebox.showerror("Error", "Please select a valid COM port.")
                return
            
            try:
                self.serial_port = serial.Serial(port, 115200, timeout=0.1)
                self.stop_event.clear()
                self.serial_thread = threading.Thread(target=self.serial_read_loop, daemon=True)
                self.serial_thread.start()
                
                self.connect_btn.configure(text="Disconnect", fg_color="red", hover_color="darkred")
                self.append_console(f"Connected to {port} at 115200 baud.\n")
                self.set_buttons_state("normal")
                self.send_cmd("")

            except Exception as e:
                messagebox.showerror("Connection Error", str(e))

    def set_buttons_state(self, state):
        self.load_btn.configure(state=state)
        self.save_btn.configure(state=state)
        self.set_active_btn.configure(state=state)

    def serial_read_loop(self):
        partial_line = ""
        while not self.stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting > 0:
                        raw = self.serial_port.readline()
                        line = raw.decode('utf-8', errors='replace')
                        if line:
                            if not line.endswith('\n') and "macropad:$" not in line:
                                partial_line += line
                            else:
                                full_line = partial_line + line
                                partial_line = ""
                                self.after(0, self.handle_serial_line, full_line)
                except Exception as e:
                    self.after(0, self.append_console, f"Serial Error: {str(e)}\n")
                    self.after(0, self.toggle_connection)
                    break
            time.sleep(0.01)

    def handle_serial_line(self, line):
        clean_line = line.replace('\r', '').replace('\n', '')
        
        if "macropad:$" in clean_line:
            if self.capturing_file:
                self.capturing_file = False
                self.finish_capture()
            self.append_console("Ready.\n")
            return

        if self.capturing_file:
            self.file_buffer.append(clean_line)
        else:
            self.append_console(line + "\n")

    def load_profile_from_device(self):
        if not self.serial_port or not self.serial_port.is_open:
            return
        
        target = self.profile_var.get()
        if not target.startswith("/"):
            target = "/" + target
        
        self.capturing_file = True
        self.file_buffer = []
        self.append_console(f"Fetching {target} from device...\n")
        self.send_cmd(f"cat {target}")

    def finish_capture(self):
        if not self.file_buffer:
            self.append_console("Warning: Received empty file or timeout.\n")
            return
            
        raw_text = "\n".join(self.file_buffer).strip()
        
        if "cat" in raw_text[:20]:
            lines = raw_text.split("\n")
            if len(lines) > 1:
                raw_text = "\n".join(lines[1:]).strip()
        
        try:
            parsed = json.loads(raw_text)
            self.profile_data = parsed
            self.sync_ui_to_data()
            self.append_console("Profile loaded successfully and mapped to GUI.\n")
        except json.JSONDecodeError as e:
            self.append_console(f"Failed to parse JSON. \nError: {str(e)}\n")
            messagebox.showerror("Parse Error", f"The downloaded profile contains invalid JSON:\\n{e}")

    def save_profile_to_device(self):
        try:
            json_str = json.dumps(self.profile_data)
        except Exception as e:
            messagebox.showerror("Serialization Error", f"Failed to build JSON:\\n{str(e)}")
            return

        target = self.profile_var.get()
        if target.startswith("/"):
            target = target[1:]

        self.append_console(f"Uploading {target}...\n")
        
        def save_thread():
            self.send_cmd(f"###BEGIN### {target}")
            formatted_text = json.dumps(self.profile_data, indent=2)
            for line in formatted_text.split('\n'):
                self.send_cmd(line)
                time.sleep(0.01)
                
            self.send_cmd("###END###")
            self.after(0, lambda: self.append_console("Upload sequence sent.\n"))
            self.after(500, self.set_active_profile)

        threading.Thread(target=save_thread, daemon=True).start()

    def set_active_profile(self):
        target = self.profile_var.get()
        import re
        match = re.search(r'profile(\d+)', target)
        if match:
            num = match.group(1)
            self.send_cmd(f"setprofile {num}")
            self.append_console(f"Setting active profile to {num}\n")
        else:
            self.append_console("Could not determine profile number.\n")

if __name__ == "__main__":
    app = MacropadV3App()
    app.mainloop()
