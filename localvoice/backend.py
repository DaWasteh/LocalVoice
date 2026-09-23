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


def kill_on_close_job():
    """Windows job whose children die with LocalVoice, even after a crash or Task Manager kill."""
    if os.name != 'nt':
        return None
    import ctypes as c
    from ctypes import wintypes as w
    kernel32 = c.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
    kernel32.CreateJobObjectW.restype = w.HANDLE
    kernel32.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    kernel32.CloseHandle.argtypes = [w.HANDLE]
    class Basic(c.Structure):
        _fields_ = [('user_time', c.c_int64), ('job_time', c.c_int64), ('flags', w.DWORD),
                    ('min_ws', c.c_size_t), ('max_ws', c.c_size_t), ('processes', w.DWORD),
                    ('affinity', c.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class Extended(c.Structure):
        _fields_ = [('basic', Basic), ('io', c.c_uint64 * 6), ('process_memory', c.c_size_t),
                    ('job_memory', c.c_size_t), ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info)):  # extended limits
        kernel32.CloseHandle(job)
        return None
    return job


def assign_to_job(job, proc):
    if job is None:
        return False
    import ctypes as c
    from ctypes import wintypes as w
    kernel32 = c.WinDLL('kernel32', use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    return bool(kernel32.AssignProcessToJobObject(job, int(proc._handle)))


def cpu_threads():
    # Roughly the physical cores, capped: more threads than cores slows whisper.cpp down.
    return str(max(2, min(8, (os.cpu_count() or 4) // 2)))


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
        self.job = kill_on_close_job()

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
                   '--request-path', prefix, '--public', str(public), '-t', cpu_threads(), '-l', 'de',
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
            assign_to_job(self.job, self.proc)
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
