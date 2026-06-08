import os
import sys
import json
import time
import queue
import threading
import serial
import serial.tools.list_ports
import customtkinter as ctk
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog
import urllib.request
import re

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ACTION_TYPES = [
    "text", "keycombo", "delay", "key", "hold", "release",
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

class TemplatesManager:
    def __init__(self, custom_file="macropad_templates.json", default_file="macropad_default_templates.json"):
        self.custom_file = custom_file
        self.default_file = default_file
        self.custom_templates = {}
        self.default_templates = {}
        self.load()

    def load(self):
        try:
            with open(self.default_file, 'r', encoding='utf-8') as f:
                self.default_templates = json.load(f)
        except:
            self.default_templates = {}
            
        try:
            with open(self.custom_file, 'r', encoding='utf-8') as f:
                self.custom_templates = json.load(f)
        except:
            self.custom_templates = {}

    def save(self):
        try:
            with open(self.custom_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_templates, f, indent=4)
        except Exception as e:
            print("Error saving templates:", e)

    def get_context_shortcuts(self, context):
        context_lower = context.lower()
        combined = []
        seen_desc = set()
        
        def add_from_dict(d, ctx):
            if ctx in d:
                for s in d[ctx]:
                    desc = s.get("description", "").lower()
                    if desc not in seen_desc:
                        combined.append(s)
                        seen_desc.add(desc)
                        
        add_from_dict(self.custom_templates, context_lower)
        add_from_dict(self.default_templates, context_lower)
        
        if not combined:
            for key in self.custom_templates:
                if key in context_lower or context_lower in key:
                    add_from_dict(self.custom_templates, key)
                    break
            for key in self.default_templates:
                if key in context_lower or context_lower in key:
                    add_from_dict(self.default_templates, key)
                    break
                    
        return combined

    def add_shortcuts(self, context, new_shortcuts):
        context_lower = context.lower()
        if context_lower not in self.custom_templates:
            self.custom_templates[context_lower] = []
        
        existing_desc = {s["description"].lower() for s in self.get_context_shortcuts(context_lower)}
        
        added = False
        for s in new_shortcuts:
            if s["description"].lower() not in existing_desc:
                self.custom_templates[context_lower].append(s)
                existing_desc.add(s["description"].lower())
                added = True
                
        if added:
            self.save()

class AIQueueManager:
    def __init__(self, app_ref):
        self.app_ref = app_ref
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.thread.start()

    def worker_loop(self):
        while True:
            task = self.queue.get()
            if task is None: break
            try:
                self.process_task(task)
            except Exception as e:
                self.app_ref.append_tracking_log(f"AI Queue Error: {e}\n")
            self.queue.task_done()

    def process_task(self, task):
        action = task.get("action")
        context = task.get("context")
        key_num = task.get("key_num", None)
        
        if action == "generate_and_validate":
            self.app_ref.append_tracking_log(f"AI: Generating for [{context}]...\n")
            raw_shortcuts = self.generate_shortcuts(context, key_num)
            if raw_shortcuts:
                self.app_ref.append_tracking_log(f"AI: Validating shortcuts for [{context}]...\n")
                validated = self.validate_shortcuts(context, raw_shortcuts)
                if validated:
                    self.app_ref.append_tracking_log(f"AI: Added new validated shortcuts for [{context}].\n")
                    self.app_ref.templates_mgr.add_shortcuts(context, validated)
                    if self.app_ref.current_context == context:
                        self.app_ref.after(0, self.app_ref.rec_widget.update_context, context, self.app_ref.templates_mgr.get_context_shortcuts(context), False)
                        
    def make_api_call(self, system_prompt, user_prompt):
        provider = self.app_ref.app_settings.get("ai_provider", "Ollama (Local)")
        key = self.app_ref.app_settings.get("ai_key", "http://localhost:11434").strip().rstrip('/')
        model = self.app_ref.app_settings.get("ai_model", "llama3:70b").strip()
        
        debug = hasattr(self.app_ref, 'ai_debug_enabled') and self.app_ref.ai_debug_enabled.get()
        if debug:
            self.app_ref.append_tracking_log(f"\n[AI DEBUG] Provider: {provider} | Model: {model}\n")
            self.app_ref.append_tracking_log(f"[AI DEBUG] Sys Prompt: {system_prompt[:50]}...\n")
            self.app_ref.append_tracking_log(f"[AI DEBUG] Usr Prompt: {user_prompt}\n")
            
        result_text = ""
        try:
            if provider == "Ollama (Local)":
                model_name = model if model else "llama3"
                url = f"{key}/api/generate"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
                payload = {"model": model_name, "prompt": f"{system_prompt}\nUser Prompt: {user_prompt}", "stream": False}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.app_ref.append_tracking_log(f"[AI DEBUG] URL: {url}\n")
                    self.app_ref.append_tracking_log(f"[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.app_ref.append_tracking_log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res.get("response", "")
                    
            elif provider == "Gemini":
                model_name = model if model else "gemini-1.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
                payload = {"contents": [{"parts": [{"text": f"{system_prompt}\nUser Prompt: {user_prompt}"}]}]}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.app_ref.append_tracking_log(f"[AI DEBUG] URL: {url[:60]}...[HIDDEN_KEY]\n")
                    self.app_ref.append_tracking_log(f"[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.app_ref.append_tracking_log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res["candidates"][0]["content"]["parts"][0]["text"]
                    
            elif provider == "OpenAI":
                model_name = model if model else "gpt-4o-mini"
                url = "https://api.openai.com/v1/chat/completions"
                req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
                payload = {"model": model_name, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                data = json.dumps(payload).encode("utf-8")
                
                if debug:
                    self.app_ref.append_tracking_log(f"[AI DEBUG] URL: {url}\n")
                    self.app_ref.append_tracking_log(f"[AI DEBUG] Payload: {json.dumps(payload)}\n")
                    
                with urllib.request.urlopen(req, data=data, timeout=120) as response:
                    raw_res = response.read().decode()
                    if debug: self.app_ref.append_tracking_log(f"[AI DEBUG] Raw Response: {raw_res[:200]}...\n")
                    res = json.loads(raw_res)
                    result_text = res["choices"][0]["message"]["content"]
                    
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8', errors='replace')
            if debug: self.app_ref.append_tracking_log(f"\n[AI ERROR] HTTP {e.code}: {err_msg}\n")
            raise Exception(f"HTTP {e.code}: {err_msg}")
        except Exception as e:
            if debug: self.app_ref.append_tracking_log(f"\n[AI ERROR] Exception: {str(e)}\n")
            raise e
                
        result_text = result_text.strip()
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
        return result_text

    def generate_shortcuts(self, context, key_num=None):
        valid_keys = "LEFT_CTRL, RIGHT_CTRL, LEFT_SHIFT, RIGHT_SHIFT, LEFT_ALT, ENTER, ESC, TAB, SPACE, F1-F12, A-Z, 0-9, UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW, MINUS, EQUAL, TILDE"
        system_prompt = f"""You are an advanced Macro Shortcut Generator for a developer. 
CRITICAL: Respond ONLY with a raw JSON array. DO NOT wrap the output in markdown code blocks (e.g. no ```json).
Valid keys for keycombo: {valid_keys}.
JSON Schema:
[
  {{"key_num": 1, "description": "Save File", "actions": [{{"type":"keycombo","keys":["LEFT_CTRL","S"]}}]}},
  {{"key_num": 2, "description": "Git Status", "actions": [{{"type":"text","value":"git status"}}, {{"type":"key","value":"ENTER"}}]}}
]"""

        user_prompt = f"Context: {context}.\nGenerate 4 new, unique, robust and highly productive keyboard shortcuts for this context."
        
        custom_existing = self.app_ref.templates_mgr.custom_templates.get(context.lower(), [])
        if custom_existing:
            existing_desc = [s.get("description", "") for s in custom_existing][-10:]
            user_prompt += f"\n\nPersonalization Context - You already have these shortcuts: {', '.join(existing_desc)}.\nDO NOT duplicate these. Adapt your suggestions based on this workflow style."

        if key_num:
            user_prompt += f"\nSpecifically assign the generated shortcuts to key_num: {key_num}."
            
        try:
            res = self.make_api_call(system_prompt, user_prompt)
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            parsed = json.loads(res.strip())
            return parsed if isinstance(parsed, list) else None
        except Exception as e:
            self.app_ref.append_tracking_log(f"Generation error: {e}\n")
            return None

    def validate_shortcuts(self, context, shortcuts):
        valid_keys = "LEFT_CTRL, RIGHT_CTRL, LEFT_SHIFT, RIGHT_SHIFT, LEFT_ALT, ENTER, ESC, TAB, SPACE, F1-F12, A-Z, 0-9, UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW, MINUS, EQUAL, TILDE"
        system_prompt = f"""You are a Validator. Ensure the JSON array is perfectly valid for Macropad actions. 
CRITICAL: Respond ONLY with a raw JSON array. DO NOT use markdown formatting.
Fix impossible key combinations. Ensure 'keys' or 'value' only use: {valid_keys}."""
        user_prompt = f"Context: {context}\nValidate and fix this JSON:\n{json.dumps(shortcuts)}"
        
        try:
            res = self.make_api_call(system_prompt, user_prompt)
            if res.startswith("```json"): res = res[7:]
            if res.startswith("```"): res = res[3:]
            if res.endswith("```"): res = res[:-3]
            parsed = json.loads(res.strip())
            return parsed if isinstance(parsed, list) else shortcuts
        except Exception as e:
            self.app_ref.append_tracking_log(f"Validation error: {e}\n")
            return shortcuts

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

class AISettingsPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("AI Settings")
        self.geometry("450x250")
        self.attributes('-topmost', 'true')
        self.app_ref = master if hasattr(master, 'app_settings') else master.app_ref
        
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
        self.app_ref.app_settings["ai_provider"] = self.provider_var.get()
        self.app_ref.app_settings["ai_key"] = self.key_var.get().strip()
        self.app_ref.app_settings["ai_model"] = self.model_var.get().strip()
        self.app_ref.save_app_settings()
        self.destroy()

class WidgetSettingsPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Widget Settings")
        self.geometry("350x200")
        self.attributes('-topmost', 'true')
        self.app_ref = master if hasattr(master, 'app_settings') else master.app_ref
        
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
        self.app_ref.app_settings["widget_alpha"] = self.alpha_var.get()
        self.app_ref.save_app_settings()
        self.destroy()


class RecommendationWidget(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Macropad AI")
        self.geometry("360x300+20+20") 
        self.attributes('-topmost', 'true')
        self.overrideredirect(True) 
        self.app_ref = master
        self.attributes("-alpha", self.app_ref.app_settings.get("widget_alpha", 0.98)) 
        
        self.current_context = ""
        self.options_map = {1: [], 2: [], 3: [], 4: []}
        self.index_map = {1: 0, 2: 0, 3: 0, 4: 0}
        
        bg_color = "#252526"
        border_color = "#3c3c3c"
        header_bg = "#333333"
        text_color = "#cccccc"
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, border_width=1, border_color=border_color, fg_color=bg_color)
        self.main_frame.pack(fill="both", expand=True)
        
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color=header_bg, corner_radius=0, height=28)
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False) 
        
        self.header = ctk.CTkLabel(self.top_bar, text=" AI Context", font=ctk.CTkFont(family="Consolas", size=12), text_color=text_color)
        self.header.pack(side="left", padx=8)
        
        close_btn = ctk.CTkButton(self.top_bar, text="✕", width=28, height=28, corner_radius=0, fg_color="transparent", text_color="#aaaaaa", hover_color="#e81123", command=self.withdraw)
        close_btn.pack(side="right")
        
        settings_btn = ctk.CTkButton(self.top_bar, text="⚙", width=28, height=28, corner_radius=0, fg_color="transparent", text_color="#aaaaaa", hover_color="#555555", command=lambda: WidgetSettingsPopup(self.app_ref))
        settings_btn.pack(side="right")
        
        self.status = ctk.CTkLabel(self.main_frame, text="", text_color="#888888", font=ctk.CTkFont(family="Consolas", size=11, slant="italic"))
        
        self.list_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=2, pady=4)
        
        self.top_bar.bind("<ButtonPress-1>", self.start_move)
        self.top_bar.bind("<B1-Motion>", self.do_move)
        self.header.bind("<ButtonPress-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        
        self.grip = ctk.CTkLabel(self.main_frame, text="", width=15, height=15, fg_color="transparent", cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<ButtonPress-1>", self.start_resize)
        self.grip.bind("<B1-Motion>", self.do_resize)

    def start_move(self, event):
        self._move_start_x = event.x
        self._move_start_y = event.y

    def do_move(self, event):
        deltax = event.x - self._move_start_x
        deltay = event.y - self._move_start_y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._start_width = self.winfo_width()
        self._start_height = self.winfo_height()

    def do_resize(self, event):
        deltax = event.x_root - self._resize_start_x
        deltay = event.y_root - self._resize_start_y
        new_w = max(260, self._start_width + deltax)
        new_h = max(200, self._start_height + deltay)
        self.geometry(f"{new_w}x{new_h}+{self.winfo_x()}+{self.winfo_y()}")

    def update_context(self, context_name, shortcuts=None, is_generating=False):
        self.current_context = context_name
        self.header.configure(text=f" {context_name[:25]}")
        
        for w in self.list_frame.winfo_children(): w.destroy()
            
        if is_generating and not shortcuts:
            self.status.configure(text="Generating AI shortcuts...", text_color="#007acc")
            self.status.pack(pady=40)
            return
            
        self.status.pack_forget()
        
        self.options_map = {1: [], 2: [], 3: [], 4: []}
        if shortcuts:
            for s in shortcuts:
                knum = s.get("key_num", 0)
                if 1 <= knum <= 4:
                    self.options_map[knum].append(s)
                    
        for i in range(1, 5):
            self.render_key_row(i)

    def render_key_row(self, knum):
        opts = self.options_map[knum]
        idx = self.index_map.setdefault(knum, 0)
        
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent", corner_radius=0, height=52)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        
        ctk.CTkFrame(row, width=3, fg_color="#007acc", corner_radius=0).pack(side="left", fill="y")
        
        chip = ctk.CTkLabel(row, text=f"K{knum}", fg_color="#37373d", corner_radius=2, width=24, font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#d4d4d4")
        chip.pack(side="left", padx=(6, 8), pady=10)
        
        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)
        
        if len(opts) == 0:
            desc = ctk.CTkLabel(text_col, text="No shortcut assigned", anchor="w", font=ctk.CTkFont(size=12, slant="italic"), text_color="#888888")
            desc.pack(side="top", anchor="w", pady=(15, 0))
        else:
            if idx >= len(opts): idx = 0
            self.index_map[knum] = idx
            s = opts[idx]
            
            desc_text = s.get('description', '')[:28]
            if len(opts) > 1:
                desc_text += f" ({idx+1}/{len(opts)})"
                
            desc = ctk.CTkLabel(text_col, text=desc_text, anchor="w", font=ctk.CTkFont(size=12, weight="bold"), text_color="#cccccc")
            desc.pack(side="top", anchor="w", pady=(5, 0))
            
            act_strs = []
            for act in s.get("actions", []):
                t = act.get("type", "")
                if t == "keycombo": act_strs.append("+".join(act.get("keys", [])))
                elif t == "text": act_strs.append(f"'{act.get('value', '')}'")
                elif t in ["key", "hold", "release"]: act_strs.append(str(act.get("value", act.get("key", ""))))
                elif t == "delay": act_strs.append(f"{act.get('ms', 0)}ms")
                elif t == "media": act_strs.append(str(act.get("value", "")))
                else: act_strs.append(t)
            
            macro_txt = " → ".join(act_strs) if act_strs else "Empty Array"
            if len(macro_txt) > 30: macro_txt = macro_txt[:27] + "..."
            
            details = ctk.CTkLabel(text_col, text=macro_txt, anchor="w", font=ctk.CTkFont(family="Consolas", size=10), text_color="#858585")
            details.pack(side="top", anchor="w", pady=(0, 4))
            
            self.app_ref.push_shortcut_to_device(s)

        controls = ctk.CTkFrame(row, fg_color="transparent")
        controls.pack(side="right", fill="y", padx=2)
        
        regen_btn = ctk.CTkButton(controls, text="⟳", width=22, height=22, corner_radius=2, fg_color="transparent", hover_color="#37373d", text_color="#aaaaaa")
        regen_btn.configure(command=lambda k=knum: self.request_regen(k))
        regen_btn.pack(side="left", padx=1, pady=15)
        
        arrows_frame = ctk.CTkFrame(controls, fg_color="transparent")
        arrows_frame.pack(side="left", padx=1)
        
        up_btn = ctk.CTkButton(arrows_frame, text="▲", width=22, height=18, corner_radius=0, fg_color="transparent", hover_color="#37373d", font=ctk.CTkFont(size=10), text_color="#888888")
        up_btn.configure(command=lambda k=knum: self.cycle_option(k, -1))
        up_btn.pack(side="top", pady=(5,0))
        
        dn_btn = ctk.CTkButton(arrows_frame, text="▼", width=22, height=18, corner_radius=0, fg_color="transparent", hover_color="#37373d", font=ctk.CTkFont(size=10), text_color="#888888")
        dn_btn.configure(command=lambda k=knum: self.cycle_option(k, 1))
        dn_btn.pack(side="bottom", pady=(0,5))

    def cycle_option(self, knum, direction):
        if len(self.options_map[knum]) <= 1: return
        self.index_map[knum] = (self.index_map[knum] + direction) % len(self.options_map[knum])
        self.update_context(self.current_context, self.app_ref.templates_mgr.get_context_shortcuts(self.current_context), False)

    def request_regen(self, knum):
        self.app_ref.ai_queue.queue.put({
            "action": "generate_and_validate",
            "context": self.current_context,
            "key_num": knum
        })
        self.app_ref.append_tracking_log(f"Queued regeneration for key {knum} in {self.current_context}\n")

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
        self.value_entry.bind("<KeyRelease>", self.value_changed)
        
        self.value_combo = ctk.CTkComboBox(self.value_frame, variable=self.value_var, command=self.value_changed)
        
        self.record_btn = ctk.CTkButton(self.value_frame, text="Record", width=60, fg_color="orange", hover_color="darkorange", command=self.open_record_popup)
        
        self.del_btn = ctk.CTkButton(self, text="X", width=30, fg_color="red", hover_color="darkred", command=self.delete_me)
        self.del_btn.grid(row=0, column=3, padx=5, pady=5)
        
        self.populate_value_from_dict()
        self.update_ui_for_type()

    def update_ui_for_type(self):
        t = self.type_var.get()
        self.record_btn.grid_forget()
        self.value_entry.grid_forget()
        self.value_combo.grid_forget()
        
        if t == "keycombo":
            self.value_entry.grid(row=0, column=0, sticky="ew")
            self.record_btn.grid(row=0, column=1, padx=(5,0))
            self.value_entry.configure(state="readonly")
        elif t == "media":
            self.value_combo.configure(values=["PLAY_PAUSE", "STOP", "NEXT", "PREVIOUS", "MUTE", "VOLUME_UP", "VOLUME_DOWN"], state="readonly")
            self.value_combo.grid(row=0, column=0, sticky="ew")
        elif t == "mouse_click":
            self.value_combo.configure(values=["LEFT", "RIGHT", "MIDDLE"], state="readonly")
            self.value_combo.grid(row=0, column=0, sticky="ew")
        elif t == "profile":
            self.value_combo.configure(values=["1", "2", "3"], state="readonly")
            self.value_combo.grid(row=0, column=0, sticky="ew")
        elif t == "telephony":
            self.value_combo.configure(values=["MIC_MUTE", "ANSWER", "DECLINE"], state="readonly")
            self.value_combo.grid(row=0, column=0, sticky="ew")
        elif t == "led_anim":
            self.value_combo.configure(values=["flash", "breathe", "none"], state="readonly")
            self.value_combo.grid(row=0, column=0, sticky="ew")
        elif t in ["key", "hold", "release"]:
            common_keys = [
                "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", 
                "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
                "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
                "ENTER", "ESC", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUAL",
                "LEFT_CTRL", "LEFT_SHIFT", "LEFT_ALT", "LEFT_GUI",
                "RIGHT_CTRL", "RIGHT_SHIFT", "RIGHT_ALT", "RIGHT_GUI",
                "UP_ARROW", "DOWN_ARROW", "LEFT_ARROW", "RIGHT_ARROW",
                "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"
            ]
            self.value_combo.configure(values=common_keys, state="normal")
            self.value_combo.grid(row=0, column=0, sticky="ew")
            if t == "release":
                self.value_combo.configure(state="disabled")
        else:
            self.value_entry.grid(row=0, column=0, sticky="ew")
            self.value_entry.configure(state="normal")

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


class MacropadV4App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Macropad Configurator V4")
        self.geometry("1200x800")

        self.serial_port = None
        self.serial_thread = None
        self.stop_event = threading.Event()
        self.capturing_file = False
        self.file_buffer = []
        
        self.selected_key_id = 1
        self.action_rows = []

        self.profile_data = self.create_empty_profile()
        self.auto_switch_enabled = ctk.BooleanVar(value=True)
        self.app_settings = {"ai_provider": "Ollama (Local)", "ai_key": "http://localhost:11434", "ai_model": "llama3:70b", "widget_alpha": 0.98}
        self.load_app_settings()
        
        self.templates_mgr = TemplatesManager()
        self.ai_queue = AIQueueManager(self)
        self.current_context = None

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_editor = self.tabview.add("Key Editor")
        self.tab_autoswitch = self.tabview.add("Auto-Switcher")
        self.tab_settings = self.tabview.add("Settings")

        self.setup_dashboard()
        self.setup_editor()
        self.setup_autoswitch()
        self.setup_settings()

        self.rec_widget = RecommendationWidget(self)
        self.rec_widget.withdraw()

        self.auto_switch_thread = threading.Thread(target=self.auto_switch_loop, daemon=True)
        self.auto_switch_thread.start()

    def load_app_settings(self):
        try:
            if os.path.exists("macropad_settings.json"):
                with open("macropad_settings.json", "r") as f:
                    self.app_settings.update(json.load(f))
        except: pass

    def save_app_settings(self):
        try:
            with open("macropad_settings.json", "w") as f:
                json.dump(self.app_settings, f, indent=2)
        except: pass

    def create_empty_profile(self):
        return {
            "profile_name": "New Profile",
            "idle_animation": "none",
            "default_delay": 30,
            "keys": [{"id": i, "actions": []} for i in range(1, 13)]
        }

    def setup_dashboard(self):
        self.tab_dashboard.grid_columnconfigure(1, weight=1)
        self.tab_dashboard.grid_rowconfigure(0, weight=1)

        left_side = ctk.CTkFrame(self.tab_dashboard, width=300)
        left_side.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        log_frame = ctk.CTkFrame(self.tab_dashboard)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        conn_box = ctk.CTkFrame(left_side)
        conn_box.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(conn_box, text="Device Connection", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.port_var = ctk.StringVar(value="Select Port")
        self.port_dropdown = ctk.CTkComboBox(conn_box, variable=self.port_var, values=self.get_ports())
        self.port_dropdown.pack(padx=10, pady=5)
        
        ctk.CTkButton(conn_box, text="Refresh Ports", command=self.refresh_ports).pack(padx=10, pady=5)
        self.connect_btn = ctk.CTkButton(conn_box, text="Connect", command=self.toggle_connection, fg_color="green", hover_color="darkgreen")
        self.connect_btn.pack(padx=10, pady=10)
        
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

        self.storage_lbl = ctk.CTkLabel(file_box, text="Storage: Unknown", font=ctk.CTkFont(size=11))
        self.storage_lbl.pack(padx=10, pady=(10, 0))
        self.storage_bar = ctk.CTkProgressBar(file_box, height=10)
        self.storage_bar.pack(padx=10, pady=(0, 10), fill="x")
        self.storage_bar.set(0)

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

        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        self.console = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=12), text_color="lightgreen", state="disabled")
        self.console.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def setup_editor(self):
        self.tab_editor.grid_columnconfigure(1, weight=1)
        self.tab_editor.grid_rowconfigure(0, weight=1)

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

        self.action_area = ctk.CTkFrame(self.tab_editor)
        self.action_area.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.action_area.grid_columnconfigure(0, weight=1)
        self.action_area.grid_rowconfigure(1, weight=1)
        
        header = ctk.CTkFrame(self.action_area, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(0, weight=1)
        
        self.action_title = ctk.CTkLabel(header, text="Actions for Key 1", font=ctk.CTkFont(size=18, weight="bold"))
        self.action_title.grid(row=0, column=0, sticky="w")
        
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")
        
        ctk.CTkButton(btn_frame, text="+ Add", width=80, command=self.add_action).pack(side="left")
        
        self.action_scroll = ctk.CTkScrollableFrame(self.action_area)
        self.action_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.select_key(1)

    def setup_autoswitch(self):
        self.tab_autoswitch.grid_columnconfigure(0, weight=1)
        self.tab_autoswitch.grid_rowconfigure(2, weight=1)
        
        ctk.CTkLabel(self.tab_autoswitch, text="Auto Switcher Tracking", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=10)
        
        controls_frame = ctk.CTkFrame(self.tab_autoswitch, fg_color="transparent")
        controls_frame.grid(row=1, column=0, pady=5)
        
        ctk.CTkCheckBox(controls_frame, text="Enable Background Auto-Switching", variable=self.auto_switch_enabled).pack(side="left", padx=10)
        self.ai_debug_enabled = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(controls_frame, text="Debug AI Payload", variable=self.ai_debug_enabled).pack(side="left", padx=10)
        
        self.tracking_console = ctk.CTkTextbox(self.tab_autoswitch, font=ctk.CTkFont(family="Consolas", size=12), text_color="cyan", state="disabled")
        self.tracking_console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

    def setup_settings(self):
        self.tab_settings.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.tab_settings, text="Application Settings", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=2, pady=10)
        ctk.CTkButton(self.tab_settings, text="AI Configuration", command=lambda: AISettingsPopup(self)).grid(row=1, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkButton(self.tab_settings, text="Widget Appearance", command=lambda: WidgetSettingsPopup(self)).grid(row=2, column=0, padx=20, pady=10, sticky="w")

    def append_tracking_log(self, text):
        self.tracking_console.configure(state="normal")
        self.tracking_console.insert("end", text)
        self.tracking_console.see("end")
        self.tracking_console.configure(state="disabled")

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
        pass

    def sync_ui_to_data(self):
        self.prof_name_var.set(self.profile_data.get("profile_name", "Unknown"))
        self.idle_anim_var.set(self.profile_data.get("idle_animation", "none"))
        self.def_delay_var.set(str(self.profile_data.get("default_delay", 30)))
        
        existing_ids = [k.get("id") for k in self.profile_data.setdefault("keys", [])]
        for i in range(1, 13):
            if i not in existing_ids:
                self.profile_data["keys"].append({"id": i, "actions": []})
        self.refresh_action_editor()

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

    def detect_context(self, title):
        title_lower = title.lower()
        if "visual studio code" in title_lower or "vscode" in title_lower:
            if "terminal" in title_lower or "bash" in title_lower or "powershell" in title_lower or "cmd" in title_lower:
                return "vscode_terminal"
            return "vscode"
        if "excel" in title_lower: return "excel"
        if "sheets" in title_lower or "google sheets" in title_lower: return "google_sheets"
        if "powershell" in title_lower: return "powershell"
        if "ubuntu" in title_lower or "wsl" in title_lower or "debian" in title_lower: return "wsl"
        if "chrome" in title_lower: return "chrome"
        if "notepad" in title_lower: return "notepad"
        if "slack" in title_lower: return "slack"
        
        parts = title.split("-")
        return parts[-1].strip() if len(parts) > 1 else title.strip()

    def auto_switch_loop(self):
        last_context = ""
        while not self.stop_event.is_set():
            try:
                is_enabled = False
                try: is_enabled = self.auto_switch_enabled.get()
                except: pass
                
                if is_enabled:
                    import pygetwindow as gw
                    win = gw.getActiveWindow()
                    if win and win.title:
                        title = win.title.replace('\u200b', '').strip()
                        context = self.detect_context(title)
                        
                        if context and context != last_context and "Macropad" not in context:
                            last_context = context
                            self.current_context = context
                            self.after(0, self.append_tracking_log, f"Context Changed -> [{context}]\n")
                            self.after(0, lambda c=context: self.handle_context_change(c))
            except Exception as e:
                pass
            import time
            time.sleep(1.0)
            
    def handle_context_change(self, context):
        def reset_to_default():
            try:
                if self.serial_port and self.serial_port.is_open:
                    p_num = self.profile_var.get().replace("profile", "").replace(".json", "")
                    if p_num.isdigit():
                        self.send_cmd(f"setprofile {p_num}")
            except: pass

        if not context or context.lower() in ["program manager", "windows explorer", "task switching"]:
            try: self.rec_widget.withdraw()
            except: pass
            reset_to_default()
            return

        shortcuts = self.templates_mgr.get_context_shortcuts(context)
        
        try:
            if self.rec_widget.winfo_exists() and self.auto_switch_enabled.get():
                self.rec_widget.deiconify()
        except: pass
            
        if shortcuts and len(shortcuts) > 0:
            try: self.rec_widget.update_context(context, shortcuts, False)
            except: pass
            self.ai_queue.queue.put({
                "action": "generate_and_validate",
                "context": context
            })
        else:
            try: self.rec_widget.update_context(context, None, True)
            except: pass
            reset_to_default()
            self.ai_queue.queue.put({
                "action": "generate_and_validate",
                "context": context
            })

    def push_shortcut_to_device(self, shortcut):
        if not self.serial_port or not self.serial_port.is_open: return
        knum = shortcut.get("key_num")
        acts = shortcut.get("actions", [])
        if knum and 1 <= knum <= 4:
            self.send_cmd(f"setkey {knum} {json.dumps(acts)}")

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
                self.after(500, lambda: self.send_cmd("fsinfo"))

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
        
        if clean_line.startswith("FS_INFO:"):
            try:
                parts = clean_line.split(":")[1].split(",")
                total = int(parts[0])
                used = int(parts[1])
                free = total - used
                self.storage_lbl.configure(text=f"Storage: {used/1024:.1f} KB used / {free/1024:.1f} KB free")
                if total > 0: self.storage_bar.set(used / total)
            except: pass
            return

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
            self.after(1000, lambda: self.send_cmd("fsinfo"))

        threading.Thread(target=save_thread, daemon=True).start()

    def set_active_profile(self):
        target = self.profile_var.get()
        match = re.search(r'profile(\d+)', target)
        if match:
            num = match.group(1)
            self.send_cmd(f"setprofile {num}")
            self.append_console(f"Setting active profile to {num}\n")
        else:
            self.append_console("Could not determine profile number.\n")

if __name__ == "__main__":
    app = MacropadV4App()
    app.mainloop()
