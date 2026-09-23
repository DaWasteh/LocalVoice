"""Explicit, checksum-verified downloads. Inference never accesses the Internet."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import threading
import requests

REPO = 'ggerganov/whisper.cpp'
MODELS = {
    'tiny': ('Tiny · ~75 MB · am schnellsten', 'ggml-tiny.bin'),
    'base': ('Base · ~142 MB', 'ggml-base.bin'),
    'small': ('Small · ~466 MB', 'ggml-small.bin'),
    'medium': ('Medium · ~1,5 GB', 'ggml-medium.bin'),
    'large-v3': ('Large v3 · ~3,1 GB · höchste Qualität', 'ggml-large-v3.bin'),
    'large-v3-turbo': ('Large v3 Turbo · ~1,6 GB · schneller', 'ggml-large-v3-turbo.bin'),
    'large-v3-q5_0': ('Large v3 Q5 · ~1,1 GB · weniger Speicher', 'ggml-large-v3-q5_0.bin'),
    'large-v3-turbo-q5_0': ('Large v3 Turbo Q5 · ~574 MB', 'ggml-large-v3-turbo-q5_0.bin'),
}
VAD_FILE = 'ggml-silero-v6.2.0.bin'


def model_path(root: Path, model: str) -> Path:
    if model not in MODELS:
        raise ValueError('Unbekannte Whisper-Variante')
    return root / 'models' / MODELS[model][1]


def download(root: Path, filename: str, progress, cancel: threading.Event):
    if filename not in [v[1] for v in MODELS.values()] + [VAD_FILE]:
        raise ValueError('Unbekannte Modelldatei')
    folder = root / 'models'
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / filename
    if dest.is_file():
        progress(f'{filename}: bereits vorhanden', 100)
        return
    repo = 'ggml-org/whisper-vad' if filename == VAD_FILE else REPO
    with requests.Session() as session:
        r = session.get(f'https://huggingface.co/api/models/{repo}/revision/main', params={'blobs': 'true'}, timeout=30)
        r.raise_for_status()
        meta = r.json()
        entry = next((x for x in meta.get('siblings', []) if x.get('rfilename') == filename), None)
        if entry is None:
            raise FileNotFoundError(f'{filename} ist im Repository {repo} nicht (mehr) vorhanden')
        expected = entry.get('lfs', {}).get('sha256')
        size = entry.get('size') or entry.get('lfs', {}).get('size')
        if not expected or not size:
            raise ValueError('Keine SHA-256-Metadaten verfügbar; Download abgebrochen')
        revision = meta['sha']
        part = dest.with_suffix('.bin.part')
        try:
            digest, received = hashlib.sha256(), 0
            with session.get(f'https://huggingface.co/{repo}/resolve/{revision}/{filename}', stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                with part.open('wb') as out:
                    for block in response.iter_content(1024 * 1024):
                        if cancel.is_set():
                            raise InterruptedError('Download abgebrochen')
                        out.write(block)
                        digest.update(block)
                        received += len(block)
                        progress(f'{filename}: {received / 1e6:.0f} / {size / 1e6:.0f} MB', int(received * 100 / size))
            if received != size or digest.hexdigest() != expected:
                raise ValueError('Prüfsumme oder Dateigröße stimmt nicht')
            part.replace(dest)
            dest.with_suffix('.bin.integrity.json').write_text(json.dumps({'repo': repo, 'revision': revision,
                'filename': filename, 'sha256': expected, 'bytes': received}, indent=2), encoding='utf-8')
        finally:
            part.unlink(missing_ok=True)
