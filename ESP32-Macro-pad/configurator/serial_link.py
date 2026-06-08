"""
Robust serial link to the macropad.

Improvements over the old serial code:
  * Line assembly has a timeout, so a partial read or a missing prompt can no
    longer stall a file capture forever.
  * Upload validates JSON before sending and uses the ###BEGIN###/###END###
    protocol with bounded, throttled writes.
  * The protocol logic (fs-info parsing, upload payload building, cat-echo
    stripping, the capture state machine) is split into pure, unit-testable
    helpers; the thread is a thin wrapper around them.
  * Callbacks are invoked for log / fs-info / captured-file / ready events;
    the UI marshals them onto the Tk thread.
"""

from __future__ import annotations

import json
import threading
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # allow importing helpers (and tests) without pyserial
    serial = None

PROMPT = "macropad:$"
CAPTURE_TIMEOUT_S = 4.0


# ---------------------------------------------------------------------------
# Pure helpers (no I/O) — these carry the protocol logic and are unit tested.
# ---------------------------------------------------------------------------
def list_ports():
    if serial is None:
        return []
    return [p.device for p in serial.tools.list_ports.comports()]


def parse_fs_info(line):
    """Parse 'FS_INFO:<total>,<used>' -> (total, used) or None."""
    line = line.strip()
    if not line.startswith("FS_INFO:"):
        return None
    try:
        total_s, used_s = line[len("FS_INFO:"):].split(",")[:2]
        return int(total_s), int(used_s)
    except (ValueError, IndexError):
        return None


def build_upload_lines(filename, obj):
    """Return the list of serial lines for uploading `obj` as JSON to `filename`.

    Raises TypeError/ValueError if `obj` is not JSON-serializable.
    """
    name = filename.lstrip("/")
    body = json.dumps(obj, indent=2)
    return [f"###BEGIN### {name}", *body.split("\n"), "###END###"]


def strip_cat_echo(text):
    """The device echoes the `cat <path>` command before the file body; drop it."""
    text = text.strip()
    lines = text.split("\n")
    if lines and lines[0].lstrip().startswith("cat "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def parse_profile_payload(captured_lines):
    """Join captured lines, strip the cat echo, and parse JSON. Raises on bad JSON."""
    raw = strip_cat_echo("\n".join(captured_lines))
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Capture state machine — testable without a real port.
# ---------------------------------------------------------------------------
class _Capture:
    def __init__(self):
        self.active = False
        self.lines = []
        self.started_at = 0.0

    def begin(self):
        self.active = True
        self.lines = []
        self.started_at = time.monotonic()

    def add(self, line):
        self.lines.append(line)

    def timed_out(self, now=None):
        if not self.active:
            return False
        now = time.monotonic() if now is None else now
        return (now - self.started_at) > CAPTURE_TIMEOUT_S

    def finish(self):
        self.active = False
        out, self.lines = self.lines, []
        return out


# ---------------------------------------------------------------------------
# Serial link
# ---------------------------------------------------------------------------
class SerialLink:
    def __init__(self, on_log=None, on_fs_info=None, on_file=None, on_ready=None,
                 on_disconnect=None):
        self.on_log = on_log or (lambda msg: None)
        self.on_fs_info = on_fs_info or (lambda total, used: None)
        self.on_file = on_file or (lambda lines: None)
        self.on_ready = on_ready or (lambda: None)
        self.on_disconnect = on_disconnect or (lambda: None)

        self._ser = None
        self._reader = None
        self._stop = threading.Event()
        self._capture = _Capture()
        self._partial = ""

    # ------------------------------------------------------------------
    def is_open(self):
        return self._ser is not None and getattr(self._ser, "is_open", False)

    def connect(self, port, baud=115200):
        if serial is None:
            self.on_log("pyserial is not installed.\n")
            return False
        try:
            self._ser = serial.Serial(port, baud, timeout=0.1)
        except Exception as e:  # noqa: BLE001 - report any port error to the UI
            self.on_log(f"Connection error: {e}\n")
            self._ser = None
            return False
        self._stop.clear()
        self._partial = ""
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.on_log(f"Connected to {port} at {baud} baud.\n")
        return True

    def disconnect(self):
        self._stop.set()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:  # noqa: BLE001
                pass
        self._ser = None

    def send_cmd(self, cmd):
        if not self.is_open():
            return
        try:
            self._ser.write((cmd + "\n").encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            self.on_log(f"Write error: {e}\n")

    def request_fs_info(self):
        self.send_cmd("fsinfo")

    def set_active_profile(self, num):
        self.send_cmd(f"setprofile {int(num)}")

    def request_profile(self, path):
        """Start capturing a `cat <path>` response; on_file fires when complete."""
        if not path.startswith("/"):
            path = "/" + path
        self._capture.begin()
        self.send_cmd(f"cat {path}")

    def upload_profile(self, filename, obj, on_complete=None):
        """Validate + upload `obj` as JSON on a background thread."""
        try:
            lines = build_upload_lines(filename, obj)
        except (TypeError, ValueError) as e:
            self.on_log(f"Serialization error: {e}\n")
            return

        def worker():
            for line in lines:
                self.send_cmd(line)
                time.sleep(0.01)
            self.on_log("Upload sequence sent.\n")
            if on_complete:
                on_complete()

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    def _read_loop(self):
        while not self._stop.is_set():
            try:
                waiting = self._ser.in_waiting if self.is_open() else 0
                if waiting:
                    raw = self._ser.readline()
                    text = raw.decode("utf-8", errors="replace")
                    self._feed(text)
                elif self._capture.timed_out():
                    self.on_log("Warning: file capture timed out.\n")
                    self.on_file(self._capture.finish())
            except Exception as e:  # noqa: BLE001
                self.on_log(f"Serial error: {e}\n")
                self.on_disconnect()
                break
            time.sleep(0.01)

    def _feed(self, text):
        """Reassemble fragmented reads into whole lines, then dispatch."""
        if not text:
            return
        # A chunk ending without a newline (and not carrying the prompt) is a
        # fragment; buffer it until the rest arrives.
        if not text.endswith("\n") and PROMPT not in text:
            self._partial += text
            return
        line = self._partial + text
        self._partial = ""
        self._handle_line(line)

    def _handle_line(self, line):
        clean = line.replace("\r", "").replace("\n", "")

        fs = parse_fs_info(clean)
        if fs is not None:
            self.on_fs_info(*fs)
            return

        if PROMPT in clean:
            if self._capture.active:
                self.on_file(self._capture.finish())
            self.on_ready()
            return

        if self._capture.active:
            self._capture.add(clean)
        else:
            self.on_log(line if line.endswith("\n") else line + "\n")
