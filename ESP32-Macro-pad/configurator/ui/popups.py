"""Small modal popups: keycombo recorder, multiline/JSON editors, settings."""

from __future__ import annotations

import json

import customtkinter as ctk

from ..config import TK_TO_ESP32_MAP
from .. import schema


def _map_keysym(keysym):
    if keysym in TK_TO_ESP32_MAP:
        return TK_TO_ESP32_MAP[keysym]
    if len(keysym) == 1:
        return keysym.upper()
    if keysym.startswith("F") and keysym[1:].isdigit():
        return keysym
    return keysym.upper()


class RecordKeycomboPopup(ctk.CTkToplevel):
    """Capture a chord of keys and return them as a comma-joined string."""

    def __init__(self, master, current_value, on_save):
        super().__init__(master)
        self.title("Record Keycombo")
        self.geometry("460x210")
        self.attributes("-topmost", True)
        self.on_save = on_save
        self._seen = set()
        self._ordered = []

        ctk.CTkLabel(self, text="Press the keys for this combo...",
                     font=ctk.CTkFont(size=15)).pack(pady=18)
        self.result_var = ctk.StringVar(value=current_value)
        ctk.CTkLabel(self, textvariable=self.result_var,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=8)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=12)
        ctk.CTkButton(btns, text="Clear", width=90, fg_color="gray",
                      command=self._clear).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Save", width=140, fg_color="green",
                      hover_color="darkgreen",
                      command=self._save).pack(side="left", padx=6)

        self.bind("<KeyPress>", self._on_key)
        self.focus_force()

    def _on_key(self, event):
        key = _map_keysym(event.keysym)
        if key not in self._seen:
            self._seen.add(key)
            self._ordered.append(key)
            self.result_var.set(", ".join(self._ordered))

    def _clear(self):
        self._seen.clear()
        self._ordered.clear()
        self.result_var.set("")

    def _save(self):
        self.on_save(self.result_var.get())
        self.destroy()


class TextEditPopup(ctk.CTkToplevel):
    """Multiline text editor used for `text` / `multiline` action values."""

    def __init__(self, master, current_value, on_save):
        super().__init__(master)
        self.title("Edit Text")
        self.geometry("520x360")
        self.attributes("-topmost", True)
        self.on_save = on_save

        self.box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=13))
        self.box.pack(fill="both", expand=True, padx=12, pady=12)
        self.box.insert("1.0", current_value)
        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=(0, 12))

    def _save(self):
        self.on_save(self.box.get("1.0", "end-1c"))
        self.destroy()


class JsonEditPopup(ctk.CTkToplevel):
    """Raw JSON editor for nested action lists (used by the `repeat` action)."""

    def __init__(self, master, current_actions, on_save):
        super().__init__(master)
        self.title("Edit Nested Actions (JSON)")
        self.geometry("560x420")
        self.attributes("-topmost", True)
        self.on_save = on_save

        ctk.CTkLabel(self, text="JSON array of actions to repeat:").pack(
            anchor="w", padx=12, pady=(10, 0))
        self.box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.box.pack(fill="both", expand=True, padx=12, pady=8)
        self.box.insert("1.0", json.dumps(current_actions or [], indent=2))
        self.status = ctk.CTkLabel(self, text="", text_color="orange")
        self.status.pack(anchor="w", padx=12)
        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=(0, 12))

    def _save(self):
        try:
            parsed = json.loads(self.box.get("1.0", "end-1c"))
        except json.JSONDecodeError as e:
            self.status.configure(text=f"Invalid JSON: {e}")
            return
        actions = schema.repair_actions(parsed if isinstance(parsed, list) else [])
        if not actions:
            self.status.configure(text="No valid actions after repair.")
            return
        self.on_save(actions)
        self.destroy()


class AISettingsPopup(ctk.CTkToplevel):
    """Configure the AI provider/endpoint/model."""

    PROVIDERS = ["Ollama (Local)", "Gemini", "OpenAI"]

    def __init__(self, master, settings, on_save=None):
        super().__init__(master)
        self.title("AI Settings")
        self.geometry("470x300")
        self.attributes("-topmost", True)
        self.settings = settings
        self.on_save = on_save

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Provider:").grid(row=0, column=0, padx=5, pady=8, sticky="e")
        self.provider_var = ctk.StringVar(value=settings.get("ai_provider"))
        ctk.CTkComboBox(frame, values=self.PROVIDERS, variable=self.provider_var,
                        command=self._on_provider).grid(row=0, column=1, padx=5, pady=8, sticky="we")

        self.endpoint_lbl = ctk.CTkLabel(frame, text="Endpoint:")
        self.endpoint_lbl.grid(row=1, column=0, padx=5, pady=8, sticky="e")
        self.endpoint_var = ctk.StringVar(value=settings.get("ai_endpoint"))
        self.endpoint_entry = ctk.CTkEntry(frame, textvariable=self.endpoint_var)
        self.endpoint_entry.grid(row=1, column=1, padx=5, pady=8, sticky="we")

        self.key_lbl = ctk.CTkLabel(frame, text="API Key:")
        self.key_lbl.grid(row=2, column=0, padx=5, pady=8, sticky="e")
        self.key_var = ctk.StringVar(value=settings.get("ai_key"))
        self.key_entry = ctk.CTkEntry(frame, textvariable=self.key_var, show="*")
        self.key_entry.grid(row=2, column=1, padx=5, pady=8, sticky="we")

        ctk.CTkLabel(frame, text="Model:").grid(row=3, column=0, padx=5, pady=8, sticky="e")
        self.model_var = ctk.StringVar(value=settings.get("ai_model"))
        ctk.CTkEntry(frame, textvariable=self.model_var).grid(
            row=3, column=1, padx=5, pady=8, sticky="we")

        ctk.CTkButton(self, text="Save", command=self._save, width=120).pack(
            pady=(0, 18))
        self._on_provider(self.provider_var.get())

    def _on_provider(self, provider):
        # Ollama uses a local endpoint and no key; cloud providers use a key.
        is_ollama = "Ollama" in provider
        if is_ollama:
            self.endpoint_lbl.grid()
            self.endpoint_entry.grid()
            self.key_lbl.grid_remove()
            self.key_entry.grid_remove()
        else:
            self.endpoint_lbl.grid_remove()
            self.endpoint_entry.grid_remove()
            self.key_lbl.grid()
            self.key_entry.grid()

    def _save(self):
        self.settings.set("ai_provider", self.provider_var.get())
        self.settings.set("ai_endpoint", self.endpoint_var.get().strip())
        self.settings.set("ai_key", self.key_var.get().strip())
        self.settings.set("ai_model", self.model_var.get().strip())
        if self.on_save:
            self.on_save()
        self.destroy()


class WidgetSettingsPopup(ctk.CTkToplevel):
    """Adjust the floating recommendation widget transparency."""

    def __init__(self, master, settings, widget=None):
        super().__init__(master)
        self.title("Widget Settings")
        self.geometry("360x180")
        self.attributes("-topmost", True)
        self.settings = settings
        self.widget = widget

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text="Transparency").pack(pady=(10, 4))
        self.alpha_var = ctk.DoubleVar(value=settings.get("widget_alpha", 0.98))
        ctk.CTkSlider(frame, from_=0.3, to=1.0, variable=self.alpha_var,
                      command=self._on_alpha).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(self, text="Save", command=self._save, width=120).pack(
            pady=(0, 16))

    def _on_alpha(self, val):
        if self.widget is not None and self.widget.winfo_exists():
            self.widget.attributes("-alpha", float(val))

    def _save(self):
        self.settings.set("widget_alpha", float(self.alpha_var.get()))
        self.destroy()
