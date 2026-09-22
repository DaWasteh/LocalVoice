from __future__ import annotations
import io
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
import wave
import numpy as np
import requests
from .models import model_path, VAD_FILE


NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def wav_bytes(audio):
    out = io.BytesIO()
    pcm = (np.clip(audio, -1, 1) * 32767).astype('<i2')
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm.tobytes())
    return out.getvalue()


def clean_text(text):
    text = re.sub(r'\[_[^]]*\]', '', text)
    text = re.sub(r'\[(?:BLANK_AUDIO|Silence|Music|Applause)\]', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


class Whisper:
    def __init__(self, root: Path):
        self.root, self.proc, self.log, self.key = root, None, None, None
        self.closing = threading.Event()
        self.lifecycle = threading.Lock()
        self.session = requests.Session()
        self.session.trust_env = False

    def start(self, settings):
        key = (settings.model, settings.device)
        if self.closing.is_set():
            raise InterruptedError('LocalVoice wird beendet')
        if self.proc and self.proc.poll() is None and self.key == key:
            return
        self.stop()
        binary = self.root / 'runtime' / ('whisper-server.exe' if os.name == 'nt' else 'whisper-server')
        model, vad = model_path(self.root, settings.model), self.root / 'models' / VAD_FILE
        for path in (binary, model, vad):
            if not path.is_file():
                raise FileNotFoundError(f'Fehlt: {path.name}. Bitte Modell herunterladen bzw. Runtime installieren.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        # Random request namespace limits accidental access by local web pages.
        # This is not authentication against other processes of the same OS user.
        prefix = '/localvoice-' + secrets.token_hex(24)
        self.url = f'http://127.0.0.1:{port}{prefix}'
        state = self.root / 'state'
        state.mkdir(exist_ok=True)
        public = state / 'empty-public'
        public.mkdir(exist_ok=True)
        env = os.environ.copy()
        for name in ('GGML_VK_VISIBLE_DEVICES', 'WHISPER_DEVICE'):
            env.pop(name, None)
        command = [str(binary), '-m', str(model), '--host', '127.0.0.1', '--port', str(port),
                   '--request-path', prefix, '--public', str(public), '-t', '8', '-l', 'de',
                   '--vad', '--vad-model', str(vad), '--vad-min-silence-duration-ms', '500',
                   '--vad-speech-pad-ms', '150', '-sns', '-nf', '-bs', '5']
        if settings.device == 'cpu':
            command.append('-ng')
        elif settings.device.startswith('vulkan:'):
            physical = int(settings.device.split(':')[1])
            env['GGML_VK_VISIBLE_DEVICES'] = str(physical)
            command.extend(['-dev', '0'])
        with self.lifecycle:
            if self.closing.is_set():
                raise InterruptedError('LocalVoice wird beendet')
            self.log = (state / 'backend.log').open('w', encoding='utf-8')
            self.proc = subprocess.Popen(command, cwd=state, env=env, stdout=self.log, stderr=subprocess.STDOUT,
                                         creationflags=NO_WINDOW)
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if self.closing.is_set():
                    raise InterruptedError('Abgebrochen')
                if not self.proc or self.proc.poll() is not None:
                    raise RuntimeError('Whisper konnte nicht starten. Details: state/backend.log')
                try:
                    response = self.session.get(self.url + '/', timeout=1)
                    if response.status_code == 200:
                        self.key = key
                        if settings.device != 'cpu':
                            log = (state / 'backend.log').read_text(encoding='utf-8', errors='replace')
                            if 'using Vulkan' not in log and 'using Metal' not in log and 'using CUDA' not in log:
                                raise RuntimeError('Keine GPU-Bestätigung vom Backend. Bitte CPU wählen oder Treiber prüfen.')
                        return
                except requests.RequestException:
                    pass
                time.sleep(.2)
            raise TimeoutError('Modellstart dauert länger als 180 Sekunden')
        except Exception:
            self.stop()
            raise

    def transcribe(self, audio, settings, prompt=''):
        if len(audio) < 1600 or not np.isfinite(audio).all():
            return ''
        # Reject digital silence before even loading Whisper; Silero then gates real speech.
        if float(np.sqrt(np.mean(audio ** 2))) < .001:
            return ''
        self.start(settings)
        response = self.session.post(self.url + '/inference',
            files={'file': ('dictation.wav', wav_bytes(audio), 'audio/wav')},
            data={'language': settings.language, 'response_format': 'json', 'translate': 'false',
                  'temperature': '0', 'vad': 'true',
                  'prompt': prompt[-400:] if settings.mode == 'preview' else ''}, timeout=(5, 600))
        response.raise_for_status()
        return clean_text(response.json().get('text', ''))

    def stop(self):
        with self.lifecycle:
            if self.proc:
                if self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait(timeout=3)
                self.proc = None
            if self.log:
                self.log.close()
                self.log = None
            self.key = None

    def close(self):
        self.closing.set()
        self.stop()
