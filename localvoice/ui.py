from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import numpy as np
from dataclasses import replace
import threading
import time
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSize
from PySide6.QtGui import QIcon, QTextCursor, QAction, QColor, QPalette
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QCheckBox, QProgressBar, QSystemTrayIcon, QMenu, QMessageBox)
from . import __version__
from .config import Settings, assets_dir
from .audio import Recorder, warm_resampler
from .backend import Whisper
from .models import MODELS
from .devices import preferred_device
from .integration import (Hotkey, foreground, is_dictation_target, send_text, set_autostart,
                          modifiers_pressed, restore_clipboard_now)
from .settings_ui import SettingsDialog
from .widgets import StableComboBox as QComboBox


class Events(QObject):
    text = Signal(str)
    error = Signal(str)
    level = Signal(float)
    done = Signal()
    status = Signal(str)
    notice = Signal(str)
    limit = Signal()
    pressed = Signal()
    released = Signal()


class TitleBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
        super().mousePressEvent(event)


class Window(QWidget):
    def __init__(self, root, start_tray=False):
        super().__init__()
        self.root = root
        first_run = not (root / 'state/settings.json').is_file()
        self.settings = Settings.load(root)
        if self.settings.model not in MODELS:
            self.settings.model = 'large-v3'
        if first_run:
            self.settings.device = preferred_device()
        self.setWindowTitle(f'LocalVoice · v{__version__}')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(490)
        self.icon = QIcon(str(assets_dir() / 'localvoice.ico'))
        self.setWindowIcon(self.icon)
        self.events = Events(self)
        self.engine = Whisper(root)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='localvoice-asr')
        self.recorder = None
        self.busy = self.quitting = False
        self.failed = threading.Event()
        self.pending_lock = threading.Lock()
        self.pending = 0
        self.queued_audio = deque()
        self.destination = self.last_external = None
        self.direct_blocked = False
        self.pending_text = []
        self.notice = ''
        self.started = 0
        self.build_ui()
        self.events.text.connect(self.receive_text)
        self.events.error.connect(self.show_error)
        self.events.level.connect(lambda value: self.level.setValue(min(100, int(value * 450))))
        self.events.done.connect(self.finished)
        self.events.status.connect(self.session_status)
        self.events.notice.connect(self.show_notice)
        self.events.limit.connect(self.recording_limit)
        self.events.pressed.connect(self.hotkey_pressed)
        self.events.released.connect(self.hotkey_released)
        self.hotkey = Hotkey(QApplication.instance(), self.events.pressed.emit, self.events.released.emit)
        self.setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(150)
        self.apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        self.apply_direct()
        try:
            self.hotkey.register(self.settings.hotkey)
        except Exception as exc:
            self.status.setText(str(exc))
        if self.settings.autostart:
            try:
                # Keep the login entry pointing at this copy after the folder was moved.
                set_autostart(True, root)
            except Exception:
                pass
        if not start_tray or not QSystemTrayIcon.isSystemTrayAvailable():
            self.show()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 14, 22, 20)
        layout.setSpacing(14)
        title = TitleBar()
        row = QHBoxLayout(title)
        row.setContentsMargins(0, 0, 0, 0)
        self.menu_button = QPushButton()
        self.menu_button.setIcon(self.icon)
        self.menu_button.setIconSize(QSize(30, 30))
        self.menu_button.setFixedSize(40, 40)
        self.menu_button.setToolTip('Einstellungen öffnen')
        self.menu_button.setAccessibleName('Einstellungen')
        self.menu_button.clicked.connect(self.open_settings)
        row.addWidget(self.menu_button)
        brand = QLabel('LocalVoice')
        brand.setObjectName('brand')
        row.addWidget(brand)
        row.addStretch()
        offline = QLabel('●  LOKAL')
        offline.setObjectName('badge')
        row.addWidget(offline)
        minimize, close = QPushButton('−'), QPushButton('×')
        for button in (minimize, close):
            button.setFixedSize(30, 30)
            row.addWidget(button)
        minimize.setAccessibleName('Minimieren')
        close.setAccessibleName('Schließen')
        minimize.clicked.connect(self.showMinimized)
        close.clicked.connect(self.close)
        layout.addWidget(title)
        heading = QLabel('Deine Stimme. Dein Text.')
        heading.setObjectName('heading')
        layout.addWidget(heading)
        self.model_label = QLabel()
        self.model_label.setObjectName('muted')
        layout.addWidget(self.model_label)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Diktiermodus'))
        self.mode = QComboBox()
        self.mode.addItem('Am Ende schreiben', 'final')
        self.mode.addItem('Vorschau in Abschnitten', 'preview')
        self.mode.setCurrentIndex(1 if self.settings.mode == 'preview' else 0)
        self.mode.currentIndexChanged.connect(self.change_mode)
        mode_row.addWidget(self.mode, 1)
        layout.addLayout(mode_row)
        self.record = QPushButton('●  Aufnahme starten')
        self.record.setObjectName('record')
        self.record.setMinimumHeight(64)
        self.record.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setValue(0)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(5)
        layout.addWidget(self.level)
        self.status = QLabel('Bereit · Silero-VAD und Stillefilter aktiv')
        self.status.setWordWrap(True)
        self.status.setObjectName('muted')
        layout.addWidget(self.status)
        self.editor_panel = QWidget()
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText('Hier erscheint dein Transkript.\nDu kannst es jederzeit bearbeiten.')
        self.editor.setMinimumHeight(185)
        self.editor.setMaximumHeight(250)
        self.editor.setAccessibleName('Editierbares Transkript')
        editor_layout.addWidget(self.editor)
        tools = QHBoxLayout()
        copy = QPushButton('Kopieren')
        copy.clicked.connect(self.copy_text)
        paste = self.paste_button = QPushButton('Einfügen in 3 s')
        paste.setToolTip('Klicken, dann innerhalb von 3 Sekunden das gewünschte Textfeld fokussieren.')
        paste.clicked.connect(self.paste_later)
        clear = QPushButton('Leeren')
        clear.clicked.connect(self.editor.clear)
        tools.addWidget(copy)
        tools.addWidget(paste)
        tools.addStretch()
        tools.addWidget(clear)
        editor_layout.addLayout(tools)
        layout.addWidget(self.editor_panel)
        self.direct = QCheckBox('Direkt ins aktive Textfeld diktieren')
        self.direct.setChecked(self.settings.direct)
        self.direct.toggled.connect(self.change_direct)
        layout.addWidget(self.direct)
        self.reveal = QPushButton('Transkript aufklappen')
        self.reveal.clicked.connect(self.reveal_editor)
        layout.addWidget(self.reveal)
        self.footer = QLabel()
        self.footer.setObjectName('muted')
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        self.update_labels()

    def update_labels(self):
        device = 'CPU' if self.settings.device == 'cpu' else self.settings.device.replace('vulkan:', 'Vulkan GPU ')
        self.model_label.setText(f'Whisper {self.settings.model}  ·  {device}  ·  Offline')
        behavior = 'halten zum Sprechen' if self.settings.hotkey_mode == 'hold' else 'Start / Stopp'
        self.footer.setText(f'{self.settings.hotkey.upper()} · {behavior}\nOptionen: Logo links oben · LocalVoice {__version__}')

    def apply_theme(self):
        system_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        dark = self.settings.theme == 'dark' or self.settings.theme == 'system' and system_dark
        bg, panel, text, muted, border = ('#121820', '#1c2632', '#edf5fc', '#9aaec2', '#2d3a48') if dark else ('#f4f7fb', '#ffffff', '#172c40', '#546a7d', '#d8e2ec')
        palette = QPalette()
        for role, value in ((QPalette.ColorRole.Window, bg), (QPalette.ColorRole.WindowText, text),
                            (QPalette.ColorRole.Base, panel), (QPalette.ColorRole.Text, text),
                            (QPalette.ColorRole.Button, panel), (QPalette.ColorRole.ButtonText, text),
                            (QPalette.ColorRole.Highlight, '#168b80'), (QPalette.ColorRole.HighlightedText, '#ffffff')):
            palette.setColor(role, QColor(value))
        QApplication.instance().setPalette(palette)
        QApplication.instance().setStyleSheet(f'''
            QWidget {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: {text}; }}
            QWidget#unused {{ background: {bg}; }}
            QDialog, Window {{ background: {bg}; }}
            QLabel#brand {{ font-size: 19px; font-weight: 700; }}
            QLabel#heading {{ font-size: 23px; font-weight: 650; margin-top: 5px; }}
            QLabel#muted {{ color: {muted}; font-size: 12px; }}
            QLabel#badge {{ color: #26b5a5; font-size: 10px; font-weight: bold; }}
            QPushButton, QComboBox, QLineEdit, QSpinBox {{ background: {panel}; border: 1px solid {border}; border-radius: 7px; padding: 8px; }}
            QPushButton:hover {{ border-color: #22b8a6; }}
            QPushButton:disabled {{ color: {muted}; }}
            QPushButton#record {{ background: #168b80; color: white; border: none; font-size: 17px; font-weight: 600; }}
            QPushButton#record:hover {{ background: #1a9e90; }}
            QPlainTextEdit {{ background: {panel}; border: 1px solid {border}; border-radius: 9px; padding: 12px; font-size: 15px; }}
            QProgressBar {{ border: none; background: {border}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: #22b8a6; border-radius: 2px; }}
            QCheckBox {{ spacing: 9px; padding: 5px 0; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
            QTabWidget::pane {{ border: 1px solid {border}; }}
            QTabBar::tab {{ padding: 10px; }}
        ''')

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip('LocalVoice · lokal diktieren')
        menu = QMenu(self)
        for label, callback in [('Öffnen', self.show_window), ('Aufnahme starten / stoppen', self.toggle_recording),
                                ('Einstellungen', self.open_settings), ('Beenden', self.quit)]:
            action = menu.addAction(label)
            action.triggered.connect(callback)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.show()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def change_mode(self):
        self.settings.mode = self.mode.currentData()
        self.settings.save(self.root)

    def change_direct(self, enabled):
        if not enabled:
            self.pending_text.clear()
        self.settings.direct = enabled
        self.settings.save(self.root)
        self.apply_direct()

    def apply_direct(self):
        self.editor_panel.setVisible(not self.settings.direct)
        self.reveal.setVisible(self.settings.direct)
        self.reveal.setText('Transkript aufklappen')
        QTimer.singleShot(0, self.adjustSize)

    def reveal_editor(self):
        visible = not self.editor_panel.isVisible()
        self.editor_panel.setVisible(visible)
        self.reveal.setText('Transkript einklappen' if visible else 'Transkript aufklappen')
        self.adjustSize()

    def hotkey_pressed(self):
        if QApplication.activeModalWidget():
            return
        if self.settings.hotkey_mode == 'hold':
            if not self.busy:
                self.toggle_recording()
        else:
            self.toggle_recording()

    def hotkey_released(self):
        if self.settings.hotkey_mode == 'hold' and self.recorder:
            self.stop_recording()

    def toggle_recording(self):
        if self.quitting:
            return
        if self.recorder:
            self.stop_recording()
            return
        if self.busy or QApplication.activeModalWidget():
            return
        if self.pending_text:
            self.status.setText('Bitte erst Zusatztasten loslassen, damit der vorige Text eingefügt werden kann.')
            return
        self.session_settings = replace(self.settings)
        self.context_text = ''
        self.failed.clear()
        self.direct_blocked = False
        self.pending_text = []
        self.notice = ''
        active = foreground()
        self.destination = active if is_dictation_target(active) else self.last_external
        if self.settings.direct and not self.destination:
            self.show_error('Bitte zuerst ein Textfeld fokussieren und den globalen Hotkey verwenden.')
            return
        self.busy = True
        self.started = time.monotonic()
        self.mode.setEnabled(False)
        self.direct.setEnabled(False)
        self.menu_button.setEnabled(False)
        self.record.setText('■  Aufnahme stoppen')
        self.status.setText('Ich höre zu …')
        try:
            self.recorder = Recorder(self.session_settings, self.queue_chunk, self.events.level.emit, self.events.error.emit,
                                     self.events.notice.emit, self.events.limit.emit)
            self.recorder.start()
            # Loading overlaps microphone capture instead of delaying the first chunk.
            self.executor.submit(self.prepare_session, self.session_settings)
        except Exception as exc:
            if self.recorder:
                self.recorder.stop()
            self.recorder = None
            self.finished()
            self.show_error(str(exc))

    def prepare_session(self, settings):
        try:
            if not self.failed.is_set() and not self.quitting:
                self.events.status.emit('Aufnahme läuft · Modell wird vorbereitet …')
                warm_resampler()
                self.engine.start(settings)
                if not self.failed.is_set() and not self.quitting:
                    self.events.status.emit('Ich höre zu · Modell bereit')
        except Exception as exc:
            self.failed.set()
            self.events.error.emit(str(exc))

    def queue_chunk(self, audio):
        with self.pending_lock:
            overloaded = len(self.queued_audio) >= 12
            if not overloaded:
                self.queued_audio.append(audio)
                self.pending = len(self.queued_audio)
        if overloaded:
            self.failed.set()
            self.events.error.emit('Erkennung kommt nicht hinterher. Bitte ein schnelleres Modell wählen oder den Endmodus nutzen.')
            return
        self.executor.submit(self.transcribe_pending, self.session_settings)

    def transcribe_pending(self, settings):
        with self.pending_lock:
            if not self.queued_audio:
                return
            parts = [self.queued_audio.popleft()]
            size = len(parts[0])
            # On slow hardware, process already buffered audio together instead of
            # paying Whisper's fixed encoder cost for every tiny queued fragment.
            while settings.mode == 'preview' and self.queued_audio and size + len(self.queued_audio[0]) <= 30 * 16000:
                part = self.queued_audio.popleft()
                size += len(part)
                parts.append(part)
            self.pending = len(self.queued_audio)
        audio = parts[0] if len(parts) == 1 else np.concatenate(parts)
        self.transcribe_chunk(audio, settings)

    def transcribe_chunk(self, audio, settings):
        try:
            if not self.failed.is_set() and not self.quitting:
                self.events.status.emit('Whisper verarbeitet einen Abschnitt …')
                prompt = self.context_text if settings.mode == 'preview' else ''
                text = self.engine.transcribe(audio, settings, prompt=prompt)
                if text:
                    if settings.mode == 'preview':
                        self.context_text = (self.context_text + ' ' + text)[-400:]
                    self.events.text.emit(text)
        except Exception as exc:
            self.failed.set()
            self.events.error.emit(str(exc))

    def stop_recording(self):
        if not self.recorder:
            return
        recorder, self.recorder = self.recorder, None
        recorder.stop()
        self.record.setEnabled(False)
        self.record.setText('Text wird fertiggestellt …')
        self.status.setText('Aufnahme beendet · Erkennung läuft …')
        self.executor.submit(self.events.done.emit)

    def receive_text(self, text):
        previous = self.editor.toPlainText()
        cursor = QTextCursor(self.editor.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText((' ' if previous and not previous[-1].isspace() else '') + text)
        if self.session_settings.direct and not self.direct_blocked and not self.failed.is_set():
            self.pending_text.append(text + ' ')
            self.flush_direct()

    def flush_direct(self):
        if not self.pending_text or self.direct_blocked:
            return
        # PTT with Ctrl/Alt must not inject shortcuts: defer until modifiers are released.
        if modifiers_pressed():
            self.status.setText('Text bereit · zum Einfügen Zusatztasten loslassen')
            return
        text = ''.join(self.pending_text)
        self.pending_text.clear()
        try:
            send_text(text, self.destination)
        except Exception as exc:
            # Not fatal: recognition continues into the editor, so no later speech is lost.
            self.direct_blocked = True
            self.editor_panel.show()
            self.reveal.setText('Transkript einklappen')
            self.adjustSize()
            self.show_notice(str(exc))

    def finished(self):
        self.busy = False
        self.record.setEnabled(True)
        self.record.setText('●  Aufnahme starten')
        self.mode.setEnabled(True)
        self.direct.setEnabled(True)
        self.menu_button.setEnabled(True)
        self.level.setValue(0)
        if not self.failed.is_set():
            # A blocked direct insertion is kept in self.notice, so it stays visible here.
            result = 'Bereit · Transkription abgeschlossen' if self.editor.toPlainText() else 'Keine Sprache erkannt · bereit'
            self.status.setText(f'{result}\n{self.notice}' if self.notice else result)

    def session_status(self, message):
        # Worker progress queued behind done/error must not overwrite the final status.
        if self.busy and not self.failed.is_set():
            self.status.setText(message)

    def show_error(self, message):
        self.failed.set()
        self.pending_text.clear()
        if self.recorder:
            self.stop_recording()
        self.show_notice(message)

    def show_notice(self, message):
        """Visible, but unlike show_error it does not end the recording or discard audio."""
        if not self.failed.is_set():
            self.notice = message  # repeated below the final status when recognition completes
        self.status.setText(message)
        if not self.isVisible():
            self.tray.showMessage('LocalVoice', message, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def recording_limit(self):
        if self.recorder:
            self.stop_recording()
        self.show_notice('Maximale Aufnahmedauer von 10 Minuten erreicht · Aufnahme wurde automatisch beendet.')

    def tick(self):
        self.flush_direct()
        # Windows foreground queries are cheap; other platforms query only at start/insertion.
        from .integration import IS_WINDOWS
        if IS_WINDOWS:
            handle = foreground()
            if is_dictation_target(handle):
                self.last_external = handle
        if self.recorder:
            seconds = int(time.monotonic() - self.started)
            self.record.setText(f'■  Stoppen   {seconds // 60:02}:{seconds % 60:02}')

    def copy_text(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.status.setText('Transkript kopiert')

    def paste_later(self):
        text = self.editor.toPlainText()
        if not text:
            return
        self.paste_button.setEnabled(False)
        self.status.setText('Jetzt das Ziel-Textfeld anklicken · Einfügen in 3 Sekunden …')
        def paste():
            if self.quitting:
                return
            try:
                send_text(text, foreground())
                self.status.setText('Text eingefügt')
            except Exception as exc:
                self.show_notice(str(exc))
            finally:
                self.paste_button.setEnabled(True)
        QTimer.singleShot(3000, paste)

    def open_settings(self):
        if self.busy:
            self.status.setText('Einstellungen sind nach der Aufnahme / Transkription verfügbar.')
            return
        self.show_window()
        dialog = SettingsDialog(self.settings, self.root, self)
        accepted = dialog.exec() and dialog.result_settings
        new = dialog.result_settings
        dialog.deleteLater()
        if accepted:
            previous = self.settings
            try:
                self.hotkey.register(new.hotkey)
                if new.autostart != previous.autostart:
                    set_autostart(new.autostart, self.root)
                new.save(self.root)
            except Exception as exc:
                try:
                    self.hotkey.register(previous.hotkey)
                    if new.autostart != previous.autostart:
                        set_autostart(previous.autostart, self.root)
                except Exception:
                    pass
                QMessageBox.warning(self, 'Einstellungen nicht übernommen', str(exc))
                return
            self.settings = new
            if (previous.model, previous.device) != (new.model, new.device):
                self.executor.submit(self.engine.stop)
            self.update_labels()
            self.apply_theme()
            self.status.setText('Einstellungen gespeichert')

    def closeEvent(self, event):
        if self.quitting:
            event.accept()
            return
        if self.settings.close_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            return
        event.ignore()
        self.quit()

    def quit(self):
        if self.quitting:
            return
        modal = QApplication.activeModalWidget()
        if isinstance(modal, SettingsDialog) and modal.downloading:
            modal.cancel.set()
            modal.download_label.setText('Download wird abgebrochen. Danach bitte erneut beenden.')
            return
        if self.busy and QMessageBox.question(self, 'LocalVoice beenden?', 'Aufnahme / Erkennung abbrechen und beenden?') != QMessageBox.StandardButton.Yes:
            return
        self.quitting = True
        self.failed.set()
        self.timer.stop()
        self.hotkey.close()
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self.engine.close()
        restore_clipboard_now()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.tray.hide()
        QApplication.instance().quit()
