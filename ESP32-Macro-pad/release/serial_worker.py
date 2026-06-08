import serial
import serial.tools.list_ports
import json

class SerialWorker:
    def __init__(self, log_callback):
        self.log = log_callback
        self.port = None

    def get_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port_name, baudrate=115200):
        try:
            self.port = serial.Serial(port_name, baudrate, timeout=1)
            self.log(f"Connected to {port_name} at {baudrate} baud.\n")
            return True
        except Exception as e:
            self.log(f"Connection Error: {e}\n")
            self.port = None
            return False

    def is_open(self):
        return self.port is not None and self.port.is_open

    def send_cmd(self, cmd_str):
        if self.is_open():
            try:
                self.port.write((cmd_str + "\n").encode())
            except Exception as e:
                self.log(f"Serial Write Error: {e}\n")

    def push_shortcut(self, shortcut):
        knum = shortcut.get("key_num")
        acts = shortcut.get("actions", [])
        if knum and 1 <= knum <= 4:
            self.send_cmd(f"setkey {knum} {json.dumps(acts)}")
            
    def close(self):
        if self.is_open():
            self.port.close()
