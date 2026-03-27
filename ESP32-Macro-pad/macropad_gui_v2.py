import os
import sys
import json
import time
import threading
import serial
import serial.tools.list_ports
import customtkinter as ctk
import tkinter.messagebox as messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ACTION_TYPES = ["text", "keycombo", "delay", "key", "media", "mouse_click", "mouse_move", "led", "led_anim", "profile", "telephony"]

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
        self.bind("<KeyRelease>", self.on_key_release)
        self.focus_force()

    def map_keysym(self, keysym):
        if keysym in TK_TO_ESP32_MAP:
            return TK_TO_ESP32_MAP[keysym]
        if len(keysym) == 1:
            return keysym.upper()
        if keysym.startswith("F") and keysym[1:].isdigit():
            return keysym
        return keysym.upper()

    def on_key_press(self, event):
        esp_key = self.map_keysym(event.keysym)
        if esp_key not in self.recorded_keys:
            self.recorded_keys.add(esp_key)
            self.ordered_keys.append(esp_key)
            self.result_var.set(", ".join(self.ordered_keys))

    def on_key_release(self, event):
        pass

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
        self.del_btn.grid(row=0, column=2, padx=5, pady=5)
        
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

    def open_record_popup(self):
        RecordKeycomboPopup(self, self.value_var.get(), self.on_record_save)

    def on_record_save(self, val):
        self.value_var.set(val)
        self.value_changed()

    def populate_value_from_dict(self):
        t = self.type_var.get()
        d = self.action_dict
        if t in ["text", "key", "led_anim"]:
            self.value_var.set(d.get("value", ""))
        elif t == "delay":
            self.value_var.set(str(d.get("ms", 30)))
        elif t == "keycombo":
            keys = d.get("keys", [])
            self.value_var.set(", ".join(keys) if isinstance(keys, list) else str(keys))
        elif t == "media":
            self.value_var.set(d.get("value", "PLAY_PAUSE"))
        elif t == "mouse_click":
            self.value_var.set(d.get("button", "LEFT"))
        elif t == "mouse_move":
            self.value_var.set(f"{d.get('x',0)}, {d.get('y',0)}")
        elif t == "led":
            c = d.get("color", [255,255,255])
            self.value_var.set(", ".join(map(str, c)))
        elif t == "profile":
            self.value_var.set(str(d.get("value", 1)))
        elif t == "telephony":
            self.value_var.set(d.get("value", "MIC_MUTE"))
        else:
            self.value_var.set("")
            
    def type_changed_cb(self, new_type):
        self.action_dict["type"] = new_type
        # Clean up old irrelevant keys
        keys_to_remove = [k for k in self.action_dict.keys() if k != "type"]
        for k in keys_to_remove:
            del self.action_dict[k]
        self.update_ui_for_type()
        self.populate_value_from_dict()
        self.on_change()
        
    def value_changed(self, event=None):
        t = self.type_var.get()
        v = self.value_var.get()
        d = self.action_dict
        
        if t in ["text", "key", "led_anim", "media", "telephony"]:
            d["value"] = v
        elif t == "delay":
            try: d["ms"] = int(v)
            except: pass
        elif t == "keycombo":
            d["keys"] = [x.strip() for x in v.split(",") if x.strip()]
        elif t == "mouse_click":
            d["button"] = v
        elif t == "mouse_move":
            try:
                parts = [x.strip() for x in v.split(",")]
                d["x"] = int(parts[0])
                if len(parts) > 1: d["y"] = int(parts[1])
            except: pass
        elif t == "led":
            try:
                d["color"] = [int(x.strip()) for x in v.split(",") if x.strip()]
            except: pass
        elif t == "profile":
            try: d["value"] = int(v)
            except: pass
            
        self.on_change()
        
    def delete_me(self):
        self.on_delete(self)


class MacropadConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Macropad Visual Configurator")
        self.geometry("1100x750")

        self.serial_port = None
        self.serial_thread = None
        self.stop_event = threading.Event()
        
        self.capturing_file = False
        self.file_buffer = []
        
        self.selected_key_id = 1
        self.action_rows = []

        # Default empty profile structure
        self.profile_data = self.create_empty_profile()

        # UI Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_sidebar()
        self.setup_main_area()

    def create_empty_profile(self):
        return {
            "profile_name": "New Profile",
            "idle_animation": "none",
            "default_delay": 30,
            "keys": [{"id": i, "actions": []} for i in range(1, 13)]
        }

    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Macro Config", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.port_var = ctk.StringVar(value="Select Port")
        self.port_dropdown = ctk.CTkComboBox(self.sidebar_frame, variable=self.port_var, values=self.get_ports())
        self.port_dropdown.grid(row=1, column=0, padx=20, pady=10)

        self.refresh_btn = ctk.CTkButton(self.sidebar_frame, text="Refresh Ports", command=self.refresh_ports)
        self.refresh_btn.grid(row=2, column=0, padx=20, pady=0)

        self.connect_btn = ctk.CTkButton(self.sidebar_frame, text="Connect", command=self.toggle_connection, fg_color="green", hover_color="darkgreen")
        self.connect_btn.grid(row=3, column=0, padx=20, pady=20)

        self.profile_var = ctk.StringVar(value="profile1.json")
        self.profile_dropdown = ctk.CTkComboBox(self.sidebar_frame, variable=self.profile_var, values=["profile1.json", "profile2.json", "profile3.json"])
        self.profile_dropdown.grid(row=4, column=0, padx=20, pady=10)

        self.load_btn = ctk.CTkButton(self.sidebar_frame, text="Load Profile", command=self.load_profile, state="disabled")
        self.load_btn.grid(row=5, column=0, padx=20, pady=5)

        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save to Device", command=self.save_profile, state="disabled")
        self.save_btn.grid(row=6, column=0, padx=20, pady=5)

        self.set_active_btn = ctk.CTkButton(self.sidebar_frame, text="Set Active", command=self.set_active_profile, state="disabled")
        self.set_active_btn.grid(row=7, column=0, padx=20, pady=5)

        self.console = ctk.CTkTextbox(self.sidebar_frame, height=150, font=ctk.CTkFont(family="Consolas", size=11), state="disabled", text_color="lightgreen")
        self.console.grid(row=9, column=0, padx=10, pady=(0, 10), sticky="nsew")

    def setup_main_area(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # 1. Global Settings
        self.settings_frame = ctk.CTkFrame(self.main_frame)
        self.settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.settings_frame, text="Global Settings", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, pady=5)

        ctk.CTkLabel(self.settings_frame, text="Profile Name:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.prof_name_var = ctk.StringVar(value=self.profile_data["profile_name"])
        self.prof_name_var.trace_add("write", lambda *args: self.update_global_setting("profile_name", self.prof_name_var.get()))
        ctk.CTkEntry(self.settings_frame, textvariable=self.prof_name_var).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(self.settings_frame, text="Idle Anim:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.idle_anim_var = ctk.StringVar(value=self.profile_data["idle_animation"])
        self.idle_anim_var.trace_add("write", lambda *args: self.update_global_setting("idle_animation", self.idle_anim_var.get()))
        ctk.CTkComboBox(self.settings_frame, values=["none", "breathe", "rainbow"], variable=self.idle_anim_var).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(self.settings_frame, text="Def. Delay (ms):").grid(row=1, column=4, padx=5, pady=5, sticky="e")
        self.def_delay_var = ctk.StringVar(value=str(self.profile_data["default_delay"]))
        self.def_delay_var.trace_add("write", lambda *args: self.update_global_int("default_delay", self.def_delay_var.get()))
        ctk.CTkEntry(self.settings_frame, textvariable=self.def_delay_var, width=80).grid(row=1, column=5, padx=5, pady=5, sticky="w")

        # 2. Visual Keyboard
        self.kb_frame = ctk.CTkFrame(self.main_frame)
        self.kb_frame.grid(row=1, column=0, padx=10, pady=10)
        
        self.key_buttons = {}
        layout = [
            [None, 1,   2,   None],
            [3,    4,   5,   6],
            [7,    8,   9,   10],
            [None, 11,  12,  None]
        ]
        
        for r, row in enumerate(layout):
            self.kb_frame.grid_rowconfigure(r, weight=1)
            for c, key_id in enumerate(row):
                self.kb_frame.grid_columnconfigure(c, weight=1)
                if key_id is not None:
                    btn = ctk.CTkButton(self.kb_frame, text=f"Key {key_id}", width=80, height=80, 
                                        command=lambda kid=key_id: self.select_key(kid))
                    btn.grid(row=r, column=c, padx=5, pady=5)
                    self.key_buttons[key_id] = btn

        # 3. Action Editor (Bottom)
        self.action_area = ctk.CTkFrame(self.main_frame)
        self.action_area.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.action_area.grid_columnconfigure(0, weight=1)
        self.action_area.grid_rowconfigure(1, weight=1)
        
        self.action_header = ctk.CTkFrame(self.action_area, fg_color="transparent")
        self.action_header.grid(row=0, column=0, sticky="ew")
        self.action_header.grid_columnconfigure(0, weight=1)
        
        self.action_title = ctk.CTkLabel(self.action_header, text="Actions for Key 1", font=ctk.CTkFont(size=16, weight="bold"))
        self.action_title.grid(row=0, column=0, pady=5, sticky="w")
        
        self.add_action_btn = ctk.CTkButton(self.action_header, text="+ Add Action", width=100, command=self.add_action)
        self.add_action_btn.grid(row=0, column=1, pady=5, sticky="e")
        
        self.action_scroll = ctk.CTkScrollableFrame(self.action_area)
        self.action_scroll.grid(row=1, column=0, sticky="nsew", pady=5)
        
        self.select_key(1)

    def update_global_setting(self, key, val):
        self.profile_data[key] = val
        
    def update_global_int(self, key, val):
        try: self.profile_data[key] = int(val)
        except: pass

    def select_key(self, key_id):
        self.selected_key_id = key_id
        self.action_title.configure(text=f"Actions for Key {key_id}")
        
        for kid, btn in self.key_buttons.items():
            btn.configure(fg_color=["#3B8ED0", "#1F6AA5"] if kid != key_id else ["#2fa572", "#106A43"])
            
        self.refresh_action_editor()

    def get_key_data(self, key_id):
        for k in self.profile_data.get("keys", []):
            if k.get("id") == key_id:
                return k
        # if not found, create it
        new_k = {"id": key_id, "actions": []}
        self.profile_data.setdefault("keys", []).append(new_k)
        return new_k

    def refresh_action_editor(self):
        for row in self.action_rows:
            row.destroy()
        self.action_rows.clear()
        
        kdata = self.get_key_data(self.selected_key_id)
        for act in kdata.get("actions", []):
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
        pass

    def sync_ui_to_data(self):
        self.prof_name_var.set(self.profile_data.get("profile_name", "Unknown"))
        self.idle_anim_var.set(self.profile_data.get("idle_animation", "none"))
        self.def_delay_var.set(str(self.profile_data.get("default_delay", 30)))
        
        # Add missing keys up to 12 just in case
        existing_ids = [k.get("id") for k in self.profile_data.get("keys", [])]
        for i in range(1, 13):
            if i not in existing_ids:
                self.profile_data.setdefault("keys", []).append({"id": i, "actions": []})
                
        self.refresh_action_editor()

    # --- SERIAL COMMS ---
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
        while not self.stop_event.is_set():
            if self.serial_port and self.serial_port.is_open:
                try:
                    if self.serial_port.in_waiting > 0:
                        line = self.serial_port.readline().decode('utf-8', errors='replace')
                        if line:
                            self.after(0, self.handle_serial_line, line)
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
            self.append_console(line)

    def load_profile(self):
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
            messagebox.showerror("Parse Error", f"The downloaded profile contains invalid JSON:\n{e}")

    def save_profile(self):
        try:
            json_str = json.dumps(self.profile_data)
        except Exception as e:
            messagebox.showerror("Serialization Error", f"Failed to build JSON:\n{str(e)}")
            return

        target = self.profile_var.get()
        if target.startswith("/"):
            target = target[1:]

        self.append_console(f"Uploading {target}...\n")
        self.send_cmd(f"###BEGIN### {target}")
        
        formatted_text = json.dumps(self.profile_data, indent=2)
        for line in formatted_text.split('\n'):
            self.send_cmd(line)
            time.sleep(0.01)
            
        self.send_cmd("###END###")
        self.append_console("Upload sequence sent.\n")

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
    app = MacropadConfigApp()
    app.mainloop()
