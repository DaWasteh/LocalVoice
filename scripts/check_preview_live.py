"""Pace an existing WAV through the real GUI/recorder/Whisper pipeline.
No microphone recording and no text injection. CPU is the default.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
import time
import wave
import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localvoice.audio import Recorder
from localvoice.config import root_dir
import localvoice.ui as ui

parser = argparse.ArgumentParser()
parser.add_argument('--audio', required=True)
parser.add_argument('--model', default='large-v3-turbo')
parser.add_argument('--device', default='cpu')
parser.add_argument('--language', default='de')
args = parser.parse_args()
with wave.open(args.audio) as wav:
    assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
    audio = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').astype(np.float32) / 32768


class FixtureEvents(QObject):
    exhausted = Signal()


app = QApplication([])
app.setStyle('Fusion')
events = FixtureEvents()


class FixtureRecorder(Recorder):
    def start(self):
        self.rate = 16000
        self.thread = threading.Thread(target=self._consume, daemon=True)
        self.thread.start()
        self.producer = threading.Thread(target=self.produce, daemon=True)
        self.producer.start()

    def produce(self):
        begin = time.perf_counter()
        for start in range(0, len(audio), 800):
            if self.stop_event.is_set():
                return
            block = audio[start:start + 800]
            due = begin + (start + len(block)) / self.rate
            self.stop_event.wait(max(0, due - time.perf_counter()))
            if self.stop_event.is_set():
                return
            self.queue.put_nowait(block.copy())
        events.exhausted.emit()


ui.Recorder = FixtureRecorder
window = ui.Window(root_dir())
window.hide()
window.hotkey.close()
window.settings = replace(window.settings, model=args.model, device=args.device, mode='preview',
                          language=args.language, direct=False, chunk_seconds=4)
events.exhausted.connect(window.stop_recording)
report = {'model': args.model, 'device': args.device, 'duration_s': len(audio) / 16000, 'results': [], 'errors': []}
begin = time.perf_counter()
window.events.text.connect(lambda text: report['results'].append({'at_s': round(time.perf_counter() - begin, 3), 'text': text}))
window.events.error.connect(report['errors'].append)


def finish():
    report['finished_s'] = round(time.perf_counter() - begin, 3)
    report['text'] = window.editor.toPlainText()
    report['passed'] = bool(report['text']) and not report['errors']
    window.busy = False
    window.quit()


def timeout():
    report['errors'].append('Timed out after 120 seconds')
    finish()


window.events.done.connect(finish)
QTimer.singleShot(120000, timeout)
QTimer.singleShot(0, window.toggle_recording)
app.exec()
folder = root_dir() / 'reports'
folder.mkdir(exist_ok=True)
(folder / f'preview-live-{args.device.replace(":", "-")}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(0 if report.get('passed') else 1)
