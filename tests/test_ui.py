import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCloseEvent
from localvoice.config import Settings
from localvoice.ui import Window
from localvoice.settings_ui import SettingsDialog


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    return instance


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setattr('localvoice.ui.Hotkey.register', lambda *args: None)
    w = Window(tmp_path)
    app.processEvents()
    yield w
    w.busy = False
    w.quit()
    w.deleteLater()
    app.processEvents()


def test_direct_checkbox_collapses_but_retains_transcript(window, app):
    window.editor.setPlainText('Editable text')
    window.direct.setChecked(True)
    app.processEvents()
    assert window.editor_panel.isHidden()
    assert window.editor.toPlainText() == 'Editable text'
    window.reveal_editor()
    assert not window.editor_panel.isHidden()
    window.direct.setChecked(False)
    assert not window.editor_panel.isHidden()


def test_preview_appends_without_destroying_edits(window):
    window.session_settings = replace(window.settings, direct=False)
    window.editor.setPlainText('Manuell korrigiert.')
    window.receive_text('Nächster Abschnitt.')
    assert window.editor.toPlainText() == 'Manuell korrigiert. Nächster Abschnitt.'


def test_error_survives_completion(window):
    window.show_error('Modell fehlt')
    window.finished()
    assert window.status.text() == 'Modell fehlt'


def test_quit_accepts_close_event(window):
    window.quitting = True
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()
    window.quitting = False


def test_settings_has_microphone_and_cpu(window, monkeypatch):
    monkeypatch.setattr('localvoice.settings_ui.microphones', lambda: [('WASAPI|RODE', 'RODE', 1), ('WASAPI|BRIO', 'BRIO', 2)])
    monkeypatch.setattr('localvoice.settings_ui.gpu_devices', lambda: [('vulkan:1', 'Test GPU')])
    dialog = SettingsDialog(window.settings, window.root, window)
    assert dialog.mic.count() == 3
    assert dialog.mic.itemData(0) == ''
    dialog.mic.setCurrentIndex(2)
    assert dialog.gpu.findData('cpu') >= 0
    dialog.save()
    assert dialog.result_settings.microphone == 'WASAPI|BRIO'
    dialog.deleteLater()


def test_direct_ptt_waits_for_modifiers(window, monkeypatch):
    window.session_settings = replace(window.settings, direct=True)
    window.destination = 123
    sent = []
    monkeypatch.setattr('localvoice.ui.modifiers_pressed', lambda: True)
    monkeypatch.setattr('localvoice.ui.send_text', lambda text, target: sent.append((text, target)))
    window.receive_text('Hallo Welt.')
    assert not sent and window.pending_text == ['Hallo Welt. ']
    monkeypatch.setattr('localvoice.ui.modifiers_pressed', lambda: False)
    window.flush_direct()
    assert sent == [('Hallo Welt. ', 123)] and not window.pending_text


def test_direct_failure_keeps_editable_transcript(window, monkeypatch):
    window.session_settings = replace(window.settings, direct=True)
    window.destination = 123
    monkeypatch.setattr('localvoice.ui.modifiers_pressed', lambda: False)
    def fail(*args):
        raise RuntimeError('Zielfenster gewechselt')
    monkeypatch.setattr('localvoice.ui.send_text', fail)
    window.receive_text('Dieser Text geht nicht verloren.')
    assert window.direct_blocked and not window.editor_panel.isHidden()
    assert 'nicht verloren' in window.editor.toPlainText()


@pytest.mark.parametrize('mode, expected', [('final', 'Abschnitt.'), ('preview', 'Abschnitt. Abschnitt.')])
def test_recording_drains_all_chunks_before_ready(window, app, monkeypatch, mode, expected):
    import time
    import numpy as np
    from PySide6.QtTest import QTest
    class FakeRecorder:
        def __init__(self, settings, on_chunk, on_level, on_error):
            self.on_chunk = on_chunk
        def start(self):
            if mode == 'preview':
                self.on_chunk(np.ones(16000, np.float32))
        def stop(self):
            self.on_chunk(np.ones(16000, np.float32))
    monkeypatch.setattr('localvoice.ui.Recorder', FakeRecorder)
    monkeypatch.setattr(window.engine, 'start', lambda *args: None)
    processed = []
    def transcribe(audio, *args, **kwargs):
        processed.append(len(audio))
        return ' '.join(['Abschnitt.'] * (len(audio) // 16000))
    monkeypatch.setattr(window.engine, 'transcribe', transcribe)
    window.settings.mode = mode
    window.toggle_recording()
    assert window.busy and not window.mode.isEnabled()
    window.stop_recording()
    deadline = time.monotonic() + 3
    while window.busy and time.monotonic() < deadline:
        QTest.qWait(20)
    assert not window.busy and window.mode.isEnabled()
    assert window.editor.toPlainText() == expected
    assert sum(processed) == (32000 if mode == 'preview' else 16000)


def test_preview_context_is_bounded_and_final_mode_has_no_prompt(window, monkeypatch):
    import numpy as np
    window.context_text = ''
    window.session_settings = replace(window.settings, mode='preview')
    received = []
    def transcribe(audio, settings, prompt=''):
        received.append(prompt)
        return 'x' * 250
    monkeypatch.setattr(window.engine, 'transcribe', transcribe)
    preview = replace(window.settings, mode='preview')
    for _ in range(3):
        window.transcribe_chunk(np.ones(16000), preview)
    assert received[0] == '' and len(received[1]) == 251 and len(received[2]) == 400
    window.transcribe_chunk(np.ones(16000), replace(preview, mode='final'))
    assert received[-1] == ''


def test_preview_backlog_coalesces_without_duplicate_samples(window, monkeypatch):
    import numpy as np
    window.context_text = ''
    preview = replace(window.settings, mode='preview')
    blocks = [np.full(16000, value, np.float32) for value in (1, 2, 3)]
    window.queued_audio.extend(blocks)
    calls = []
    monkeypatch.setattr(window.engine, 'transcribe', lambda audio, *a, **k: calls.append(audio) or '')
    for _ in blocks:
        window.transcribe_pending(preview)
    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0], np.concatenate(blocks))
    assert window.pending == 0 and not window.queued_audio


def test_new_recording_never_reuses_previous_session_context(window, monkeypatch):
    import time
    import numpy as np
    from PySide6.QtTest import QTest
    class FakeRecorder:
        def __init__(self, settings, on_chunk, *args):
            self.on_chunk = on_chunk
        def start(self): pass
        def stop(self): self.on_chunk(np.ones(16000, np.float32))
    prompts = []
    monkeypatch.setattr('localvoice.ui.Recorder', FakeRecorder)
    monkeypatch.setattr(window.engine, 'start', lambda *args: None)
    monkeypatch.setattr(window.engine, 'transcribe', lambda audio, settings, prompt='': prompts.append(prompt) or 'Hallo.')
    window.settings.mode = 'preview'
    for _ in range(2):
        window.toggle_recording()
        assert window.context_text == ''
        window.stop_recording()
        deadline = time.monotonic() + 3
        while window.busy and time.monotonic() < deadline:
            QTest.qWait(20)
        assert not window.busy
    assert prompts == ['', '']
    assert window.editor.toPlainText() == 'Hallo. Hallo.'


def test_warmup_error_stops_recording_and_remains_visible(window, monkeypatch):
    import time
    from PySide6.QtTest import QTest
    class FakeRecorder:
        def __init__(self, *args): pass
        def start(self): pass
        def stop(self): pass
    def fail(*args):
        raise RuntimeError('Modellstart fehlgeschlagen')
    monkeypatch.setattr('localvoice.ui.Recorder', FakeRecorder)
    monkeypatch.setattr(window.engine, 'start', fail)
    window.toggle_recording()
    deadline = time.monotonic() + 3
    while window.busy and time.monotonic() < deadline:
        QTest.qWait(20)
    assert not window.busy and window.recorder is None
    assert window.status.text() == 'Modellstart fehlgeschlagen'


def test_idle_close_hides_to_tray(window, monkeypatch):
    monkeypatch.setattr('localvoice.ui.QSystemTrayIcon.isSystemTrayAvailable', lambda: True)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted() and window.isHidden()
