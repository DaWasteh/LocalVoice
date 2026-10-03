"""Opt-in GNOME/Wayland portal smoke; requires existing write access to /dev/uinput.

Injects Ctrl+Alt+Space via a temporary virtual keyboard. Tests actual desktop
press/release events and GUI toggle/push-to-talk, including held-key autorepeat.
Microphone/inference are stubbed: no audio is captured. No privilege changes.
"""
import fcntl
import os
from pathlib import Path
import struct
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from localvoice import ui

assert os.environ.get('XDG_SESSION_TYPE') == 'wayland'
app = QApplication([])
app.setQuitOnLastWindowClosed(False)


def wait_until(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('Portal did not reach expected GUI state: ' + window.status.text())


def pump(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)


calls = []
class Recorder:
    def __init__(self, *args): pass
    def start(self): calls.append('start')
    def stop(self): calls.append('stop')
ui.Recorder = Recorder
with tempfile.TemporaryDirectory(prefix='localvoice-hotkey-') as folder, open('/dev/uinput', 'wb', buffering=0) as keyboard:
    root = Path(folder)
    os.environ['LOCALVOICE_HOME'] = folder
    window = ui.Window(root, start_tray=True)
    window.prepare_session = lambda _: None
    window.hide()
    try:
        wait_until(lambda: window.hotkey.registered, seconds=120)
        print(window.status.text(), flush=True)
        # Linux UAPI: UI_SET_EVBIT, UI_SET_KEYBIT, UI_DEV_SETUP, UI_DEV_CREATE.
        fcntl.ioctl(keyboard, 0x40045564, 1)
        fcntl.ioctl(keyboard, 0x40045564, 20)  # EV_REP: exercise held-key autorepeat
        for key in (29, 56, 57):  # left Ctrl, left Alt, Space
            fcntl.ioctl(keyboard, 0x40045565, key)
        fcntl.ioctl(keyboard, 0x405c5503, struct.pack('HHHH80sI', 3, 1, 1, 1, b'LocalVoice hotkey smoke', 0))
        fcntl.ioctl(keyboard, 0x5501)
        pump(2)  # compositor discovers the device
        def event(key, state):
            keyboard.write(struct.pack('llHHi', 0, 0, 1, key, state))
            keyboard.write(struct.pack('llHHi', 0, 0, 0, 0, 0))
        def press():
            for key in (29, 56, 57):
                event(key, 1)
                pump(.04)
        def release():
            for key in (57, 56, 29):
                event(key, 0)
                pump(.04)
        try:
            press()
            wait_until(lambda: window.recorder is not None)
            pump(1)
            release()
            assert calls == ['start'] and window.busy and window.isHidden(), calls
            press()
            release()
            wait_until(lambda: window.recorder is None and not window.busy)
            assert calls == ['start', 'stop'], calls
            window.settings.hotkey_mode = 'hold'
            press()
            wait_until(lambda: window.recorder is not None)
            pump(1)
            assert calls == ['start', 'stop', 'start'], calls
            release()
            wait_until(lambda: window.recorder is None and not window.busy)
            assert calls == ['start', 'stop', 'start', 'stop'] and window.isHidden(), calls
            print('PASS: Ctrl+Alt+Space → portal → GUI toggle and push-to-talk; no repeats, no window activation, no audio captured')
        finally:
            release()
    finally:
        print('GUI recording transitions:', calls)
        portal = window.hotkey.portal
        if window.recorder:
            window.stop_recording()
        window.busy = False
        window.quit()
        wait_until(lambda: not portal.thread.is_alive())
        assert not window.hotkey.registered
print('PASS: portal session closed and worker stopped')
