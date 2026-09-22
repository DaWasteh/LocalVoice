"""Opt-in Windows smoke: owned target window, Unicode injection, real hotkey and microphone.
Does not send text to any existing user window or persist microphone samples.
"""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
if sys.platform != 'win32':
    raise SystemExit('Windows-only integration check')

TARGET = r'''
import json,sys
from pathlib import Path
from PySide6.QtWidgets import QApplication,QPlainTextEdit
from PySide6.QtCore import QTimer
app=QApplication([])
w=QPlainTextEdit()
w.setWindowTitle('LocalVoice - isolated integration target')
w.resize(430,160)
w.show()
w.activateWindow()
folder=Path(sys.argv[1])
(folder/'window.json').write_text(json.dumps({'hwnd':int(w.winId())}))
def tick():
    (folder/'text.txt').write_text(w.toPlainText(),encoding='utf-8')
    if (folder/'stop').exists(): app.quit()
t=QTimer(); t.timeout.connect(tick); t.start(50)
QTimer.singleShot(25000,app.quit)
app.exec()
'''
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from localvoice.integration import Hotkey, send_text, foreground, user32
from localvoice.audio import Recorder
from localvoice.config import Settings

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
report = {'python': sys.version, 'unicode': False, 'hotkey_press': False, 'hotkey_release': False, 'microphone': False}
original = foreground()
with tempfile.TemporaryDirectory(prefix='localvoice-test-') as temp:
    folder = Path(temp)
    child = subprocess.Popen([sys.executable, '-c', TARGET, str(folder)])
    try:
        deadline = time.monotonic() + 8
        while not (folder / 'window.json').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        hwnd = json.loads((folder / 'window.json').read_text())['hwnd']
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        user32.SetForegroundWindow(hwnd)
        time.sleep(.4)
        text = 'LocalVoice: Grüß dich! ÄÖÜ ß € 🗣'
        prior_clipboard_text = app.clipboard().text()
        send_text(text, hwnd)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            app.processEvents()
            if (folder / 'text.txt').exists() and (folder / 'text.txt').read_text(encoding='utf-8') == text:
                report['unicode'] = True
                break
            time.sleep(.05)
        report['received_text'] = (folder / 'text.txt').read_text(encoding='utf-8') if (folder / 'text.txt').exists() else '<missing>'
        events = []
        hotkey = Hotkey(app, lambda: events.append('press'), lambda: events.append('release'))
        hotkey.register('ctrl+alt+F10')
        def press():
            # Only generate the registered shortcut while our disposable target is active.
            if foreground() != hwnd:
                app.quit()
                return
            for key in (0x11, 0x12, 0x79): user32.keybd_event(key, 0, 0, 0)
        def release():
            for key in (0x79, 0x12, 0x11): user32.keybd_event(key, 0, 2, 0)
        QTimer.singleShot(150, press)
        QTimer.singleShot(350, release)
        QTimer.singleShot(800, app.quit)
        app.exec()
        hotkey.close()
        report['clipboard_restored'] = app.clipboard().text() == prior_clipboard_text
        report['hotkey_press'] = events.count('press') == 1
        report['hotkey_release'] = events.count('release') == 1
        samples, errors = [], []
        recorder = Recorder(Settings(), lambda data: samples.append(len(data)), lambda level: None, errors.append)
        try:
            recorder.start()
            time.sleep(.3)
        finally:
            recorder.stop()
        report['microphone'] = bool(samples) and sum(samples) > 1600 and not errors
        report['microphone_errors'] = errors
    finally:
        (folder / 'stop').touch()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=3)
        if original:
            user32.SetForegroundWindow(original)
report['passed'] = all(report[key] for key in ('unicode', 'hotkey_press', 'hotkey_release', 'microphone', 'clipboard_restored'))
(root / 'reports').mkdir(exist_ok=True)
(root / 'reports/windows-integration.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
