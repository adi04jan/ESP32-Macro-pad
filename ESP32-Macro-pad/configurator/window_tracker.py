"""
Active-window context detection for the auto-switcher.

Runs a background poll of the foreground window title and maps it to a context
name (vscode, excel, slack, ...). Unlike the old tracker, exception handling is
scoped (no bare `except: pass` swallowing real bugs) and a missing
`pygetwindow` dependency is reported once and degrades gracefully instead of
silently disabling tracking forever.
"""

from __future__ import annotations

import threading

# Window titles that should never trigger a context switch.
IGNORE_CONTEXTS = {"program manager", "windows explorer", "task switching", ""}


def detect_context(title):
    """Map a window title to a context key. Pure function — easy to test."""
    if not title:
        return ""
    t = title.lower()
    if "visual studio code" in t or "vscode" in t:
        if any(term in t for term in ("terminal", "bash", "powershell", "cmd")):
            return "vscode_terminal"
        return "vscode"
    if "excel" in t:
        return "excel"
    if "google sheets" in t or "sheets" in t:
        return "google_sheets"
    if "powershell" in t:
        return "powershell"
    if any(term in t for term in ("ubuntu", "wsl", "debian")):
        return "wsl"
    if "chrome" in t:
        return "chrome"
    if "notepad" in t:
        return "notepad"
    if "slack" in t:
        return "slack"
    # Fallback: last segment of a "Doc - App" style title.
    parts = title.split("-")
    return parts[-1].strip() if len(parts) > 1 else title.strip()


class WindowTracker:
    def __init__(self, on_context, is_enabled, poll_interval=1.0, log=None):
        # on_context(context_name): called (on the worker thread) when context
        #   changes. is_enabled(): bool gate. log(msg): optional status sink.
        self.on_context = on_context
        self.is_enabled = is_enabled
        self.poll_interval = poll_interval
        self.log = log or (lambda msg: None)

        self._stop = threading.Event()
        self._thread = None
        self._last_context = ""
        self._gw = None
        self._warned = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _ensure_backend(self):
        if self._gw is not None:
            return True
        try:
            import pygetwindow
            self._gw = pygetwindow
            return True
        except ImportError:
            if not self._warned:
                self._warned = True
                self.log("Auto-switch unavailable: install 'pygetwindow'.\n")
            return False

    def _active_title(self):
        try:
            win = self._gw.getActiveWindow()
        except Exception:  # noqa: BLE001 - platform quirks; treat as no window
            return None
        if not win:
            return None
        title = getattr(win, "title", None)
        return title.replace("​", "").strip() if title else None

    def _run(self):
        while not self._stop.wait(self.poll_interval):
            try:
                if not self.is_enabled():
                    continue
                if not self._ensure_backend():
                    continue
                title = self._active_title()
                if not title:
                    continue
                context = detect_context(title)
                if (context and context != self._last_context
                        and context.lower() not in IGNORE_CONTEXTS
                        and "macropad" not in context.lower()):
                    self._last_context = context
                    self.on_context(context)
            except Exception as e:  # noqa: BLE001 - never let the poll thread die
                self.log(f"Window tracker error: {e}\n")
