"""Tests for the serial protocol helpers and capture state machine.

These exercise the pure logic and the line-handling state machine of
SerialLink without needing a real serial port (or pyserial).
"""

import json

from configurator import serial_link as sl


def test_parse_fs_info_ok():
    assert sl.parse_fs_info("FS_INFO:1048576,20480") == (1048576, 20480)
    assert sl.parse_fs_info("  FS_INFO:100,50  ") == (100, 50)


def test_parse_fs_info_rejects_non_fs_lines():
    assert sl.parse_fs_info("Ready.") is None
    assert sl.parse_fs_info("FS_INFO:bad,data") is None
    assert sl.parse_fs_info("FS_INFO:100") is None


def test_build_upload_lines_wraps_with_markers():
    obj = {"profile_name": "P1", "keys": []}
    lines = sl.build_upload_lines("/profile1.json", obj)
    assert lines[0] == "###BEGIN### profile1.json"   # leading slash stripped
    assert lines[-1] == "###END###"
    body = "\n".join(lines[1:-1])
    assert json.loads(body) == obj


def test_strip_cat_echo_removes_command_line():
    text = "cat /profile1.json\n{\n  \"a\": 1\n}"
    assert sl.strip_cat_echo(text) == '{\n  "a": 1\n}'


def test_strip_cat_echo_leaves_plain_json():
    text = '{"a": 1}'
    assert sl.strip_cat_echo(text) == '{"a": 1}'


def test_parse_profile_payload_roundtrip():
    captured = ["cat /profile2.json", "{", '  "profile_name": "X",', '  "keys": []', "}"]
    assert sl.parse_profile_payload(captured) == {"profile_name": "X", "keys": []}


# ---------------------------------------------------------------------------
# Capture state machine via _handle_line (no port needed).
# ---------------------------------------------------------------------------
class _Recorder:
    def __init__(self):
        self.logs = []
        self.fs = []
        self.files = []
        self.ready = 0

    def link(self):
        return sl.SerialLink(
            on_log=self.logs.append,
            on_fs_info=lambda t, u: self.fs.append((t, u)),
            on_file=self.files.append,
            on_ready=lambda: setattr(self, "ready", self.ready + 1),
        )


def test_capture_collects_lines_until_prompt():
    rec = _Recorder()
    link = rec.link()
    link.request_profile = None  # ensure we don't touch serial; begin manually
    link._capture.begin()
    for line in ["cat /profile1.json\n", "{\n", '  "keys": []\n', "}\n"]:
        link._handle_line(line)
    assert not rec.files  # not finished yet
    link._handle_line("macropad:$ \n")
    assert len(rec.files) == 1
    assert sl.parse_profile_payload(rec.files[0]) == {"keys": []}
    assert rec.ready == 1


def test_fs_info_line_routes_to_callback():
    rec = _Recorder()
    link = rec.link()
    link._handle_line("FS_INFO:2048,512\n")
    assert rec.fs == [(2048, 512)]
    assert not rec.logs  # fs-info should not be logged as console text


def test_non_capture_lines_go_to_log():
    rec = _Recorder()
    link = rec.link()
    link._handle_line("hello world\n")
    assert rec.logs == ["hello world\n"]


def test_fragment_reassembly():
    rec = _Recorder()
    link = rec.link()
    link._capture.begin()
    link._feed("{\"partial")     # fragment, no newline, no prompt
    link._feed("_line\": 1}\n")  # completion
    link._handle_line("macropad:$\n")
    assert json.loads("\n".join(rec.files[0])) == {"partial_line": 1}


def test_capture_timeout():
    cap = sl._Capture()
    cap.begin()
    assert not cap.timed_out(now=cap.started_at + 1.0)
    assert cap.timed_out(now=cap.started_at + sl.CAPTURE_TIMEOUT_S + 0.1)
