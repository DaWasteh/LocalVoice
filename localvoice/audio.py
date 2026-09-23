from __future__ import annotations
import queue
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
MAX_SECONDS = 600


def warm_resampler():
    from scipy.signal import resample_poly
    return resample_poly


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
    """Lossless, non-overlapping preview chunks with an early first result.

    Prefer 350 ms pauses after half the target (minimum 1.5 s) for the first
    result, after the full target thereafter. Bound first-chunk buffering to
    the target and later chunks to
    target + 2 s. RMS only proposes boundaries; Silero still gates inference.
    """
    def __init__(self, seconds=4, rate=SAMPLE_RATE):
        self.rate, self.target = rate, seconds
        self.minimum = max(1.5, seconds / 2)
        self.first = True
        self.parts, self.length, self.quiet = [], 0, 0

    def feed(self, data):
        if not len(data):
            return None
        self.parts.append(data)
        self.length += len(data)
        self.quiet = self.quiet + len(data) if np.sqrt(np.mean(data ** 2)) < 0.008 else 0
        minimum = self.minimum if self.first else self.target
        pause = self.length >= self.rate * minimum and self.quiet >= self.rate * .35
        deadline = self.target if self.first else self.target + 2
        if pause or self.length >= self.rate * deadline:
            return self.flush()
        return None

    def flush(self):
        if not self.parts:
            return None
        audio = np.concatenate(self.parts)
        if np.sqrt(np.mean(audio ** 2)) >= .001:
            self.first = False
        self.parts, self.length, self.quiet = [], 0, 0
        return audio


class Recorder:
    """Captures until stopped. Glitches and the duration limit never discard captured audio."""
    def __init__(self, settings, on_chunk, on_level, on_error, on_notice=None, on_limit=None):
        self.settings, self.on_chunk, self.on_level, self.on_error = settings, on_chunk, on_level, on_error
        self.on_notice = on_notice or (lambda _: None)
        self.on_limit = on_limit or (lambda: None)
        self.queue = queue.Queue(maxsize=600)
        self.stop_event = threading.Event()
        self.stream = None
        self.thread = None
        self.glitches = 0
        self.limit_reached = False

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
        # A single overflow must not throw away minutes of dictation: keep going, warn once.
        if status:
            self.glitches += 1
        try:
            self.queue.put_nowait(data[:, 0].copy())
        except queue.Full:
            self.glitches += 1

    def _consume(self):
        try:
            self._consume_blocks()
        except Exception as exc:
            self.on_error(f'Audioverarbeitung fehlgeschlagen: {exc}')

    def _consume_blocks(self):
        chunker = Chunker(self.settings.chunk_seconds, self.rate)
        parts, length, warned = [], 0, False
        limit = self.rate * MAX_SECONDS
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                data = self.queue.get(timeout=.1)
            except queue.Empty:
                continue
            self.on_level(float(np.sqrt(np.mean(data ** 2))))
            if self.glitches and not warned:
                warned = True
                self.on_notice('Kurzer Audio-Aussetzer erkannt · Text an dieser Stelle bitte prüfen.')
            data = data[:limit - length]
            length += len(data)
            if self.settings.mode == 'preview':
                chunk = chunker.feed(data)
                if chunk is not None:
                    self.on_chunk(self._resample(chunk))
            else:
                parts.append(data)
            if length >= limit:
                self.limit_reached = True
                break
        tail = chunker.flush() if self.settings.mode == 'preview' else (np.concatenate(parts) if parts else None)
        if tail is not None:
            self.on_chunk(self._resample(tail))
        if self.limit_reached:
            self.on_limit()

    def _resample(self, data):
        if self.rate == SAMPLE_RATE:
            return data
        # PortAudio captures at the hardware rate; polyphase filtering prevents aliasing.
        from math import gcd
        divisor = gcd(self.rate, SAMPLE_RATE)
        return warm_resampler()(data, SAMPLE_RATE // divisor, self.rate // divisor).astype(np.float32)

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
