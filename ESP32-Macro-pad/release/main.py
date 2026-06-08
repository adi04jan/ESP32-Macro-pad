import customtkinter as ctk
from tkinter import filedialog, messagebox
import json

from config import AppSettings
from templates import TemplatesManager
from serial_worker import SerialWorker
from ai_worker import AIQueueManager
from window_tracker import WindowTracker

from ui_widget import RecommendationWidget
from ui_components import ActionEditorRow, AISettingsPopup, WidgetSettingsPopup

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MacropadV4App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Macropad Manager V4 - Production Release")
        self.geometry("900x750")
        
        self.app_settings = AppSettings()
        self.templates_mgr = TemplatesManager()
        self.serial_worker = SerialWorker(self.append_tracking_log)
        
        self.profile_data = {
            "profile_name": "Profile 1",
            "idle_animation": "none",
            "default_delay": 30,
            "keys": [{"id": i, "actions": []} for i in range(1, 13)]
        }
        self.selected_key_id = 1
        self.current_context = ""
        self.auto_switch_enabled = ctk.BooleanVar(value=self.app_settings.get("auto_switch_enabled", False))
        self.ai_debug_enabled = ctk.BooleanVar(value=self.app_settings.get("ai_debug_enabled", False))
        
        self.build_ui()
        
        self.rec_widget = RecommendationWidget(self, lambda: WidgetSettingsPopup(self))
        self.rec_widget.withdraw()
        
        self.ai_worker = AIQueueManager(
            self.app_settings, 
            self.templates_mgr, 
            self.append_tracking_log,
            self.on_ai_success
        )
        
        self.window_tracker = WindowTracker(
            self.app_settings, 
            self.append_tracking_log, 
            self.handle_context_change_async
        )
        self.window_tracker.start()
        
        self.refresh_ports()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def build_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_device = self.tabview.add("Device Setup")
        self.tab_profile = self.tabview.add("Profile Editor")
        self.tab_autoswitch = self.tabview.add("Auto Switcher")
        
        self.setup_device_tab()
        self.setup_profile_tab()
        self.setup_autoswitch()
        
    def setup_device_tab(self):
        self.tab_device.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.tab_device, text="Serial Port:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.port_var = ctk.StringVar()
        self.port_combo = ctk.CTkComboBox(self.tab_device, variable=self.port_var, values=[])
        self.port_combo.grid(row=0, column=1, padx=10, pady=10, sticky="we")
        
        ctk.CTkButton(self.tab_device, text="Refresh", command=self.refresh_ports, width=80).grid(row=0, column=2, padx=10, pady=10)
        ctk.CTkButton(self.tab_device, text="Connect", command=self.connect_serial, width=80).grid(row=0, column=3, padx=10, pady=10)
        
        ctk.CTkLabel(self.tab_device, text="Profile:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.profile_var = ctk.StringVar(value="profile1.json")
        self.profile_combo = ctk.CTkComboBox(self.tab_device, variable=self.profile_var, values=[f"profile{i}.json" for i in range(1,6)])
        self.profile_combo.grid(row=1, column=1, padx=10, pady=10, sticky="we")
        
        self.btn_load_hw = ctk.CTkButton(self.tab_device, text="Load from Device", command=self.load_from_device)
        self.btn_load_hw.grid(row=1, column=2, padx=10, pady=10, sticky="we")
        self.btn_save_hw = ctk.CTkButton(self.tab_device, text="Save to Device", command=self.save_to_device)
        self.btn_save_hw.grid(row=1, column=3, padx=10, pady=10, sticky="we")
        
        self.console = ctk.CTkTextbox(self.tab_device, font=ctk.CTkFont(family="Consolas", size=12), text_color="lightgreen", state="disabled")
        self.console.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=10, pady=10)
        self.tab_device.grid_rowconfigure(2, weight=1)

    def setup_profile_tab(self):
        self.tab_profile.grid_columnconfigure(0, weight=1)
        self.tab_profile.grid_rowconfigure(1, weight=1)
        
        top_frame = ctk.CTkFrame(self.tab_profile)
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(top_frame, text="Profile Name:").grid(row=0, column=0, padx=5, pady=5)
        self.prof_name_var = ctk.StringVar(value="Profile 1")
        ctk.CTkEntry(top_frame, textvariable=self.prof_name_var).grid(row=0, column=1, padx=5, pady=5)
        
        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=4, padx=10, pady=5, sticky="e")
        top_frame.grid_columnconfigure(3, weight=1)
        ctk.CTkButton(btn_frame, text="Import (Disk)", command=self.import_disk, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Export (Disk)", command=self.export_disk, width=100).pack(side="left", padx=5)
        
        split_frame = ctk.CTkFrame(self.tab_profile, fg_color="transparent")
        split_frame.grid(row=1, column=0, sticky="nsew")
        split_frame.grid_columnconfigure(1, weight=1)
        split_frame.grid_rowconfigure(0, weight=1)
        
        keys_frame = ctk.CTkFrame(split_frame, width=150)
        keys_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        keys_frame.pack_propagate(False)
        ctk.CTkLabel(keys_frame, text="Keys", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.key_buttons = {}
        for i in range(1, 13):
            btn = ctk.CTkButton(keys_frame, text=f"Key {i}", fg_color="transparent", text_color=("gray10", "gray90"),
                                hover_color=("gray70", "gray30"), command=lambda x=i: self.select_key(x))
            btn.pack(fill="x", padx=5, pady=2)
            self.key_buttons[i] = btn
            
        self.editor_frame = ctk.CTkFrame(split_frame)
        self.editor_frame.grid(row=0, column=1, sticky="nsew")
        self.editor_frame.grid_columnconfigure(0, weight=1)
        
        lbl_header = ctk.CTkLabel(self.editor_frame, text="Action Sequence", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_header.grid(row=0, column=0, pady=(10, 5))
        
        self.action_list_frame = ctk.CTkScrollableFrame(self.editor_frame)
        self.action_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.editor_frame.grid_rowconfigure(1, weight=1)
        
        ctrl_frame = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        ctrl_frame.grid(row=2, column=0, pady=10)
        ctk.CTkButton(ctrl_frame, text="+ Add Action", command=self.add_action).pack()
        
        self.action_rows = []
        self.select_key(1)

    def setup_autoswitch(self):
        self.tab_autoswitch.grid_columnconfigure(0, weight=1)
        self.tab_autoswitch.grid_rowconfigure(2, weight=1)
        
        ctk.CTkLabel(self.tab_autoswitch, text="Auto Switcher Tracking", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=10)
        
        controls_frame = ctk.CTkFrame(self.tab_autoswitch, fg_color="transparent")
        controls_frame.grid(row=1, column=0, pady=5)
        
        ctk.CTkCheckBox(controls_frame, text="Enable Background Auto-Switching", variable=self.auto_switch_enabled, command=self.toggle_autoswitch).pack(side="left", padx=10)
        ctk.CTkCheckBox(controls_frame, text="Debug AI Payload", variable=self.ai_debug_enabled, command=self.toggle_debug).pack(side="left", padx=10)
        ctk.CTkButton(controls_frame, text="AI Settings", command=lambda: AISettingsPopup(self)).pack(side="left", padx=10)
        
        self.tracking_console = ctk.CTkTextbox(self.tab_autoswitch, font=ctk.CTkFont(family="Consolas", size=12), text_color="cyan", state="disabled")
        self.tracking_console.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

    def toggle_autoswitch(self):
        self.app_settings.set("auto_switch_enabled", self.auto_switch_enabled.get())
        
    def toggle_debug(self):
        self.app_settings.set("ai_debug_enabled", self.ai_debug_enabled.get())

    def refresh_ports(self):
        ports = self.serial_worker.get_ports()
        self.port_combo.configure(values=ports)
        if ports: self.port_var.set(ports[0])
            
    def connect_serial(self):
        if self.serial_worker.connect(self.port_var.get()):
            self.append_console(f"Connected to {self.port_var.get()}\n")
            
    def load_from_device(self):
        self.append_console("Simulating load from device for Production Code...\n")
        
    def save_to_device(self):
        self.append_console("Simulating save to device for Production Code...\n")

    def append_console(self, text):
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def append_tracking_log(self, text):
        self.tracking_console.configure(state="normal")
        self.tracking_console.insert("end", text)
        self.tracking_console.see("end")
        self.tracking_console.configure(state="disabled")

    def get_key_data(self, key_id):
        for k in self.profile_data.get("keys", []):
            if k.get("id") == key_id: return k
        new_k = {"id": key_id, "actions": []}
        self.profile_data["keys"].append(new_k)
        return new_k

    def select_key(self, key_id):
        self.selected_key_id = key_id
        for i, btn in self.key_buttons.items():
            btn.configure(fg_color=("gray75", "gray25") if i == key_id else "transparent")
        self.refresh_action_editor()

    def refresh_action_editor(self):
        for r in self.action_rows: r.destroy()
        self.action_rows.clear()
        
        kdata = self.get_key_data(self.selected_key_id)
        for act in kdata.get("actions", []):
            row = ActionEditorRow(self.action_list_frame, act, self.remove_action, self.on_action_change)
            row.pack(fill="x", pady=2)
            self.action_rows.append(row)

    def add_action(self):
        kdata = self.get_key_data(self.selected_key_id)
        new_act = {"type": "text", "value": ""}
        kdata["actions"].append(new_act)
        self.refresh_action_editor()

    def remove_action(self, row_obj):
        kdata = self.get_key_data(self.selected_key_id)
        if row_obj.action_dict in kdata.get("actions", []):
            kdata["actions"].remove(row_obj.action_dict)
        row_obj.destroy()
        self.action_rows.remove(row_obj)
        
    def on_action_change(self):
        pass

    def import_disk(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if f:
            try:
                with open(f, "r") as file:
                    self.profile_data = json.load(file)
                    self.refresh_action_editor()
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

    def on_ai_success(self, context):
        if context == self.current_context:
            shortcuts = self.templates_mgr.get_context_shortcuts(context)
            if shortcuts:
                self.after(0, self.rec_widget.update_context, context, shortcuts, False)

    def handle_context_change_async(self, context):
        self.after(0, lambda c=context: self.handle_context_change_sync(c))
        
    def handle_context_change_sync(self, context):
        def reset_to_default():
            try:
                if self.serial_worker.is_open():
                    p_num = self.profile_var.get().replace("profile", "").replace(".json", "")
                    if p_num.isdigit():
                        self.serial_worker.send_cmd(f"setprofile {p_num}")
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
            self.ai_worker.queue.put({"action": "generate_and_validate", "context": context})
        else:
            try: self.rec_widget.update_context(context, None, True)
            except: pass
            reset_to_default()
            self.ai_worker.queue.put({"action": "generate_and_validate", "context": context})

    def on_closing(self):
        self.window_tracker.stop()
        self.serial_worker.close()
        self.destroy()

if __name__ == "__main__":
    app = MacropadV4App()
    app.mainloop()
