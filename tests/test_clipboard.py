import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import ctypes
import sys
import pytest
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication
from localvoice.integration import ClipboardPaste


class FakeClipboard:
    """Mimics the OS sequence number: every clipboard write increments it."""
    def __init__(self, text):
        self.sequence = 0
        self.setText(text)
    def setText(self, text):
        data = QMimeData()
        data.setText(text)
        self.setMimeData(data)
    def setMimeData(self, data):
        self.data, self.sequence = data, self.sequence + 1
    def mimeData(self):
        return self.data
    def text(self):
        return self.data.text()


@pytest.fixture
def clipboard():
    QApplication.instance() or QApplication([])
    board = FakeClipboard('Passwort des Nutzers')
    paste = ClipboardPaste(board, lambda: board.sequence)
    yield board, paste
    paste.timer.stop()


def test_single_paste_restores_original(clipboard):
    board, paste = clipboard
    paste.put('Diktat')
    assert board.text() == 'Diktat'
    paste.restore()
    assert board.text() == 'Passwort des Nutzers'


def test_overlapping_pastes_restore_the_original_not_the_first_dictation(clipboard):
    board, paste = clipboard
    paste.put('Erster Abschnitt')
    paste.put('Zweiter Abschnitt')
    paste.restore()
    assert board.text() == 'Passwort des Nutzers'


def test_newer_user_copy_always_wins(clipboard):
    board, paste = clipboard
    paste.put('Erster Abschnitt')
    board.setText('Neu kopiert')
    paste.restore()
    assert board.text() == 'Neu kopiert'
    paste.put('Erster Abschnitt')
    board.setText('Noch neuer')
    paste.put('Zweiter Abschnitt')
    paste.restore()
    assert board.text() == 'Noch neuer'


def test_restore_waits_long_enough_for_slow_targets(clipboard):
    _, paste = clipboard
    paste.put('Diktat')
    assert paste.timer.isActive() and paste.timer.interval() >= 2000


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows shell windows')
def test_taskbar_is_never_a_dictation_target():
    from ctypes import wintypes
    from localvoice.integration import is_dictation_target, user32
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = wintypes.HWND
    taskbar = user32.FindWindowW('Shell_TrayWnd', None)
    if not taskbar:
        pytest.skip('No interactive taskbar in this session')
    assert not is_dictation_target(taskbar)
