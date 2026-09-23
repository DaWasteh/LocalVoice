from __future__ import annotations
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import sys
import time
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer

IS_WINDOWS = sys.platform == 'win32'
_held_modifiers = set()

if IS_WINDOWS:
    user32 = c.WinDLL('user32', use_last_error=True)
    user32.GetForegroundWindow.restype = w.HWND
    user32.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    user32.IsWindow.argtypes = [w.HWND]
    user32.RegisterHotKey.argtypes = [w.HWND, c.c_int, w.UINT, w.UINT]
    user32.UnregisterHotKey.argtypes = [w.HWND, c.c_int]
    user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    user32.GetClipboardSequenceNumber.restype = w.DWORD


def foreground():
    if IS_WINDOWS:
        return user32.GetForegroundWindow()
    if sys.platform == 'darwin':
        try:
            result = subprocess.run(['osascript', '-e', 'tell application "System Events" to get unix id of first process whose frontmost is true'],
                                    capture_output=True, text=True, timeout=2)
            return int(result.stdout.strip()) if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        return None
    try:
        return subprocess.check_output(['xdotool', 'getactivewindow'], text=True, timeout=2).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def is_own_window(handle):
    if not handle:
        return True
    if IS_WINDOWS:
        pid = w.DWORD()
        user32.GetWindowThreadProcessId(handle, c.byref(pid))
        return pid.value == os.getpid()
    if sys.platform == 'darwin':
        return handle == os.getpid()
    try:
        pid = subprocess.check_output(['xdotool', 'getwindowpid', str(handle)], text=True, timeout=2).strip()
        return int(pid) == os.getpid()
    except (OSError, subprocess.SubprocessError, ValueError):
        return True


def modifiers_pressed():
    if IS_WINDOWS:
        return any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))
    return bool(_held_modifiers)


SHELL_CLASSES = {'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'NotifyIconOverflowWindow',
                 'TopLevelWindowForOverflowXamlIsland', 'Progman', 'WorkerW'}


def is_shell_window(handle):
    """Taskbar, tray overflow and desktop are never dictation targets."""
    if not IS_WINDOWS or not handle:
        return False
    buffer = c.create_unicode_buffer(256)
    user32.GetClassNameW(handle, buffer, 256)
    return buffer.value in SHELL_CLASSES


def is_dictation_target(handle):
    return bool(handle) and not is_own_window(handle) and not is_shell_window(handle)


class ClipboardPaste:
    """Put text on the clipboard for Ctrl+V, then restore the user's content exactly once.

    Overlapping pastes share one backup, so a second paste never mistakes the first
    dictated text for the user's clipboard. A newer change by the user always wins.
    """
    RESTORE_MS = 2000  # generous: slow targets (remote desktop, busy apps) read the clipboard late

    def __init__(self, clipboard, sequence, delay_ms=RESTORE_MS):
        self.clipboard, self.sequence = clipboard, sequence
        self.backup = self.expected = None
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_ms)
        self.timer.timeout.connect(self.restore)

    def put(self, text):
        from PySide6.QtCore import QMimeData
        if self.backup is None or self.sequence() != self.expected:
            self.backup = QMimeData()
            current = self.clipboard.mimeData()
            if current:
                for format_name in current.formats():
                    self.backup.setData(format_name, current.data(format_name))
        payload = QMimeData()
        payload.setText(text)
        for format_name in ('CanIncludeInClipboardHistory', 'CanUploadToCloudClipboard'):
            payload.setData(f'application/x-qt-windows-mime;value="{format_name}"', b'\0\0\0\0')
        self.clipboard.setMimeData(payload)
        self.expected = self.sequence()
        self.timer.start()

    def restore(self):
        self.timer.stop()
        if self.backup is not None and self.sequence() == self.expected:
            self.clipboard.setMimeData(self.backup)
        self.backup = None


_paster = None


def clipboard_paster():
    global _paster
    if _paster is None:
        from PySide6.QtWidgets import QApplication
        _paster = ClipboardPaste(QApplication.clipboard(), lambda: user32.GetClipboardSequenceNumber())
    return _paster


def restore_clipboard_now():
    if _paster is not None:
        _paster.restore()


def send_text(text, target):
    """Never steal focus. Fail closed if the destination changed."""
    if not target or foreground() != target or is_own_window(target):
        raise RuntimeError('Zielfenster nicht mehr aktiv. Text bleibt im Transkript; bitte Kopieren nutzen.')
    if IS_WINDOWS:
        # Do not combine injected characters with held Ctrl/Alt/Win keys.
        if modifiers_pressed():
            raise RuntimeError('Bitte Zusatztasten loslassen. Text bleibt im Transkript.')
        class Keyboard(c.Structure):
            _fields_ = [('vk', w.WORD), ('scan', w.WORD), ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]
        class Mouse(c.Structure):
            _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('data', w.DWORD), ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]
        class Payload(c.Union):
            _fields_ = [('ki', Keyboard), ('mi', Mouse)]
        class Input(c.Structure):
            _fields_ = [('type', w.DWORD), ('payload', Payload)]
        # Clipboard paste preserves Unicode (including surrogate pairs) and line breaks.
        clipboard_paster().put(text)
        inputs = (Input * 4)()
        for i, (key, flags) in enumerate(((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))):
            inputs[i].type = 1
            inputs[i].payload.ki = Keyboard(key, 0, flags, 0, 0)
        user32.SendInput.argtypes = [w.UINT, c.POINTER(Input), c.c_int]
        user32.SendInput.restype = w.UINT
        if foreground() != target or user32.SendInput(4, inputs, c.sizeof(Input)) != 4:
            # The pending restore still runs; an immediate restore could race an earlier paste.
            raise RuntimeError('Einfügen blockiert (z. B. Administratorfenster). Text bitte kopieren.')
    else:
        if modifiers_pressed():
            raise RuntimeError('Bitte Zusatztasten loslassen. Text bleibt im Transkript.')
        from pynput.keyboard import Controller
        Controller().type(text)


def parse_hotkey(value):
    pieces = value.lower().replace(' ', '').split('+')
    mods, key = 0, None
    for part in pieces:
        if part in ('ctrl', 'alt', 'shift', 'win', 'cmd'):
            mods |= {'alt': 1, 'ctrl': 2, 'shift': 4, 'win': 8, 'cmd': 8}[part]
        elif key is None:
            if part == 'space':
                key = 0x20
            elif part.startswith('f') and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
                key = 0x70 + int(part[1:]) - 1
            elif len(part) == 1 and part.isascii() and part.isalnum():
                key = ord(part.upper())
            else:
                raise ValueError('Hotkey: z. B. ctrl+alt+space, ctrl+shift+d oder F9')
        else:
            raise ValueError('Nur eine Haupttaste im Hotkey erlaubt')
    if key is None or (not mods and key < 0x70):
        raise ValueError('Bitte Zusatztaste oder F-Taste wählen')
    if mods == 4 and key < 0x70:
        # Shift+letter/space would swallow ordinary typing (e.g. every capital "A").
        raise ValueError('Shift allein reicht nicht: bitte Ctrl, Alt oder Win ergänzen oder eine F-Taste wählen')
    return mods, key


class Hotkey(QAbstractNativeEventFilter):
    def __init__(self, app, on_press, on_release):
        super().__init__()
        self.app, self.on_press, self.on_release = app, on_press, on_release
        self.registered, self.held, self.listener = False, False, None
        self.timer = QTimer()
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._release_poll)
        app.installNativeEventFilter(self)

    def register(self, value):
        mods, key = parse_hotkey(value)
        self.close()
        self.key, self.mods = key, mods
        if IS_WINDOWS:
            if not user32.RegisterHotKey(None, 0x4C56, mods | 0x4000, key):
                raise RuntimeError('Hotkey bereits belegt. Bitte eine andere Kombination wählen.')
            self.registered = True
            self.timer.start()
        else:
            if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                raise RuntimeError('Wayland: globaler Hotkey benötigt Desktop-Integration. Aufnahme-Button verfügbar.')
            from pynput import keyboard
            keys = value.lower().split('+')
            normalized = '+'.join(f'<{p}>' if p in ('ctrl', 'alt', 'shift', 'cmd', 'space') or p.startswith('f') and len(p) > 1 else p for p in keys)
            combo = keyboard.HotKey.parse(normalized)
            self.active_keys = set()
            def press(k):
                canonical = listener.canonical(k)
                self.active_keys.add(canonical)
                if getattr(canonical, 'name', '').split('_')[0] in ('ctrl', 'alt', 'shift', 'cmd'):
                    _held_modifiers.add(canonical)
                if set(combo) <= self.active_keys and not self.held:
                    self.held = True
                    self.on_press()
            def release(k):
                canonical = listener.canonical(k)
                self.active_keys.discard(canonical)
                _held_modifiers.discard(canonical)
                if self.held and not set(combo) <= self.active_keys:
                    self.held = False
                    self.on_release()
            listener = keyboard.Listener(on_press=press, on_release=release)
            self.listener = listener
            listener.start()

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS:
            msg = w.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == 0x4C56:
                if not self.held:
                    self.held = True
                    self.on_press()
                return True, 0
        return False, 0

    def _release_poll(self):
        required = [self.key] + [vk for bit, vk in ((1, 0x12), (2, 0x11), (4, 0x10)) if self.mods & bit]
        held = all(user32.GetAsyncKeyState(key) & 0x8000 for key in required)
        if self.mods & 8:
            held = held and bool((user32.GetAsyncKeyState(0x5B) | user32.GetAsyncKeyState(0x5C)) & 0x8000)
        if self.held and not held:
            self.held = False
            self.on_release()

    def close(self):
        self.timer.stop()
        _held_modifiers.clear()
        if self.registered:
            user32.UnregisterHotKey(None, 0x4C56)
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.registered, self.held = False, False


def set_autostart(enabled, root: Path):
    if IS_WINDOWS:
        import winreg
        if getattr(sys, 'frozen', False):
            args = [sys.executable, '--tray']
        else:
            args = [str(Path(sys.executable).with_name('pythonw.exe')), str(root / 'main.py'), '--tray']
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                winreg.SetValueEx(key, 'LocalVoice', 0, winreg.REG_SZ, subprocess.list2cmdline(args))
            else:
                try:
                    winreg.DeleteValue(key, 'LocalVoice')
                except FileNotFoundError:
                    pass
    elif enabled:
        raise RuntimeError('Autostart ist in dieser Version nur für Windows implementiert.')
