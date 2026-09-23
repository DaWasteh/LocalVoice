from __future__ import annotations
from dataclasses import replace
import threading
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QCheckBox,
    QLineEdit, QLabel, QPushButton, QHBoxLayout, QProgressBar, QDialogButtonBox,
    QMessageBox, QSpinBox, QTabWidget, QWidget)
from .audio import microphones
from .devices import gpu_devices
from .models import MODELS, VAD_FILE, download, model_path
from .integration import parse_hotkey
from .widgets import StableComboBox as QComboBox


class DownloadSignals(QObject):
    progress = Signal(str, int)
    finished = Signal(str)


class SettingsDialog(QDialog):
    def __init__(self, settings, root, parent):
        super().__init__(parent)
        self.setWindowTitle('LocalVoice · Einstellungen')
        self.setMinimumWidth(530)
        self.original, self.root, self.result_settings = settings, root, None
        self.cancel = threading.Event()
        self.downloading = False
        self.signals = DownloadSignals(self)
        self.signals.progress.connect(self.progress_update)
        self.signals.finished.connect(self.download_finished)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        general, audio = QWidget(), QWidget()
        tabs.addTab(general, 'Allgemein')
        tabs.addTab(audio, 'Audio && Modelle')
        form = QFormLayout(general)
        form.setSpacing(16)
        self.theme = QComboBox()
        for title, key in [('System', 'system'), ('Dunkel', 'dark'), ('Hell', 'light')]:
            self.theme.addItem(title, key)
        self.select(self.theme, settings.theme)
        form.addRow('Darstellung', self.theme)
        self.hotkey = QLineEdit(settings.hotkey)
        form.addRow('Globaler Hotkey', self.hotkey)
        self.hotkey_mode = QComboBox()
        self.hotkey_mode.addItem('Einmal drücken: Start / Stopp', 'toggle')
        self.hotkey_mode.addItem('Gedrückt halten: Push-to-talk', 'hold')
        self.select(self.hotkey_mode, settings.hotkey_mode)
        form.addRow('Hotkey-Verhalten', self.hotkey_mode)
        self.autostart = QCheckBox('Mit Windows starten (im Infobereich)')
        self.autostart.setChecked(settings.autostart)
        import sys
        self.autostart.setEnabled(sys.platform == 'win32')
        form.addRow(self.autostart)
        self.tray = QCheckBox('Beim Schließen in den Infobereich minimieren')
        self.tray.setChecked(settings.close_to_tray)
        form.addRow(self.tray)
        privacy = QLabel('Audio und Transkripte bleiben lokal.\nKeine Cloud-Erkennung, kein Konto, keine Telemetrie.\nNur der bewusste Modell-Download benötigt Internet.')
        privacy.setWordWrap(True)
        privacy.setObjectName('muted')
        form.addRow(privacy)
        af = QFormLayout(audio)
        af.setSpacing(14)
        self.mic = QComboBox()
        self.mic.setMinimumContentsLength(20)
        self.mic.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        refresh = QPushButton('↻')
        refresh.setToolTip('Geräteliste neu einlesen (bei neu angeschlossenem Gerät ggf. App neu starten)')
        refresh.clicked.connect(self.refresh_mics)
        row = QHBoxLayout()
        row.addWidget(self.mic, 1)
        row.addWidget(refresh)
        af.addRow('Mikrofon', row)
        self.refresh_mics()
        self.gpu = QComboBox()
        self.gpu.addItem('CPU · ohne GPU', 'cpu')
        for key, name in gpu_devices():
            self.gpu.addItem(name, key)
        if self.gpu.findData(settings.device) < 0:
            self.gpu.addItem(f'{settings.device} · derzeit nicht gefunden', settings.device)
        self.select(self.gpu, settings.device)
        af.addRow('Rechengerät', self.gpu)
        self.model = QComboBox()
        self.refresh_models()
        af.addRow('Whisper-Modell', self.model)
        self.download_button = QPushButton('Ausgewähltes Modell + VAD herunterladen')
        self.download_button.clicked.connect(self.start_download)
        af.addRow(self.download_button)
        self.progress = QProgressBar()
        self.progress.hide()
        af.addRow(self.progress)
        self.download_label = QLabel(f'Modellordner: {root / "models"}')
        self.download_label.setWordWrap(True)
        self.download_label.setObjectName('muted')
        af.addRow(self.download_label)
        self.language = QComboBox()
        for name, code in [('Deutsch', 'de'), ('Automatisch erkennen', 'auto'), ('English', 'en'),
                           ('Français', 'fr'), ('Español', 'es'), ('Italiano', 'it')]:
            self.language.addItem(name, code)
        self.select(self.language, settings.language)
        af.addRow('Sprache', self.language)
        self.chunk = QSpinBox()
        self.chunk.setRange(2, 20)
        self.chunk.setSuffix(' Sekunden')
        self.chunk.setValue(settings.chunk_seconds)
        af.addRow('Vorschau-Ziel (4 s empfohlen)', self.chunk)
        hint = QLabel('Silero-VAD bleibt aktiv. Frühe Ausgabe an Sprechpausen;\nerster Abschnitt spätestens am Ziel, weitere bis zu 2 s später.\nDazu kommt die Rechenzeit. Kurze Abschnitte haben weniger\nSatzkontext; 4–6 s sind ein Kompromiss, 2 s eher experimentell.')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        af.addRow(hint)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Speichern')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @staticmethod
    def select(combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    def refresh_mics(self):
        selected = self.mic.currentData() if self.mic.count() else self.original.microphone
        self.mic.clear()
        self.mic.addItem('Systemstandard', '')
        try:
            for key, name, _ in microphones():
                self.mic.addItem(name, key)
        except Exception as exc:
            self.mic.addItem(f'Gerätefehler: {exc}', '')
        if selected and self.mic.findData(selected) < 0:
            self.mic.addItem(f'{selected} · nicht verfügbar', selected)
        self.select(self.mic, selected)

    def refresh_models(self):
        selected = self.model.currentData() if self.model.count() else self.original.model
        self.model.clear()
        for key, (label, _) in MODELS.items():
            exists = model_path(self.root, key).is_file()
            self.model.addItem(('✓ ' if exists else '↓ ') + label, key)
        self.select(self.model, selected)

    def start_download(self):
        if self.downloading:
            self.cancel.set()
            return
        self.downloading = True
        self.cancel.clear()
        self.model.setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        self.download_button.setText('Download abbrechen')
        self.progress.show()
        filename = MODELS[self.model.currentData()][1]
        def work():
            message = ''
            try:
                for name in (filename, VAD_FILE):
                    download(self.root, name, self.signals.progress.emit, self.cancel)
            except Exception as exc:
                # Some exceptions have no text; an empty message would read as success.
                message = str(exc) or f'Download fehlgeschlagen ({type(exc).__name__})'
            self.signals.finished.emit(message)
        threading.Thread(target=work, daemon=True).start()

    def progress_update(self, text, percent):
        self.download_label.setText(text)
        self.progress.setValue(percent)

    def download_finished(self, error):
        self.downloading = False
        self.model.setEnabled(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)
        self.download_button.setText('Ausgewähltes Modell + VAD herunterladen')
        self.download_label.setText(error or 'Download vollständig und SHA-256 geprüft.')
        self.refresh_models()

    def reject(self):
        if self.downloading:
            self.cancel.set()
            self.download_label.setText('Download wird abgebrochen; bitte kurz warten …')
            return
        super().reject()

    def save(self):
        try:
            parse_hotkey(self.hotkey.text())
        except ValueError as exc:
            QMessageBox.warning(self, 'Hotkey prüfen', str(exc))
            return
        self.result_settings = replace(self.original, theme=self.theme.currentData(), hotkey=self.hotkey.text().lower().strip(),
            hotkey_mode=self.hotkey_mode.currentData(), autostart=self.autostart.isChecked(), close_to_tray=self.tray.isChecked(),
            microphone=self.mic.currentData(), device=self.gpu.currentData(), model=self.model.currentData(),
            language=self.language.currentData(), chunk_seconds=self.chunk.value())
        self.accept()
