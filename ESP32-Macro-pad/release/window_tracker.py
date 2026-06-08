import threading
import time

class WindowTracker:
    def __init__(self, settings, log_callback, on_context_change):
        self.settings = settings
        self.log = log_callback
        self.on_context_change = on_context_change
        
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()

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

    def loop(self):
        last_context = ""
        while not self.stop_event.is_set():
            try:
                if self.settings.get("auto_switch_enabled", False):
                    import pygetwindow as gw
                    win = gw.getActiveWindow()
                    if win and win.title:
                        title = win.title.replace('\u200b', '').strip()
                        context = self.detect_context(title)
                        
                        if context and context != last_context and "Macropad" not in context:
                            last_context = context
                            self.log(f"Context Changed -> [{context}]\n")
                            self.on_context_change(context)
            except Exception:
                pass
            time.sleep(1.0)
