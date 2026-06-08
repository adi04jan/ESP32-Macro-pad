import customtkinter as ctk
from config import TK_TO_ESP32_MAP

class ActionEditorRow(ctk.CTkFrame):
    def __init__(self, master, action_dict, on_remove, on_change):
        super().__init__(master, fg_color=("gray85", "gray25"))
        self.action_dict = action_dict
        self.on_remove = on_remove
        self.on_change = on_change
        
        self.grid_columnconfigure(1, weight=1)
        
        self.type_var = ctk.StringVar(value=action_dict.get("type", "text"))
        self.type_combo = ctk.CTkComboBox(self, values=["text", "keycombo", "key", "hold", "release", "delay"], variable=self.type_var, width=100, command=self.update_ui_for_type)
        self.type_combo.grid(row=0, column=0, padx=5, pady=5)
        
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        self.val_entry = None
        self.key_combo_lbl = None
        
        ctk.CTkButton(self, text="Remove", width=60, fg_color="#C62828", hover_color="#B71C1C", command=lambda: self.on_remove(self)).grid(row=0, column=2, padx=5, pady=5)
        
        self.update_ui_for_type(self.type_var.get(), init=True)
        
    def update_ui_for_type(self, atype, init=False):
        for w in self.content_frame.winfo_children(): w.destroy()
        if not init:
            self.action_dict["type"] = atype
            if atype in ("text", "key", "hold", "release"):
                self.action_dict["value"] = ""
                if "keys" in self.action_dict: del self.action_dict["keys"]
                if "ms" in self.action_dict: del self.action_dict["ms"]
            elif atype == "keycombo":
                self.action_dict["keys"] = []
                if "value" in self.action_dict: del self.action_dict["value"]
                if "ms" in self.action_dict: del self.action_dict["ms"]
            elif atype == "delay":
                self.action_dict["ms"] = 50
                if "value" in self.action_dict: del self.action_dict["value"]
                if "keys" in self.action_dict: del self.action_dict["keys"]
            self.on_change()
            
        if atype in ("text", "key", "hold", "release"):
            self.val_entry = ctk.CTkEntry(self.content_frame)
            self.val_entry.grid(row=0, column=0, sticky="ew")
            self.val_entry.insert(0, str(self.action_dict.get("value", "")))
            self.val_entry.bind("<KeyRelease>", self.save_val)
        elif atype == "delay":
            self.val_entry = ctk.CTkEntry(self.content_frame)
            self.val_entry.grid(row=0, column=0, sticky="ew")
            self.val_entry.insert(0, str(self.action_dict.get("ms", 50)))
            self.val_entry.bind("<KeyRelease>", self.save_delay)
        elif atype == "keycombo":
            keys = self.action_dict.get("keys", [])
            txt = ", ".join(keys) if keys else "Click to record"
            self.key_combo_lbl = ctk.CTkButton(self.content_frame, text=txt, command=self.record_keys)
            self.key_combo_lbl.grid(row=0, column=0, sticky="ew")

    def save_val(self, event=None):
        self.action_dict["value"] = self.val_entry.get()
        self.on_change()

    def save_delay(self, event=None):
        try:
            self.action_dict["ms"] = int(self.val_entry.get())
            self.on_change()
        except: pass

    def record_keys(self):
        RecordKeycomboPopup(self, self.action_dict.get("keys", []), self.save_recorded_keys)

    def save_recorded_keys(self, key_str):
        keys = [k.strip() for k in key_str.split(",") if k.strip()]
        self.action_dict["keys"] = keys
        self.key_combo_lbl.configure(text=", ".join(keys) if keys else "Click to record")
        self.on_change()


class RecordKeycomboPopup(ctk.CTkToplevel):
    def __init__(self, master, current_value, on_save):
        super().__init__(master)
        self.title("Record Keycombo")
        self.geometry("450x200")
        self.attributes('-topmost', 'true')
        self.on_save = on_save
        
        self.result_var = ctk.StringVar(value=", ".join(current_value))
        self.recorded_keys = set(current_value)
        self.ordered_keys = list(current_value)
        
        ctk.CTkLabel(self, text="Press keys. Press 'Save' when done. Press 'Clear' to restart.").pack(pady=10)
        self.lbl = ctk.CTkLabel(self, textvariable=self.result_var, font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Clear", command=self.clear_keys, fg_color="#C62828", hover_color="#B71C1C").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Save", command=self.save_and_close).pack(side="left", padx=10)
        
        self.bind("<KeyPress>", self.on_key_press)
        self.focus_force()

    def map_keysym(self, keysym):
        return TK_TO_ESP32_MAP.get(keysym, keysym.upper())

    def clear_keys(self):
        self.recorded_keys.clear()
        self.ordered_keys.clear()
        self.result_var.set("")

    def on_key_press(self, event):
        esp_key = self.map_keysym(event.keysym)
        if esp_key not in self.recorded_keys:
            self.recorded_keys.add(esp_key)
            self.ordered_keys.append(esp_key)
            self.result_var.set(", ".join(self.ordered_keys))

    def save_and_close(self):
        self.on_save(self.result_var.get())
        self.destroy()


class AISettingsPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("AI Settings")
        self.geometry("450x250")
        self.attributes('-topmost', 'true')
        self.app_ref = master
        
        cfg_frame = ctk.CTkFrame(self)
        cfg_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(cfg_frame, text="Provider:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.provider_var = ctk.StringVar(value=self.app_ref.app_settings.get("ai_provider", "Ollama (Local)"))
        self.provider_combo = ctk.CTkComboBox(cfg_frame, values=["Ollama (Local)", "Gemini", "OpenAI"], variable=self.provider_var, command=self.on_provider_change)
        self.provider_combo.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        
        self.key_lbl = ctk.CTkLabel(cfg_frame, text="Key/URL:")
        self.key_lbl.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.key_var = ctk.StringVar(value=self.app_ref.app_settings.get("ai_key", "http://localhost:11434"))
        self.key_entry = ctk.CTkEntry(cfg_frame, textvariable=self.key_var, width=250)
        self.key_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        
        ctk.CTkLabel(cfg_frame, text="Model/Tag:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.model_var = ctk.StringVar(value=self.app_ref.app_settings.get("ai_model", "llama3:70b"))
        self.model_entry = ctk.CTkEntry(cfg_frame, textvariable=self.model_var, width=250)
        self.model_entry.grid(row=2, column=1, padx=5, pady=5, sticky="we")
        
        self.on_provider_change(self.provider_var.get(), initialize=True)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0,20))
        ctk.CTkButton(btn_frame, text="Save", command=self.save_settings, width=100).pack(side="right")

    def on_provider_change(self, val, initialize=False):
        if val == "Ollama (Local)":
            if not initialize: self.key_var.set(self.app_ref.app_settings.get("ai_key", "http://localhost:11434"))
            self.key_lbl.grid()
            self.key_entry.grid()
            self.key_lbl.configure(text="Ollama URL:")
            self.key_entry.configure(show="")
        elif val == "Gemini":
            if not initialize: self.key_var.set("")
            self.key_lbl.grid()
            self.key_entry.grid()
            self.key_lbl.configure(text="API Key:")
            self.key_entry.configure(show="*")
        else:
            if not initialize: self.key_var.set("")
            self.key_lbl.grid()
            self.key_entry.grid()
            self.key_lbl.configure(text="API Key:")
            self.key_entry.configure(show="*")

    def save_settings(self):
        self.app_ref.app_settings.set("ai_provider", self.provider_var.get())
        self.app_ref.app_settings.set("ai_key", self.key_var.get().strip())
        self.app_ref.app_settings.set("ai_model", self.model_var.get().strip())
        self.destroy()


class WidgetSettingsPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Widget Settings")
        self.geometry("350x200")
        self.attributes('-topmost', 'true')
        self.app_ref = master
        
        cfg_frame = ctk.CTkFrame(self)
        cfg_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(cfg_frame, text="Transparency:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        self.alpha_var = ctk.DoubleVar(value=self.app_ref.app_settings.get("widget_alpha", 0.98))
        self.alpha_slider = ctk.CTkSlider(cfg_frame, from_=0.1, to=1.0, variable=self.alpha_var, command=self.on_alpha_change)
        self.alpha_slider.grid(row=0, column=1, padx=5, pady=10, sticky="we")
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0,20))
        ctk.CTkButton(btn_frame, text="Save", command=self.save_settings, width=100).pack(side="right")

    def on_alpha_change(self, val):
        if hasattr(self.app_ref, 'rec_widget') and self.app_ref.rec_widget.winfo_exists():
            self.app_ref.rec_widget.attributes("-alpha", val)

    def save_settings(self):
        self.app_ref.app_settings.set("widget_alpha", self.alpha_var.get())
        self.destroy()
