from __future__ import annotations
from collections import deque
import queue
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


def microphones():
    hosts = sd.query_hostapis()
    return [(f"{hosts[d['hostapi']]['name']}|{d['name']}",
             f"{d['name']} · {hosts[d['hostapi']]['name']}", i)
            for i, d in enumerate(sd.query_devices()) if d['max_input_channels'] > 0]


def resolve_microphone(key):
    if not key:
        return None
    for device_key, _, index in microphones():
        if device_key == key:
            return index
    raise RuntimeError('Das gewählte Mikrofon ist nicht verfügbar. Bitte in den Einstellungen neu auswählen.')


class Chunker:
    """Non-overlapping chunks; prefer a short pause near the target duration."""
    def __init__(self, seconds=8, rate=SAMPLE_RATE):
        self.rate, self.target = rate, seconds
        self.parts, self.length, self.quiet = [], 0, 0

    def feed(self, data):
        self.parts.append(data)
        self.length += len(data)
        self.quiet = self.quiet + len(data) if np.sqrt(np.mean(data ** 2)) < 0.008 else 0
        if self.length >= self.rate * self.target and (self.quiet >= self.rate * .35 or self.length >= self.rate * (self.target + 3)):
            return self.flush()
        return None

    def flush(self):
        if not self.parts:
            return None
        audio = np.concatenate(self.parts)
        self.parts, self.length, self.quiet = [], 0, 0
        return audio


class Recorder:
    def __init__(self, settings, on_chunk, on_level, on_error):
        self.settings, self.on_chunk, self.on_level, self.on_error = settings, on_chunk, on_level, on_error
        self.queue = queue.Queue(maxsize=600)
        self.stop_event = threading.Event()
        self.stream = None
        self.thread = None
        self.failed = False

    def start(self):
        device = resolve_microphone(self.settings.microphone)
        info = sd.query_devices(device, 'input')
        self.rate = int(info['default_samplerate'])
        self.stream = sd.InputStream(device=device, channels=1, samplerate=self.rate,
                                    blocksize=int(self.rate * .05), dtype='float32', callback=self._callback)
        self.stream.start()
        self.thread = threading.Thread(target=self._consume, daemon=True)
        self.thread.start()

    def _callback(self, data, frames, timing, status):
        if status:
            self.failed = True
        try:
            self.queue.put_nowait(data[:, 0].copy())
        except queue.Full:
            self.failed = True

    def _consume(self):
        chunker = Chunker(self.settings.chunk_seconds, self.rate)
        parts, length = [], 0
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                data = self.queue.get(timeout=.1)
            except queue.Empty:
                continue
            self.on_level(float(np.sqrt(np.mean(data ** 2))))
            length += len(data)
            if self.failed:
                self.on_error('Audio-Aussetzer erkannt. Aufnahme bitte wiederholen.')
                return
            if length > self.rate * 600:
                self.on_error('Maximale Aufnahmedauer von 10 Minuten erreicht. Bitte stoppen.')
                return
            if self.settings.mode == 'preview':
                chunk = chunker.feed(data)
                if chunk is not None:
                    self.on_chunk(self._resample(chunk))
            else:
                parts.append(data)
        tail = chunker.flush() if self.settings.mode == 'preview' else (np.concatenate(parts) if parts else None)
        if tail is not None:
            self.on_chunk(self._resample(tail))

    def _resample(self, data):
        if self.rate == SAMPLE_RATE:
            return data
        # PortAudio captures at the hardware rate; polyphase filtering prevents aliasing.
        from scipy.signal import resample_poly
        from math import gcd
        divisor = gcd(self.rate, SAMPLE_RATE)
        return resample_poly(data, SAMPLE_RATE // divisor, self.rate // divisor).astype(np.float32)

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
