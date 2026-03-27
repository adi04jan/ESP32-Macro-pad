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

class MacropadConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ESP32 Macropad Configurator")
        self.geometry("1000x700")

        self.serial_port = None
        self.serial_thread = None
        self.stop_event = threading.Event()
        
        self.capturing_file = False
        self.file_buffer = []

        # UI Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Sidebar (Controls)
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Macro Config", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Port Selection
        self.port_var = ctk.StringVar(value="Select Port")
        self.port_dropdown = ctk.CTkComboBox(self.sidebar_frame, variable=self.port_var, values=self.get_ports())
        self.port_dropdown.grid(row=1, column=0, padx=20, pady=10)

        self.refresh_btn = ctk.CTkButton(self.sidebar_frame, text="Refresh Ports", command=self.refresh_ports)
        self.refresh_btn.grid(row=2, column=0, padx=20, pady=0)

        self.connect_btn = ctk.CTkButton(self.sidebar_frame, text="Connect", command=self.toggle_connection, fg_color="green", hover_color="darkgreen")
        self.connect_btn.grid(row=3, column=0, padx=20, pady=20)

        # Profile Selection
        self.profile_var = ctk.StringVar(value="profile1.json")
        self.profile_dropdown = ctk.CTkComboBox(self.sidebar_frame, variable=self.profile_var, 
                                                values=["profile1.json", "profile2.json", "profile3.json"])
        self.profile_dropdown.grid(row=4, column=0, padx=20, pady=10)

        self.load_btn = ctk.CTkButton(self.sidebar_frame, text="Load Profile", command=self.load_profile, state="disabled")
        self.load_btn.grid(row=5, column=0, padx=20, pady=5)

        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save to Device", command=self.save_profile, state="disabled")
        self.save_btn.grid(row=6, column=0, padx=20, pady=5)

        self.set_active_btn = ctk.CTkButton(self.sidebar_frame, text="Set Active", command=self.set_active_profile, state="disabled")
        self.set_active_btn.grid(row=7, column=0, padx=20, pady=5)

        # Bottom Buttons
        self.status_btn = ctk.CTkButton(self.sidebar_frame, text="Get Status", command=self.get_status, state="disabled")
        self.status_btn.grid(row=9, column=0, padx=20, pady=5)

        self.reboot_btn = ctk.CTkButton(self.sidebar_frame, text="Reboot Device", command=self.reboot_device, fg_color="red", hover_color="darkred", state="disabled")
        self.reboot_btn.grid(row=10, column=0, padx=20, pady=20)

        # Center Main Area (JSON Editor)
        self.editor_frame = ctk.CTkFrame(self)
        self.editor_frame.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="nsew")
        self.editor_frame.grid_columnconfigure(0, weight=1)
        self.editor_frame.grid_rowconfigure(1, weight=1)

        self.editor_label = ctk.CTkLabel(self.editor_frame, text="JSON Editor:")
        self.editor_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.json_editor = ctk.CTkTextbox(self.editor_frame, font=ctk.CTkFont(family="Consolas", size=14))
        self.json_editor.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Format JSON button inside the editor frame
        self.format_btn = ctk.CTkButton(self.editor_frame, text="Format JSON", font=ctk.CTkFont(size=12), width=100, command=self.format_json)
        self.format_btn.grid(row=0, column=0, padx=10, pady=5, sticky="e")

        # Bottom Area (Console Output)
        self.console_frame = ctk.CTkFrame(self, height=150)
        self.console_frame.grid(row=1, column=1, padx=10, pady=(5, 10), sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        self.console_label = ctk.CTkLabel(self.console_frame, text="Console Output:")
        self.console_label.grid(row=0, column=0, padx=10, pady=0, sticky="w")

        self.console = ctk.CTkTextbox(self.console_frame, font=ctk.CTkFont(family="Consolas", size=12), state="disabled", text_color="lightgreen")
        self.console.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

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

                # Send return to trigger prompt
                self.send_cmd("")

            except Exception as e:
                messagebox.showerror("Connection Error", str(e))

    def set_buttons_state(self, state):
        self.load_btn.configure(state=state)
        self.save_btn.configure(state=state)
        self.status_btn.configure(state=state)
        self.reboot_btn.configure(state=state)
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
        # Check for prompt indicator (end of commands)
        if "macropad:$" in clean_line:
            if self.capturing_file:
                self.capturing_file = False
                self.finish_capture()
            self.append_console("Ready.\n")
            return

        # If we are currently downloading a profile, buffer the lines instead of just console logging
        if self.capturing_file:
            self.file_buffer.append(clean_line)
            # still echo to console for debug:
            # self.append_console(line)
        else:
            self.append_console(line)

    def load_profile(self):
        if not self.serial_port or not self.serial_port.is_open:
            return
        
        target = self.profile_var.get()
        if not target.startswith("/"):
            target = "/" + target
        
        self.json_editor.delete("1.0", "end")
        self.capturing_file = True
        self.file_buffer = []
        self.append_console(f"Fetching {target} from device...\n")
        
        # In the original firmware, `cat <file>` output goes down directly
        self.send_cmd(f"cat {target}")

    def finish_capture(self):
        # We've hit the prompt, attempt to parse file_buffer as JSON
        if not self.file_buffer:
            self.append_console("Warning: Received empty file or timeout.\n")
            return
            
        raw_text = "\n".join(self.file_buffer).strip()
        
        # Sometimes the ESP32 might echo the command "cat /profile1.json"
        # We should strip out the first line if it looks like the command
        if "cat" in raw_text[:20]:
            lines = raw_text.split("\n")
            if len(lines) > 1:
                raw_text = "\n".join(lines[1:]).strip()
        
        try:
            parsed = json.loads(raw_text)
            formatted = json.dumps(parsed, indent=4)
            self.json_editor.insert("end", formatted)
            self.append_console("Profile loaded successfully.\n")
        except json.JSONDecodeError as e:
            self.append_console(f"Failed to parse JSON. Raw output loaded.\nError: {str(e)}\n")
            self.json_editor.insert("end", raw_text)

    def format_json(self):
        text = self.json_editor.get("1.0", "end").strip()
        if not text:
            return
        try:
            parsed = json.loads(text)
            formatted = json.dumps(parsed, indent=4)
            self.json_editor.delete("1.0", "end")
            self.json_editor.insert("end", formatted)
            self.append_console("JSON formatted successfully.\n")
        except Exception as e:
            messagebox.showerror("JSON Format Error", f"Invalid JSON:\n{str(e)}")

    def save_profile(self):
        text = self.json_editor.get("1.0", "end").strip()
        if not text:
            messagebox.showerror("Error", "Editor is empty.")
            return
            
        try:
            # Validate JSON before upload
            json.loads(text)
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Please fix JSON errors before saving:\n{str(e)}")
            return

        target = self.profile_var.get()
        if target.startswith("/"):
            target = target[1:] # the macro firmware wants filename directly after BEGIN

        self.append_console(f"Uploading {target}...\n")
        self.send_cmd(f"###BEGIN### {target}")
        
        # Send line by line to prevent dropping characters due to slow buffer handling on ESP
        for line in text.split('\n'):
            self.send_cmd(line)
            time.sleep(0.01) # Small delay for safety
            
        self.send_cmd("###END###")
        self.append_console("Upload sequence sent.\n")

    def set_active_profile(self):
        target = self.profile_var.get()
        # Extract the profile number (e.g. from "profile2.json" to "2")
        import re
        match = re.search(r'profile(\d+)', target)
        if match:
            num = match.group(1)
            self.send_cmd(f"setprofile {num}")
            self.append_console(f"Setting active profile to {num}\n")
        else:
            self.append_console("Could not determine profile number.\n")

    def get_status(self):
        self.send_cmd("status")

    def reboot_device(self):
        if messagebox.askyesno("Confirm Reboot", "Are you sure you want to reboot the ESP32?"):
            self.send_cmd("reboot")
            # Usually we might want to automatically disconnect here or handle graceful reconnection
            self.after(500, self.toggle_connection)

if __name__ == "__main__":
    app = MacropadConfigApp()
    app.mainloop()
